"""
Support for Atrea Air Ventilation.

configuration.yaml

climate:
  - platform: atrea
    name: name
    host: ip
    password: password
"""

__version__ = "4.3.1"

import logging
import json
import voluptuous as vol
import re

from pyatrea import Atrea, AtreaProgram, AtreaMode

from datetime import timedelta

try:
    from homeassistant.components.climate import (
        ClimateEntity, PLATFORM_SCHEMA)
except ImportError:
    from homeassistant.components.climate import (
        ClimateDevice as ClimateEntity, PLATFORM_SCHEMA)

from homeassistant.components.climate.const import (ATTR_HVAC_MODE, ATTR_FAN_MODE, SUPPORT_PRESET_MODE,
                                                    SUPPORT_TARGET_TEMPERATURE, HVAC_MODE_OFF, HVAC_MODE_AUTO, HVAC_MODE_FAN_ONLY, SUPPORT_FAN_MODE)

from homeassistant.const import (STATE_ON, STATE_OFF, CONF_NAME, CONF_HOST,
                                 CONF_MONITORED_CONDITIONS, CONF_PASSWORD, TEMP_CELSIUS, ATTR_TEMPERATURE, CONF_CUSTOMIZE)
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)
SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_FAN_MODE | SUPPORT_PRESET_MODE
_LOGGER = logging.getLogger(__name__)
DEFAULT_NAME = "Atrea"
STATE_MANUAL = 'manual'
STATE_UNKNOWN = 'unknown'
CONF_FAN_MODES = 'fan_modes'
CONF_PRESETS = 'presets'
CUSTOMIZE_SCHEMA = vol.Schema({
    vol.Optional(CONF_FAN_MODES): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(CONF_PRESETS): vol.All(cv.ensure_list, [cv.string])
})
DEFAULT_FAN_MODE_LIST = ['12%', '20%', '30%', '40%',
                         '50%', '60%', '70%', '80%', '90%', '100%']
ALL_PRESET_LIST = ["Off", "Automatic", "Ventilation", "Circulation and Ventilation",
                   "Circulation", "Night precooling", "Disbalance", "Overpressure",
                   "Periodic ventilation", "Startup", "Rundown", "Defrosting", "External", "HP defrosting",
                   "IN1", "IN2", "D1", "D2", "D3", "D4"]

ICONS = {
    AtreaMode.OFF: "mdi:fan-off",
    AtreaMode.AUTOMATIC: "mdi:fan",
    AtreaMode.VENTILATION: "mdi:fan-chevron-up",
    AtreaMode.CIRCULATION_AND_VENTILATION: "mdi:fan",
    AtreaMode.CIRCULATION: "mdi:fan-chevron-down",
    AtreaMode.NIGHT_PRECOOLING: "mdi:fan-speed-1",
    AtreaMode.DISBALANCE: "mdi:fan-speed-2",
    AtreaMode.OVERPRESSURE: "mdi:fan-speed-3",
    AtreaMode.STARTUP: "mdi:chevron-up",
    AtreaMode.RUNDOWN: "mdi:chevron-down",
    AtreaMode.DEFROSTING: "mdi:car-defrost-rear",
    AtreaMode.EXTERNAL: "mdi:fan-alert",
    AtreaMode.HP_DEFROSTING: "mdi:car-defrost-front",
    AtreaMode.IN1: "mdi:fan-chevron-up",
    AtreaMode.IN2: "mdi:fan-chevron-up",
    AtreaMode.D1: "mdi:fan-chevron-up",
    AtreaMode.D2: "mdi:fan-chevron-up",
    AtreaMode.D3: "mdi:fan-chevron-up",
    AtreaMode.D4: "mdi:fan-chevron-up" }

HVAC_MODES = [HVAC_MODE_OFF, HVAC_MODE_AUTO, HVAC_MODE_FAN_ONLY]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Optional(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_CUSTOMIZE, default={}): CUSTOMIZE_SCHEMA
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    host = config.get(CONF_HOST)
    password = config.get(CONF_PASSWORD)
    sensor_name = config.get(CONF_NAME)
    conditions = config.get(CONF_MONITORED_CONDITIONS)
    fan_list = config.get(CONF_CUSTOMIZE).get(
        CONF_FAN_MODES, []) or DEFAULT_FAN_MODE_LIST
    preset_list = config.get(CONF_CUSTOMIZE).get(
        CONF_PRESETS, []) or ALL_PRESET_LIST

    add_devices([AtreaDevice(host, password, sensor_name, fan_list, preset_list, conditions)])


