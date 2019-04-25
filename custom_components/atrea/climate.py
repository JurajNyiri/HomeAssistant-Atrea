"""
Support for Atrea Air Ventilation.

configuration.yaml

climate:
  - platform: atrea
    name: name
    host: ip
    password: password
"""

__version__ = "2.1"

import logging
import json
import voluptuous as vol
import re

from datetime import timedelta

from homeassistant.components.climate.const import (SUPPORT_TARGET_TEMPERATURE, SUPPORT_OPERATION_MODE, SUPPORT_ON_OFF, SUPPORT_FAN_MODE)
from homeassistant.components.climate import (ClimateDevice, PLATFORM_SCHEMA)
from homeassistant.const import (STATE_ON, STATE_OFF, CONF_NAME, CONF_HOST, CONF_MONITORED_CONDITIONS, CONF_PASSWORD, TEMP_CELSIUS, ATTR_TEMPERATURE, CONF_CUSTOMIZE)
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=10)
SUPPORT_FLAGS = SUPPORT_TARGET_TEMPERATURE | SUPPORT_OPERATION_MODE | SUPPORT_FAN_MODE | SUPPORT_ON_OFF
_LOGGER = logging.getLogger(__name__)
DEFAULT_NAME = "Atrea"
STATE_MANUAL = 'manual'
STATE_UNKNOWN = 'unknown'
CONF_FAN_MODES = 'fan_modes'
CUSTOMIZE_SCHEMA = vol.Schema({
    vol.Optional(CONF_FAN_MODES): vol.All(cv.ensure_list, [cv.string])
})
DEFAULT_FAN_MODE_LIST = ['12%', '20%', '30%', '40%', '50%', '60%', '70%', '80%', '90%', '100%']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_CUSTOMIZE, default={}): CUSTOMIZE_SCHEMA
})


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    import pyatrea
    host = config.get(CONF_HOST)
    password = config.get(CONF_PASSWORD)
    sensor_name = config.get(CONF_NAME)
    conditions = config.get(CONF_MONITORED_CONDITIONS)
    fan_list = config.get(CONF_CUSTOMIZE).get(CONF_FAN_MODES, []) or DEFAULT_FAN_MODE_LIST

    add_devices([Atrea(host, password, sensor_name, fan_list, conditions)])

