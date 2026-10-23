"""Read-only summaries of controller-declared faults and warnings."""

from urllib.parse import unquote

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CONF_IP_ADDRESS, CONF_NAME, EVENT_LOGBOOK_ENTRY
from homeassistant.core import callback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify

from .const import DOMAIN

CONDITIONS = {
    "alert": ("fault_active", "Fault active", "active_faults"),
    "warning": ("warning_active", "Warning active", "active_warnings"),
    "filter": (
        "filter_maintenance_required",
        "Filter maintenance required",
        "active_warnings",
    ),
}
# The unit reports these independently: pressure-based clogging and service interval.
FILTER_CODES = {"D11122", "D11183"}


def condition_codes(data, kind):
    """Use the unit's declared groups, not a firmware-wide list of alarms."""
    params = data.get("params") or {}
    if kind == "filter":
        return sorted(FILTER_CODES.intersection(params.get("warning") or []))
    return sorted(set(params.get(kind) or []))


def condition_label(data, code, kind):
    """Decode already-loaded controller text; entity properties never do I/O."""
    value = ((data.get("translations") or {}).get("params") or {}).get(code)
    candidates = (
        [value.get("d"), value.get("t")] if isinstance(value, dict) else [value]
    )
    for candidate in candidates:
        if isinstance(candidate, str):
            text = unquote(candidate).strip()
            if text and text.lower() != "not to be translated" and text != code:
                return text
    return f"{'Fault' if kind == 'alert' else 'Warning'} ({code})"


def discover_conditions(entry, data, known):
    """Create each supported summary once, even if none of its flags is active."""
    entities = []
    for kind in CONDITIONS:
        if kind not in known and condition_codes(data, kind):
            known.add(kind)
            entities.append(AtreaConditionSensor(entry, data, kind))
    return entities


class AtreaConditionBase(CoordinatorEntity):
    """A problem sensor with the complete list of active controller flags."""

    _attr_has_entity_name = True

    def __init__(self, entry, data, kind):
        super().__init__(data["coordinator"])
        self._data = data
        self._kind = kind
        key, self._attr_name, self._list_attribute = CONDITIONS[kind]
        device_id = slugify(f"atrea_{entry.data.get(CONF_IP_ADDRESS)}")
        self._attr_unique_id = f"{device_id}_{key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_id)},
            "name": entry.data.get(CONF_NAME) or "atrea",
        }
        self._previous_active = None

    @property
    def _active_codes(self):
        status = self._data.get("status") or {}
        return [
            code
            for code in condition_codes(self._data, self._kind)
            if str(status.get(code)) == "1"
        ]

    @property
    def is_on(self):
        codes = condition_codes(self._data, self._kind)
        status = self._data.get("status") or {}
        if self._active_codes:
            return True
        if codes and all(str(status.get(code)) == "0" for code in codes):
            return False
        # Missing or invalid flags must never be interpreted as 'all clear'.
        return None

    @property
    def available(self):
        return super().available and self.is_on is not None

    @property
    def extra_state_attributes(self):
        status = self._data.get("status") or {}
        active = self._active_codes
        return {
            self._list_attribute: [
                condition_label(self._data, code, self._kind) for code in active
            ],
            "active_codes": active,
            "unavailable_codes": [
                code
                for code in condition_codes(self._data, self._kind)
                if str(status.get(code)) not in ("0", "1")
            ],
        }


class AtreaConditionSensor(AtreaConditionBase, BinarySensorEntity):
    """Boolean problem status with Activity messages for changing conditions."""

    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        self._previous_active = set(self._active_codes) if self.available else None

    @callback
    def _handle_coordinator_update(self):
        previous = self._previous_active
        current = set(self._active_codes) if self.available else None
        super()._handle_coordinator_update()
        # Native on/off entries cover the first fault and the last clearance.
        # Log only changes while the summary remains on, avoiding duplicate entries.
        if previous and current and previous != current:
            parts = []
            status = self._data.get("status") or {}
            cleared = {
                code for code in previous - current if str(status.get(code)) == "0"
            }
            for label, codes in (("Active", current - previous), ("Cleared", cleared)):
                if codes:
                    parts.append(
                        f"{label}: "
                        + ", ".join(
                            condition_label(self._data, code, self._kind)
                            for code in sorted(codes)
                        )
                    )
            if parts:
                self.hass.bus.async_fire(
                    EVENT_LOGBOOK_ENTRY,
                    {
                        "name": self.name,
                        "entity_id": self.entity_id,
                        "message": "; ".join(parts),
                    },
                )
            # A missing flag is not proof that its fault cleared.
            current |= previous - current - cleared
        self._previous_active = current


def discover_condition_details(entry, data, known):
    """Add readable reasons to the device page for supported condition groups."""
    entities = []
    for kind in ("alert", "warning"):
        if kind not in known and condition_codes(data, kind):
            known.add(kind)
            entities.append(AtreaConditionDetailsSensor(entry, data, kind))
    return entities


class AtreaConditionDetailsSensor(AtreaConditionBase, SensorEntity):
    """Readable conditions using the same flags and labels as problem sensors."""

    def __init__(self, entry, data, kind):
        super().__init__(entry, data, kind)
        label = "Fault" if kind == "alert" else "Warning"
        self._attr_name = f"{label} details"
        device_id = slugify(f"atrea_{entry.data.get(CONF_IP_ADDRESS)}")
        self._attr_unique_id = f"{device_id}_{label.lower()}_details"

    @property
    def native_value(self):
        if not self.available:
            return None
        labels = self.extra_state_attributes[self._list_attribute]
        if not labels:
            return "No active faults" if self._kind == "alert" else "No active warnings"
        text = "; ".join(labels)
        # HA limits state strings to 255 characters; attributes retain every reason.
        return text if len(text) <= 255 else text[:254] + "…"
