import logging
import time
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from typing import Callable
from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
from homeassistant.util import slugify, Throttle
from homeassistant.const import CONF_IP_ADDRESS

from .const import DOMAIN, MIN_TIME_BETWEEN_SCANS, UPDATE_DELAY

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: Callable
):
    async_add_entities([AtreaUpdate(hass, entry)])


class AtreaUpdate(UpdateEntity):
    def __init__(self, hass, entry):
        super().__init__()
        self._coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
        self.updatePending = False
        self.data = hass.data[DOMAIN][entry.entry_id]
        self.atrea = self.data["atrea"]
        self._in_progress = False
        self._enabled = False
        self.ip = entry.data.get(CONF_IP_ADDRESS)
        self.manualUpdate()

    async def async_added_to_hass(self) -> None:
        self._enabled = True

    async def async_will_remove_from_hass(self) -> None:
        self._enabled = False

    @property
    def brand(self):
        return "ATREA s.r.o."

    @property
    def model(self):
        return self._model["category"] + " " + self._model["model"]

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

    def manualUpdate(self):
        status = self.data["status"]
        self._id = self.atrea.getID()
        self._model = self.atrea.getModel()
        self._swVersion = self.atrea.getVersion()
        self._latestVersion = self.atrea.getLatestVersion()

    @property
    def supported_features(self):
        return UpdateEntityFeature.INSTALL

    @property
    def name(self) -> str:
        return "Atrea Update"

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
        return "Atrea: {0}".format(self._latestVersion)

    async def async_install(
        self, version, backup,
    ):
        print("todo install")

