"""Comparaison des offres d'énergie en Wallonie via le comparateur officiel de la CWaPE."""
import logging
import urllib.parse
from datetime import datetime
from enum import Enum

import requests

from .const import DOMAIN

_LOGGER = logging.getLogger(DOMAIN)

CWAPE_API_URL = "https://api.compacwape.be"
CWAPE_SITE_URL = "https://www.compacwape.be/"
CWAPE_DUREE_CACHE_SECONDES = 600
CWAPE_TAUX_TVA = 0.06
NB_OFFRES = 10

# Identifiants des types de compteur de la CWaPE (voir https://api.compacwape.be/counter_types)
COMPTEUR_SIMPLE = 1
COMPTEUR_BI_JOUR, COMPTEUR_BI_NUIT = 3, 4
COMPTEUR_SIMPLE_EXCL_JOUR, COMPTEUR_SIMPLE_EXCL_NUIT = 6, 7
COMPTEUR_BI_EXCL_JOUR, COMPTEUR_BI_EXCL_NUIT, COMPTEUR_BI_EXCL_EXCLUSIF = 9, 10, 11
# Segments de puissance de raccordement par défaut (https://api.compacwape.be/connection_power_segments)
SEGMENT_PUISSANCE_ELECTRICITE = 3  # 6,1 à 9,6 kVA
SEGMENT_PUISSANCE_GAZ = 9
FOURNISSEURS_EXCLUS = ("tarif social",)

AUCUN_FOURNISSEUR = "Aucun"
FOURNISSEURS = [
    AUCUN_FOURNISSEUR,
    "Bolt",
    "Cociter",
    "DATS 24",
    "Ecofix Gas & Power",
    "Eneco",
    "EnergyVision",
    "Engie",
    "Luminus",
    "Mega",
    "Octa+",
    "TotalEnergies",
]


class TypeEnergie(Enum):
    """Type d'énergie : (clé CWaPE, identifiant stable des entités, libellé)."""

    ELECTRICITE = ("electricity", "Electricity", "Électricité")
    GAZ = ("gas", "Gas", "Gaz")

    def __init__(self, cle, uid, libelle):
        self.cle = cle
        self.uid = uid
        self.libelle = libelle


class TypeContrat(Enum):
    """Type de contrat : (clé CWaPE billingBase, identifiant stable des entités, libellé)."""

    FIXE = ("fixed", "Fixed", "Fixe")
    VARIABLE = ("variable", "Variable", "Variable")

    def __init__(self, cle, uid, libelle):
        self.cle = cle
        self.uid = uid
        self.libelle = libelle


def _nombre(valeur, defaut=0.0):
    try:
        if valeur is None:
            return defaut
        return float(valeur)
    except (TypeError, ValueError):
        return defaut


def _fournisseur(nom):
    """Nom de fournisseur configuré, None si aucun (accepte les anciennes valeurs anglaises)."""
    if not nom or nom in (AUCUN_FOURNISSEUR, "No provider", "Other", "Social rate"):
        return None
    return nom


def normaliser_config(config):
    """Valeurs de configuration typées, utilisées par le reste de l'intégration."""
    jour = int(config.get("day_electricity_consumption", 0) or 0)
    nuit = int(config.get("night_electricity_consumption", 0) or 0)
    exclusif_nuit = int(config.get("excl_night_electricity_consumption", 0) or 0)
    gaz = int(config.get("gas_consumption", 0) or 0)
    return {
        "code_postal": str(config.get("postalcode", "")).strip(),
        "compteur_intelligent": bool(config.get("electricity_digital_counter", False)),
        "conso_jour": jour,
        "conso_nuit": nuit,
        "conso_exclusif_nuit": exclusif_nuit,
        "conso_electricite": jour + nuit + exclusif_nuit,
        "conso_gaz": gaz,
        "fournisseur_electricite": _fournisseur(config.get("electricity_provider")),
        "fournisseur_gaz": _fournisseur(config.get("gas_provider")),
        "produit_actuel": str(config.get("current_product", "") or "").strip(),
        "prix_jour": _nombre(config.get("own_price_day")),
        "prix_nuit": _nombre(config.get("own_price_night")),
        "prix_exclusif_nuit": _nombre(config.get("own_price_excl_night")),
        "redevance_fixe": _nombre(config.get("own_fixed_fee")),
        "cout_energie_verte": _nombre(config.get("own_green_cost")),
    }


