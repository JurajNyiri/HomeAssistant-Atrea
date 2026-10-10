"""Named fan choices must remain distinct from numeric percentages."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from homeassistant.exceptions import HomeAssistantError
from pyatrea import AtreaPowerMode, AtreaProgram

from custom_components.atrea.climate import AtreaDevice
from custom_components.atrea.const import POWER_MODES
from custom_components.atrea.utils import processFanModes


def test_options_accept_names_or_percentages_but_not_mixed_modes():
    assert processFanModes(" Min-Vent, Norm-Circ/Min-Vent ") == [
        "Min-Vent", "Norm-Circ/Min-Vent",
    ]
    assert processFanModes("50,20%,100") == ["20%", "50%", "100%"]
    for value in ("", "Min-Vent,20%", "typo", "11", "101"):
        assert processFanModes(value) is False


@pytest.fixture
def climate():
    device = object.__new__(AtreaDevice)
    device.atrea = Mock()
    device.atrea.getProgram.return_value = AtreaProgram.WEEKLY
    device.atrea.setPowerMode.return_value = True
    device._fan_list = list(POWER_MODES)
    device._coordinator = SimpleNamespace(async_request_refresh=AsyncMock())
    device.hass = SimpleNamespace(async_add_executor_job=AsyncMock(
        side_effect=lambda func, *args: func(*args)
    ))
    device.manualUpdate = Mock()
    return device


@pytest.mark.asyncio
@pytest.mark.parametrize("name,code", POWER_MODES.items())
async def test_discrete_command_preserves_code(climate, name, code):
    await climate.async_set_fan_mode(name)
    climate.atrea.setPowerMode.assert_called_once_with(AtreaPowerMode(code))
    climate.atrea.setPower.assert_not_called()
    climate.atrea.setProgram.assert_called_once_with(AtreaProgram.TEMPORARY)
    climate.atrea.exec.assert_called_once()


def test_33_percent_is_not_a_circulation_mode(climate):
    climate._current_fan_mode = "33%"
    assert climate.fan_mode == "Norm-Circ/Min-Vent"
    climate._fan_list = ["33%", "50%"]
    assert climate.fan_mode == "33%"


@pytest.mark.asyncio
async def test_percentages_keep_the_existing_command_path(climate):
    climate._fan_list = ["33%"]
    await climate.async_set_fan_mode("33%")
    climate.atrea.setPower.assert_called_once_with(33)
    climate.atrea.setPowerMode.assert_not_called()


@pytest.mark.asyncio
async def test_named_mode_requires_explicit_discrete_configuration(climate):
    climate._fan_list = ["33%"]
    with pytest.raises(HomeAssistantError):
        await climate.async_set_fan_mode("Min-Vent")
    climate.atrea.exec.assert_not_called()


@pytest.mark.asyncio
async def test_rejected_command_does_not_change_program(climate):
    climate.atrea.setPowerMode.return_value = False
    with pytest.raises(HomeAssistantError):
        await climate.async_set_fan_mode("Min-Vent")
    climate.atrea.setProgram.assert_not_called()
    climate.atrea.exec.assert_not_called()


@pytest.mark.asyncio
async def test_failed_command_does_not_disable_future_polling(climate):
    climate.atrea.exec.side_effect = OSError("connection lost")
    with pytest.raises(OSError):
        await climate.async_set_fan_mode("Min-Vent")
    assert climate.updatePending is False
