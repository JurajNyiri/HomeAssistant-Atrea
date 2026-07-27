"""Buttons representing active ATREA warnings and alerts."""

from collections.abc import Callable

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import DOMAIN

FILTER_WARNING_CODE = "D11183"
FILTER_ACKNOWLEDGE_REGISTER = "C10007"
ALERT_RESET_REGISTER = "C10005"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: Callable,
) -> None:
    """Create buttons as warning and alert conditions appear."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    known_conditions: set[tuple[str, str]] = set()

    def async_discover_conditions() -> None:
        entities = []
        for severity, code in _active_conditions(data):
            key = (severity, code)
            if key in known_conditions:
                continue
            known_conditions.add(key)
            entities.append(AtreaConditionButton(entry, data, severity, code))

        if entities:
            async_add_entities(entities)

    async_discover_conditions()
    entry.async_on_unload(coordinator.async_add_listener(async_discover_conditions))


def _active_conditions(data: dict) -> list[tuple[str, str]]:
    """Return active warning and alert parameter IDs."""
    status = data.get("status") or {}
    params = data.get("params") or {}
    conditions = []

    for severity in ("warning", "alert"):
        for code in params.get(severity, []):
            if str(status.get(code, "0")) == "1":
                conditions.append((severity, code))

    return conditions


class AtreaConditionButton(CoordinatorEntity, ButtonEntity):
    """A button representing one ATREA condition."""

    _attr_has_entity_name = True

    def __init__(
        self,
        entry: ConfigEntry,
        data: dict,
        severity: str,
        code: str,
    ) -> None:
        super().__init__(data["coordinator"])
        self._data = data
        self._severity = severity
        self._code = code
        self._atrea = data["atrea"]

        ip_address = entry.data.get(CONF_IP_ADDRESS)
        device_unique_id = slugify(f"atrea_{ip_address}")
        self._attr_unique_id = slugify(
            f"{device_unique_id}_{severity}_{code}"
        )
        self._attr_name = self._translation
        self._attr_icon = (
            "mdi:alert-octagon-outline"
            if severity == "alert"
            else "mdi:alert-outline"
        )
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_unique_id)},
            "name": entry.data.get(CONF_NAME) or "atrea",
        }

    @property
    def _translation(self) -> str:
        """Return the unit-provided text, falling back to the parameter ID."""
        return self._atrea.getTranslation(self._code) or self._code

    @property
    def available(self) -> bool:
        """Only allow interaction while this condition is active."""
        return super().available and (
            (self._severity, self._code) in _active_conditions(self._data)
        )

    @property
    def extra_state_attributes(self) -> dict:
        """Expose stable machine-readable condition details."""
        acknowledgement_supported = (
            self._severity == "alert" or self._code == FILTER_WARNING_CODE
        )
        return {
            "code": self._code,
            "severity": self._severity,
            "message": self._translation,
            "acknowledgement_supported": acknowledgement_supported,
            "acknowledgement_scope": (
                "all_alerts" if self._severity == "alert" else "this_warning"
            )
            if acknowledgement_supported
            else None,
        }

    async def async_press(self) -> None:
        """Acknowledge the condition using the unit's native web UI command."""
        if not self.available:
            raise HomeAssistantError("This ATREA condition is no longer active")

        if self._severity == "alert":
            register = ALERT_RESET_REGISTER
        elif self._code == FILTER_WARNING_CODE:
            register = FILTER_ACKNOWLEDGE_REGISTER
        else:
            raise HomeAssistantError(
                f"ATREA warning {self._code} cannot be acknowledged"
            )

        success = await self.hass.async_add_executor_job(
            self._atrea.executeOneShotCommand, register, 1
        )
        if not success:
            raise HomeAssistantError(
                f"ATREA did not accept acknowledgement register {register}"
            )

        await self.coordinator.async_request_refresh()
