from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from pyatrea import AtreaMode, AtreaProgram

from .base_entity import AtreaEntityBase
from .const import ALL_PRESET_LIST, DOMAIN
from .utils import is_two_zone_power, power_2z_options, raw_status_int


PROGRAM_OPTIONS = {
    "Manual": AtreaProgram.MANUAL,
    "Schedule": AtreaProgram.WEEKLY,
    "Temporary": AtreaProgram.TEMPORARY,
}

PROGRAM_LABELS = {value: key for key, value in PROGRAM_OPTIONS.items()}

ZONE_OPTIONS = {
    "Zone 1": 0,
    "Zone 2": 1,
    "Zone 1+2": 2,
}

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    data = hass.data[DOMAIN][entry.entry_id]
    status = data["status"]

    entities = []
    if "H10700" in status:
        entities.append(AtreaProgramSelect(hass, entry))
    if "H10705" in status:
        entities.append(AtreaModeSelect(hass, entry))
    if "H10707" in status or "H10717" in status:
        entities.append(AtreaZoneSelect(hass, entry))
    if is_two_zone_power(status):
        entities.append(AtreaPowerProfileSelect(hass, entry))

    async_add_entities(entities)


class AtreaSelectBase(AtreaEntityBase, CoordinatorEntity, SelectEntity):
    def __init__(self, hass, entry, name, unique_suffix):
        CoordinatorEntity.__init__(self, hass.data[DOMAIN][entry.entry_id]["coordinator"])
        self.init_atrea_entity(hass, entry, name, unique_suffix)

    async def async_select_option(self, option: str) -> None:
        await self.hass.async_add_executor_job(self._select_option, option)
        await self.coordinator.async_request_refresh()
        self.async_write_ha_state()

    def _select_option(self, option):
        raise NotImplementedError


class AtreaProgramSelect(AtreaSelectBase):
    def __init__(self, hass, entry):
        super().__init__(hass, entry, "Program", "program")

    @property
    def options(self):
        return list(PROGRAM_OPTIONS)

    @property
    def current_option(self):
        program = self.atrea.getProgram()
        return PROGRAM_LABELS.get(program)

    def _select_option(self, option):
        if option not in PROGRAM_OPTIONS:
            return
        self.atrea.setProgram(PROGRAM_OPTIONS[option])
        self.atrea.exec()


class AtreaModeSelect(AtreaSelectBase):
    def __init__(self, hass, entry):
        super().__init__(hass, entry, "Ventilation mode", "mode")

    @property
    def options(self):
        modes = dict(self.data["supportedModes"])
        return [
            self._mode_label(mode)
            for mode, supported in modes.items()
            if supported or mode == AtreaMode.OFF
        ]

    @property
    def current_option(self):
        mode = self.atrea.getMode()
        return self._mode_label(mode)

    def _select_option(self, option):
        mode = self._mode_for_label(option)
        if mode is None:
            return
        if self.atrea.getProgram() == AtreaProgram.WEEKLY:
            self.atrea.setProgram(AtreaProgram.TEMPORARY)
        self.atrea.setMode(mode)
        self.atrea.exec()

    def _mode_label(self, mode):
        if mode is None:
            return None
        if int(mode) < len(ALL_PRESET_LIST):
            return ALL_PRESET_LIST[int(mode)]
        return getattr(mode, "name", str(mode))

    def _mode_for_label(self, label):
        modes = dict(self.data["supportedModes"])
        for mode, supported in modes.items():
            if (supported or mode == AtreaMode.OFF) and self._mode_label(mode) == label:
                return mode
        return None


class AtreaZoneSelect(AtreaSelectBase):
    def __init__(self, hass, entry):
        super().__init__(hass, entry, "Zone", "zone")

    @property
    def options(self):
        return list(ZONE_OPTIONS)

    @property
    def current_option(self):
        status = self.data["status"]
        zone = raw_status_int(status, "H10717")
        if zone is None:
            zone = raw_status_int(status, "H10707")
        for label, value in ZONE_OPTIONS.items():
            if value == zone:
                return label
        return None

    def _select_option(self, option):
        if option not in ZONE_OPTIONS:
            return
        self.atrea.setCommand("H10711", ZONE_OPTIONS[option])
        if raw_status_int(self.data["status"], "H10703") == 1:
            self.atrea.setCommand("H10703", 2)
        self.atrea.exec()


class AtreaPowerProfileSelect(AtreaSelectBase):
    def __init__(self, hass, entry):
        super().__init__(hass, entry, "Power profile", "power_profile")

    @property
    def options(self):
        options = list(self._available_options())
        current = self.current_option
        if current is not None and current not in options:
            options.append(current)
        return options

    @property
    def current_option(self):
        power = raw_status_int(self.data["status"], "H10714")
        for label, value in self._available_options().items():
            if value == power:
                return label
        if power is not None:
            return f"Code {power}"
        return None

    def _select_option(self, option):
        options = self._available_options()
        if option not in options:
            return
        if self.atrea.getProgram() == AtreaProgram.WEEKLY:
            self.atrea.setProgram(AtreaProgram.TEMPORARY)
        self.atrea.setCommand("H10708", options[option])
        self.atrea.exec()

    def _available_options(self):
        return power_2z_options(self.data["status"])
