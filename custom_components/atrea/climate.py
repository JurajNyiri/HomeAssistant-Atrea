import time
import re
import json
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.util import slugify
from homeassistant.components.climate.const import HVACAction


from custom_components.atrea.utils import processFanModes

try:
    from homeassistant.components.climate import ClimateEntity, PLATFORM_SCHEMA
except ImportError:
    from homeassistant.components.climate import (
        ClimateDevice as ClimateEntity,
        PLATFORM_SCHEMA,
    )
from homeassistant.components.climate.const import (
    HVAC_MODE_OFF,
    HVAC_MODE_AUTO,
    HVAC_MODE_FAN_ONLY,
    SWING_VERTICAL, 
    SWING_HORIZONTAL, 
    SWING_BOTH,
)
from homeassistant.const import (
    CONF_NAME,
    CONF_IP_ADDRESS,
    TEMP_CELSIUS,
    ATTR_TEMPERATURE,
)
from homeassistant.util import Throttle
from homeassistant.helpers import device_registry as dr
from typing import Callable
from pyatrea import AtreaProgram, AtreaMode

from .const import (
    DOMAIN,
    LOGGER,
    UPDATE_DELAY,
    MIN_TIME_BETWEEN_SCANS,
    SUPPORT_FLAGS,
    STATE_UNKNOWN,
    CONF_FAN_MODES,
    CONF_PRESETS,
    DEFAULT_FAN_MODE_LIST,
    ALL_PRESET_LIST,
    ICONS,
    HVAC_MODES,
    SWING_MODES,
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: Callable
):
    sensor_name = entry.data.get(CONF_NAME)
    if sensor_name is None:
        sensor_name = "atrea"

    fan_list = entry.data.get(CONF_FAN_MODES)
    if fan_list is None:
        fan_list = DEFAULT_FAN_MODE_LIST

    # todo: verify this works with options
    preset_list = entry.data.get(CONF_PRESETS)
    if preset_list is None:
        preset_list = {}
        for preset in ALL_PRESET_LIST:
            preset_list[preset] = True

    hass.data[DOMAIN][entry.entry_id]["climate"] = AtreaDevice(
        hass, entry, sensor_name, fan_list, preset_list
    )

    async_add_entities([hass.data[DOMAIN][entry.entry_id]["climate"]])


