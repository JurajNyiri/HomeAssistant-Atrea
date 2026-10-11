"""Climate mode states must not have a unit; temperatures still use Celsius."""
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from homeassistant.components.climate import HVACMode
from homeassistant.const import UnitOfTemperature

from custom_components.atrea.climate import AtreaDevice


@pytest.mark.parametrize("mode", [HVACMode.OFF, HVACMode.AUTO, HVACMode.FAN_ONLY])
def test_climate_mode_has_no_unit(mode):
    entry = SimpleNamespace(entry_id="test", data={})
    hass = SimpleNamespace(data={"atrea": {"test": {
        "atrea": Mock(), "coordinator": Mock(), "userLabels": {},
    }}})
    # Isolate the presentation contract from network/device register setup.
    with patch.object(AtreaDevice, "manualUpdate"), \
         patch.object(AtreaDevice, "updatePresetList"), \
         patch.object(AtreaDevice, "updateFanList"):
        device = AtreaDevice(hass, entry, "Atrea", "", {})
    device._current_hvac_mode = mode
    assert device.state == mode
    assert device.unit_of_measurement is None
    assert device.temperature_unit == UnitOfTemperature.CELSIUS
