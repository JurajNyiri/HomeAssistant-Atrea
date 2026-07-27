"""Binary sensors for ATREA operating states."""

from collections.abc import Callable

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import DOMAIN

DEFROST_REGISTER = "D10207"


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
        if (
            DEFROST_REGISTER in status
            and DEFROST_REGISTER not in known_registers
        ):
            known_registers.add(DEFROST_REGISTER)
            async_add_entities([AtreaDefrostSensor(entry, data)])

    async_discover_sensors()
    entry.async_on_unload(coordinator.async_add_listener(async_discover_sensors))


class AtreaDefrostSensor(CoordinatorEntity, BinarySensorEntity):
    """Heat-pump defrost input state."""

    _attr_has_entity_name = True
    _attr_name = "Heat pump defrost"
    _attr_icon = "mdi:snowflake-melt"

    def __init__(self, entry: ConfigEntry, data: dict) -> None:
        super().__init__(data["coordinator"])
        self._data = data

        ip_address = entry.data.get(CONF_IP_ADDRESS)
        device_unique_id = slugify(f"atrea_{ip_address}")
        self._attr_unique_id = slugify(
            f"{device_unique_id}_heat_pump_defrost"
        )
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_unique_id)},
            "name": entry.data.get(CONF_NAME) or "atrea",
        }

    @property
    def available(self) -> bool:
        """Report whether the register is present in the latest status."""
        return (
            super().available
            and DEFROST_REGISTER in (self._data.get("status") or {})
        )

    @property
    def is_on(self) -> bool | None:
        """Return whether heat-pump defrost is active."""
        value = (self._data.get("status") or {}).get(DEFROST_REGISTER)
        return None if value is None else str(value) == "1"

    @property
    def extra_state_attributes(self) -> dict:
        """Expose the source register for diagnostics."""
        return {"register": DEFROST_REGISTER}
