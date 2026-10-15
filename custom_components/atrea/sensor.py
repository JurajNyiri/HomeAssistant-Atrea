"""Sensors for ATREA analog inputs and outputs."""

from collections.abc import Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_IP_ADDRESS,
    CONF_NAME,
    PERCENTAGE,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify
from pyatrea import AtreaMode

from .const import DOMAIN, ALL_PRESET_LIST, POWER_DISPLAY_LABELS
from .utils import convert_temperature, forced_mode_label

VOLT = "V"
VOLUME_FLOW_RATE_CUBIC_METERS_PER_HOUR = "m³/h"

INPUT_LABEL_IDS = {"I10205": "IN1", "I10206": "IN2"}

SENSOR_REGISTERS = {
    "I10211": {
        "key": "outdoor_air_temperature",
        "name": "Outdoor air temperature",
        "unit": UnitOfTemperature.CELSIUS,
        "device_class": SensorDeviceClass.TEMPERATURE,
        "display_precision": 1,
        "convert": convert_temperature,
    },
    "I10212": {
        "key": "supply_air_temperature",
        "name": "Supply air temperature",
        "unit": UnitOfTemperature.CELSIUS,
        "device_class": SensorDeviceClass.TEMPERATURE,
        "display_precision": 1,
        "convert": convert_temperature,
    },
    "I10213": {
        "key": "extract_air_temperature",
        "name": "Extract air temperature",
        "unit": UnitOfTemperature.CELSIUS,
        "device_class": SensorDeviceClass.TEMPERATURE,
        "display_precision": 1,
        "convert": convert_temperature,
    },
    "I10214": {
        "key": "exhaust_air_temperature",
        "name": "Exhaust air temperature",
        "unit": UnitOfTemperature.CELSIUS,
        "device_class": SensorDeviceClass.TEMPERATURE,
        "display_precision": 1,
        "convert": convert_temperature,
    },
    "I10215": {
        "key": "indoor_air_temperature",
        "name": "Indoor air temperature",
        "unit": UnitOfTemperature.CELSIUS,
        "device_class": SensorDeviceClass.TEMPERATURE,
        "display_precision": 1,
        "convert": convert_temperature,
    },
    "I11420": {
        "key": "average_outdoor_air_temperature",
        "name": "Average outdoor air temperature",
        "unit": UnitOfTemperature.CELSIUS,
        "device_class": SensorDeviceClass.TEMPERATURE,
        "display_precision": 1,
        "convert": convert_temperature,
    },
    "I10205": {
        "key": "in1_voltage",
        "name": "IN1 voltage",
        "unit": VOLT,
        "device_class": SensorDeviceClass.VOLTAGE,
        "display_precision": 3,
        "convert": lambda value: int(value) / 1000,
    },
    "I10206": {
        "key": "in2_voltage",
        "name": "IN2 voltage",
        "unit": VOLT,
        "device_class": SensorDeviceClass.VOLTAGE,
        "display_precision": 3,
        "convert": lambda value: int(value) / 1000,
    },
    "H10202": {
        "key": "sa1_output",
        "name": "SA1 output",
        "unit": PERCENTAGE,
        "device_class": None,
        "convert": lambda value: int(value) * 10,
    },
    "I11600": {
        "key": "supply_requested_airflow",
        "name": "Supply requested airflow",
        "unit": VOLUME_FLOW_RATE_CUBIC_METERS_PER_HOUR,
        "device_class": None,
        "convert": int,
        "constant_flow_only": True,
    },
    "I11602": {
        "key": "supply_actual_airflow",
        "name": "Supply actual airflow",
        "unit": VOLUME_FLOW_RATE_CUBIC_METERS_PER_HOUR,
        "device_class": None,
        "convert": int,
        "constant_flow_only": True,
    },
    "I11601": {
        "key": "extract_requested_airflow",
        "name": "Extract requested airflow",
        "unit": VOLUME_FLOW_RATE_CUBIC_METERS_PER_HOUR,
        "device_class": None,
        "convert": int,
        "constant_flow_only": True,
    },
    "I11603": {
        "key": "extract_actual_airflow",
        "name": "Extract actual airflow",
        "unit": VOLUME_FLOW_RATE_CUBIC_METERS_PER_HOUR,
        "device_class": None,
        "convert": int,
        "constant_flow_only": True,
    },
    "I11604": {
        "key": "outdoor_requested_airflow",
        "name": "Outdoor requested airflow",
        "unit": VOLUME_FLOW_RATE_CUBIC_METERS_PER_HOUR,
        "device_class": None,
        "convert": int,
        "constant_flow_only": True,
    },
    "I11605": {
        "key": "outdoor_actual_airflow",
        "name": "Outdoor actual airflow",
        "unit": VOLUME_FLOW_RATE_CUBIC_METERS_PER_HOUR,
        "device_class": None,
        "convert": int,
        "constant_flow_only": True,
    },
}


