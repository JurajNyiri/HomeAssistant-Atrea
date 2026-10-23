"""Read-only condition summaries, partial data, and Activity transitions."""

from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

import pytest
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from custom_components.atrea.conditions import (
    AtreaConditionSensor,
    discover_conditions,
    condition_label,
)


@pytest.fixture
def data():
    return {
        "coordinator": NS(last_update_success=True),
        "params": {
            "alert": ["D11100", "D11107"],
            "warning": ["D11183", "D11122", "D11149"],
        },
        "status": {
            "D11100": "0",
            "D11107": "0",
            "D11183": "0",
            "D11122": "0",
            "D11149": "0",
        },
        "translations": {
            "params": {
                "D11100": {"d": "Unit%20overheat"},
                "D11107": {"t": "Temperature sensor failure"},
                "D11183": {"t": "Filter replace interval"},
                "D11149": {"t": "Heat pump defrosting"},
            }
        },
    }


def sensor(data, kind="alert"):
    entity = AtreaConditionSensor(NS(data={"ip_address": "192.0.2.1"}), data, kind)
    entity.entity_id = f"binary_sensor.atrea_{kind}"
    entity.hass = NS(bus=NS(async_fire=Mock()))
    return entity


def update(entity):
    with patch.object(CoordinatorEntity, "_handle_coordinator_update"):
        entity._handle_coordinator_update()


def test_discover_supported_summaries_once_even_when_inactive(data):
    known = set()
    entry = NS(data={"ip_address": "192.0.2.1"})
    entities = discover_conditions(entry, data, known)
    assert [e.name for e in entities] == [
        "Fault active",
        "Warning active",
        "Filter maintenance required",
    ]
    assert all(e.available and e.is_on is False for e in entities)
    assert discover_conditions(entry, data, known) == []
    assert len({e.unique_id for e in entities}) == 3


def test_absent_metadata_does_not_create_false_all_clear(data):
    data["params"] = {}
    assert discover_conditions(NS(data={}), data, set()) == []
    entity = sensor(data)
    assert not entity.available
    assert entity.is_on is None


def test_multiple_faults_have_descriptions_and_codes(data):
    data["status"].update(D11100="1", D11107="1")
    entity = sensor(data)
    assert entity.is_on is True
    assert entity.extra_state_attributes == {
        "active_faults": ["Unit overheat", "Temperature sensor failure"],
        "active_codes": ["D11100", "D11107"],
        "unavailable_codes": [],
    }


@pytest.mark.parametrize("value", [None, "", "unknown", "2", "-1"])
def test_invalid_flags_cannot_mean_all_clear(data, value):
    data["status"]["D11100"] = value
    entity = sensor(data)
    assert entity.is_on is None
    assert not entity.available
    assert entity.extra_state_attributes["unavailable_codes"] == ["D11100"]


def test_missing_status_and_metadata_recover(data):
    entity = sensor(data)
    status = data.pop("status")
    assert not entity.available
    data["status"] = status
    assert entity.available and entity.is_on is False
    params = data.pop("params")
    assert not entity.available
    data["params"] = params
    assert entity.available


def test_active_fault_is_not_hidden_by_another_missing_flag(data):
    data["status"]["D11100"] = "1"
    del data["status"]["D11107"]
    entity = sensor(data)
    assert entity.available and entity.is_on
    assert entity.extra_state_attributes["unavailable_codes"] == ["D11107"]


def test_disconnection_never_reports_no_problem(data):
    data["status"]["D11100"] = "1"
    entity = sensor(data)
    data["coordinator"].last_update_success = False
    assert not entity.available
    data["coordinator"].last_update_success = True
    assert entity.available and entity.is_on


@pytest.mark.parametrize("code", ["D11122", "D11183"])
def test_filter_warning_is_separate_and_still_in_warning_summary(data, code):
    data["status"][code] = "1"
    assert sensor(data, "warning").is_on
    assert sensor(data, "filter").is_on
    assert not sensor(data, "alert").is_on


def test_other_warnings_are_not_filter_maintenance(data):
    data["status"]["D11149"] = "1"
    assert sensor(data, "warning").is_on
    assert not sensor(data, "filter").is_on
    data["params"]["warning"] = ["D11149"]
    entities = discover_conditions(NS(data={}), data, set())
    assert len(entities) == 2


@pytest.mark.parametrize(
    "translation,expected",
    [
        ({"d": "not%20to%20be%20translated", "t": "Useful%20title"}, "Useful title"),
        ("Readable%20description", "Readable description"),
        (
            {"d": "not to be translated", "t": "not%20to%20be%20translated"},
            "Fault (D11100)",
        ),
        (None, "Fault (D11100)"),
        ({}, "Fault (D11100)"),
    ],
)
def test_translation_fallbacks_without_network(data, translation, expected):
    data["translations"]["params"]["D11100"] = translation
    assert condition_label(data, "D11100", "alert") == expected


def test_normal_on_off_and_repeated_polls_need_no_extra_activity(data):
    entity = sensor(data)
    update(entity)
    data["status"]["D11100"] = "1"
    update(entity)
    update(entity)
    data["status"]["D11100"] = "0"
    update(entity)
    entity.hass.bus.async_fire.assert_not_called()


