from pyatrea import Atrea
from .const import LOGGER, DOMAIN, CONF_PRESETS, ALL_PRESET_LIST


def isAtreaUnit(host):
    atrea = Atrea(host, "")
    return atrea.isAtreaUnit()


async def update_listener(hass, entry):
    LOGGER.debug("update_listener")
    preset_list = entry.data.get(CONF_PRESETS)
    if preset_list is None:
        preset_list = ALL_PRESET_LIST
    LOGGER.debug("triggering updatePresetList")
    LOGGER.debug(hass.data[DOMAIN][entry.entry_id]["climate"])
    await hass.data[DOMAIN][entry.entry_id]["climate"].updatePresetList(preset_list)
    LOGGER.debug("triggerred updatePresetList")