# Physical sensor names stay independent of installation orientation and rooms.
for register, key, name in (
    ("I10200", "tu1_temperature", "TU1 temperature"),
    ("I10201", "tu2_temperature", "TU2 temperature"),
    ("I10203", "teb_temperature", "TEb temperature"),
    ("I10207", "control_panel_temperature", "Control panel temperature"),
):
    SENSOR_REGISTERS[register] = {
        "key": key, "name": name, "unit": UnitOfTemperature.CELSIUS,
        "device_class": SensorDeviceClass.TEMPERATURE,
        "display_precision": 1, "convert": convert_temperature,
        "entity_category": EntityCategory.DIAGNOSTIC, "enabled": False,
    }

for register, key, name in (
    ("H10200", "m1_output_voltage", "M1 output voltage"),
    ("H10201", "m2_output_voltage", "M2 output voltage"),
    ("H10203", "sa2_output_voltage", "SA2 output voltage"),
    ("H10204", "sc_output_voltage", "SC output voltage"),
):
    SENSOR_REGISTERS[register] = {
        "key": key, "name": name, "unit": VOLT,
        "device_class": SensorDeviceClass.VOLTAGE,
        "display_precision": 3, "convert": lambda value: int(value) / 1000,
        "entity_category": EntityCategory.DIAGNOSTIC, "enabled": False,
    }

# R5/Power_2Z circulation damper command: 0 V = circulation, 10 V = ventilation.
# Keep the raw voltage diagnostic as a separate entity.
CIRCULATION_SENSOR = {
    "key": "circulation", "name": "Circulation", "unit": PERCENTAGE,
    "device_class": None, "display_precision": 0,
    "convert": lambda value: 100 - int(value) / 100 if 0 <= int(value) <= 10000 else None,
    "circulation_only": True,
}

OPERATING_MODES = {int(mode): ALL_PRESET_LIST[int(mode)] for mode in AtreaMode}
PROGRAMS = {0: "manual", 1: "weekly", 2: "temporary"}
SEASONS = {0: "heating", 1: "non_heating"}

for register, key, name, values in (
    ("H10715", "requested_operating_mode", "Requested operating mode", OPERATING_MODES),
    ("H10705", "effective_operating_mode", "Effective operating mode", OPERATING_MODES),
    ("H10700", "operating_program", "Operating program", PROGRAMS),
    ("I11401", "operating_season", "Operating season", SEASONS),
):
    SENSOR_REGISTERS[register] = {
        "key": key, "name": name, "unit": None,
        "device_class": SensorDeviceClass.ENUM, "state_class": None,
        "options": list(values.values()),
        "convert": lambda value, values=values: values.get(int(value)),
    }

SENSOR_REGISTERS["H10712"] = {
    "key": "forced_operating_mode", "name": "Forced operating mode",
    "unit": None, "device_class": SensorDeviceClass.ENUM, "state_class": None,
    "options": list(OPERATING_MODES.values()) + ["unknown"],
    "convert": int, "forced_mode": True,
}

# Discrete power codes are not percentages. Keep these diagnostics optional.
for register, key, name in (
    ("H10714", "requested_power_code", "Requested power code"),
    ("H10704", "effective_power_code", "Effective power code"),
):
    SENSOR_REGISTERS[register] = {
        "key": key, "name": name, "unit": None, "device_class": None,
        "state_class": None, "convert": int,
        "entity_category": EntityCategory.DIAGNOSTIC, "enabled": False,
    }