def energies_actives(profil):
    energies = []
    if profil["conso_electricite"] > 0:
        energies.append(TypeEnergie.ELECTRICITE)
    if profil["conso_gaz"] > 0:
        energies.append(TypeEnergie.GAZ)
    return energies


def verifier_config(config):
    profil = normaliser_config(config)
    if not profil["code_postal"]:
        raise ValueError("Code postal manquant")
    if not energies_actives(profil):
        raise ValueError("Aucune consommation d'électricité ou de gaz configurée")


def _consommations_par_compteur(profil):
    jour, nuit, excl = profil["conso_jour"], profil["conso_nuit"], profil["conso_exclusif_nuit"]
    if nuit and excl:
        return [
            {"counterType": COMPTEUR_BI_EXCL_JOUR, "consumption": jour},
            {"counterType": COMPTEUR_BI_EXCL_NUIT, "consumption": nuit},
            {"counterType": COMPTEUR_BI_EXCL_EXCLUSIF, "consumption": excl},
        ]
    if nuit:
        return [
            {"counterType": COMPTEUR_BI_JOUR, "consumption": jour},
            {"counterType": COMPTEUR_BI_NUIT, "consumption": nuit},
        ]
    if excl:
        return [
            {"counterType": COMPTEUR_SIMPLE_EXCL_JOUR, "consumption": jour},
            {"counterType": COMPTEUR_SIMPLE_EXCL_NUIT, "consumption": excl},
        ]
    return [{"counterType": COMPTEUR_SIMPLE, "consumption": jour}]


def _montant_ligne(produit, ligne):
    """Montant d'une ligne de facture, avec les mêmes règles que le site de la CWaPE."""
    poste = ligne.get("invoiceItem") or {}
    if produit.get("isAllInProduct") and poste.get("isExcludedFromAllIn"):
        return 0.0
    if not produit.get("isAllInProduct") and poste.get("isOnlyForAllIn"):
        return 0.0
    prix = ligne.get("price")
    if isinstance(prix, list):
        total = sum(_nombre(p.get("price")) for p in prix)
    else:
        total = _nombre(prix)
    for sous_ligne in ligne.get("prosumerInvoiceItems") or []:
        total += _montant_ligne(produit, sous_ligne)
    return total


def _resume_offre(offre, consommation):
    return {
        "fournisseur": offre["fournisseur"],
        "produit": offre["produit"].get("name", ""),
        "type_contrat": TypeContrat.FIXE.libelle if offre["produit"].get("billingBase") == "fixed" else TypeContrat.VARIABLE.libelle,
        "prix_kwh": round(offre["total"] / consommation, 4) if consommation > 0 else None,
        "prix_an": round(offre["total"], 2),
        "url": offre["produit"].get("sheetPageUrl") or CWAPE_SITE_URL,
    }


def cout_energie_contrat_actuel(profil):
    """Partie énergie annuelle (TVA comprise) du contrat actuel, None si les prix ne sont pas configurés."""
    if not (profil["prix_jour"] or profil["prix_nuit"] or profil["prix_exclusif_nuit"]):
        return None
    hors_tva = (
        profil["redevance_fixe"]
        + profil["conso_jour"] * profil["prix_jour"]
        + profil["conso_nuit"] * profil["prix_nuit"]
        + profil["conso_exclusif_nuit"] * profil["prix_exclusif_nuit"]
        + profil["conso_electricite"] * profil["cout_energie_verte"]
    )
    return hors_tva * (1 + CWAPE_TAUX_TVA)


