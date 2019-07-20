"""
Support for Atrea Air Ventilation.

configuration.yaml

climate:
  - platform: atrea
    name: name
    host: ip
    password: password
"""

__version__ = "3.0"

import logging
import json
import voluptuous as vol
import re

from datetime import timedelta

from homeassistant.components.climate import (ClimateDevice, PLATFORM_SCHEMA)
from homeassistant.components.climate.const import (ATTR_HVAC_MODE, ATTR_FAN_MODE, SUPPORT_PRESET_MODE, SUPPORT_TARGET_TEMPERATURE, HVAC_MODE_OFF, HVAC_MODE_AUTO, HVAC_MODE_FAN_ONLY, SUPPORT_FAN_MODE)

from homeassistant.const import (STATE_ON, STATE_OFF, CONF_NAME, CONF_HOST, CONF_MONITORED_CONDITIONS, CONF_PASSWORD, TEMP_CELSIUS, ATTR_TEMPERATURE, CONF_CUSTOMIZE)
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)
SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_FAN_MODE | SUPPORT_PRESET_MODE
_LOGGER = logging.getLogger(__name__)
DEFAULT_NAME = "Atrea"
STATE_MANUAL = 'manual'
STATE_UNKNOWN = 'unknown'
CONF_FAN_MODES = 'fan_modes'
CUSTOMIZE_SCHEMA = vol.Schema({
    vol.Optional(CONF_FAN_MODES): vol.All(cv.ensure_list, [cv.string])
})
DEFAULT_FAN_MODE_LIST = ['12%', '20%', '30%', '40%', '50%', '60%', '70%', '80%', '90%', '100%']
PRESET_LIST = ["Off", "Automat", "Ventilation", "Night precooling", "Disbalance"]
HVAC_MODES = [HVAC_MODE_OFF, HVAC_MODE_AUTO, HVAC_MODE_FAN_ONLY]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_CUSTOMIZE, default={}): CUSTOMIZE_SCHEMA
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    import pyatrea
    host = config.get(CONF_HOST)
    password = config.get(CONF_PASSWORD)
    sensor_name = config.get(CONF_NAME)
    conditions = config.get(CONF_MONITORED_CONDITIONS)
    fan_list = config.get(CONF_CUSTOMIZE).get(CONF_FAN_MODES, []) or DEFAULT_FAN_MODE_LIST

    add_devices([Atrea(host, password, sensor_name, fan_list, conditions)])

