"""
Atrea Ventilation
Author: Juraj Nyiri
Repository: https://github.com/JurajNyiri/HomeAssistant-Atrea
"""

REQUIREMENTS = ['pyatrea']

import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import (CONF_NAME, CONF_HOST, CONF_MONITORED_CONDITIONS, CONF_PASSWORD)
from homeassistant.helpers.entity import Entity
from homeassistant.util import Throttle

from datetime import timedelta

_LOGGER = logging.getLogger(__name__)

MIN_TIME_BETWEEN_SCANS = timedelta(seconds=60)

DEFAULT_NAME = "Atrea"

SENSOR_TYPES = {
    'status': ['Status', 'Status', 'mdi:information'],
    'warnings': ['Warnings', 'Warnings', 'mdi:alert-box'],
    'alerts': ['Alerts', 'Alerts', 'mdi:alert-decagram']
}


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_HOST): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_MONITORED_CONDITIONS, default=['warnings']):
        vol.All(cv.ensure_list, [vol.In(list(SENSOR_TYPES))])
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    import pyatrea
    """Set up date countdown sensor."""
    host = config.get(CONF_HOST)
    password = config.get(CONF_PASSWORD)
    sensor_name = config.get(CONF_NAME)
    conditions = config.get(CONF_MONITORED_CONDITIONS)

    add_entities(
        [Atrea(host, password, sensor_name, sensor) for sensor in conditions], True)

class Atrea(Entity):
    """Implementation of the atrea sensor."""

    def __init__(self, host, password, sensor_name, sensor_type):
        import pyatrea
        """Initialize the sensor."""
        self.host = host
        self.password = password
        self.atrea = pyatrea.Atrea(self.host,self.password)
        self._state = None
        self._warnings = []
        self._prefixName = sensor_name
        self._alerts = []
        self._outside_temp = ""
        self._inside_temp = ""
        self._supply_air_temp = ""
        self._requested_temp = ""
        self._requested_power = ""

        self.type = sensor_type
        self._name = SENSOR_TYPES[self.type][0]
        self._unit = SENSOR_TYPES[self.type][1]
        self._icon = SENSOR_TYPES[self.type][2]

        self.update()

    @property
    def name(self):
        """Return the name of the sensor."""
        return '{} {}'.format(self._prefixName, self._name)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of the sensor."""
        return self._unit

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def device_state_attributes(self):
        """Return the state attributes of the sensor."""
        attributes = {}

        if self.type == 'status':
            attributes['outside_temp'] = self._outside_temp
            attributes['inside_temp'] = self._inside_temp
            attributes['supply_air_temp'] = self._supply_air_temp
            attributes['requested_temp'] = self._requested_temp
            attributes['requested_power'] = self._requested_power
        elif self.type == 'warnings':
            attributes['warnings'] = self._warnings
        elif self.type == 'alerts':
            attributes['alerts'] = self._alerts

        return attributes

    @Throttle(MIN_TIME_BETWEEN_SCANS)
    def update(self):
        status = self.atrea.getStatus()
        
        self._warnings = []
        self._alerts = []

        if(status != False):

            if self.type == 'status':
                self._outside_temp = int(status['I10202'])/10
                self._inside_temp = int(status['I10203'])/10
                self._supply_air_temp = int(status['I10200'])/10
                self._requested_temp = int(status['H10706'])/10
                self._requested_power = int(status['H10708'])
            
                if(int(status['H10705']) == 0):
                    self._state = "Off"
                elif(int(status['H10705']) == 1):
                    self._state = "Automat"
                elif(int(status['H10705']) == 2):
                    self._state = "Ventilation"
                elif(int(status['H10705']) == 5):
                    self._state = "Night precooling"
                elif(int(status['H10705']) == 6):
                    self._state = "Disbalance"
                else:
                    self._state = "Unknown"

            elif self.type == 'warnings':
                params = self.atrea.getParams()
                for warning in params['warning']:
                    if status[warning] == "1":
                        self._warnings.append(self.atrea.getTranslation(warning))
                self._state = len(self._warnings)

            elif self.type == 'alerts':
                params = self.atrea.getParams()
                for alert in params['alert']:
                    if status[alert] == "1":
                        self._alerts.append(self.atrea.getTranslation(alert))
                self._state = len(self._alerts)

        else:
            if self.type == 'status':
                self._state = "Disconnected"
            else:
                self._state = "Disconnected"

        #power_set -> http://192.168.100.4/config/xml.cgi?auth=49972&H1070800020 = 20%
        #power_set -> http://192.168.100.4/config/xml.cgi?auth=49972&H1070800097 = 97%
        # http://192.168.100.4/config/xml.cgi?auth=49972&H1070800100 = 100%
        # http://192.168.100.4/config/xml.cgi?auth=49972&H1070800000 = off
        #power read <O I="H10708" V="0"/>

        

        #mode  - 1 - automat, 2 - ventilation, 5 - night precooling, 6 - disbalance, 0 - off