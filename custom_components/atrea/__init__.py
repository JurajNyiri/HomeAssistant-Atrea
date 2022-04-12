from homeassistant.const import (
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
)
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.exceptions import ConfigEntryNotReady
from pyatrea import Atrea

from .utils import update_listener
from .const import DOMAIN, LOGGER


async def async_migrate_entry(hass, config_entry: ConfigEntry):
    """Migrate old entry."""
    LOGGER.debug("Migrating from version %s", config_entry.version)
    LOGGER.info("Migration to version %s successful", config_entry.version)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    await hass.config_entries.async_forward_entry_unload(entry, "climate")
    await hass.config_entries.async_forward_entry_unload(entry, "update")
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    async def async_update_data():
        hass.data[DOMAIN][entry.entry_id]["status"] = await hass.async_add_executor_job(
            atrea.getStatus, False
        )
        hass.data[DOMAIN][entry.entry_id]["params"] = await hass.async_add_executor_job(
            atrea.getParams, False
        )
        hass.data[DOMAIN][entry.entry_id]["supportedModes"] = (
            await hass.async_add_executor_job(atrea.getSupportedModes)
        ).items()
        hass.data[DOMAIN][entry.entry_id][
            "userLabels"
        ] = await hass.async_add_executor_job(atrea.loadUserLabels)

    atreaCoordinator = DataUpdateCoordinator(
        hass, LOGGER, name="Atrea resource status", update_method=async_update_data,
    )

    atrea = Atrea(entry.data.get(CONF_IP_ADDRESS), entry.data.get(CONF_PASSWORD))

    status = await hass.async_add_executor_job(atrea.getStatus, False)

    if not status:
        raise ConfigEntryNotReady("Incorrect password or too many signed in users.")
    else:
        hass.data[DOMAIN] = {}
        hass.data[DOMAIN][entry.entry_id] = {
            "atrea": atrea,
            "update_listener": entry.add_update_listener(update_listener),
            "coordinator": atreaCoordinator,
            "supportedModes": (
                await hass.async_add_executor_job(atrea.getSupportedModes)
            ).items(),
            "userLabels": (await hass.async_add_executor_job(atrea.loadUserLabels)),
            "status": status,
            "params": (await hass.async_add_executor_job(atrea.getParams, False)),
            "translations": (await hass.async_add_executor_job(atrea.getTranslations)),
            "configDir": (await hass.async_add_executor_job(atrea.getConfigDir)),
        }
        entry.async_on_unload(hass.data[DOMAIN][entry.entry_id]["update_listener"])

        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, "climate")
        )
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, "update")
        )
        return True
