"""Program control must not implicitly select operating mode or fan power."""
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
import pytest
from homeassistant.exceptions import HomeAssistantError
from pyatrea import AtreaProgram
from custom_components.atrea.select import AtreaControlSelect, RD5_PROGRAM_REGISTERS, RD4_PROGRAM_REGISTERS


def control(values, registers=RD5_PROGRAM_REGISTERS):
    data = {"status": dict(zip(registers, values)), "atrea": Mock(),
            "coordinator": SimpleNamespace(last_update_success=True, config_entry=None,
                                            async_request_refresh=AsyncMock())}
    entry = SimpleNamespace(data={"ip_address": "192.0.2.1", "name": "Atrea"})
    entity = AtreaControlSelect(entry, data)
    entity.hass = SimpleNamespace(async_add_executor_job=AsyncMock(side_effect=lambda fn, *args: fn(*args)))
    return entity, data


@pytest.mark.parametrize("values,expected", [([0]*4, "Manual"), ([1]*4, "Weekly"),
    ([2, 1, 1, 1], None), ([0, 1, 0, 0], None), ([9]*4, None)])
def test_rd5_reads_all_channels_without_inventing_off(values, expected):
    entity, data = control(values)
    assert entity.current_option == expected
    assert entity.options == ["Manual", "Weekly"]
    assert entity.available


@pytest.mark.parametrize("values,expected", [([1]*3, "Manual"), ([0]*3, "Weekly"), ([2]*3, None)])
def test_rd4_uses_inverted_manual_weekly_codes(values, expected):
    entity, _ = control(values, RD4_PROGRAM_REGISTERS)
    assert entity.current_option == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("option,value,program", [("Manual", 0, AtreaProgram.MANUAL), ("Weekly", 1, AtreaProgram.WEEKLY)])
async def test_control_only_writes_program_and_waits_for_readback(option, value, program):
    entity, data = control([1-value]*4)
    async def refresh():
        data["status"] = dict.fromkeys(RD5_PROGRAM_REGISTERS, value)
    data["coordinator"].async_request_refresh.side_effect = refresh
    await entity.async_select_option(option)
    data["atrea"].setProgram.assert_called_once_with(program)
    data["atrea"].setMode.assert_not_called()
    data["atrea"].setPower.assert_not_called()
    data["atrea"].setTemperature.assert_not_called()
    assert entity.current_option == option


@pytest.mark.asyncio
async def test_already_manual_does_not_send_commands():
    entity, data = control([0]*4)
    await entity.async_select_option("Manual")
    data["atrea"].exec.assert_not_called()


@pytest.mark.asyncio
async def test_rejection_does_not_optimistically_change_state():
    entity, data = control([0]*4)
    data["atrea"].exec.return_value = False
    with pytest.raises(HomeAssistantError):
        await entity.async_select_option("Weekly")
    assert entity.current_option == "Manual"


@pytest.mark.asyncio
async def test_missing_readback_is_an_error(monkeypatch):
    monkeypatch.setattr("custom_components.atrea.select.asyncio.sleep", AsyncMock())
    entity, data = control([0]*4)
    with pytest.raises(HomeAssistantError, match="did not confirm"):
        await entity.async_select_option("Weekly")
    assert data["coordinator"].async_request_refresh.await_count == 3
    assert entity.current_option == "Manual"


@pytest.mark.asyncio
async def test_off_is_not_a_program_choice():
    entity, data = control([0]*4)
    with pytest.raises(HomeAssistantError):
        await entity.async_select_option("Off")
    data["atrea"].setProgram.assert_not_called()
