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
    ("H10205", "65535", None),
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


@pytest.mark.parametrize("register", ["H10205", "H10206"])
@pytest.mark.parametrize("value,expected", [
    ("0", 0), ("1250", 1250), ("32768", 32768),
    ("32769", None), ("65534", None), ("65535", None),
])
def test_bypass_pulses_and_special_codes(register, value, expected):
    entity = sensor(register, value)
    assert entity.native_unit_of_measurement == "ms"
    assert entity.device_class == SensorDeviceClass.DURATION
    assert entity.state_class == "measurement"
    assert entity.native_value == expected
    assert entity.available
    assert entity.extra_state_attributes["raw_value"] == value
    assert not entity.entity_registry_enabled_default
    suffix = "plus" if register == "H10205" else "minus"
    assert entity.unique_id == f"atrea_192_0_2_1_bypass_{suffix}_code"


@pytest.mark.parametrize("value", [None, "", "bad", "-1", "65536"])
def test_invalid_bypass_register_is_unavailable(value):
    assert not sensor("H10205", value).available


@pytest.mark.asyncio
async def test_bypass_measurements_are_filtered_from_device_activity(tmp_path):
    from homeassistant.core import HomeAssistant
    from homeassistant.components.logbook.helpers import async_filter_entities
    hass = HomeAssistant(str(tmp_path))
    try:
        entity = sensor("H10205", "1250")
        hass.states.async_set("sensor.bypass", entity.native_value, {
            "unit_of_measurement": entity.native_unit_of_measurement,
            "state_class": entity.state_class,
            "device_class": entity.device_class,
        })
        hass.states.async_set("sensor.program", "manual", {"device_class": "enum"})
        assert async_filter_entities(hass, ["sensor.bypass", "sensor.program"]) == ["sensor.program"]
    finally:
        await hass.async_stop(force=True)


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


@pytest.mark.parametrize("register", ["H10714", "H10704"])
def test_device_confirmed_power_codes_have_readable_states(register):
    entry, data = context({register: "33", "C10509": "1"})
    data["powerModeOptions"] = {0: "Off", 33: "Norm/Min"}
    entity = AtreaRegisterSensor(entry, data, register, SENSOR_REGISTERS[register])
    assert entity.native_value == "Normal circulation / minimum ventilation"
    assert entity.extra_state_attributes["raw_value"] == "33"
    assert entity.device_class == SensorDeviceClass.ENUM
    assert entity.state_class is None
    assert entity.native_unit_of_measurement is None
    assert entity.available
    assert entity.unique_id.endswith("power_code")
    assert entity.entity_category is None
    assert entity.entity_registry_enabled_default
    data["status"][register] = "99"
    assert entity.native_value is None
    assert entity.available
    assert entity.extra_state_attributes["raw_value"] == "99"
    data["status"]["C10509"] = "0"
    assert not entity.available
    assert entity.native_value is None


def test_power_33_without_device_metadata_stays_raw():
    entity = sensor("H10704", "33")
    assert entity.native_value == 33
    assert entity.device_class is None
    assert entity.name == "Effective power code"


def test_device_input_names_preserve_register_identity():
    entry, data = context({"I10205": "3500", "D10200": "1"})
    data["userLabels"] = {"IN1": "Room A", "D1": "Room B"}
    analog = AtreaRegisterSensor(entry, data, "I10205", SENSOR_REGISTERS["I10205"])
    binary = AtreaRegisterBinarySensor(entry, data, "D10200", "D1 input", "mdi:electric-switch")
    assert analog.name == "IN1 voltage (Room A)"
    assert analog.unique_id.endswith("in1_voltage")
    assert binary.name == "D1 input (Room B)"
    assert binary.unique_id.endswith("d10200")
