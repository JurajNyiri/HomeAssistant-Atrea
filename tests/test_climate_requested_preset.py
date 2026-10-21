"""Climate preset reflects requested, rather than forced effective, mode."""

from unittest.mock import Mock

import pytest
from pyatrea import AtreaMode, AtreaProgram

from custom_components.atrea.climate import AtreaDevice


def make_climate(status):
    """Build an Atrea climate entity around a captured status response."""
    climate = object.__new__(AtreaDevice)
    climate.data = {"status": status, "model": {}}
    climate.atrea = Mock()
    climate.atrea.getID.return_value = "test"
    climate.atrea.getVersion.return_value = "test"
    climate.atrea.getMode.side_effect = lambda: AtreaMode(int(status.get("H10705", 0)))
    climate.atrea.getForcedMode.return_value = AtreaMode.D1
    climate.atrea.getProgram.return_value = AtreaProgram.WEEKLY
    climate.atrea.getValue.side_effect = lambda key: int(status[key])
    climate.atrea.getParams.return_value = {"warning": [], "alert": []}
    climate._userLabels = {}
    climate._outside_temp = 0
    climate._inside_temp = 0
    climate._supply_air_temp = 0
    climate._exhaust_temp = 0
    climate._extract_temp = 0
    climate._requested_temp = 0
    climate._requested_power = None
    climate._active_inputs = []
    climate._forced_mode = None
    climate._current_power = None
    climate._in1 = None
    climate._in2 = None
    climate._sa1 = None
    climate._current_preset = None
    climate._requested_preset = None
    climate._current_hvac_mode = None
    climate._heating = -1
    climate._cooling = -1
    climate._warnings = []
    climate._alerts = []
    climate.async_schedule_update_ha_state = Mock()
    return climate


@pytest.mark.parametrize("effective", [0, 1, 3, 4])
def test_preset_stays_requested_automatic_during_effective_override(effective):
    climate = make_climate({
        "H10700": "1", "H10705": str(effective), "H10715": "1", "H10714": "50",
    })

    climate.manualUpdate(False)

    assert climate.preset_mode == "Automatic"
    assert climate._current_preset == AtreaMode(effective)


def test_preset_follows_requested_mode_when_it_changes():
    status = {"H10700": "1", "H10705": "3", "H10715": "1", "H10714": "50"}
    climate = make_climate(status)
    climate.manualUpdate(False)
    assert climate.preset_mode == "Automatic"

    status["H10715"] = "4"
    climate.manualUpdate(False)
    assert climate.preset_mode == "Circulation"


@pytest.mark.parametrize("invalid", ["invalid", "65535", "-1"])
def test_invalid_requested_mode_does_not_fall_back_to_effective(invalid):
    climate = make_climate({
        "H10700": "1", "H10705": "3", "H10715": invalid, "H10714": "50",
    })

    climate.manualUpdate(False)

    assert climate.preset_mode is None


def test_legacy_unit_without_requested_mode_uses_effective_mode():
    climate = make_climate({"H10700": "1", "H10705": "2", "H10714": "50"})

    climate.manualUpdate(False)

    assert climate.preset_mode == "Ventilation"