# pylint: disable=abstract-method
# pylint: disable=too-many-instance-attributes
class Atrea(ClimateDevice):

    def __init__(self, host, password, sensor_name, fan_list, conditions):
        import pyatrea
        self.host = host
        self.password = password
        self.atrea = pyatrea.Atrea(self.host,self.password)
        self._state = None
        self._warnings = []
        self._prefixName = sensor_name
        self._current_fan_mode = -1
        self._alerts = []
        self._outside_temp = ""
        self._inside_temp = ""
        self._supply_air_temp = ""
        self._requested_temp = ""
        self._requested_power = ""
        self._fan_list = fan_list

        #todo: better names
        self._current_operation_mode = -1
        self._air_handling_control = -1
        self._current_mode = -1

        self._unit = "Status"
        self._icon = "mdi:alert-decagram"

        self._operation_list = ['Schedule', "Manual: Automat", "Manual: Ventilation", "Manual: Night precooling", "Manual: Disbalance", "Temporary: Automat", "Temporary: Ventilation", "Temporary: Night precooling", "Temporary: Disbalance"]

        self.update()

    @property
    def should_poll(self):
        """Polling needed for climate."""
        return True

    @property
    def unit_of_measurement(self):
        """Return the unit of the climate state."""
        return self._unit

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def state(self):
        """Return the state of the climate sensors."""
        if self.is_on is False:
            return STATE_OFF
        else:
            return self._state

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
            
            if(int(status['H10701']) == 0):
                self._air_handling_control = 'Manual'

                if(int(status['H10705']) == 0):
                    self._state = "Manual: Off"
                    self._current_operation_mode = -1
                    self._current_mode = 0
                elif(int(status['H10705']) == 1):
                    self._state = "Manual: Automat"
                    self._current_operation_mode = 1
                    self._current_mode = 1
                elif(int(status['H10705']) == 2):
                    self._state = "Manual: Ventilation"
                    self._current_operation_mode = 2
                    self._current_mode = 2
                elif(int(status['H10705']) == 5):
                    self._state = "Manual: Night precooling"
                    self._current_operation_mode = 3
                    self._current_mode = 3
                elif(int(status['H10705']) == 6):
                    self._state = "Manual: Disbalance"
                    self._current_operation_mode = 4
                    self._current_mode = 4
                else:
                    self._state = "Manual: Unknown"
                    self._current_operation_mode = -1
                    self._current_mode = -1

            elif(int(status['H10701']) == 1):
                self._air_handling_control = 'Schedule'

                if(int(status['H10705']) == 0):
                    self._state = "Schedule: Off"
                    self._current_operation_mode = -1
                    self._current_mode = 0
                elif(int(status['H10705']) == 1):
                    self._state = "Schedule: Automat"
                    self._current_operation_mode = 0
                    self._current_mode = 1
                elif(int(status['H10705']) == 2):
                    self._state = "Schedule: Ventilation"
                    self._current_operation_mode = 0
                    self._current_mode = 2
                elif(int(status['H10705']) == 5):
                    self._state = "Schedule: Night precooling"
                    self._current_operation_mode = 0
                    self._current_mode = 3
                elif(int(status['H10705']) == 6):
                    self._state = "Schedule: Disbalance"
                    self._current_operation_mode = 0
                    self._current_mode = 4
                else:
                    self._state = "Schedule: Unknown"
                    self._current_operation_mode = -1
                    self._current_mode = -1

            elif(int(status['H10701']) == 2):
                self._air_handling_control = 'Temporary'

                if(int(status['H10705']) == 0):
                    self._state = "Temporary: Off"
                    self._current_operation_mode = -1
                    self._current_mode = 0
                elif(int(status['H10705']) == 1):
                    self._state = "Temporary: Automat"
                    self._current_operation_mode = 5
                    self._current_mode = 1
                elif(int(status['H10705']) == 2):
                    self._state = "Temporary: Ventilation"
                    self._current_operation_mode = 6
                    self._current_mode = 2
                elif(int(status['H10705']) == 5):
                    self._state = "Temporary: Night precooling"
                    self._current_operation_mode = 7
                    self._current_mode = 3
                elif(int(status['H10705']) == 6):
                    self._state = "Temporary: Disbalance"
                    self._current_operation_mode = 8
                    self._current_mode = 4
                else:
                    self._state = "Temporary: Unknown"
                    self._current_operation_mode = -1
                    self._current_mode = -1

            else:
                self._air_handling_control = "Unknown (" + str(status['H10701']) + ")"
            
                
                

            
            params = self.atrea.getParams()
            for warning in params['warning']:
                if status[warning] == "1":
                    self._warnings.append(self.atrea.getTranslation(warning))

            params = self.atrea.getParams()
            for alert in params['alert']:
                if status[alert] == "1":
                    self._alerts.append(self.atrea.getTranslation(alert))

        else:
            self._state = 'Disconnected'

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{}'.format(self._prefixName)

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
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
        """Return the unit of measurement."""
        return TEMP_CELSIUS

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return float(self._requested_temp)

    @property
    def current_operation(self):
        """Return the current state of the thermostat."""
        state = self._current_operation_mode
        if state in (0, 1, 2, 3, 4, 5, 6, 7, 8):
            return self._operation_list[state]
        else:
            return STATE_UNKNOWN

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return float(self._supply_air_temp)
        
    @property
    def min_temp(self):
        """Return the polling state."""
        return 10
        
    @property
    def max_temp(self):
        """Return the polling state."""
        return 40

    @property
    def operation_list(self):
        """List of available operation modes."""
        return self._operation_list
    
    @property
    def fan_list(self):
        """Return the list of available fan modes."""
        return self._fan_list

    @property
    def current_fan_mode(self):
        """Return the fan setting."""
        return self._current_fan_mode

    def set_fan_mode(self, fan_percent):
        fan_percent = int(re.sub("[^0-9]", "", fan_percent))
        if(fan_percent < 12):
            fan_percent = 12
        if(fan_percent > 100):
            fan_percent = 100
        if(fan_percent >= 12 and fan_percent <= 100):
            if(self._air_handling_control == 'Schedule' or self.is_on is False):
                if(self._air_handling_control == 'Manual'):
                    self.atrea.setProgram(0)
                else:
                    self.atrea.setProgram(2)

                self.atrea.setMode(2)
            self.atrea.setPower(fan_percent)
            self.atrea.exec()
            self.manualUpdate()
        else:
            _LOGGER.warn("Power out of range (12,100)")

    @property
    def is_on(self):
        return (": Off" not in self._state)

    def turn_on(self):
        if(self._air_handling_control == 'Manual'):
            self.atrea.setProgram(0)
        elif(self._air_handling_control == 'Schedule'):
            self.atrea.setProgram(1)
        elif(self._air_handling_control == 'Temporary'):
            self.atrea.setProgram(2)
        self.atrea.setMode(2)
        self.atrea.exec()
        self.manualUpdate()

    def turn_off(self):
        program = False
        if("Manual:" in self._state):
            program = "0"
        elif("Temporary:" in self._state):
            program = "2"
        else:
            program = "1"
        if(program != False):
            self.atrea.setProgram(program)
            self.atrea.setMode(0)
            self.atrea.exec()
            self.manualUpdate()

    def set_operation_mode(self, operation_mode):
        mode = False
        program = False
        if operation_mode == 'Schedule':
            mode = False
            program = 1
        elif operation_mode == "Manual: Automat":
            mode = 1
            program = 0
        elif operation_mode == "Manual: Ventilation":
            mode = 2
            program = 0
        elif operation_mode == "Manual: Night precooling":
            mode = 3
            program = 0
        elif operation_mode == "Manual: Disbalance":
            mode = 4
            program = 0
        elif operation_mode == "Temporary: Automat":
            mode = 1
            program = 2
        elif operation_mode == "Temporary: Ventilation":
            mode = 2
            program = 2
        elif operation_mode == "Temporary: Night precooling":
            mode = 3
            program = 2
        elif operation_mode == "Temporary: Disbalance":
            mode = 4
            program = 2
        else:
            _LOGGER.warn("Chosen operation mode=%s(%s) is incorrect mode.", str(operation_mode),
                      str(mode))
        

        if((self._air_handling_control == 'Manual' and program != 0)
            or (self._air_handling_control == 'Schedule' and program != 1)
            or (self._air_handling_control == 'Temporary' and program != 2)):
            self.atrea.setProgram(program)

        if((mode != False and self._current_mode != mode)
             or self._air_handling_control == 'Schedule'):
            self.atrea.setMode(mode)

        self.atrea.exec()
        
        self.manualUpdate()

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        elif(temperature >= 10 and temperature<= 40):
            if(self._air_handling_control == 'Schedule'):
                self.atrea.setProgram(2)
            self.atrea.setTemperature(temperature)
            self.atrea.exec()
            self.manualUpdate()
        else:
            _LOGGER.warn("Chosen temperature=%s is incorrect. It needs to be between 10 and 40.", str(temperature))
        
            
