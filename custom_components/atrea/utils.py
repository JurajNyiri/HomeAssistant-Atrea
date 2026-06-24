from pyatrea import Atrea
from .const import (
    LOGGER,
    DOMAIN,
    CONF_PRESETS,
    ALL_PRESET_LIST,
    CONF_FAN_MODES,
    DEFAULT_FAN_MODE_LIST,
    POWER_2Z_OPTIONS,
)
from homeassistant.const import CONF_NAME


def as_signed_int(value):
    """Return Atrea 16-bit register values as signed integers."""
    value = int(value)
    if value > 32767:
        value -= 65536
    return value


def raw_status_int(status, key, default=None):
    if not isinstance(status, dict):
        return default
    if key not in status:
        return default
    try:
        return as_signed_int(status[key])
    except (TypeError, ValueError):
        return default


def raw_status_temperature(status, key, default=None):
    value = raw_status_int(status, key)
    if value is None:
        return default
    return round(value / 10, 1)


def is_two_zone_power(status):
    return (
        isinstance(status, dict)
        and raw_status_int(status, "C10509", 0) == 1
        and "H10714" in status
    )


def power_2z_group(status):
    mode = raw_status_int(status, "H10715")
    if mode is None:
        mode = raw_status_int(status, "H10705", 0)
    if mode == 4:
        return 2
    if mode in (1, 3):
        return 3
    if mode == 0:
        return 0
    return 1


def power_2z_options(status):
    return POWER_2Z_OPTIONS[power_2z_group(status)]


def power_2z_label(status, key="H10714"):
    power = raw_status_int(status, key)
    for label, value in power_2z_options(status).items():
        if value == power:
            return label
    if power is not None:
        return f"Code {power}"
    return None


def official_outside_temperature_available(status):
    """Mirror the RD5 UI availability rule for T-ODA."""
    if not isinstance(status, dict):
        return False
    if "I10211" not in status:
        return False

    h10508 = raw_status_int(status, "H10508")
    h10501 = raw_status_int(status, "H10501")
    h10200 = raw_status_int(status, "H10200", 0)
    h10201 = raw_status_int(status, "H10201", 0)

    if h10508 == 1:
        return True
    if h10508 == 0:
        return (h10501 == 1 and h10201 > 0) or (h10501 == 2 and h10200 > 0)
    return False


def official_inside_temperature_available(status):
    """Mirror the RD5 UI availability rule for T-IDA."""
    if not isinstance(status, dict):
        return False
    if "I10215" not in status:
        return False

    h10514 = raw_status_int(status, "H10514")
    h10532 = raw_status_int(status, "H10532")
    h10501 = raw_status_int(status, "H10501")
    h10200 = raw_status_int(status, "H10200", 0)
    h10201 = raw_status_int(status, "H10201", 0)

    if h10514 in (0, 2, 3) or h10532 == 1:
        return True
    if h10514 == 1:
        return (h10501 == 1 and h10200 > 0) or (h10501 == 2 and h10201 > 0)
    return False


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
    hass.data[DOMAIN][entry.entry_id]["name"] = sensor_name
    hass.data[DOMAIN][entry.entry_id]["climate"].updatePresetList(preset_list)
    hass.data[DOMAIN][entry.entry_id]["climate"].updateFanList(fan_list)
    hass.data[DOMAIN][entry.entry_id]["climate"].updateName(sensor_name)
    hass.data[DOMAIN][entry.entry_id]["update"].updateName(sensor_name)
