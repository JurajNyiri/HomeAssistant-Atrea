import logging
import time
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from typing import Callable
from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
from homeassistant.util import slugify, Throttle
from homeassistant.const import CONF_IP_ADDRESS, CONF_NAME
from .const import DOMAIN, MIN_TIME_BETWEEN_SCANS, UPDATE_DELAY, LOGGER


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: Callable
):
    sensor_name = entry.data.get(CONF_NAME)
    if sensor_name is None:
        sensor_name = "atrea"
    hass.data[DOMAIN][entry.entry_id]["update"] = AtreaUpdate(hass, entry, sensor_name)
    async_add_entities([hass.data[DOMAIN][entry.entry_id]["update"]])


class AtreaUpdate(UpdateEntity):
    def __init__(self, hass, entry, sensor_name):
        super().__init__()
        self._coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
        self.updatePending = False
        self.data = hass.data[DOMAIN][entry.entry_id]
        self.atrea = self.data["atrea"]
        self._in_progress = False
        self._enabled = False
        self.ip = entry.data.get(CONF_IP_ADDRESS)
        self.updateName(sensor_name, False)
        self.manualUpdate(False)

    async def async_added_to_hass(self) -> None:
        self._enabled = True

    async def async_will_remove_from_hass(self) -> None:
        self._enabled = False

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
    def unique_id(self) -> str:
        return self.getUniqueID()

    def getUniqueID(self):
        return slugify(f"atrea_{self.ip}")

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
        self._in_progress = "I10005" in status and int(status["I10005"]) > 3
        self._id = self.atrea.getID()
        self._model = self.data["model"]
        self._swVersion = self.atrea.getVersion()
        self._latestVersion = self.atrea.getLatestVersion()
        if self._latestVersion == "0.0":
            self._latestVersion = self._swVersion
        if updateState:
            self.async_schedule_update_ha_state(True)

    @property
    def supported_features(self):
        return UpdateEntityFeature.INSTALL

    def updateName(self, name, updateState=True):
        self._name = name
        if updateState:
            self.async_schedule_update_ha_state(True)

    @property
    def name(self) -> str:
        return "{}".format(self._name)

    @property
    def in_progress(self) -> bool:
        return self._in_progress

    @property
    def installed_version(self) -> str:
        return self._swVersion

    @property
    def latest_version(self) -> str:
        return self._latestVersion

    @property
    def title(self) -> str:
        return "{0}: {1}".format(self.name, self._latestVersion)

    async def async_install(
        self, version, backup,
    ):
        self._in_progress = True
        self.atrea.prepareUpdate()
        await self.hass.async_add_executor_job(self.atrea.exec)
        await self._coordinator.async_request_refresh()
        self.manualUpdate()

