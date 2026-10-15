from pyatrea import Atrea, AtreaMode
from .const import (
    LOGGER,
    DOMAIN,
    CONF_PRESETS,
    ALL_PRESET_LIST,
    CONF_FAN_MODES,
    DEFAULT_FAN_MODE_LIST,
)
from homeassistant.const import CONF_NAME
from homeassistant.helpers import entity_registry as er


# Existing entity identities, independent of user-renamed entity IDs.
INPUT_MODE_ENTITIES = {
    AtreaMode.IN1: ("sensor", "in1_voltage"),
    AtreaMode.IN2: ("sensor", "in2_voltage"),
    AtreaMode.D1: ("binary_sensor", "d10200"),
    AtreaMode.D2: ("binary_sensor", "d10201"),
    AtreaMode.D3: ("binary_sensor", "d10202"),
    AtreaMode.D4: ("binary_sensor", "d10203"),
}


def forced_mode_label(hass, device_unique_id, mode, user_labels):
    """Use the input's HA override, then its device label, then the mode name."""
    if mode not in INPUT_MODE_ENTITIES:
        return ALL_PRESET_LIST[int(mode)]
    label = user_labels.get(mode.name)
    if hass is not None:
        registry = er.async_get(hass)
        domain, suffix = INPUT_MODE_ENTITIES[mode]
        entity_id = registry.async_get_entity_id(domain, DOMAIN, f"{device_unique_id}_{suffix}")
        entry = registry.async_get(entity_id) if entity_id else None
        if entry and entry.name:
            label = entry.name
    if not label or not label.strip() or label.strip() == mode.name:
        return ALL_PRESET_LIST[int(mode)]
    label = label.strip()
    suffix = f"({mode.name})"
    return label if label.endswith(suffix) else f"{label} {suffix}"


def convert_temperature(value):
    """Convert a signed 16-bit ATREA temperature register to Celsius."""
    value = int(value)
    if value > 32767:
        value -= 65536
    return value / 10


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
