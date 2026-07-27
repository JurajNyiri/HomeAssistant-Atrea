"""Binary sensors for ATREA operating states."""

from collections.abc import Callable

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import DOMAIN

BINARY_SENSOR_REGISTERS = {
    "D10200": ("D1 input", "mdi:electric-switch"),
    "D10201": ("D2 input", "mdi:electric-switch"),
    "D10202": ("D3 input", "mdi:electric-switch"),
    "D10203": ("D4 input", "mdi:electric-switch"),
    "D10207": ("Heat pump defrost", "mdi:snowflake-melt"),
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Callable,
) -> None:
    """Create supported operating-state sensors."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    known_registers: set[str] = set()

    def async_discover_sensors() -> None:
        status = data.get("status") or {}
        entities = []

        for register, (name, icon) in BINARY_SENSOR_REGISTERS.items():
            if register not in status or register in known_registers:
                continue
            known_registers.add(register)
            entities.append(
                AtreaRegisterBinarySensor(entry, data, register, name, icon)
            )

        if entities:
            async_add_entities(entities)

    async_discover_sensors()
    entry.async_on_unload(coordinator.async_add_listener(async_discover_sensors))


class AtreaRegisterBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """A binary sensor backed by one ATREA status register."""

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: ConfigEntry,
        data: dict,
        register: str,
        name: str,
        icon: str,
    ) -> None:
        super().__init__(data["coordinator"])
        self._data = data
        self._register = register
        self._attr_name = name
        self._attr_icon = icon

        ip_address = entry.data.get(CONF_IP_ADDRESS)
        device_unique_id = slugify(f"atrea_{ip_address}")
        self._attr_unique_id = slugify(f"{device_unique_id}_{register}")
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_unique_id)},
            "name": entry.data.get(CONF_NAME) or "atrea",
        }

    @property
    def available(self) -> bool:
        """Report whether the register is present in the latest status."""
        return (
            super().available
            and self._register in (self._data.get("status") or {})
        )

    @property
    def is_on(self) -> bool | None:
        """Return whether heat-pump defrost is active."""
        value = (self._data.get("status") or {}).get(self._register)
        return None if value is None else str(value) == "1"

    @property
    def extra_state_attributes(self) -> dict:
        """Expose the source register for diagnostics."""
        return {"register": self._register}
