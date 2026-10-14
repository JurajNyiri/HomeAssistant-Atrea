"""Fresh coordinator data must reach climate and HomeKit without another poll."""
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from homeassistant.components.climate import HVACMode
from pyatrea import AtreaMode, AtreaProgram
from custom_components.atrea.climate import AtreaDevice


@pytest.fixture
def device():
    entity = object.__new__(AtreaDevice)
    entity.data = {'status': {'H10700':'0','H10705':'2','H10714':'33','H10706':'225'},
                   'model': {}}
    entity.atrea = Mock()
    entity.atrea.getParams.return_value = {'warning':[], 'alert':[]}
    entity.atrea.getValue.side_effect = lambda key: int(entity.data['status'][key])
    entity.atrea.getProgram.side_effect = lambda: AtreaProgram(int(entity.data['status']['H10700']))
    entity.atrea.getMode.side_effect = lambda: AtreaMode(int(entity.data['status']['H10705']))
    entity._coordinator = SimpleNamespace(last_update_success=True, async_add_listener=Mock())
    entity.async_on_remove = Mock()
    entity.async_write_ha_state = Mock()
    entity.async_schedule_update_ha_state = Mock()
    entity.updatePending = True  # Coordinator callbacks also arrive during command refreshes.
    return entity


@pytest.mark.asyncio
async def test_registers_listener_and_unregisters_on_removal(device):
    await device.async_added_to_hass()
    device._coordinator.async_add_listener.assert_called_once_with(device._handle_coordinator_update)
    device.async_on_remove.assert_called_once_with(device._coordinator.async_add_listener.return_value)


@pytest.mark.parametrize('program,mode,expected', [(0,2,HVACMode.FAN_ONLY),(1,1,HVACMode.AUTO),(0,0,HVACMode.OFF)])
def test_fresh_program_and_mode_publish_without_extra_poll(device, program, mode, expected):
    device.data['status'].update(H10700=str(program), H10705=str(mode))
    device._handle_coordinator_update()
    assert device.hvac_mode == expected
    assert device._current_preset == AtreaMode(mode)
    assert device._requested_temp == 22.5
    device.async_write_ha_state.assert_called_once()
    device.async_schedule_update_ha_state.assert_not_called()
    device.atrea.exec.assert_not_called()


def test_failed_refresh_does_not_publish_cached_data_as_new(device):
    device._coordinator.last_update_success = False
    device._handle_coordinator_update()
    device.async_write_ha_state.assert_not_called()
    device.atrea.getProgram.assert_not_called()
