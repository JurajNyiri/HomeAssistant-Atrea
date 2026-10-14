"""Regression tests for mode-service command dispatch."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from homeassistant.components.climate import HVACMode
from pyatrea import AtreaMode, AtreaProgram

from custom_components.atrea.climate import AtreaDevice


@pytest.fixture
def climate():
    device = object.__new__(AtreaDevice)
    device.atrea = Mock()
    device.atrea.getProgram.return_value = AtreaProgram.WEEKLY
    device.air_handling_control = "Schedule"
    device._current_preset = AtreaMode.VENTILATION
    device._coordinator = SimpleNamespace(async_request_refresh=AsyncMock())
    device.hass = SimpleNamespace(async_add_executor_job=AsyncMock(
        side_effect=lambda func, *args: func(*args)
    ))
    device.manualUpdate = Mock()
    device.async_turn_off = AsyncMock()
    return device


@pytest.mark.asyncio
async def test_auto_does_not_send_none_as_a_mode(climate):
    await climate.async_set_hvac_mode(HVACMode.AUTO)
    climate.atrea.setMode.assert_not_called()
    climate.atrea.exec.assert_called_once()


@pytest.mark.asyncio
async def test_fan_only_from_schedule_still_sets_ventilation(climate):
    await climate.async_set_hvac_mode(HVACMode.FAN_ONLY)
    climate.atrea.setProgram.assert_called_once_with(AtreaProgram.MANUAL)
    climate.atrea.setMode.assert_called_once_with(AtreaMode.VENTILATION)
    climate.atrea.exec.assert_called_once()


@pytest.mark.asyncio
async def test_hvac_off_stops_after_turn_off(climate):
    await climate.async_set_hvac_mode(HVACMode.OFF)
    climate.async_turn_off.assert_awaited_once()
    climate.atrea.exec.assert_not_called()
    climate.atrea.setProgram.assert_not_called()


@pytest.mark.asyncio
async def test_preset_off_does_not_switch_to_temporary_after_turn_off(climate):
    await climate.async_set_preset_mode("Off")
    climate.async_turn_off.assert_awaited_once()
    climate.atrea.setProgram.assert_not_called()
    climate.atrea.exec.assert_not_called()