class AtreaDevice(ClimateEntity):
    def __init__(
        self, hass, entry, sensor_name, fan_list, preset_list,
    ):
        super().__init__()
        self.data = hass.data[DOMAIN][entry.entry_id]
        self.atrea = self.data["atrea"]
        self._coordinator = self.data["coordinator"]
        self._userLabels = self.data["userLabels"]
        self.ip = entry.data.get(CONF_IP_ADDRESS)
        self.updatePending = False
        self._preset_list = []
        self._warnings = []
        self._name = sensor_name
        self._current_fan_mode = None
        self._alerts = []
        self._outside_temp = 0.0
        self._inside_temp = 0.0
        self._supply_air_temp = 0.0
        self._requested_temp = 0.0
        self._requested_power = None
        self._co2 = 0.0
        self._vent_air_temp = 0.0
        self._filter_change = 0
        self._defrost = 0
        self._sup_req = 0
        self._sup_act_flow = 0
        self._sup_fan_voltage = 0.0
        self._eta_req = 0
        self._eta_act_flow = 0
        self._eta_fan_voltage = 0.0
        self._oda_req = 0
        self._oda_act_flow = 0
        self._sc_voltage = 0.0
        self._all_values = ""

        self._current_preset = None
        self._current_hvac_mode = None
        self._unit = "Status"
        self.air_handling_control = None
        self._enabled = False
        self._cooling = -1
        self._heating = -1
        self._zone = -1

        self.updatePresetList(preset_list, False)
        self.updateFanList(fan_list, False)
        self.manualUpdate(False)

    def updatePresetList(self, preset_list, updateState=True):
        self._preset_list = []
        for required_preset in preset_list:
            if preset_list[required_preset]:
                for i, preset_supported in self.data["supportedModes"]:
                    if preset_supported and ALL_PRESET_LIST[i] == required_preset:
                        self._preset_list.append(ALL_PRESET_LIST[i])
        if updateState:
            self.async_schedule_update_ha_state(True)

    def updateFanList(self, fan_list, updateState=True):
        self._fan_list = processFanModes(fan_list)
        if updateState:
            self.async_schedule_update_ha_state(True)

    def updateName(self, name, updateState=True):
        self._name = name
        if updateState:
            self.async_schedule_update_ha_state(True)

    async def async_added_to_hass(self) -> None:
        self._enabled = True

    async def async_will_remove_from_hass(self) -> None:
        self._enabled = False

    def getUniqueID(self):
        return slugify(f"atrea_{self.ip}")

    @property
    def brand(self):
        return "ATREA s.r.o."

    @property
    def model(self):
        if self._model:
            return self._model["category"] + " " + self._model["model"]
        return False

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.getUniqueID())},
            "name": self.name,
            "manufacturer": self.brand,
            "model": self.model,
            "sw_version": self._swVersion,
            "hw_version": self._id,
            "connections": {},
        }

    @property
    def should_poll(self):
        return True

    @property
    def unit_of_measurement(self):
        return self._unit

    @property
    def icon(self):
        if len(self._alerts) > 0:
            return "mdi:fan-alert"
        elif self.fan_mode == "0%":
            return "mdi:fan-off"
        elif self._current_preset in ICONS:
            return ICONS[self._current_preset]
        else:
            return "mdi:fan"

    @property
    def state(self):
        return self._current_hvac_mode

    @property
    def supported_features(self):
        return SUPPORT_FLAGS

    @property
    def unique_id(self) -> str:
        return self.getUniqueID()

    @property
    def name(self):
        return "{}".format(self._name)

    @property
    def extra_state_attributes(self):
        attributes = {}

        attributes["outside_temp"] = self._outside_temp
        attributes["inside_temp"] = self._inside_temp
        attributes["supply_air_temp"] = self._supply_air_temp
        attributes["requested_temp"] = self._requested_temp
        attributes["requested_power"] = self._requested_power
        attributes["warnings"] = self._warnings
        attributes["alerts"] = self._alerts
        attributes["program"] = self.air_handling_control
<<<<<<< HEAD
        attributes['zone'] = self._zone
=======
        attributes['co2'] = self._co2
        attributes['vent_air_temp'] = self._vent_air_temp
        attributes['filter_change'] = self._filter_change
        attributes['defrost'] = self._defrost
        attributes['supply_required'] = self._sup_req
        attributes['supply_actual_flow'] = self._sup_act_flow
        attributes['supply_fan_voltage'] = self._sup_fan_voltage
        attributes['eta_required'] = self._eta_req
        attributes['eta_actual_flow'] = self._eta_act_flow
        attributes['eta_fan_voltage'] = self._eta_fan_voltage
        attributes['oda_required'] = self._oda_req
        attributes['oda_actual_flow'] = self._oda_act_flow
        attributes['sc_voltage'] = self._sc_voltage
        attributes['all_values'] = self._all_values
>>>>>>> additional_attributes

        return attributes

    @property
    def temperature_unit(self):
        return TEMP_CELSIUS

    @property
    def target_temperature(self):
        return float(self._requested_temp)

    @property
    def hvac_modes(self):
        return HVAC_MODES

    @property
    def hvac_mode(self):
        return self._current_hvac_mode

    @property
    def preset_mode(self):
        if self._current_preset.name and self._current_preset.name in self._userLabels:
            return self._userLabels[self._current_preset.name]
        elif self._current_preset < len(ALL_PRESET_LIST):
            return ALL_PRESET_LIST[self._current_preset]
        else:
            return STATE_UNKNOWN

    @property
    def preset_modes(self):
        return self._preset_list

    @property
    def current_temperature(self):
        return float(self._inside_temp)

    @property
    def min_temp(self):
        return 10

    @property
    def max_temp(self):
        return 40

    @property
    def fan_mode(self):
        return self._current_fan_mode

    @property
    def fan_modes(self):
        return self._fan_list

    @property
    def program(self):
        return self.air_handling_control

    @property
    def hvac_action(self):
        if (self._heating == 1):
            return HVACAction.HEATING
        elif (self._cooling == 1):
            return HVACAction.COOLING
        elif (self._current_hvac_mode == HVAC_MODE_OFF):
            return HVACAction.OFF
        else:
            return HVACAction.IDLE

    @property
    def swing_modes(self):
        return SWING_MODES

    @property
    def swing_mode(self):
        if (self._zone == 0):
            return SWING_VERTICAL;
        if (self._zone == 1):
            return SWING_HORIZONTAL;
        if (self._zone == 2):
            return SWING_BOTH;
        return None

    @Throttle(MIN_TIME_BETWEEN_SCANS)
    async def async_update(self):
        if not self.updatePending:
            self.updatePending = True
            await self._coordinator.async_request_refresh()
            await self.hass.async_add_executor_job(time.sleep, UPDATE_DELAY / 1000)
            self.manualUpdate()
            self.updatePending = False

    def manualUpdate(self, updateState=True):
        status = self.data["status"]
        self._id = self.atrea.getID()
        self._model = self.data["model"]
        self._swVersion = self.atrea.getVersion()
        self._warnings = []
        self._alerts = []
        if status != False:
