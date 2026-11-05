import logging
from datetime import datetime, timedelta

import requests
from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.util import Throttle

from . import DOMAIN, NAME
from .utils import (
    CWAPE_SITE_URL,
    SessionCwape,
    TypeContrat,
    energies_actives,
    normaliser_config,
    verifier_config,
)

_LOGGER = logging.getLogger(DOMAIN)

MIN_TIME_BETWEEN_UPDATES = timedelta(hours=1)
NB_ESSAIS_MAX = 5


async def async_setup_entry(hass, config_entry, async_add_devices):
    """Création des capteurs à partir de l'intégration configurée dans l'interface."""
    config = config_entry.data
    verifier_config(config)
    profil = normaliser_config(config)

    donnees = DonneesComparaison(config, hass)
    await donnees.mise_a_jour_forcee()

    capteurs = [
        CapteurOffre(donnees, energie, type_contrat)
        for energie in energies_actives(profil)
        for type_contrat in TypeContrat
    ]
    async_add_devices(capteurs)
    return True


class DonneesComparaison:
    """Récupère et garde en mémoire la comparaison de la CWaPE pour tous les capteurs."""

    def __init__(self, config, hass):
        self._config = config
        self._hass = hass
        self._session = SessionCwape()
        self.profil = normaliser_config(config)
        self.code_postal = self.profil["code_postal"]
        self.resultats = {}
        self.derniere_mise_a_jour = None
        self._essais = 0

    @property
    def unique_id(self):
        return f"{NAME} {self.code_postal}"

    @property
    def name(self) -> str:
        return self.unique_id

    async def mise_a_jour_forcee(self):
        self._essais += 1
        try:
            self.resultats = await self._hass.async_add_executor_job(self._session.comparer, self._config)
            self.derniere_mise_a_jour = datetime.now()
            self._essais = 0
        except (requests.RequestException, ValueError) as erreur:
            _LOGGER.warning("%s : comparaison CWaPE impossible (essai %s) : %s", NAME, self._essais, erreur)

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def _mise_a_jour(self):
        await self.mise_a_jour_forcee()

    async def update(self):
        if not self.resultats and self._essais < NB_ESSAIS_MAX:
            await self.mise_a_jour_forcee()
        else:
            await self._mise_a_jour()


class CapteurOffre(SensorEntity):
    """Prix de la meilleure offre (€/kWh, TVA et frais de réseau compris) pour une énergie et un type de contrat."""

    _attr_native_unit_of_measurement = "€/kWh"
    # Statistiques long terme : l'historique des prix est conservé au-delà de la purge du recorder.
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 4

    def __init__(self, donnees: DonneesComparaison, energie, type_contrat):
        self._donnees = donnees
        self._energie = energie
        self._type_contrat = type_contrat
        self._resultat = None

    @property
    def unique_id(self) -> str:
        # Format inchangé depuis la version d'origine pour conserver les entités existantes.
        return f"{self._donnees.unique_id} {self._energie.uid} {self._type_contrat.uid}"

    @property
    def name(self) -> str:
        return f"{NAME} {self._donnees.code_postal} {self._energie.libelle} {self._type_contrat.libelle}"

    @property
    def icon(self) -> str:
        return "mdi:transmission-tower" if self._energie.uid == "Electricity" else "mdi:meter-gas"

    @property
    def native_value(self):
        if not self._resultat:
            return None
        return self._resultat["meilleure_offre"]["prix_kwh"]

    async def async_update(self):
        await self._donnees.update()
        self._resultat = self._donnees.resultats.get((self._energie, self._type_contrat))

    @property
    def extra_state_attributes(self) -> dict:
        r = self._resultat or {}
        meilleure = r.get("meilleure_offre") or {}
        return {
            ATTR_ATTRIBUTION: "Comparateur CWaPE (compacwape.be)",
            "mise à jour": self._donnees.derniere_mise_a_jour,
            "code postal": self._donnees.code_postal,
            "énergie": self._energie.libelle,
            "type de contrat": self._type_contrat.libelle,
            "fournisseur": meilleure.get("fournisseur"),
            "produit": meilleure.get("produit"),
            "url": meilleure.get("url"),
            "coût énergie (€/an)": r.get("cout_energie"),
            "coût réseau et taxes (€/an)": r.get("cout_reseau"),
            "prix total (€/an)": meilleure.get("prix_an"),
            "consommation (kWh/an)": r.get("consommation"),
            "offres": r.get("offres"),
            "votre contrat": r.get("votre_contrat"),
            "économie par an": r.get("economie_par_an"),
        }

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(NAME, self._donnees.unique_id)},
            name=self._donnees.name,
            manufacturer=NAME,
            configuration_url=CWAPE_SITE_URL,
        )
