"""RK5 profile coverage: independent operating state and optional telemetry."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from pyatrea import AtreaMode

from custom_components.atrea.binary_sensor import async_setup_entry as setup_binary
from custom_components.atrea.sensor import async_setup_entry as setup_sensors


@pytest.fixture
def profile():
    return json.loads((Path(__file__).parent / "fixtures/rk5.json").read_text())


@pytest.mark.asyncio
async def test_rk5_registers_create_independent_native_entities(profile):
    entry = SimpleNamespace(
        entry_id="rk5", data={"ip_address": "192.0.2.1", "name": "Atrea"},
        async_on_unload=Mock(),
    )
    data = {
        "status": profile["status"],
        "coordinator": SimpleNamespace(last_update_success=True, config_entry=None, async_add_listener=Mock()),
        "supportedForcedModes": [(int(code), AtreaMode[name]) for code, name in profile["forced_modes"].items()],
    }
    hass = SimpleNamespace(data={"atrea": {"rk5": data}})
    sensors, binary = [], []

    await setup_sensors(hass, entry, sensors.extend)
    await setup_binary(hass, entry, binary.extend)

    prefix = "atrea_192_0_2_1_"
    measured = {entity.unique_id.removeprefix(prefix): entity.native_value for entity in sensors}
    assert measured == profile["expected"]
    assert len({entity.unique_id for entity in sensors + binary}) == len(sensors) + len(binary)
    assert all(entity.available for entity in sensors + binary)
    states = {entity.extra_state_attributes["register"]: entity.is_on for entity in binary}
    assert states == {"D10200": False, "D10201": True, "D10202": False,
                      "D10203": False, "D10207": False, "C10215": True, "C10216": False}

    # Requested, effective, and forced modes are deliberately different.
    assert measured["requested_operating_mode"] == "automatic"
    assert measured["effective_operating_mode"] == "circulation_and_ventilation"
    assert measured["forced_operating_mode"] == "in1"

    data["status"] = False
    assert all(not entity.available for entity in sensors + binary)


@pytest.mark.asyncio
async def test_constant_flow_discovery_does_not_treat_rk5_codes_as_airflow():
    entry = SimpleNamespace(entry_id="rk5", data={"ip_address": "192.0.2.1"}, async_on_unload=Mock())
    status = {"H10510": "0", "I11600": "180"}
    coordinator = SimpleNamespace(last_update_success=True, config_entry=None, async_add_listener=Mock())
    data = {"status": status, "coordinator": coordinator}
    entities = []
    await setup_sensors(SimpleNamespace(data={"atrea": {"rk5": data}}), entry, entities.extend)
    assert entities == []
    status["H10510"] = "1"
    coordinator.async_add_listener.call_args.args[0]()
    assert len(entities) == 1
    assert entities[0].native_value == 180
    status["H10510"] = "0"
    assert not entities[0].available


def test_register_names_produce_distinct_expected_entity_ids():
    from homeassistant.util import slugify
    from custom_components.atrea.sensor import SENSOR_REGISTERS

    names = [slugify(description["name"]) for description in SENSOR_REGISTERS.values()]
    assert len(set(names)) == len(names)
    assert names == [description["key"] for description in SENSOR_REGISTERS.values()]
