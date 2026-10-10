"""Regression tests for options changes on entries without saved presets."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from custom_components.atrea.climate import AtreaDevice
from custom_components.atrea.const import ALL_PRESET_LIST, DOMAIN
from custom_components.atrea.utils import update_listener


@pytest.mark.asyncio
async def test_missing_presets_enable_supported_modes():
    """An old entry without presets must not pass a list to updatePresetList."""
    climate = object.__new__(AtreaDevice)
    climate.data = {"supportedModes": [(0, True), (1, True), (2, False)]}
    climate.async_schedule_update_ha_state = Mock()
    climate.updateFanList = Mock()
    climate.updateName = Mock()
    entry = SimpleNamespace(entry_id="test", data={})
    hass = SimpleNamespace(data={DOMAIN: {"test": {
        "climate": climate, "update": Mock(),
    }}})

    await update_listener(hass, entry)

    assert climate.preset_modes == ALL_PRESET_LIST[:2]


@pytest.mark.asyncio
async def test_explicit_preset_choices_are_preserved():
    climate = object.__new__(AtreaDevice)
    climate.data = {"supportedModes": [(0, True), (1, True)]}
    climate.async_schedule_update_ha_state = Mock()
    climate.updateFanList = Mock()
    climate.updateName = Mock()
    entry = SimpleNamespace(entry_id="test", data={
        "presets": {"Off": False, "Automatic": True},
    })
    hass = SimpleNamespace(data={DOMAIN: {"test": {
        "climate": climate, "update": Mock(),
    }}})

    await update_listener(hass, entry)

    assert climate.preset_modes == ["Automatic"]
