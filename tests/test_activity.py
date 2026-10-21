"""Regression tests for retained D1–D4 activity; no controller writes."""

import asyncio
from datetime import date, datetime
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock, patch
from zoneinfo import ZoneInfo

import pytest
import requests
from pyatrea import AtreaMode

from custom_components.atrea.activity import (
    ActivityLog,
    fetch_log,
    parse_samples,
    input_label,
)

MODULE = "custom_components.atrea.activity"
TODAY = date(2026, 10, 21)


@pytest.fixture
def reader():
    hass = NS(
        config=NS(time_zone="Europe/Prague"),
        bus=NS(async_fire=Mock()),
        states=NS(get=Mock(return_value=None)),
        async_add_executor_job=AsyncMock(),
    )
    entry = NS(entry_id="test", data={"ip_address": "192.0.2.1"})
    with patch(f"{MODULE}.Store"):
        obj = ActivityLog(
            hass,
            entry,
            Mock(),
            {
                "supportedForcedModes": [
                    (3, AtreaMode.D1),
                    (4, AtreaMode.D2),
                    (5, AtreaMode.D3),
                    (6, AtreaMode.D4),
                ]
            },
        )
    obj.store = NS(async_save=AsyncMock(), async_load=AsyncMock(return_value=None))
    obj.observation_store = NS(
        async_save=AsyncMock(),
        async_load=AsyncMock(return_value={}),
        async_delay_save=Mock(),
    )
    obj.cursor = {"date": TODAY.isoformat(), "seconds": 35000}
    obj.data["coordinator"] = NS(
        last_update_success=True, async_add_listener=Mock(return_value=Mock())
    )
    with patch(
        f"{MODULE}.dt_util.now",
        return_value=datetime(2026, 10, 21, 10, 1, tzinfo=ZoneInfo("Europe/Prague")),
    ), patch(
        f"{MODULE}._entity_id",
        side_effect=lambda h, ip, reg: f"binary_sensor.{reg.lower()}",
    ):
        with patch(
            f"{MODULE}.er.async_get",
            return_value=NS(
                async_get=Mock(return_value=None),
                async_get_entity_id=Mock(return_value=None),
            ),
        ):
            yield obj


def events(reader):
    return [call.args[1] for call in reader.hass.bus.async_fire.call_args_list]


def test_parser_preserves_same_second_and_clock_rollback():
    assert parse_samples("0,0;3600,3;3600,0;3500,4;") == [
        (0, 0),
        (3600, 3),
        (3600, 0),
        (3500, 4),
    ]


@pytest.mark.parametrize("raw", ["broken;", "86400,3;", "-1,3;", "1,no;"])
def test_malformed_log_is_not_partially_consumed(raw):
    with pytest.raises(ValueError):
        parse_samples(raw)


@pytest.mark.asyncio
async def test_dynamic_mapping_all_inputs_and_current_event_timestamp(reader):
    reader.hass.async_add_executor_job.return_value = [
        (0, 0),
        (36000, 3),
        (36001, 4),
        (36002, 5),
        (36003, 6),
        (36004, 0),
    ]
    await reader.async_poll()
    await reader.async_poll()
    assert [e["entity_id"] for e in events(reader)] == [
        f"binary_sensor.d1020{i}" for i in range(4)
    ]
    assert "2026-10-21 10:00:00" in events(reader)[0]["message"]
    assert all(
        "time_fired" not in c.kwargs for c in reader.hass.bus.async_fire.call_args_list
    )
    assert reader.store.async_save.await_count == 1


@pytest.mark.asyncio
async def test_midnight_snapshot_and_unchanged_values_are_not_activations(reader):
    reader.cursor = {"date": "2026-10-20", "seconds": 86399}
    reader.hass.async_add_executor_job.side_effect = [
        [date(2026, 10, 20)],
        [(0, 3)],
        [(0, 3), (36000, 3), (36001, 0), (36002, 3), (36003, 0)],
    ]
    await reader.async_poll()
    assert len(events(reader)) == 1
    assert "10:00:02" in events(reader)[0]["message"]


@pytest.mark.asyncio
async def test_multiday_outage_catches_up_in_bounded_batches(reader):
    reader.cursor = {"date": "2026-10-17", "seconds": 86399}
    available = [date(2026, 10, d) for d in range(17, 22)]

    async def fetch(fn, atrea, day):
        return available if day is None else [(0, 0), (36000, 3), (36001, 0)]

    reader.hass.async_add_executor_job.side_effect = fetch
    await reader.async_poll()
    assert reader.cursor["date"] == "2026-10-19"
    await reader.async_poll()
    assert reader.cursor["date"] == "2026-10-21"
    assert len(events(reader)) == 4


