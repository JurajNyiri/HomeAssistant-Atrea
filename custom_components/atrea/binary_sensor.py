from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .base_entity import AtreaEntityBase
from .const import DOMAIN
from .utils import raw_status_int


@dataclass(frozen=True)
class AtreaBinarySensorDescription:
    key: str
    name: str
    value_fn: Callable[["AtreaBinarySensor", Dict[str, str]], bool]
    exists_fn: Callable[[Dict[str, str]], bool]
    device_class: Optional[BinarySensorDeviceClass] = None
    icon: Optional[str] = None
    attributes_fn: Optional[
        Callable[["AtreaBinarySensor", Dict[str, str]], Dict[str, Any]]
    ] = None


def _is_one(status, key):
    return raw_status_int(status, key, 0) == 1


def _heating_active(status):
    if _is_one(status, "C10202"):
        return True
    if _is_one(status, "C10215") and raw_status_int(status, "H10519", 0) == 0:
        return True
    if raw_status_int(status, "H10203", 0) > 0:
        return True
    if _is_one(status, "C10217") and raw_status_int(status, "H11801", 0) == 0:
        return True
    return False


def _active_problem_items(entity, status, kind):
    items = []
    for key in entity.data["params"].get(kind, []):
        if key in status and status[key] == "1":
            items.append(entity.atrea.getTranslation(key))
    return items


def _has_active_problem(entity, status, kind):
    return len(_active_problem_items(entity, status, kind)) > 0


BINARY_SENSOR_DESCRIPTIONS = [
    AtreaBinarySensorDescription(
        key="heating_active",
        name="Heating active",
        value_fn=lambda entity, status: _heating_active(status),
        exists_fn=lambda status: any(
            key in status for key in ("C10202", "C10215", "H10203", "C10217")
        ),
        icon="mdi:heat-wave",
    ),
    AtreaBinarySensorDescription(
        key="C10216",
        name="Cooling active",
        value_fn=lambda entity, status: _is_one(status, "C10216"),
        exists_fn=lambda status: "C10216" in status,
        icon="mdi:snowflake",
    ),
    AtreaBinarySensorDescription(
        key="D10200",
        name="D1 input active",
        value_fn=lambda entity, status: _is_one(status, "D10200"),
        exists_fn=lambda status: "D10200" in status,
        icon="mdi:electric-switch",
    ),
    AtreaBinarySensorDescription(
        key="D10201",
        name="D2 input active",
        value_fn=lambda entity, status: _is_one(status, "D10201"),
        exists_fn=lambda status: "D10201" in status,
        icon="mdi:electric-switch",
    ),
    AtreaBinarySensorDescription(
        key="D10202",
        name="D3 input active",
        value_fn=lambda entity, status: _is_one(status, "D10202"),
        exists_fn=lambda status: "D10202" in status,
        icon="mdi:electric-switch",
    ),
    AtreaBinarySensorDescription(
        key="D10203",
        name="D4 input active",
        value_fn=lambda entity, status: _is_one(status, "D10203"),
        exists_fn=lambda status: "D10203" in status,
        icon="mdi:electric-switch",
    ),
    AtreaBinarySensorDescription(
        key="active_alert",
        name="Active alert",
        value_fn=lambda entity, status: _has_active_problem(entity, status, "alert"),
        exists_fn=lambda status: True,
        device_class=BinarySensorDeviceClass.PROBLEM,
        attributes_fn=lambda entity, status: {
            "alerts": _active_problem_items(entity, status, "alert")
        },
    ),
    AtreaBinarySensorDescription(
        key="active_warning",
        name="Active warning",
        value_fn=lambda entity, status: _has_active_problem(entity, status, "warning"),
        exists_fn=lambda status: True,
        device_class=BinarySensorDeviceClass.PROBLEM,
        attributes_fn=lambda entity, status: {
            "warnings": _active_problem_items(entity, status, "warning")
        },
    ),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    data = hass.data[DOMAIN][entry.entry_id]
    status = data["status"]

    entities = [
        AtreaBinarySensor(hass, entry, description)
        for description in BINARY_SENSOR_DESCRIPTIONS
        if description.exists_fn(status)
    ]

    async_add_entities(entities)


class AtreaBinarySensor(AtreaEntityBase, CoordinatorEntity, BinarySensorEntity):
    def __init__(self, hass, entry, description):
        CoordinatorEntity.__init__(self, hass.data[DOMAIN][entry.entry_id]["coordinator"])
        self._atrea_description = description
        self.entity_description = BinarySensorEntityDescription(
            key=description.key,
            name=description.name,
            icon=description.icon,
            device_class=description.device_class,
        )
        self.init_atrea_entity(
            hass,
            entry,
            description.name,
            description.key.lower(),
        )

    @property
    def is_on(self):
        return self._atrea_description.value_fn(self, self.data["status"])

    @property
    def device_class(self):
        return self._atrea_description.device_class

    @property
    def icon(self):
        return self._atrea_description.icon

    @property
    def extra_state_attributes(self):
        if self._atrea_description.attributes_fn is None:
            return None
        return self._atrea_description.attributes_fn(self, self.data["status"])

    @property
    def available(self):
        status = self.data["status"]
        return bool(status) and self._atrea_description.exists_fn(status)