def analyser_offres(donnees, type_contrat, fournisseur_actuel=None, produit_actuel=None, cout_energie_actuel=None):
    """Classe les offres d'une énergie pour un type de contrat et compare avec le contrat actuel."""
    if not donnees:
        return None

    offres_par_produit = {}
    for ligne in donnees.get("providerProduct") or []:
        produit = ligne.get("providerProduct") or {}
        if produit.get("id") is None:
            continue
        offre = offres_par_produit.setdefault(
            produit["id"],
            {"produit": produit, "fournisseur": (ligne.get("provider") or {}).get("name", ""), "energie": 0.0},
        )
        offre["energie"] += _montant_ligne(produit, ligne)

    lignes_reseau = (donnees.get("common") or []) + (donnees.get("dnm") or [])
    offres = []
    for offre in offres_par_produit.values():
        if offre["fournisseur"].strip().lower() in FOURNISSEURS_EXCLUS:
            continue
        offre["reseau"] = sum(_montant_ligne(offre["produit"], ligne) for ligne in lignes_reseau)
        offre["total"] = offre["energie"] + offre["reseau"]
        if offre["total"] > 0:
            offres.append(offre)

    offres_du_type = sorted(
        (o for o in offres if o["produit"].get("billingBase") == type_contrat.cle), key=lambda o: o["total"]
    )
    if not offres_du_type:
        return None

    consommation = int(_nombre(donnees.get("totalConsumption")))
    meilleure = offres_du_type[0]
    resultat = {
        "meilleure_offre": _resume_offre(meilleure, consommation),
        "cout_energie": round(meilleure["energie"], 2),
        "cout_reseau": round(meilleure["reseau"], 2),
        "consommation": consommation,
        "offres": [_resume_offre(o, consommation) for o in offres_du_type[:NB_OFFRES]],
        "votre_contrat": None,
        "economie_par_an": None,
    }

    if cout_energie_actuel is not None:
        # Prix du contrat actuel configurés : mêmes coûts de réseau et taxes que les offres.
        total = cout_energie_actuel + meilleure["reseau"]
        resultat["votre_contrat"] = {
            "fournisseur": fournisseur_actuel or "",
            "produit": f"{produit_actuel or 'Contrat actuel'} (vos prix)",
            "type_contrat": "Votre contrat",
            "prix_kwh": round(total / consommation, 4) if consommation > 0 else None,
            "prix_an": round(total, 2),
            "url": "",
        }
        resultat["economie_par_an"] = round(total - meilleure["total"], 2)
    elif fournisseur_actuel:
        du_fournisseur = sorted(
            (o for o in offres if o["fournisseur"].strip().lower() == fournisseur_actuel.strip().lower()),
            key=lambda o: o["total"],
        )
        actuelle = None
        if produit_actuel:
            # Le produit configuré peut être fixe ou variable : les deux capteurs se comparent à lui.
            recherche = produit_actuel.lower()
            actuelle = next((o for o in du_fournisseur if recherche in (o["produit"].get("name") or "").lower()), None)
        if actuelle is None:
            actuelle = next((o for o in du_fournisseur if o["produit"].get("billingBase") == type_contrat.cle), None)
        if actuelle is not None:
            resultat["votre_contrat"] = _resume_offre(actuelle, consommation)
            resultat["economie_par_an"] = round(actuelle["total"] - meilleure["total"], 2)

    return resultat