@pytest.mark.asyncio
async def test_expired_days_are_skipped_using_controller_index(reader):
    reader.cursor = {"date": "2026-10-17", "seconds": 0}
    reader.hass.async_add_executor_job.side_effect = [
        [TODAY],
        [(0, 0), (36000, 3), (36001, 0)],
    ]
    await reader.async_poll()
    assert reader.cursor["date"] == TODAY.isoformat()
    assert len(events(reader)) == 1


@pytest.mark.asyncio
async def test_restart_and_same_second_appends_and_clock_rollback(reader):
    reader.hass.async_add_executor_job.return_value = [(0, 0), (36000, 3), (36001, 0)]
    await reader.async_poll()
    saved = dict(reader.cursor)
    reader.cursor = saved  # persisted cursor after restart
    reader.hass.async_add_executor_job.return_value += [
        (36002, 4),
        (36003, 0),
        (35990, 5),
        (35991, 0),
    ]
    await reader.async_poll()
    assert len(events(reader)) == 3


@pytest.mark.asyncio
async def test_old_seconds_cursor_migrates_without_duplicates(reader):
    reader.cursor = {"date": TODAY.isoformat(), "seconds": 36000}
    reader.hass.async_add_executor_job.return_value = [
        (0, 0),
        (36000, 3),
        (36001, 4),
        (36002, 0),
    ]
    await reader.async_poll()
    assert len(events(reader)) == 1
    assert reader.cursor["position"] == 4


@pytest.mark.asyncio
async def test_missing_entity_retried_without_replaying_earlier_events(reader):
    reader.hass.async_add_executor_job.return_value = [
        (0, 0),
        (36000, 3),
        (36001, 4),
        (36002, 0),
    ]
    with patch(f"{MODULE}._entity_id", side_effect=["binary_sensor.d1", None]):
        await reader.async_poll()
    assert reader.cursor["position"] == 2
    await reader.async_poll()
    assert len(events(reader)) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [requests.Timeout(), ValueError("unsupported")])
async def test_failure_keeps_cursor_and_retries(reader, error):
    reader.cursor = {"date": TODAY.isoformat(), "seconds": 35000}
    before = dict(reader.cursor)
    reader.hass.async_add_executor_job.side_effect = error
    await reader.async_poll()
    assert reader.cursor == before
    assert not events(reader)
    reader.hass.async_add_executor_job.side_effect = None
    reader.hass.async_add_executor_job.return_value = [(0, 0), (36000, 3), (36001, 0)]
    await reader.async_poll()
    assert len(events(reader)) == 1


@pytest.mark.asyncio
async def test_truncated_log_not_replayed(reader):
    reader.cursor = {"date": TODAY.isoformat(), "position": 2, "sample": [36000, 3]}
    reader.hass.async_add_executor_job.return_value = [(0, 0)]
    await reader.async_poll()
    assert reader.cursor["position"] == 2
    assert not events(reader)


@pytest.mark.asyncio
async def test_stop_cancels_inflight_poll_and_prevents_rescheduling(reader):
    started = asyncio.Event()

    async def fetch(*args):
        started.set()
        await asyncio.Event().wait()

    reader.hass.async_add_executor_job.side_effect = fetch
    reader.hass.async_create_task = asyncio.create_task
    reader._unsub = Mock()
    unsub = reader._unsub
    reader._schedule()
    await started.wait()
    task = reader._task
    reader._schedule()
    assert reader._task is task
    await reader.async_stop()
    reader._schedule()
    assert task.cancelled()
    unsub.assert_called_once()
    assert not events(reader)
    reader.store.async_save.assert_not_awaited()


def test_fetch_uses_read_endpoint_and_parses_available_dates():
    atrea = Mock()
    atrea.getURL.side_effect = lambda path: f"http://example.invalid/{path}"
    response = Mock(text="20261020\n20261021\n")
    response.json.return_value = {"H10712": "0,0;36000,3;"}
    with patch(f"{MODULE}.requests.get", return_value=response) as get:
        assert fetch_log(atrea, None) == [date(2026, 10, 20), TODAY]
        assert fetch_log(atrea, TODAY) == [(0, 0), (36000, 3)]
        assert all("config/log.cgi?type=" in c.args[0] for c in get.call_args_list)
        assert all(c.kwargs["timeout"] == 15 for c in get.call_args_list)


@pytest.mark.parametrize("payload", [{}, [], {"H10712": None}])
def test_unsupported_response_does_not_become_empty_success(payload):
    response = Mock()
    response.json.return_value = payload
    with patch(f"{MODULE}.requests.get", return_value=response), pytest.raises(
        ValueError
    ):
        fetch_log(Mock(), TODAY)


