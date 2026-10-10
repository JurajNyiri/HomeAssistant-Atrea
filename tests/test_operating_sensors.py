"""Native telemetry regression tests using real Home Assistant entity classes."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.helpers.entity import EntityCategory
from pyatrea import AtreaMode

from custom_components.atrea.binary_sensor import AtreaRegisterBinarySensor
from custom_components.atrea.sensor import (
    SENSOR_REGISTERS, AtreaRegisterSensor, async_setup_entry,
)


def context(status):
    entry = SimpleNamespace(
        entry_id="test", data={"ip_address": "192.0.2.1", "name": "Atrea"},
        async_on_unload=Mock(),
    )
    coordinator = SimpleNamespace(
        last_update_success=True, config_entry=None, async_add_listener=Mock(),
    )
    return entry, {"status": status, "coordinator": coordinator,
                   "supportedForcedModes": [(7, AtreaMode.IN1)]}


def sensor(register, value):
    entry, data = context({register: value})
    return AtreaRegisterSensor(entry, data, register, SENSOR_REGISTERS[register])


@pytest.mark.parametrize("register,value,expected", [
    ("I10200", "215", 21.5), ("I10201", "65511", -2.5),
    ("I10203", "220", 22), ("I10207", "235", 23.5),
    ("H10200", "3500", 3.5), ("H10201", "10000", 10),
    ("H10204", "0", 0), ("H10715", "3", "circulation_and_ventilation"),
    ("H10705", "1", "automatic"), ("H10700", "2", "temporary"),
    ("I11401", "0", "heating"), ("I11401", "1", "non_heating"),
    ("H10712", "7", "in1"), ("H10712", "0", "off"),
    ("H10712", "65000", "unknown"), ("H10714", "11", 11),
    ("H10205", "65535", 65535),
])
def test_native_values(register, value, expected):
    entity = sensor(register, value)
    assert entity.native_value == expected
    assert entity.available


@pytest.mark.parametrize("value", [None, "", "invalid", float("nan")])
def test_invalid_readings_are_unavailable(value):
    entity = sensor("H10200", value)
    assert entity.native_value is None
    assert not entity.available


def test_missing_register_and_failed_refresh_are_unavailable():
    entity = sensor("H10200", "3500")
    entity._data["status"] = {}
    assert not entity.available
    entity._data["status"] = {"H10200": "3500"}
    entity.coordinator.last_update_success = False
    assert not entity.available


def test_diagnostics_are_disabled_by_default_and_have_stable_identity():
    entity = sensor("H10200", "3500")
    assert entity.entity_category == EntityCategory.DIAGNOSTIC
    assert not entity.entity_registry_enabled_default
    assert entity.unique_id == "atrea_192_0_2_1_m1_output_voltage"
    assert entity.device_info["identifiers"] == {("atrea", "atrea_192_0_2_1")}
    assert entity.native_unit_of_measurement == "V"


def test_enums_do_not_have_measurement_statistics():
    entity = sensor("I11401", "1")
    assert entity.device_class == SensorDeviceClass.ENUM
    assert entity.state_class is None
    assert entity.native_unit_of_measurement is None
    assert entity.options == ["heating", "non_heating"]
    assert entity.entity_registry_enabled_default
    assert not sensor("I11401", "99").available


def test_bypass_sentinel_is_not_reported_as_seconds():
    entity = sensor("H10205", "65535")
    assert entity.native_unit_of_measurement is None
    assert entity.state_class is None
    assert entity.native_value == 65535


@pytest.mark.parametrize("register", ["C10215", "C10216"])
def test_heat_pump_binary_states(register):
    entry, data = context({register: "1"})
    entity = AtreaRegisterBinarySensor(entry, data, register, "Heat pump", "mdi:heat-pump")
    assert entity.is_on is True
    data["status"][register] = "0"
    assert entity.is_on is False
    data["status"][register] = "invalid"
    assert entity.is_on is None
    assert not entity.available


@pytest.mark.asyncio
async def test_discovery_is_incremental_and_does_not_duplicate_entities():
    entry, data = context({"I11401": "0"})
    hass = SimpleNamespace(data={"atrea": {"test": data}})
    add = Mock()
    await async_setup_entry(hass, entry, add)
    assert len(add.call_args.args[0]) == 1
    discover = data["coordinator"].async_add_listener.call_args.args[0]
    discover()
    assert add.call_count == 1
    data["status"]["H10200"] = "3500"
    discover()
    assert add.call_count == 2
    assert len(add.call_args.args[0]) == 1