<<<<<<< HEAD
            if "I10211" in status:
=======

            self._all_values = json.dumps(status)

            if "I10202" in status:
>>>>>>> additional_attributes
                if float(status["I10211"]) > 1300:
                    self._outside_temp = round(
                        ((50 - (float(status["I10211"]) - 65036) / 10) * -1), 1
                    )
                else:
                    self._outside_temp = float(status["I10211"]) / 10
            elif "I00202" in status:
                if self.atrea.getValue("I00202") == 126.0:
                    if self.atrea.getValue("H00511") == 1:
                        self._outside_temp = self.atrea.getValue("I00200")
                    elif self.atrea.getValue("H00511") == 1:
                        self._outside_temp = self.atrea.getValue("I00201")
                else:
                    self._outside_temp = self.atrea.getValue("I00202")

            # Depending on configuration of ventilation unit, indoor temp is read from different addresses
            if "H10514" in status:
                if int(status["H10514"]) == 1:
                    self._inside_temp = float(status["I10203"]) / 10
                elif int(status["H10514"]) == 0:
                    self._inside_temp = float(status["I10207"]) / 10
                else:
                    LOGGER.warn(
                        "Indoor sensor not supported yet. Please contact repository owner with information about your unit."
                    )
            elif "I00210" in status:
                self._inside_temp = self.atrea.getValue("I00210")

            if "I10200" in status:
                self._supply_air_temp = float(status["I10200"]) / 10
            elif "I00200" in status:
                self._supply_air_temp = self.atrea.getValue("I00200")

            if "H10706" in status:
                self._requested_temp = float(status["H10706"]) / 10
            elif "H01006" in status:
                self._requested_temp = self.atrea.getValue("H01006")

            if "H10714" in status:
                self._requested_power = int(status["H10714"])
            elif "H01005" in status:
                self._requested_power = int(self.atrea.getValue("H01005"))

            if "H01001" in status:
                self._current_fan_mode = str(int(self.atrea.getValue("H01001"))) + "%"
            else:
                self._current_fan_mode = str(self._requested_power) + "%"

            if("C10215" in status):
                self._heating = int(status["C10215"])
            else:
                self._heating = -1

            if("C10216" in status):
                self._cooling = int(status["C10216"])
            else:
                self._cooling = -1

            if("H10711" in status):
                self._zone = int(status["H10711"])
            else:
                self._zone = -1

            self._current_preset = self.atrea.getMode()
            if self._current_preset == AtreaMode.OFF:
                self._current_hvac_mode = HVAC_MODE_OFF

            if('I10205' in status):
                # Converting IN1 value to ppm 
                self._co2 = round(float(status['I10205'])*0.2, 0)
            else:
                self._co2 = -1

            if('I10214' in status):
                self._vent_air_temp = float(status['I10214'])/10

            if('D11183' in status):
                self._filter_change = int(status['D11183'])
            else:
                self._filter_change = -1

            if('D10207' in status):
                self._defrost = int(status['D10207'])
            else:
                self._defrost = -1

            if('I11600' in status):
                self._sup_req = int(status['I11600'])
            else:
                self._sup_req = -1

            if('I11602' in status):
                self._sup_act_flow = int(status['I11602'])
            else:
                self._sup_act_flow = -1

            if('H10200' in status):
                self._sup_fan_voltage = float(status['H10200'])/1000
            else:
                self._sup_fan_voltage = -1.0

            if('I11601' in status):
                self._eta_req = int(status['I11601'])
            else:
                self._eta_req = -1

            if('I11603' in status):
                self._eta_act_flow = int(status['I11603'])
            else:
                self._eta_act_flow = -1

            if('H10201' in status):
                self._eta_fan_voltage = float(status['H10201'])/1000
            else:
                self._eta_fan_voltage = -1.0

            if('I11604' in status):
                self._oda_req = int(status['I11604'])
            else:
                self._oda_req = -1

            if('I11605' in status):
                self._oda_act_flow = int(status['I11605'])
            else:
                self._oda_act_flow = -1

            if('H10204' in status):
                self._sc_voltage = float(status['H10204'])/1000
            else:
                self._sc_voltage = -1.0

            program = self.atrea.getProgram()
            if program == AtreaProgram.MANUAL:
                self.air_handling_control = "Manual"
                if self.atrea.getValue("H10705") == 0:
                    self._current_hvac_mode = HVAC_MODE_OFF
                else:
                    self._current_hvac_mode = HVAC_MODE_FAN_ONLY
            elif program == AtreaProgram.WEEKLY:
                self.air_handling_control = "Schedule"
                self._current_hvac_mode = HVAC_MODE_AUTO
            elif program == AtreaProgram.TEMPORARY:
                self.air_handling_control = "Temporary"
                if self.atrea.getValue("H10705") == 0:
                    self._current_hvac_mode = HVAC_MODE_OFF
                else:
                    self._current_hvac_mode = HVAC_MODE_FAN_ONLY
            else:
                self.air_handling_control = "Unknown (" + str(program) + ")"

            if self._current_fan_mode == "0%":
                self._current_hvac_mode = HVAC_MODE_OFF

            # todo fix warning not translated
            params = self.atrea.getParams()
            for warning in params["warning"]:
                if status[warning] == "1":
                    self._warnings.append(self.atrea.getTranslation(warning))

            for alert in params["alert"]:
                if status[alert] == "1":
                    self._alerts.append(self.atrea.getTranslation(alert))

        else:
            self._current_hvac_mode = None
        if updateState:
            self.async_schedule_update_ha_state(True)

    async def async_set_fan_mode(self, fan_mode):
        fan_percent = int(re.sub("[^0-9]", "", fan_mode))
        if fan_percent < 12:
            fan_percent = 12
        if fan_percent > 100:
            fan_percent = 100
        if fan_percent >= 12 and fan_percent <= 100:
            if (
                await self.hass.async_add_executor_job(self.atrea.getProgram)
                == AtreaProgram.WEEKLY
            ):
                self.atrea.setProgram(AtreaProgram.TEMPORARY)
            self.atrea.setPower(fan_percent)

            self.updatePending = True
            await self.hass.async_add_executor_job(self.atrea.exec)
            await self._coordinator.async_request_refresh()
            await self.hass.async_add_executor_job(time.sleep, UPDATE_DELAY / 1000)
            self.updatePending = False
            self.manualUpdate()
        else:
            LOGGER.warn("Power out of range (12,100)")

    async def async_turn_on(self):
        if self.air_handling_control == "Manual":
            self.atrea.setProgram(AtreaProgram.MANUAL)
            self._current_hvac_mode = HVAC_MODE_FAN_ONLY
        elif self.air_handling_control == "Schedule":
            self.atrea.setProgram(AtreaProgram.WEEKLY)
            self._current_hvac_mode = HVAC_MODE_AUTO
        elif self.air_handling_control == "Temporary":
            self.atrea.setProgram(AtreaProgram.TEMPORARY)
            self._current_hvac_mode = HVAC_MODE_FAN_ONLY
        self.atrea.setMode(AtreaMode.VENTILATION)

        self.updatePending = True
        await self.hass.async_add_executor_job(self.atrea.exec)
        await self._coordinator.async_request_refresh()
        await self.hass.async_add_executor_job(time.sleep, UPDATE_DELAY / 1000)
        self.manualUpdate()
        self.updatePending = False

    async def async_turn_off(self):
        if self.air_handling_control == "Manual":
            self.atrea.setProgram(AtreaProgram.MANUAL)
        elif self.air_handling_control == "Temporary":
            self.atrea.setProgram(AtreaProgram.TEMPORARY)
        else:
            self.atrea.setProgram(AtreaProgram.WEEKLY)

        self._current_hvac_mode = HVAC_MODE_OFF
        self.atrea.setMode(AtreaMode.OFF)

        self.updatePending = True
        await self.hass.async_add_executor_job(self.atrea.exec)
        await self._coordinator.async_request_refresh()
        await self.hass.async_add_executor_job(time.sleep, UPDATE_DELAY / 1000)
        self.manualUpdate()
        self.updatePending = False

    async def async_set_hvac_mode(self, hvac_mode):
        mode = None
        program = None
        if hvac_mode == HVAC_MODE_AUTO:
            self._current_hvac_mode = HVAC_MODE_AUTO
            program = AtreaProgram.WEEKLY
        elif hvac_mode == HVAC_MODE_FAN_ONLY:
            mode = AtreaMode.VENTILATION
            program = AtreaProgram.MANUAL
            self._current_hvac_mode = HVAC_MODE_FAN_ONLY
        elif hvac_mode == HVAC_MODE_OFF:
            await self.async_turn_off()
            self._current_hvac_mode = HVAC_MODE_OFF

        if program != None and program != await self.hass.async_add_executor_job(
            self.atrea.getProgram
        ):
            self.atrea.setProgram(program)

        if (
            mode != None and self._current_preset != mode
        ) or self.air_handling_control == "Schedule":
            self.atrea.setMode(mode)

        self.updatePending = True
        await self.hass.async_add_executor_job(self.atrea.exec)
        await self._coordinator.async_request_refresh()
        await self.hass.async_add_executor_job(time.sleep, UPDATE_DELAY / 1000)
        self.manualUpdate()
        self.updatePending = False

    async def async_set_preset_mode(self, preset_mode):
        mode = None
        try:
            mode = AtreaMode(ALL_PRESET_LIST.index(preset_mode))
        except ValueError:
            LOGGER.warn("Chosen preset=%s is incorrect preset.", str(preset_mode))
            return

        if mode == AtreaMode.OFF:
            await self.async_turn_off()
        if (
            await self.hass.async_add_executor_job(self.atrea.getProgram)
            == AtreaProgram.WEEKLY
        ):
            self.atrea.setProgram(AtreaProgram.TEMPORARY)
        if mode != await self.hass.async_add_executor_job(self.atrea.getMode):
            self.atrea.setMode(mode)

        self.updatePending = True
        await self.hass.async_add_executor_job(self.atrea.exec)
        await self._coordinator.async_request_refresh()
        await self.hass.async_add_executor_job(time.sleep, UPDATE_DELAY / 1000)
        self.manualUpdate()
        self.updatePending = False

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        elif temperature >= 10 and temperature <= 40:
            self.atrea.setTemperature(temperature)
            self.updatePending = True
            await self.hass.async_add_executor_job(self.atrea.exec)
            await self._coordinator.async_request_refresh()
            await self.hass.async_add_executor_job(time.sleep, UPDATE_DELAY / 1000)
            self.manualUpdate()
            self.updatePending = False
        else:
            LOGGER.warn(
                "Chosen temperature=%s is incorrect. It needs to be between 10 and 40.",
                str(temperature),
            )

    def set_swing_mode(self, swing_mode):
        """Set new target swing operation."""
        LOGGER.debug("Setting swing mode to %s", str(swing_mode))

        if (swing_mode == SWING_VERTICAL):
            self._zone = 0;
        elif (swing_mode == SWING_HORIZONTAL):
            self._zone = 1;
        elif (swing_mode == SWING_BOTH):
            self._zone = 2;
        else:
            LOGGER.warn(
                "Zone setting (%s) is not supported.", str(swing_mode))
            return

        LOGGER.debug("Setting zone to %s", str(self._zone))

        #Have to set H10703 as it gets reset by the setProgram method
        if(self.atrea.getValue("H10703") == 1):
            self.atrea.setCommand("H10703", 2)
        self.atrea.setCommand("H10711", int(self._zone))
        if (self.atrea.exec() == False):
            LOGGER.debug("Zone set succesfully to %s", str(self._zone))
        else: 
            LOGGER.error("Error setting zone")
        
        self.manualUpdate()