@pytest.mark.asyncio
async def test_real_home_assistant_bus_uses_discovery_time(reader, tmp_path):
    from homeassistant.core import HomeAssistant, callback
    from homeassistant.const import EVENT_LOGBOOK_ENTRY
    from homeassistant.util import dt as dt_util

    hass = HomeAssistant(str(tmp_path))
    received = []

    @callback
    def receive(event):
        received.append(event)

    unsub = hass.bus.async_listen(EVENT_LOGBOOK_ENTRY, receive)
    reader.hass.bus = hass.bus
    reader.hass.async_add_executor_job.return_value = [(0, 0), (36000, 3), (36001, 0)]
    before = dt_util.utcnow().timestamp()
    await reader.async_poll()
    await hass.async_block_till_done()
    unsub()
    assert len(received) == 1
    assert received[0].time_fired_timestamp >= before
    assert "10:00:00" in received[0].data["message"]


@pytest.mark.asyncio
async def test_start_loads_persisted_cursor_before_polling(reader):
    saved = {"date": TODAY.isoformat(), "position": 3, "sample": [36001, 0]}
    reader.store.async_load.return_value = saved
    reader.hass.async_create_task = asyncio.create_task
    reader.hass.async_add_executor_job.return_value = [(0, 0), (36000, 3), (36001, 0)]
    with patch(f"{MODULE}.async_track_time_interval", return_value=Mock()):
        await reader.async_start()
        await reader._task
        await reader.async_stop()
    assert reader.cursor == saved
    assert not events(reader)


def observe(reader, seconds, raw):
    reader.data["status"] = {"H10712": str(raw)}
    reader.data["status_observed_at"] = f"2026-10-21T10:00:{seconds:02d}"
    registered = NS(disabled_by=None, name=None)
    registry = NS(
        async_get_entity_id=Mock(return_value="sensor.forced"),
        async_get=Mock(return_value=registered),
    )
    with patch(f"{MODULE}.er.async_get", return_value=registry):
        reader._observe_status()


@pytest.mark.asyncio
@pytest.mark.parametrize("raw", [3, 4, 5, 6])
async def test_normal_polling_covers_any_input_without_history_duplicate(reader, raw):
    observe(reader, 0, 0)
    observe(reader, 10, raw)
    observe(reader, 20, raw)
    observe(reader, 30, 0)
    reader.hass.async_add_executor_job.return_value = [(0, 0), (36005, raw), (36025, 0)]
    await reader.async_poll()
    assert not events(reader)
    assert reader.cursor["position"] == 3


@pytest.mark.asyncio
async def test_history_first_waits_for_normal_poll_then_suppresses(reader):
    reader.hass.async_add_executor_job.return_value = [(0, 0), (36005, 3)]
    await reader.async_poll()
    assert not events(reader)
    assert reader.cursor["position"] == 1
    observe(reader, 10, 3)
    await reader.async_poll()
    assert not events(reader)
    assert reader.cursor["position"] == 2


@pytest.mark.asyncio
async def test_whole_episode_between_samples_is_recovered_once(reader):
    observe(reader, 0, 0)
    observe(reader, 10, 0)
    reader.hass.async_add_executor_job.return_value = [(0, 0), (36003, 4), (36007, 0)]
    await reader.async_poll()
    await reader.async_poll()
    assert len(events(reader)) == 1
    assert "Recovered" in events(reader)[0]["message"]
    assert "10:00:03" in events(reader)[0]["message"]


@pytest.mark.asyncio
async def test_hidden_off_on_same_source_is_not_suppressed_by_unchanged_samples(reader):
    observe(reader, 2, 3)
    observe(
        reader, 10, 3
    )  # HA saw no change, so this is NOT another logged transition.
    reader.hass.async_add_executor_job.return_value = [
        (0, 0),
        (36001, 3),
        (36004, 0),
        (36006, 3),
        (36015, 0),
    ]
    await reader.async_poll()
    assert len(events(reader)) == 1
    assert "10:00:06" in events(reader)[0]["message"]


@pytest.mark.asyncio
async def test_d1_after_d4_release_is_not_a_new_press_or_duplicate(reader):
    observe(reader, 2, 6)
    observe(reader, 20, 3)
    reader.hass.async_add_executor_job.return_value = [
        (0, 0),
        (36001, 6),
        (36015, 3),
        (36030, 0),
    ]
    await reader.async_poll()
    assert not events(reader)


@pytest.mark.asyncio
async def test_midnight_episode_is_not_recovered_while_still_active(reader):
    reader.cursor = {"date": "2026-10-20", "seconds": 86000}
    prior = [(0, 0), (86390, 3)]
    current = [(0, 3)]

    async def fetch(fn, unit, day):
        if day is None:
            return [date(2026, 10, 20), TODAY]
        return prior if day < TODAY else current

    reader.hass.async_add_executor_job.side_effect = fetch
    await reader.async_poll()
    assert not events(reader)
    current.append((36000, 0))
    await reader.async_poll()
    assert len(events(reader)) == 1
    assert "2026-10-20 23:59:50" in events(reader)[0]["message"]


