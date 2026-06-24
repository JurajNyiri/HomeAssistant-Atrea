from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .base_entity import AtreaEntityBase
from .const import DOMAIN
from .utils import (
    official_inside_temperature_available,
    official_outside_temperature_available,
    raw_status_int,
    raw_status_temperature,
)


@dataclass(frozen=True)
class AtreaSensorDescription:
    key: str
    name: str
    value_fn: Callable[[Dict[str, str]], Any]
    exists_fn: Callable[[Dict[str, str]], bool]
    native_unit_of_measurement: Optional[str] = None
    device_class: Optional[SensorDeviceClass] = None
    state_class: Optional[SensorStateClass] = None
    icon: Optional[str] = None


SEASON_NAMES = {
    0: "Heating",
    1: "Non-heating",
    2: "T-ODA",
    3: "T-ODA+",
}

AVERAGE_WINDOW_NAMES = {
    0: "1 h",
    1: "3 h",
    2: "6 h",
    3: "12 h",
    4: "1 d",
    5: "2 d",
    6: "3 d",
    7: "4 d",
    8: "5 d",
    9: "6 d",
    10: "7 d",
    11: "8 d",
    12: "9 d",
    13: "10 d",
}

FORCED_MODE_NAMES = {
    0: "Off",
    1: "Startup",
    2: "Rundown",
    3: "D1",
    4: "D2",
    5: "D3",
    6: "D4",
    7: "IN1",
    8: "IN2",
    27: "HP defrosting",
    28: "Prewarm",
    29: "Learning",
    30: "HP defrosting",
    31: "Filter test",
    32: "Periodic ventilation",
}


def _mapped_value(status, key, labels):
    value = raw_status_int(status, key)
    if value is None:
        return None
    return labels.get(value, f"Code {value}")


def _temperature_sensor(key: str, name: str, exists_fn=None):
    if exists_fn is None:
        exists_fn = lambda status: key in status

    return AtreaSensorDescription(
        key=key,
        name=name,
        value_fn=lambda status: raw_status_temperature(status, key),
        exists_fn=exists_fn,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    )


SENSOR_DESCRIPTIONS = [
    _temperature_sensor(
        "I10211",
        "Outdoor air temperature",
        official_outside_temperature_available,
    ),
    _temperature_sensor(
        "I11420",
        "Average outdoor air temperature",
    ),
    _temperature_sensor(
        "I10215",
        "Indoor air temperature",
        official_inside_temperature_available,
    ),
    _temperature_sensor("I10212", "Supply air temperature"),
    _temperature_sensor("I10213", "Extract air temperature"),
    _temperature_sensor("I10214", "Exhaust air temperature"),
    _temperature_sensor("H10716", "Current temperature requirement"),
    AtreaSensorDescription(
        key="I11401",
        name="Season",
        value_fn=lambda status: SEASON_NAMES.get(raw_status_int(status, "I11401")),
        exists_fn=lambda status: "I11401" in status,
        icon="mdi:sun-snowflake",
    ),
    AtreaSensorDescription(
        key="H11431",
        name="Outdoor temperature average window",
        value_fn=lambda status: AVERAGE_WINDOW_NAMES.get(
            raw_status_int(status, "H11431")
        ),
        exists_fn=lambda status: "H11431" in status,
        icon="mdi:timer-outline",
    ),
    AtreaSensorDescription(
        key="H10712",
        name="Forced mode",
        value_fn=lambda status: _mapped_value(status, "H10712", FORCED_MODE_NAMES),
        exists_fn=lambda status: "H10712" in status,
        icon="mdi:fan-alert",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    data = hass.data[DOMAIN][entry.entry_id]
    status = data["status"]

    entities = [
        AtreaSensor(hass, entry, description)
        for description in SENSOR_DESCRIPTIONS
        if description.exists_fn(status)
    ]

    async_add_entities(entities)


class AtreaSensor(AtreaEntityBase, CoordinatorEntity, SensorEntity):
    def __init__(self, hass, entry, description):
        CoordinatorEntity.__init__(self, hass.data[DOMAIN][entry.entry_id]["coordinator"])
        self._atrea_description = description
        self.entity_description = SensorEntityDescription(
            key=description.key,
            name=description.name,
            icon=description.icon,
            device_class=description.device_class,
            state_class=description.state_class,
            native_unit_of_measurement=description.native_unit_of_measurement,
        )
        self.init_atrea_entity(
            hass,
            entry,
            description.name,
            description.key.lower(),
        )

    @property
    def native_value(self):
        status = self.data["status"]
        return self._atrea_description.value_fn(status)

    @property
    def native_unit_of_measurement(self):
        return self._atrea_description.native_unit_of_measurement

    @property
    def unit_of_measurement(self):
        return self._atrea_description.native_unit_of_measurement

    @property
    def device_class(self):
        return self._atrea_description.device_class

    @property
    def state_class(self):
        return self._atrea_description.state_class

    @property
    def icon(self):
        return self._atrea_description.icon

    @property
    def available(self):
        status = self.data["status"]
        return bool(status) and self._atrea_description.exists_fn(status)
