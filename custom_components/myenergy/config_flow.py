"""Formulaires de configuration de l'intégration."""
import logging
from collections import OrderedDict

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.selector import selector

from . import DOMAIN, NAME
from .utils import AUCUN_FOURNISSEUR, FOURNISSEURS

_LOGGER = logging.getLogger(DOMAIN)

# (clé, valeur par défaut, type)
CHAMPS = [
    ("postalcode", "", str),
    ("electricity_provider", AUCUN_FOURNISSEUR, "fournisseur"),
    ("current_product", "", str),
    ("electricity_digital_counter", False, bool),
    ("day_electricity_consumption", 0, int),
    ("night_electricity_consumption", 0, int),
    ("excl_night_electricity_consumption", 0, int),
    ("own_price_day", 0.0, float),
    ("own_price_night", 0.0, float),
    ("own_price_excl_night", 0.0, float),
    ("own_fixed_fee", 0.0, float),
    ("own_green_cost", 0.0, float),
    ("gas_provider", AUCUN_FOURNISSEUR, "fournisseur"),
    ("gas_consumption", 0, int),
]
OBLIGATOIRES = ("postalcode", "electricity_provider", "electricity_digital_counter", "gas_provider")


def _ancienne_valeur_fournisseur(valeur):
    return AUCUN_FOURNISSEUR if valeur in (None, "", "No provider") else valeur


def creer_schema(valeurs=None):
    """Schéma du formulaire, prérempli avec les valeurs existantes en modification."""
    valeurs = valeurs or {}
    schema = OrderedDict()
    for cle, defaut, type_champ in CHAMPS:
        valeur = valeurs.get(cle, defaut)
        cle_schema = vol.Required if cle in OBLIGATOIRES else vol.Optional
        if type_champ == "fournisseur":
            schema[cle_schema(cle, default=_ancienne_valeur_fournisseur(valeur))] = selector(
                {"select": {"options": FOURNISSEURS, "mode": "dropdown", "custom_value": True}}
            )
        elif type_champ is float:
            schema[cle_schema(cle, default=valeur)] = vol.Coerce(float)
        else:
            schema[cle_schema(cle, default=valeur)] = type_champ
    return vol.Schema(schema)


class ComponentFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Ajout de l'intégration."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title=NAME, data=user_input)
        return self.async_show_form(step_id="user", data_schema=creer_schema())

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return ComponentOptionsHandler()


class ComponentOptionsHandler(config_entries.OptionsFlow):
    """Modification de la configuration : tous les champs sont modifiables."""

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            _LOGGER.debug("%s nouvelle configuration : %s", NAME, user_input)
            # Les anciens champs (sites MijnEnergie / VTest) ne sont pas conservés.
            self.hass.config_entries.async_update_entry(self.config_entry, data=user_input)
            return self.async_create_entry(title=NAME, data={})
        return self.async_show_form(step_id="init", data_schema=creer_schema(self.config_entry.data))