@pytest.mark.asyncio
async def test_restart_preserves_previously_observed_transition(reader):
    observe(reader, 10, 3)
    persisted = reader._observation_data()
    reader.observations = []
    reader._last_source = None
    reader.observation_store.async_load.return_value = persisted
    reader.store.async_load.return_value = reader.cursor
    reader.hass.async_create_task = asyncio.create_task
    reader.hass.async_add_executor_job.return_value = [(0, 0), (36005, 3), (36025, 0)]
    with patch(
        f"{MODULE}.async_track_time_interval", return_value=Mock()
    ), patch.object(reader, "_observe_status"):
        await reader.async_start()
        await reader._task
        await reader.async_stop()
    assert not events(reader)


@pytest.mark.asyncio
async def test_fresh_install_does_not_replay_existing_activity(reader):
    reader.cursor = {}
    reader.hass.async_add_executor_job.return_value = [(0, 0), (36005, 3), (36025, 0)]
    await reader.async_poll()
    assert not events(reader)
    assert reader.cursor["position"] == 3


@pytest.mark.asyncio
async def test_recent_closed_episode_waits_for_inflight_status_update(reader):
    reader.hass.async_add_executor_job.return_value = [(0, 0), (36045, 3), (36055, 0)]
    await reader.async_poll()  # fixed now is 10:01:00
    assert not events(reader)
    observe(reader, 50, 3)
    await reader.async_poll()
    assert not events(reader)


@pytest.mark.parametrize(
    "override,unit_label,expected",
    [
        ("Office", "Kitchen", "Office"),
        (None, "Kitchen", "Kitchen (D1)"),
        (None, None, "D1 input"),
        (None, "D1", "D1 input"),
    ],
)
def test_names_are_configurable_and_not_tied_to_input_numbers(
    reader, override, unit_label, expected
):
    reader.data["userLabels"] = {"D1": unit_label}
    registry = NS(async_get=Mock(return_value=NS(name=override)))
    with patch(f"{MODULE}.er.async_get", return_value=registry):
        assert (
            input_label(
                reader.hass, reader.entry, reader.data, "D1", "binary_sensor.input"
            )
            == expected
        )


def test_failed_poll_does_not_count_as_observed(reader):
    reader.data["coordinator"].last_update_success = False
    observe(reader, 10, 3)
    assert not reader.observations


def test_upstream_source_sensor_uses_device_mapping_and_personalized_name(reader):
    from custom_components.atrea.sensor import AtreaRegisterSensor, SENSOR_REGISTERS
    from custom_components.atrea.const import ALL_PRESET_LIST

    reader.data["coordinator"].config_entry = None
    sensor = AtreaRegisterSensor(
        reader.entry, reader.data, "H10712", SENSOR_REGISTERS["H10712"]
    )
    sensor.hass = reader.hass
    reader.data["status"] = {"H10712": "6"}
    reader.data["userLabels"] = {"D4": "Office"}
    assert sensor.native_value == "Office (D4)"
    reader.data["status"]["H10712"] = "0"
    assert sensor.native_value == ALL_PRESET_LIST[0]


def test_identical_room_names_keep_source_inputs_distinguishable(reader):
    from custom_components.atrea.sensor import AtreaRegisterSensor, SENSOR_REGISTERS

    reader.data["coordinator"].config_entry = None
    sensor = AtreaRegisterSensor(
        reader.entry, reader.data, "H10712", SENSOR_REGISTERS["H10712"]
    )
    sensor.hass = reader.hass
    registry = NS(
        async_get_entity_id=Mock(return_value="binary_sensor.renamed"),
        async_get=Mock(return_value=NS(name="Office")),
    )
    with patch(f"{MODULE}.er.async_get", return_value=registry):
        reader.data["status"] = {"H10712": "3"}
        assert sensor.native_value == "Office (D1)"
        reader.data["status"] = {"H10712": "6"}
        assert sensor.native_value == "Office (D4)"


@pytest.mark.asyncio
async def test_controller_log_timestamp_trails_live_observation(reader):
    observe(reader, 13, 6)
    reader.hass.async_add_executor_job.return_value = [(0, 0), (36019, 6)]
    await reader.async_poll()
    assert not events(reader)
    assert reader.cursor["position"] == 2
    assert not reader.observations


@pytest.mark.asyncio
async def test_one_observation_cannot_suppress_two_nearby_episodes(reader):
    observe(reader, 20, 6)
    reader.hass.async_add_executor_job.return_value = [
        (0, 0),
        (36019, 6),
        (36021, 0),
        (36023, 6),
        (36025, 0),
    ]
    await reader.async_poll()
    assert len(events(reader)) == 1
    assert "10:00:23" in events(reader)[0]["message"]