class SessionCwape:
    """Appels à l'API publique du comparateur de la CWaPE (sans compte)."""

    def __init__(self):
        self.s = requests.Session()
        self.s.headers["User-Agent"] = "HomeAssistant-MyEnergy"
        self.s.headers["Accept"] = "application/json"
        self._cache = None
        self._fournisseurs = None

    def _get(self, chemin):
        reponse = self.s.get(f"{CWAPE_API_URL}{chemin}", timeout=30)
        reponse.raise_for_status()
        return reponse.json() or []

    def _id_fournisseur(self, nom):
        if not nom:
            return None
        if self._fournisseurs is None:
            self._fournisseurs = {(f.get("name") or "").strip().lower(): f.get("id") for f in self._get("/providers")}
        return self._fournisseurs.get(nom.strip().lower())

    def _simulation(self, profil):
        cle_cache = tuple(sorted((k, v) for k, v in profil.items() if not k.startswith(("prix_", "redevance", "cout_", "produit"))))
        if self._cache and self._cache[0] == cle_cache and (datetime.now() - self._cache[1]).total_seconds() < CWAPE_DUREE_CACHE_SECONDES:
            return self._cache[2]

        code_postal = profil["code_postal"]
        localites = self._get(f"/postal_codes?code={urllib.parse.quote(code_postal)}")
        localite = next((l for l in localites if str(l.get("code")) == code_postal), None)
        if localite is None:
            raise ValueError(f"Code postal {code_postal} inconnu de la CWaPE (seule la Wallonie est couverte)")

        electricite = profil["conso_electricite"] > 0
        gaz = profil["conso_gaz"] > 0
        requete = {
            "gasProvider": self._id_fournisseur(profil["fournisseur_gaz"]),
            "electricityProvider": self._id_fournisseur(profil["fournisseur_electricite"]),
            "isElectricitySimulation": electricite,
            "isGasSimulation": gaz,
            "consumerType": "resident",
            "isProsumer": False,
            "postalCode": localite.get("id"),
            "isGasConsumptionUnknown": False,
            "gasConsumption": profil["conso_gaz"] if gaz else None,
            "gasTypicalProfile": None,
            "isElectricityConsumptionUnknown": False,
            "electricityTypicalProfile": None,
            "electricityConsumptionsPerCounterType": _consommations_par_compteur(profil) if electricite else [],
            "prosumerConsumptionsPerCounterType": [],
            "electricityConnectionPowerSegment": SEGMENT_PUISSANCE_ELECTRICITE,
            "gasConnectionPowerSegment": SEGMENT_PUISSANCE_GAZ if gaz else None,
            "prosumerNetPower": None,
            "computeNetForProsumer": True,
            "hasElectricitySmartCounter": profil["compteur_intelligent"],
            "isInjectionSeparated": False,
            "hasCompensation": False,
            "prosumerUnknownConsumptionNetPower": 3,
            "prosumerUnknownConsumptionProductivity": 800,
            "prosumerUnknownConsumptionAutoConsumption": 50,
            "installationCertification": "before2024",
            "clientFile": None,
            "clientHeaderFile": None,
            "nightOnly": False,
            "isTariffImpact": False,
        }
        reponse = self.s.post(
            f"{CWAPE_API_URL}/offer_simulations",
            json=requete,
            headers={"Origin": "https://app.compacwape.be"},
            timeout=60,
        )
        reponse.raise_for_status()
        simulation = reponse.json() or {}
        self._cache = (cle_cache, datetime.now(), simulation)
        return simulation

    def comparer(self, config):
        """Résultats par (TypeEnergie, TypeContrat) pour la configuration donnée."""
        profil = normaliser_config(config)
        simulation = self._simulation(profil)
        resultats = {}
        for energie in energies_actives(profil):
            electricite = energie == TypeEnergie.ELECTRICITE
            for type_contrat in TypeContrat:
                resultats[(energie, type_contrat)] = analyser_offres(
                    simulation.get(energie.cle),
                    type_contrat,
                    profil["fournisseur_electricite"] if electricite else profil["fournisseur_gaz"],
                    profil["produit_actuel"] if electricite else None,
                    cout_energie_contrat_actuel(profil) if electricite else None,
                )
        return resultats