class AtreaDevice(ClimateEntity):

    def __init__(self, host, password, sensor_name, fan_list, preset_list, conditions):
        self.host = host
        self.password = password
        self.atrea = Atrea(self.host, self.password)
        self._warnings = []
        self._prefixName = sensor_name
        self._current_fan_mode = None
        self._alerts = []
        self._preset_list = []
        self._outside_temp = 0.0
        self._inside_temp = 0.0
        self._supply_air_temp = 0.0
        self._requested_temp = 0.0
        self._requested_power = None
        self._fan_list = fan_list
        self._current_preset = None
        self._current_hvac_mode = None
        self._unit = "Status"
        self.air_handling_control = None

        for required_preset in preset_list:
            for i, preset_supported in self.atrea.getSupportedModes().items():
                if preset_supported and ALL_PRESET_LIST[i] == required_preset:
                    self._preset_list.append(ALL_PRESET_LIST[i])

        self._userLabels = self.atrea.loadUserLabels()
        self.update()

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
    def name(self):
        return '{}'.format(self._prefixName)

    @property
    def device_state_attributes(self):
        attributes = {}

        attributes['outside_temp'] = self._outside_temp
        attributes['inside_temp'] = self._inside_temp
        attributes['supply_air_temp'] = self._supply_air_temp
        attributes['requested_temp'] = self._requested_temp
        attributes['requested_power'] = self._requested_power
        attributes['warnings'] = self._warnings
        attributes['alerts'] = self._alerts
        attributes['program'] = self.air_handling_control

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
    
    @Throttle(MIN_TIME_BETWEEN_SCANS)
    def update(self):
        self.manualUpdate()

    def manualUpdate(self):
        status = self.atrea.getStatus(False)
        self._warnings = []
        self._alerts = []
        if(status != False):
            if('I10202' in status):
                if(float(status['I10211']) > 1300):
                    self._outside_temp = round(((50-(float(status['I10211'])-65036)/10)*-1),1)
                else:
                    self._outside_temp = float(status['I10211'])/10
            elif('I00202' in status):
                if(self.atrea.getValue('I00202') == 126.0):
                    if(self.atrea.getValue('H00511') == 1):
                        self._outside_temp = self.atrea.getValue('I00200')
                    elif(self.atrea.getValue('H00511') == 1):
                        self._outside_temp = self.atrea.getValue('I00201')
                else:
                    self._outside_temp = self.atrea.getValue('I00202')
            
            # Depending on configuration of ventilation unit, indoor temp is read from different addresses
            if('H10514' in status):
                if(int(status['H10514']) == 1):
                    self._inside_temp = float(status['I10203'])/10
                elif(int(status['H10514']) == 0):
                    self._inside_temp = float(status['I10207'])/10
                else:
                    _LOGGER.warn(
                        "Indoor sensor not supported yet. Please contact repository owner with information about your unit.")
            elif('I00210' in status):
                self._inside_temp = self.atrea.getValue('I00210')

            if('I10200' in status):
                self._supply_air_temp = float(status['I10200'])/10
            elif('I00200' in status):
                self._supply_air_temp = self.atrea.getValue('I00200')
            
            if('H10706' in status):
                self._requested_temp = float(status['H10706'])/10
            elif('H01006' in status):
                self._requested_temp = self.atrea.getValue('H01006')
            
            if('H10714' in status):
                self._requested_power = int(status['H10714'])
            elif('H01005' in status):
                self._requested_power = int(self.atrea.getValue('H01005'))
            
            if('H01001' in status):
                self._current_fan_mode = str(int(self.atrea.getValue('H01001')))+"%"
            else:
                self._current_fan_mode = str(self._requested_power)+"%"

            self._current_preset = self.atrea.getMode()
            if(self._current_preset == AtreaMode.OFF):
                self._current_hvac_mode = HVAC_MODE_OFF

            program = self.atrea.getProgram()
            if(program == AtreaProgram.MANUAL):
                self.air_handling_control = 'Manual'
                if(self.atrea.getValue('H10705') == 0):
                    self._current_hvac_mode = HVAC_MODE_OFF
                else:
                    self._current_hvac_mode = HVAC_MODE_FAN_ONLY
            elif(program == AtreaProgram.WEEKLY):
                self.air_handling_control = 'Schedule'
                self._current_hvac_mode = HVAC_MODE_AUTO
            elif(program == AtreaProgram.TEMPORARY):
                self.air_handling_control = 'Temporary'
                if(self.atrea.getValue('H10705') == 0):
                    self._current_hvac_mode = HVAC_MODE_OFF
                else:
                    self._current_hvac_mode = HVAC_MODE_FAN_ONLY
            else:
                self.air_handling_control = "Unknown (" + str(program) + ")"

            params = self.atrea.getParams()
            for warning in params['warning']:
                if status[warning] == "1":
                    self._warnings.append(self.atrea.getTranslation(warning))

            params = self.atrea.getParams()
            for alert in params['alert']:
                if status[alert] == "1":
                    self._alerts.append(self.atrea.getTranslation(alert))

        else:
            self._current_hvac_mode = None

    def set_fan_mode(self, fan_percent):
        fan_percent = int(re.sub("[^0-9]", "", fan_percent))
        if(fan_percent < 12):
            fan_percent = 12
        if(fan_percent > 100):
            fan_percent = 100
        if(fan_percent >= 12 and fan_percent <= 100):
            if self.atrea.getProgram() == AtreaProgram.WEEKLY:
                self.atrea.setProgram(AtreaProgram.TEMPORARY)
            self.atrea.setPower(fan_percent)
            self.atrea.exec()
            self.manualUpdate()
        else:
            _LOGGER.warn("Power out of range (12,100)")

    def turn_on(self):
        if(self.air_handling_control == 'Manual'):
            self.atrea.setProgram(AtreaProgram.MANUAL)
            self._current_hvac_mode = HVAC_MODE_FAN_ONLY
        elif(self.air_handling_control == 'Schedule'):
            self.atrea.setProgram(AtreaProgram.WEEKLY)
            self._current_hvac_mode = HVAC_MODE_AUTO
        elif(self.air_handling_control == 'Temporary'):
            self.atrea.setProgram(AtreaProgram.TEMPORARY)
            self._current_hvac_mode = HVAC_MODE_FAN_ONLY
        self.atrea.setMode(AtreaMode.VENTILATION)
        self.atrea.exec()
        self.manualUpdate()

    def turn_off(self):
        if(self.air_handling_control == 'Manual'):
            self.atrea.setProgram(AtreaProgram.MANUAL)
        elif(self.air_handling_control == 'Temporary'):
            self.atrea.setProgram(AtreaProgram.TEMPORARY)
        else:
            self.atrea.setProgram(AtreaProgram.WEEKLY)

        self._current_hvac_mode = HVAC_MODE_OFF
        self.atrea.setMode(AtreaMode.OFF)
        self.atrea.exec()
        self.manualUpdate()

    def set_hvac_mode(self, hvac_mode):
        mode = None
        program = None
        if(hvac_mode == HVAC_MODE_AUTO):
            self._current_hvac_mode = HVAC_MODE_AUTO
            program = AtreaProgram.WEEKLY
        elif(hvac_mode == HVAC_MODE_FAN_ONLY):
            mode = AtreaMode.VENTILATION
            program = AtreaProgram.MANUAL
            self._current_hvac_mode = HVAC_MODE_FAN_ONLY
        elif(hvac_mode == HVAC_MODE_OFF):
            self.turn_off()
            self._current_hvac_mode = HVAC_MODE_OFF

        if program != None and program != self.atrea.getProgram():
            self.atrea.setProgram(program)

        if((mode != None and self._current_preset != mode)
           or self.air_handling_control == 'Schedule'):
            self.atrea.setMode(mode)

        self.atrea.exec()
        self.manualUpdate()

    def set_preset_mode(self, preset):
        mode = None
        try:
            mode = AtreaMode(ALL_PRESET_LIST.index(preset))
        except ValueError:
            _LOGGER.warn("Chosen preset=%s is incorrect preset.", str(preset))
            return

        if mode == AtreaMode.OFF:
            self.turn_off()
        if self.atrea.getProgram() == AtreaProgram.WEEKLY:
            self.atrea.setProgram(AtreaProgram.TEMPORARY)
        if mode != self.atrea.getMode():
            self.atrea.setMode(mode)

        self.atrea.exec()
        self.manualUpdate()

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        elif(temperature >= 10 and temperature <= 40):
            self.atrea.setTemperature(temperature)
            self.atrea.exec()
            self.manualUpdate()
        else:
            _LOGGER.warn(
                "Chosen temperature=%s is incorrect. It needs to be between 10 and 40.", str(temperature))
