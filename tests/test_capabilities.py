"""Component discovery, including old units and installed-component changes."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from custom_components.atrea.capabilities import supports_register
from custom_components.atrea.sensor import async_setup_entry as setup_sensors
from custom_components.atrea.binary_sensor import async_setup_entry as setup_binary


@pytest.mark.parametrize("register,config,expected", [
    ("H10202", {"H10504": "0"}, False),
    ("H10202", {"H10504": "1"}, True),
    ("H10202", {"H10504": "2"}, True),
    ("H10205", {"H11800": "0"}, False),
    ("H10206", {"H11800": "1"}, True),
    ("H10204", {"H11700": "0", "C10509": "0"}, False),
    ("H10204", {"H11700": "1", "C10509": "0"}, True),
    ("H10204", {"H11700": "0", "C10509": "1"}, True),
    ("H10203", {"H10503": "0", "H10517": "0"}, False),
    ("H10203", {"H10503": "0", "H10517": "2"}, True),
    ("C10215", {"H10503": "2"}, False),
    ("C10215", {"H10503": "5"}, True),
    ("C10215", {"H10503": "6"}, True),
    ("C10216", {"H10507": "0"}, False),
    ("C10216", {"H10507": "1"}, True),
    ("C10216", {"H10507": "2"}, True),
    ("D10207", {"H10503": "2", "H10507": "1"}, False),
    ("D10207", {"H10503": "5", "H10507": "1"}, True),
    ("D10207", {"H10503": "0", "H10507": "2"}, True),
    ("I11600", {"H10510": "1"}, True),
    ("I11600", {"H10510": "4", "C10509": "1"}, True),
    ("I11600", {"H10510": "4", "C10509": "0"}, False),
    ("I11600", {"H10510": "0"}, False),
    ("I11600", {"H10510": "2"}, False),
    ("I11604", {"H10510": "1", "C10509": "0"}, False),
    ("I11604", {"H10510": "4", "C10509": "1"}, True),
])
def test_known_component_configuration(register, config, expected):
    assert supports_register(config, register) == expected


@pytest.mark.parametrize("register", ["H10202", "H10203", "H10204", "H10205", "H10206", "C10215", "C10216", "D10207"])
@pytest.mark.parametrize("missing", [None, "invalid", "99"])
def test_older_or_unknown_configuration_preserves_discovery(register, missing):
    status = dict.fromkeys(["H10503", "H10504", "H10507", "H10517", "H11700", "H11800", "C10509"], missing)
    assert supports_register(status, register)
    assert supports_register({}, register)


@pytest.mark.asyncio
@pytest.mark.parametrize("setup,register,capability", [
    (setup_sensors, "H10202", "H10504"),
    (setup_sensors, "H10205", "H11800"),
    (setup_sensors, "H10206", "H11800"),
    (setup_binary, "C10216", "H10507"),
])
async def test_component_added_removed_and_restored_without_duplicates(setup, register, capability):
    entry = SimpleNamespace(entry_id="test", data={"ip_address": "192.0.2.1"}, async_on_unload=Mock())
    coordinator = SimpleNamespace(last_update_success=True, config_entry=None, async_add_listener=Mock())
    data = {"status": {register: "1", capability: "0"}, "coordinator": coordinator}
    entities = []
    await setup(SimpleNamespace(data={"atrea": {"test": data}}), entry, entities.extend)
    assert entities == []
    discover = coordinator.async_add_listener.call_args.args[0]
    data["status"][capability] = "1"
    discover()
    assert len(entities) == 1 and entities[0].available
    identity = entities[0].unique_id
    data["status"][capability] = "0"
    discover()
    assert not entities[0].available
    data["status"][capability] = "1"
    discover()
    assert len(entities) == 1 and entities[0].available
    assert entities[0].unique_id == identity


@pytest.mark.asyncio
async def test_rk5_water_heating_cooling_and_constant_flow_profile():
    import json
    from pathlib import Path
    status = json.loads((Path(__file__).parent / "fixtures/rk5_components.json").read_text())["status"]
    entry = SimpleNamespace(entry_id="test", data={"ip_address": "192.0.2.1"}, async_on_unload=Mock())
    data = {"status": status, "coordinator": SimpleNamespace(last_update_success=True, config_entry=None, async_add_listener=Mock())}
    hass = SimpleNamespace(data={"atrea": {"test": data}})
    sensors, binary = [], []
    await setup_sensors(hass, entry, sensors.extend)
    await setup_binary(hass, entry, binary.extend)
    values = {s.unique_id.removeprefix("atrea_192_0_2_1_"): s.native_value for s in sensors}
    assert "sa1_output" not in values
    assert values["sa2_output_voltage"] == 0
    assert values["circulation"] == 71
    assert values["supply_requested_airflow"] == 600
    assert values["supply_actual_airflow"] == 589
    assert values["extract_requested_airflow"] == 180
    assert values["extract_actual_airflow"] == 182
    assert values["outdoor_requested_airflow"] == 180
    assert values["outdoor_actual_airflow"] == 177
    assert [s.extra_state_attributes["register"] for s in binary] == ["C10216"]
    assert all(s.available for s in sensors + binary)
