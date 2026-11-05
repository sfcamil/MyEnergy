"""MyEnergy : comparaison des offres d'énergie en Wallonie (comparateur CWaPE)."""
import json
import logging
from pathlib import Path

import homeassistant.helpers.config_validation as cv
from homeassistant.components.frontend import add_extra_js_url
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

manifestfile = Path(__file__).parent / "manifest.json"
with open(manifestfile, "r", encoding="utf-8") as json_file:
    manifest_data = json.load(json_file)

DOMAIN = manifest_data.get("domain")
NAME = manifest_data.get("name")
VERSION = manifest_data.get("version")
PLATFORMS = [Platform.SENSOR]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
CARTE_FICHIER = "myenergy-offers-card.js"
CARTE_URL = f"/{DOMAIN}_static/{CARTE_FICHIER}"

_LOGGER = logging.getLogger(DOMAIN)


async def _async_enregistrer_carte(hass: HomeAssistant):
    """Sert la carte des offres et la charge dans l'interface (aucune ressource à ajouter à la main)."""
    await hass.http.async_register_static_paths(
        [StaticPathConfig(CARTE_URL, str(Path(__file__).parent / "frontend" / CARTE_FICHIER), True)]
    )
    add_extra_js_url(hass, f"{CARTE_URL}?v={VERSION}")


async def async_setup(hass: HomeAssistant, config: ConfigType):
    _LOGGER.info("%s %s", NAME, VERSION)
    await _async_enregistrer_carte(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    config_entry.async_on_unload(config_entry.add_update_listener(_async_recharger))
    return True


async def _async_recharger(hass: HomeAssistant, config_entry: ConfigEntry):
    """Recharge l'intégration quand la configuration change."""
    await hass.config_entries.async_reload(config_entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry):
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
