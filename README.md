# MyEnergy – comparateur d'énergie pour la Wallonie (Home Assistant)

Intégration Home Assistant qui compare les offres d'électricité (et de gaz) en **Wallonie** à partir du comparateur officiel du régulateur wallon, la **CWaPE** ([compacwape.be](https://www.compacwape.be/)), et les met en regard de votre propre contrat.

> **Origine du projet** – Cette intégration est un clone mis à jour de [MyEnergy](https://github.com/myTselection/MyEnergy), créée par **myTselection** (licence MIT). Le dépôt d'origine n'existe plus et les sites qu'il utilisait (MijnEnergie.be, comparateur.be) ne fournissent plus de résultats. Ce clone, maintenu par **sfcamil**, remplace ces sources par l'API publique de la CWaPE. Merci à myTselection pour le travail d'origine.

Ce projet n'est affilié ni à la CWaPE, ni à aucun fournisseur d'énergie.

## Ce que fait l'intégration

- Envoie votre profil de consommation au comparateur de la CWaPE (sans compte, environ une fois par heure).
- Calcule pour chaque offre le **coût annuel tout compris** : énergie, frais de réseau, taxes et TVA, avec les mêmes règles que le site de la CWaPE.
- Crée un capteur par énergie et par type de contrat, par exemple :
  - `sensor.myenergy_6220_electricity_fixed` – meilleure offre à **prix fixe** ;
  - `sensor.myenergy_6220_electricity_variable` – meilleure offre à **prix variable**.
- Compare avec **votre contrat** : soit le produit de votre fournisseur aux prix du jour, soit, plus précis, avec **vos propres prix** recopiés depuis votre décompte annuel.
- Fournit une **carte de tableau de bord** prête à l'emploi.

Les contrats dynamiques et le tarif social ne sont pas pris en compte. Les panneaux solaires (injection) ne sont pas encore gérés.

## Installation

1. Dans **Marketplace** (anciennement HACS) : menu ⋮ → **Dépôts personnalisés** → ajouter `https://github.com/sfcamil/MyEnergy`, type **Integration**.
2. Installer **MyEnergy**, puis **redémarrer Home Assistant** (redémarrage complet).
3. **Paramètres → Appareils et services → Ajouter une intégration → MyEnergy**.

## Configuration

Toutes les valeurs se trouvent sur votre **décompte annuel** (facture de régularisation). Elles restent modifiables ensuite via **Configurer**.

| Champ | Description |
|---|---|
| Code postal | Code postal en Wallonie (ex. `6220`). |
| Fournisseur d'électricité actuel | Votre fournisseur (ex. `Engie`). |
| Nom de votre produit actuel | Facultatif, ex. `EASY`. Sert à vous comparer au même produit aux prix du jour. |
| Compteur intelligent | Cocher si vous avez un compteur numérique. |
| Consommation jour / heures pleines | En kWh par an. Compteur simple : toute votre consommation ici. |
| Consommation nuit / heures creuses | En kWh par an, pour un compteur bi-horaire. Sinon 0. |
| Consommation exclusif nuit | En kWh par an, pour un compteur exclusif nuit. Sinon 0. |
| Vos prix (jour, nuit, exclusif nuit) | Facultatif. Prix de l'énergie de **votre** contrat en €/kWh **hors TVA**, tels qu'imprimés sur le décompte. |
| Votre redevance fixe | Facultatif. En €/an hors TVA (ex. 11,41 € pour 64 jours → 11,41 × 365 / 64 = 65,07). |
| Votre coût énergie verte | Facultatif. En €/kWh hors TVA (montant « coûts énergie verte » ÷ kWh consommés). |
| Fournisseur et consommation de gaz | Facultatif. Laisser 0 si vous n'avez pas le gaz. |

**Pourquoi entrer vos propres prix ?** Un contrat à prix fixe garde le prix du moment où il a été conclu. Le même produit aux prix d'aujourd'hui peut être beaucoup plus cher (ou moins cher) : sans vos prix, l'économie affichée peut être trompeuse. Avec vos prix, votre coût annuel est calculé avec vos tarifs plus les mêmes frais de réseau et taxes que les offres.

## Capteurs

État : prix de la meilleure offre en **€/kWh**, TVA et frais de réseau compris.

| Attribut | Contenu |
|---|---|
| `fournisseur`, `produit`, `url` | Meilleure offre et lien vers sa fiche tarifaire |
| `coût énergie (€/an)` | Partie fournisseur de la meilleure offre |
| `coût réseau et taxes (€/an)` | Frais de réseau, taxes et redevances (identiques pour tous les fournisseurs) |
| `prix total (€/an)` | Coût annuel total de la meilleure offre |
| `consommation (kWh/an)` | Consommation utilisée pour le calcul |
| `offres` | Les 10 meilleures offres : `fournisseur`, `produit`, `type_contrat`, `prix_kwh`, `prix_an`, `url` |
| `votre contrat` | Votre contrat, au même format |
| `économie par an` | Différence avec la meilleure offre (négatif : votre contrat est moins cher) |
| `mise à jour` | Date de la dernière comparaison |

Exemple de modèle : `{{ state_attr('sensor.myenergy_6220_electricity_fixed', 'économie par an') }}`

## Carte « Offres MyEnergy »

La carte est livrée avec l'intégration et chargée automatiquement : aucune ressource à ajouter. Dans un tableau de bord : **Ajouter une carte** → chercher **« Offres MyEnergy »**.

Elle affiche les meilleures offres fixes et variables, met en évidence la meilleure offre et votre contrat, et indique l'économie possible.

```yaml
type: custom:myenergy-offers-card
# Facultatif :
# title: Comparateur d'énergie
# max_offers: 5
# entities:
#   - sensor.myenergy_6220_electricity_fixed
#   - sensor.myenergy_6220_electricity_variable
```

## Alertes (blueprints)

Deux modèles d'automatisation sont fournis, à importer dans Home Assistant puis à configurer par formulaire :

| Blueprint | Rôle | Importer |
|---|---|---|
| Alerte offre intéressante | Prévient quand la meilleure offre fixe ou variable fait économiser au moins le seuil choisi (une seule fois au franchissement du seuil). | [![Importer](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fsfcamil%2FMyEnergy%2Fblob%2Fmaster%2Fblueprints%2Fautomation%2Fmyenergy%2Falerte_offre_interessante.yaml) |
| Rappel fin de contrat | Quelques semaines avant la fin du contrat, envoie votre coût et les meilleures offres du moment. | [![Importer](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2Fsfcamil%2FMyEnergy%2Fblob%2Fmaster%2Fblueprints%2Fautomation%2Fmyenergy%2Frappel_fin_contrat.yaml) |

Réglages dans le formulaire : capteurs MyEnergy, seuil d'économie (€/an), date de fin de contrat, nombre de jours avant, heure d'envoi, **téléphones** (application Home Assistant, plusieurs possibles) et **chats Telegram** (bot et destinataire, plusieurs possibles). Laisser une liste vide désactive ce canal.

## Limites

- Seule la **Wallonie** est couverte (comparateur de la CWaPE).
- Profil résidentiel, puissance de raccordement par défaut (6,1 à 9,6 kVA).
- Pas d'injection photovoltaïque, pas de contrats dynamiques.
- Les prix sont ceux publiés par les fournisseurs auprès de la CWaPE ; en cas de doute, la fiche tarifaire du fournisseur fait foi.

## Licence

MIT – voir [LICENSE](LICENSE). Code d'origine © myTselection, modifications © sfcamil.
