"""Failures must be visible and must not leave polling suspended."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
import pytest
from homeassistant.exceptions import HomeAssistantError
from custom_components.atrea.climate import AtreaDevice


@pytest.fixture
def climate():
    device = object.__new__(AtreaDevice)
    device.atrea = Mock(commands={"H10700": "00000"})
    device._coordinator = SimpleNamespace(async_request_refresh=AsyncMock())
    device.hass = SimpleNamespace(async_add_executor_job=AsyncMock(side_effect=lambda fn, *args: fn(*args)))
    device.manualUpdate = Mock()
    return device


@pytest.mark.asyncio
async def test_false_command_result_is_reported(climate):
    climate.atrea.exec.return_value = False
    with pytest.raises(HomeAssistantError):
        await climate.async_set_temperature(temperature=22)
    assert not climate.updatePending
    climate.manualUpdate.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["exec", "refresh", "readback"])
async def test_exceptions_always_release_polling_guard(climate, failure):
    if failure == "exec":
        climate.atrea.exec.side_effect = OSError("transport failure")
    elif failure == "refresh":
        climate._coordinator.async_request_refresh.side_effect = OSError("refresh failure")
    else:
        climate.manualUpdate.side_effect = OSError("readback failure")
    with pytest.raises(OSError):
        await climate._async_flush_commands()
    assert not climate.updatePending


@pytest.mark.asyncio
async def test_empty_queue_is_a_readback_not_a_failed_write(climate):
    climate.atrea.commands = {}
    await climate._async_flush_commands()
    climate.atrea.exec.assert_not_called()
    climate._coordinator.async_request_refresh.assert_awaited_once()
    climate.manualUpdate.assert_called_once()
    assert not climate.updatePending
