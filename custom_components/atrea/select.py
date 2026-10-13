"""Manual/weekly program control, separate from operating mode and power."""
import asyncio
from homeassistant.components.select import SelectEntity
from homeassistant.const import CONF_IP_ADDRESS, CONF_NAME
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import slugify
from pyatrea import AtreaProgram
from .const import DOMAIN

CONTROL_OPTIONS = {"Manual": AtreaProgram.MANUAL, "Weekly": AtreaProgram.WEEKLY}
RD5_PROGRAM_REGISTERS = ("H10700", "H10701", "H10702", "H10703")
RD4_PROGRAM_REGISTERS = ("H01015", "H01016", "H01017")


def program_registers(status):
    for registers in (RD5_PROGRAM_REGISTERS, RD4_PROGRAM_REGISTERS):
        if all(register in status for register in registers):
            return registers
    return ()


async def async_setup_entry(hass, entry, async_add_entities):
    data = hass.data[DOMAIN][entry.entry_id]
    added = False

    def discover():
        nonlocal added
        if not added and program_registers(data.get("status") or {}):
            added = True
            async_add_entities([AtreaControlSelect(entry, data)])

    discover()
    entry.async_on_unload(data["coordinator"].async_add_listener(discover))


class AtreaControlSelect(CoordinatorEntity, SelectEntity):
    _attr_has_entity_name = True
    _attr_name = "Control"
    _attr_icon = "mdi:calendar-clock"
    _attr_options = list(CONTROL_OPTIONS)

    def __init__(self, entry, data):
        super().__init__(data["coordinator"])
        self._data = data
        device_id = slugify(f"atrea_{entry.data[CONF_IP_ADDRESS]}")
        self._attr_unique_id = f"{device_id}_control"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_id)},
            "name": entry.data.get(CONF_NAME) or "atrea",
        }

    @property
    def available(self):
        return super().available and bool(program_registers(self._data.get("status") or {}))

    @property
    def current_option(self):
        status = self._data.get("status") or {}
        registers = program_registers(status)
        if not registers:
            return None
        values = {str(status[register]) for register in registers}
        manual, weekly = ("0", "1") if registers == RD5_PROGRAM_REGISTERS else ("1", "0")
        if values == {manual}:
            return "Manual"
        if values == {weekly}:
            return "Weekly"
        return None

    @property
    def extra_state_attributes(self):
        status = self._data.get("status") or {}
        channels = {register: status[register] for register in program_registers(status)}
        values = {str(value) for value in channels.values()}
        state = self.current_option
        if state is None:
            state = "Temporary" if "2" in values else "Mixed" if values == {"0", "1"} else "Unknown"
        return {"program_state": state, "program_channels": channels}

    async def async_select_option(self, option):
        if option not in CONTROL_OPTIONS:
            raise HomeAssistantError("Control must be Manual or Weekly")
        if not self.available:
            raise HomeAssistantError("Atrea control is unavailable")
        if self.current_option == option:
            return
        atrea = self._data["atrea"]

        def send():
            return atrea.setProgram(CONTROL_OPTIONS[option]) and atrea.exec()

        if not await self.hass.async_add_executor_job(send):
            raise HomeAssistantError("Atrea rejected the control command or could not be reached")
        for attempt in range(3):
            await self.coordinator.async_request_refresh()
            if self.available and self.current_option == option:
                return
            if attempt < 2:
                await asyncio.sleep(1)
        raise HomeAssistantError("Atrea did not confirm the requested control setting")