class Atrea(ClimateDevice):

    def __init__(self, host, password, sensor_name, fan_list, conditions):
        import pyatrea
        self.host = host
        self.password = password
        self.atrea = pyatrea.Atrea(self.host,self.password)
        self._warnings = []
        self._prefixName = sensor_name
        self._current_fan_mode = None
        self._alerts = []
        self._outside_temp = ""
        self._inside_temp = ""
        self._supply_air_temp = ""
        self._requested_temp = ""
        self._requested_power = ""
        self._fan_list = fan_list
        self._current_preset = None
        self._current_hvac_mode = None
        self._unit = "Status"
        self._icon = "mdi:alert-decagram"

        self.current_mode = None
        self.air_handling_control = None

        self.update()

    @property
    def should_poll(self):
        return True

    @property
    def unit_of_measurement(self):
        return self._unit

    @property
    def icon(self):
        return self._icon

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
        if self._current_preset in (0, 1, 2, 3, 4):
            return PRESET_LIST[self._current_preset]
        else:
            return STATE_UNKNOWN

    @property
    def preset_modes(self):
        return PRESET_LIST
    
    @property
    def current_temperature(self):
        return float(self._supply_air_temp)
        
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

    @Throttle(MIN_TIME_BETWEEN_SCANS)
    def update(self):
        self.manualUpdate()

    def manualUpdate(self):
        status = self.atrea.getStatus()
        self._warnings = []
        self._alerts = []
        if(status != False):            
            self._outside_temp = float(status['I10202'])/10
            self._inside_temp = float(status['I10203'])/10
            self._supply_air_temp = float(status['I10200'])/10
            self._requested_temp = float(status['H10706'])/10
            self._requested_power = int(status['H10714'])
            self._current_fan_mode = str(self._requested_power)+"%"
            
            if(int(status['H10705']) == 0):
                self._current_hvac_mode = HVAC_MODE_OFF
                self._current_preset = 0
                # Off
                self.current_mode = 0
            elif(int(status['H10705']) == 1):
                self._current_preset = 1
                # Automat
                self.current_mode = 1
            elif(int(status['H10705']) == 2):
                self._current_preset = 2
                # Ventilation
                self.current_mode = 2
            elif(int(status['H10705']) == 5):
                self._current_preset = 3
                # Night precooling
                self.current_mode = 3
            elif(int(status['H10705']) == 6):
                self._current_preset = 4
                # Disbalance
                self.current_mode = 4
            else:
                self._current_preset = None
                # Unknown
                self.current_mode = None

            if(int(status['H10701']) == 0):
                self.air_handling_control = 'Manual'
                if(int(status['H10705']) == 0):
                    self._current_hvac_mode = HVAC_MODE_OFF
                else:
                    self._current_hvac_mode = HVAC_MODE_FAN_ONLY
            elif(int(status['H10701']) == 1):
                self.air_handling_control = 'Schedule'
                self._current_hvac_mode = HVAC_MODE_AUTO
            elif(int(status['H10701']) == 2):
                self.air_handling_control = 'Temporary'
                if(int(status['H10705']) == 0):
                    self._current_hvac_mode = HVAC_MODE_OFF
                else:
                    self._current_hvac_mode = HVAC_MODE_FAN_ONLY
            else:
                self.air_handling_control = "Unknown (" + str(status['H10701']) + ")"
            
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
            self.atrea.setPower(fan_percent)
            self.atrea.exec()
            self.manualUpdate()
        else:
            _LOGGER.warn("Power out of range (12,100)")

    def turn_on(self):
        if(self.air_handling_control == 'Manual'):
            self.atrea.setProgram(0)
            self._current_hvac_mode = HVAC_MODE_FAN_ONLY
        elif(self.air_handling_control == 'Schedule'):
            self.atrea.setProgram(1)
            self._current_hvac_mode = HVAC_MODE_AUTO
        elif(self.air_handling_control == 'Temporary'):
            self.atrea.setProgram(2)
            self._current_hvac_mode = HVAC_MODE_FAN_ONLY
        self.atrea.setMode(2)
        self.atrea.exec()
        self.manualUpdate()

    def turn_off(self):
        if(self.air_handling_control == 'Manual'):
            self.atrea.setProgram(0)
        elif(self.air_handling_control == 'Temporary'):
            self.atrea.setProgram(2)
        else:
            self.atrea.setProgram(1)

        self._current_hvac_mode = HVAC_MODE_OFF
        self.atrea.setMode(0)
        self.atrea.exec()
        self.manualUpdate()

    def set_hvac_mode(self, hvac_mode):
        mode = False
        program = False
        if(hvac_mode == HVAC_MODE_AUTO):
            mode = False
            self._current_hvac_mode = HVAC_MODE_AUTO
            program = 1
        elif(hvac_mode == HVAC_MODE_FAN_ONLY):
            mode = 2
            program = 0
            self._current_hvac_mode = HVAC_MODE_FAN_ONLY
        elif(hvac_mode == HVAC_MODE_OFF):
            self.turn_off()
            self._current_hvac_mode = HVAC_MODE_OFF
            
        if(((self.air_handling_control == 'Manual' and program != 0)
            or (self.air_handling_control == 'Schedule' and program != 1)
            or (self.air_handling_control == 'Temporary' and program != 2))
            and program != None):
            self.atrea.setProgram(program)

        if((mode != False and self.current_mode != mode)
             or self.air_handling_control == 'Schedule'):
            self.atrea.setMode(mode)

        self.atrea.exec()
        self.manualUpdate()

    def set_preset_mode(self, preset):
        mode = False
        program = False
        if preset == "Off":
            self.turn_off()
        elif preset == "Automat":
            mode = 1
            program = 0
        elif preset == "Ventilation":
            mode = 2
            program = 0
        elif preset == "Night precooling":
            mode = 3
            program = 0
        elif preset == "Disbalance":
            mode = 4
            program = 0
        else:
            _LOGGER.warn("Chosen preset=%s(%s) is incorrect preset.", str(preset),
                      str(mode))

        if(((self.air_handling_control == 'Manual' and program != 0)
            or (self.air_handling_control == 'Schedule' and program != 1)
            or (self.air_handling_control == 'Temporary' and program != 2))
            and program != None):
            self.atrea.setProgram(program)

        if((mode != False and self.current_mode != mode)
             or self.air_handling_control == 'Schedule'):
            self.atrea.setMode(mode)

        self.atrea.exec()
        self.manualUpdate()

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        elif(temperature >= 10 and temperature<= 40):
            self.atrea.setTemperature(temperature)
            self.atrea.exec()
            self.manualUpdate()
        else:
            _LOGGER.warn("Chosen temperature=%s is incorrect. It needs to be between 10 and 40.", str(temperature))
        
            
