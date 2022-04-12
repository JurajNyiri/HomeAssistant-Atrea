import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from typing import Callable
from homeassistant.components.update import UpdateEntity, UpdateEntityFeature
from homeassistant.util import slugify

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: Callable
):
    _LOGGER.warn("TESTING 1")
    async_add_entities([AtreaUpdate()])


class AtreaUpdate(UpdateEntity):
    def __init__(self,):
        self._in_progress = False
        self._enabled = False
        super().__init__()

    async def async_added_to_hass(self) -> None:
        self._enabled = True

    async def async_will_remove_from_hass(self) -> None:
        self._enabled = False

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
        return "todo"

    @property
    def latest_version(self) -> str:
        return "todo2"

    @property
    def title(self) -> str:
        return "Atrea: {0}".format("todo")

    async def async_install(
        self, version, backup,
    ):
        print("todo install")

