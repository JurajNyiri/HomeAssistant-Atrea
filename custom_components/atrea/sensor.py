"""Sensors for ATREA analog inputs and outputs."""

from collections.abc import Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, CONF_NAME, PERCENTAGE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import DOMAIN

VOLT = "V"
VOLUME_FLOW_RATE_CUBIC_METERS_PER_HOUR = "m³/h"

SENSOR_REGISTERS = {
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


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Callable,
) -> None:
    """Create sensors for registers supported by the unit."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    known_registers: set[str] = set()

    def async_discover_sensors() -> None:
        status = data.get("status") or {}
        entities = []

        for register, description in SENSOR_REGISTERS.items():
            if (
                register not in status
                or register in known_registers
                or (
                    description.get("constant_flow_only")
                    and str(status.get("H10510")) != "1"
                )
            ):
                continue
            known_registers.add(register)
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

        ip_address = entry.data.get(CONF_IP_ADDRESS)
        device_unique_id = slugify(f"atrea_{ip_address}")
        self._attr_unique_id = slugify(
            f"{device_unique_id}_{description['key']}"
        )
        self._attr_name = description["name"]
        self._attr_native_unit_of_measurement = description["unit"]
        self._attr_device_class = description["device_class"]
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_unique_id)},
            "name": entry.data.get(CONF_NAME) or "atrea",
        }

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
        if not register_available:
            return False
        return (
            not self._constant_flow_only
            or str((self._data.get("status") or {}).get("H10510")) == "1"
        )

    @property
    def native_value(self):
        """Return the converted register value."""
        value = (self._data.get("status") or {}).get(self._register)
        return None if value is None else self._convert(value)

    @property
    def extra_state_attributes(self) -> dict:
        """Expose the source register for diagnostics."""
        return {
            "register": self._register,
            "constant_flow_only": self._constant_flow_only,
        }