def test_changed_faults_while_on_are_logged_once(data):
    data["status"]["D11100"] = "1"
    entity = sensor(data)
    update(entity)  # initial snapshot
    data["status"]["D11107"] = "1"
    update(entity)
    update(entity)
    data["status"]["D11100"] = "0"
    update(entity)
    messages = [c.args[1]["message"] for c in entity.hass.bus.async_fire.call_args_list]
    assert messages == ["Active: Temperature sensor failure", "Cleared: Unit overheat"]


def test_missing_flag_is_not_logged_as_cleared(data):
    data["status"].update(D11100="1", D11107="1")
    entity = sensor(data)
    update(entity)
    del data["status"]["D11100"]
    update(entity)
    update(entity)
    entity.hass.bus.async_fire.assert_not_called()
    data["status"]["D11100"] = "0"
    update(entity)
    assert (
        entity.hass.bus.async_fire.call_args.args[1]["message"]
        == "Cleared: Unit overheat"
    )


def test_reconnect_does_not_invent_fault_change_messages(data):
    data["status"]["D11100"] = "1"
    entity = sensor(data)
    update(entity)
    data["coordinator"].last_update_success = False
    update(entity)
    data["status"].update(D11100="0", D11107="1")
    data["coordinator"].last_update_success = True
    update(entity)
    entity.hass.bus.async_fire.assert_not_called()


def test_details_discovery_and_identity(data):
    from custom_components.atrea.conditions import discover_condition_details

    entry = NS(data={"ip_address": "192.0.2.1"})
    known = set()
    details = discover_condition_details(entry, data, known)
    assert [e.name for e in details] == ["Fault details", "Warning details"]
    assert [e.native_value for e in details] == [
        "No active faults",
        "No active warnings",
    ]
    assert discover_condition_details(entry, data, known) == []
    binary = discover_conditions(entry, data, set())
    assert len({e.unique_id for e in details + binary}) == 5
    assert details[0].device_info == binary[0].device_info
    data["params"] = {}
    assert discover_condition_details(entry, data, set()) == []


def test_details_follow_conditions_without_emitting_extra_activity(data):
    from custom_components.atrea.conditions import AtreaConditionDetailsSensor

    entity = AtreaConditionDetailsSensor(NS(data={}), data, "warning")
    entity.hass = NS(bus=NS(async_fire=Mock()))
    data["status"]["D11183"] = "1"
    assert entity.native_value == "Filter replace interval"
    data["status"]["D11149"] = "1"
    assert entity.native_value == "Heat pump defrosting; Filter replace interval"
    update(entity)
    entity.hass.bus.async_fire.assert_not_called()
    data["status"]["D11183"] = "0"
    assert entity.native_value == "Heat pump defrosting"
    data["status"]["D11149"] = "0"
    assert entity.native_value == "No active warnings"


@pytest.mark.parametrize("invalid", [None, "", "unknown", "2"])
def test_details_missing_data_and_reconnection(data, invalid):
    from custom_components.atrea.conditions import AtreaConditionDetailsSensor

    entity = AtreaConditionDetailsSensor(NS(data={}), data, "alert")
    data["status"]["D11100"] = invalid
    assert not entity.available
    assert entity.native_value is None
    data["status"]["D11107"] = "1"
    assert entity.available
    assert entity.native_value == "Temperature sensor failure"
    assert entity.extra_state_attributes["unavailable_codes"] == ["D11100"]
    data["coordinator"].last_update_success = False
    assert not entity.available
    assert entity.native_value is None
    data["coordinator"].last_update_success = True
    data["status"].update(D11100="0", D11107="0")
    assert entity.native_value == "No active faults"


def test_details_bound_state_length_preserving_full_descriptions(data):
    from custom_components.atrea.conditions import AtreaConditionDetailsSensor

    data["status"].update(D11100="1", D11107="1")
    data["translations"]["params"]["D11100"] = "A" * 255
    entity = AtreaConditionDetailsSensor(NS(data={}), data, "alert")
    assert len(entity.native_value) == 255
    assert entity.native_value.endswith("…")
    assert entity.extra_state_attributes["active_faults"] == [
        "A" * 255,
        "Temperature sensor failure",
    ]


def test_sensor_platform_discovers_details_when_metadata_arrives(data):
    import asyncio
    from custom_components.atrea.const import DOMAIN
    from custom_components.atrea.sensor import async_setup_entry

    entry = NS(data={}, entry_id="test", async_on_unload=Mock())
    data["coordinator"].async_add_listener = Mock()
    params = data.pop("params")
    add = Mock()
    asyncio.run(async_setup_entry(NS(data={DOMAIN: {"test": data}}), entry, add))
    add.assert_not_called()
    data["params"] = params
    listener = data["coordinator"].async_add_listener.call_args.args[0]
    listener()
    assert [e.name for e in add.call_args.args[0]] == ["Fault details", "Warning details"]
    listener()
    assert add.call_count == 1
