import logging
from datetime import timedelta

from homeassistant.components.climate.const import ClimateEntityFeature, HVACMode
from pyatrea import AtreaMode

DOMAIN = "atrea"
LOGGER = logging.getLogger(__name__)
UPDATE_DELAY = 1  # update delay disabled
MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)
SUPPORT_FLAGS = (
    ClimateEntityFeature.TARGET_TEMPERATURE
    | ClimateEntityFeature.FAN_MODE
    | ClimateEntityFeature.PRESET_MODE
    | ClimateEntityFeature.TURN_OFF
    | ClimateEntityFeature.TURN_ON
)
DEFAULT_NAME = "Atrea"
STATE_MANUAL = "manual"
STATE_UNKNOWN = "unknown"
CONF_FAN_MODES = "fan_modes"
CONF_PRESETS = "presets"
DEFAULT_FAN_MODE_LIST = "12,20,30,40,50,60,70,80,90,100"
ALL_PRESET_LIST = [
    "Off",
    "Automatic",
    "Ventilation",
    "Circulation and Ventilation",
    "Circulation",
    "Night precooling",
    "Disbalance",
    "Overpressure",
    "Periodic ventilation",
    "Startup",
    "Rundown",
    "Defrosting",
    "External",
    "HP defrosting",
    "IN1",
    "IN2",
    "D1",
    "D2",
    "D3",
    "D4",
]

ICONS = {
    AtreaMode.OFF: "mdi:fan-off",
    AtreaMode.AUTOMATIC: "mdi:fan",
    AtreaMode.VENTILATION: "mdi:fan-chevron-up",
    AtreaMode.CIRCULATION_AND_VENTILATION: "mdi:fan",
    AtreaMode.CIRCULATION: "mdi:fan-chevron-down",
    AtreaMode.NIGHT_PRECOOLING: "mdi:fan-speed-1",
    AtreaMode.DISBALANCE: "mdi:fan-speed-2",
    AtreaMode.OVERPRESSURE: "mdi:fan-speed-3",
    AtreaMode.STARTUP: "mdi:chevron-up",
    AtreaMode.RUNDOWN: "mdi:chevron-down",
    AtreaMode.DEFROSTING: "mdi:car-defrost-rear",
    AtreaMode.EXTERNAL: "mdi:fan-alert",
    AtreaMode.HP_DEFROSTING: "mdi:car-defrost-front",
    AtreaMode.IN1: "mdi:fan-chevron-up",
    AtreaMode.IN2: "mdi:fan-chevron-up",
    AtreaMode.D1: "mdi:fan-chevron-up",
    AtreaMode.D2: "mdi:fan-chevron-up",
    AtreaMode.D3: "mdi:fan-chevron-up",
    AtreaMode.D4: "mdi:fan-chevron-up",
}

HVAC_MODES = [HVACMode.OFF, HVACMode.AUTO, HVACMode.FAN_ONLY]