# RD5 register reference, page 3: finite pulses use milliseconds (0..32768).
# Special codes have no finite duration. Preserve them as diagnostic attributes;
# do not guess a duration or include sentinel values in measurement statistics.
for register, direction, legacy_key in (
    ("H10205", "opening", "bypass_plus_code"),
    ("H10206", "closing", "bypass_minus_code"),
):
    SENSOR_REGISTERS[register] = {
        "key": f"bypass_{direction}_pulse_duration",
        "unique_id_key": legacy_key,
        "name": f"Bypass {direction} pulse duration",
        "unit": UnitOfTime.MILLISECONDS, "device_class": SensorDeviceClass.DURATION,
        "convert": lambda value: int(value) if 0 <= int(value) <= 32768 else None,
        "pulse_duration": True,
        "entity_category": EntityCategory.DIAGNOSTIC, "enabled": False,
    }


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Callable,
) -> None:
    """Create sensors for registers supported by the unit."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    known_sensors: set[str] = set()

    def async_discover_sensors() -> None:
        status = data.get("status") or {}
        entities = []

        for register, description in (*SENSOR_REGISTERS.items(), ("H10204", CIRCULATION_SENSOR)):
            if (
                register not in status
                or description["key"] in known_sensors
                or (description.get("circulation_only") and str(status.get("C10509")) != "1")
                or (
                    description.get("constant_flow_only")
                    and str(status.get("H10510")) != "1"
                )
            ):
                continue
            known_sensors.add(description["key"])
            entities.append(
                AtreaRegisterSensor(entry, data, register, description)
            )

        if entities:
            async_add_entities(entities)

    async_discover_sensors()
    entry.async_on_unload(coordinator.async_add_listener(async_discover_sensors))


class AtreaRegisterSensor(CoordinatorEntity, SensorEntity):
    """A sensor backed by one ATREA status register."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        entry: ConfigEntry,
        data: dict,
        register: str,
        description: dict,
    ) -> None:
        super().__init__(data["coordinator"])
        self._data = data
        self._register = register
        self._convert = description["convert"]
        self._display_precision = description.get("display_precision")
        self._constant_flow_only = description.get("constant_flow_only", False)
        self._forced_mode = description.get("forced_mode", False)
        self._circulation_only = description.get("circulation_only", False)
        self._pulse_duration = description.get("pulse_duration", False)
        self._power_labels = {}
        if register in ("H10714", "H10704"):
            self._power_labels = {
                code: POWER_DISPLAY_LABELS.get(code, label)
                for code, label in data.get("powerModeOptions", {}).items()
            }
        self._attr_state_class = description.get("state_class", SensorStateClass.MEASUREMENT)
        self._attr_options = description.get("options")
        self._attr_entity_category = description.get("entity_category")
        self._attr_entity_registry_enabled_default = description.get("enabled", True)

        ip_address = entry.data.get(CONF_IP_ADDRESS)
        device_unique_id = slugify(f"atrea_{ip_address}")
        self._device_unique_id = device_unique_id
        unique_id_key = description.get("unique_id_key", description["key"])
        self._attr_unique_id = slugify(f"{device_unique_id}_{unique_id_key}")
        self._attr_name = description["name"]
        self._attr_native_unit_of_measurement = description["unit"]
        self._attr_device_class = description["device_class"]
        input_label = data.get("userLabels", {}).get(INPUT_LABEL_IDS.get(register))
        if input_label:
            self._attr_name = f"{self._attr_name} ({input_label})"
        if self._power_labels:
            self._attr_name = "Requested fan setting" if register == "H10714" else "Effective fan setting"
            self._attr_device_class = SensorDeviceClass.ENUM
            self._attr_options = list(dict.fromkeys(self._power_labels.values()))
            self._attr_entity_category = None
            self._attr_entity_registry_enabled_default = True
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_unique_id)},
            "name": entry.data.get(CONF_NAME) or "atrea",
        }

    def _forced_label(self, mode):
        return forced_mode_label(
            getattr(self, "hass", None), self._device_unique_id, mode,
            self._data.get("userLabels", {}),
        )

    @property
    def options(self):
        if self._forced_mode:
            return list(dict.fromkeys(self._forced_label(mode) for mode in AtreaMode)) + ["unknown"]
        return self._attr_options

    @property
    def suggested_display_precision(self) -> int | None:
        """Return the preferred number of decimal places."""
        return self._display_precision

    @property
    def available(self) -> bool:
        """Report whether the register is present in the latest status."""
        register_available = (
            super().available
            and self._register in (self._data.get("status") or {})
        )
        if self._circulation_only and str((self._data.get("status") or {}).get("C10509")) != "1":
            return False
        if not register_available:
            return False
        if self._pulse_duration:
            try:
                # A valid special code means connected, but no finite duration.
                return 0 <= int(self._data["status"][self._register]) <= 65535
            except (TypeError, ValueError, OverflowError):
                return False
        if self._power_labels:
            if str(self._data["status"].get("C10509")) != "1":
                return False
            try:
                # Keep an unrecognized code available as raw diagnostic data.
                return 0 <= int(self._data["status"][self._register]) <= 65535
            except (TypeError, ValueError, OverflowError):
                return False
        if self.native_value is None:
            return False
        return (
            not self._constant_flow_only
            or str((self._data.get("status") or {}).get("H10510")) == "1"
        )

    @property
    def native_value(self):
        """Return the converted register value."""
        value = (self._data.get("status") or {}).get(self._register)
        if value is None:
            return None
        try:
            if self._power_labels:
                if str(self._data["status"].get("C10509")) != "1":
                    return None
                return self._power_labels.get(int(value))
            if self._forced_mode:
                code = int(value)
                modes = dict(self._data.get("supportedForcedModes", []))
                mode = modes.get(code)
                if code == 0:
                    return OPERATING_MODES[0]
                return self._forced_label(mode) if mode is not None else "unknown"
            return self._convert(value)
        except (TypeError, ValueError, OverflowError):
            return None

    @property
    def extra_state_attributes(self) -> dict:
        """Expose the source register for diagnostics."""
        return {
            "register": self._register,
            "constant_flow_only": self._constant_flow_only,
            **({"raw_value": (self._data.get("status") or {}).get(self._register)}
               if self._attr_state_class is None or self._pulse_duration else {}),
        }
