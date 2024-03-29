from pyatrea import Atrea
from .const import (
    LOGGER,
    DOMAIN,
    CONF_PRESETS,
    ALL_PRESET_LIST,
    CONF_FAN_MODES,
    DEFAULT_FAN_MODE_LIST,
)
from homeassistant.const import CONF_NAME


def isAtreaUnit(host, port):
    atrea = Atrea(host, port)
    return atrea.isAtreaUnit()


def processFanModes(fan_modes):
    fanModesArr = fan_modes.split(",")
    numericArr = []
    convertedFanMode = []
    for fan_mode in fanModesArr:
        fan_mode = fan_mode.strip().rstrip("%")
        if not fan_mode.isnumeric() or int(fan_mode) < 12 or int(fan_mode) > 100:
            return False
        numericArr.append(int(fan_mode.strip().rstrip("%")))

    numericArr.sort()
    for fan_mode in numericArr:
        fan_mode = str(fan_mode) + "%"
        convertedFanMode.append(fan_mode)
    return convertedFanMode


async def update_listener(hass, entry):
    preset_list = entry.data.get(CONF_PRESETS)
    if preset_list is None:
        preset_list = ALL_PRESET_LIST
    fan_list = entry.data.get(CONF_FAN_MODES)
    if fan_list is None:
        fan_list = DEFAULT_FAN_MODE_LIST
    sensor_name = entry.data.get(CONF_NAME)
    if sensor_name is None:
        sensor_name = "atrea"
    hass.data[DOMAIN][entry.entry_id]["climate"].updatePresetList(preset_list)
    hass.data[DOMAIN][entry.entry_id]["climate"].updateFanList(fan_list)
    hass.data[DOMAIN][entry.entry_id]["climate"].updateName(sensor_name)
    hass.data[DOMAIN][entry.entry_id]["update"].updateName(sensor_name)

