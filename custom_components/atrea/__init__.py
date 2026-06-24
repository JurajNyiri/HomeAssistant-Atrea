from homeassistant.const import (
    CONF_IP_ADDRESS,
    CONF_PORT,
    CONF_PASSWORD,
    CONF_NAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.exceptions import ConfigEntryNotReady
from pyatrea import Atrea

from .utils import update_listener
from .const import DOMAIN, LOGGER, MIN_TIME_BETWEEN_SCANS

PLATFORMS = ["binary_sensor", "climate", "select", "sensor", "update"]


async def async_migrate_entry(hass, config_entry: ConfigEntry):
    """Migrate old entry."""
    LOGGER.debug("Migrating from version %s", config_entry.version)

    new = {**config_entry.data}
    if config_entry.version == 1:
        new[CONF_PORT] = 80
        hass.config_entries.async_update_entry(config_entry, data=new, version=2)
        LOGGER.info("Migration to version %s successful", 2)
        return True

    LOGGER.info("Migration to version %s successful", config_entry.version)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if DOMAIN in hass.data:
        hass.data[DOMAIN].pop(entry.entry_id, None)
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
        hass.data[DOMAIN][entry.entry_id]["userLabels"] = (
            await hass.async_add_executor_job(atrea.loadUserLabels)
        )
        hass.data[DOMAIN][entry.entry_id]["supportedForcedModes"] = (
            await hass.async_add_executor_job(atrea.getSupportedForcedModes)
        ).items()

    atreaCoordinator = DataUpdateCoordinator(
        hass,
        LOGGER,
        name="Atrea resource status",
        update_method=async_update_data,
        update_interval=MIN_TIME_BETWEEN_SCANS,
    )

    atrea = Atrea(
        entry.data.get(CONF_IP_ADDRESS),
        entry.data.get(CONF_PORT),
        entry.data.get(CONF_PASSWORD),
    )

    status = await hass.async_add_executor_job(atrea.getStatus, False)

    if not status:
        raise ConfigEntryNotReady("Incorrect password or too many signed in users.")
    else:
        hass.data.setdefault(DOMAIN, {})

        hass.data[DOMAIN][entry.entry_id] = {
            "atrea": atrea,
            "name": entry.data.get(CONF_NAME, "Atrea"),
            "update_listener": entry.add_update_listener(update_listener),
            "coordinator": atreaCoordinator,
            "supportedModes": (
                await hass.async_add_executor_job(atrea.getSupportedModes)
            ).items(),
            "userLabels": (await hass.async_add_executor_job(atrea.loadUserLabels)),
            "supportedForcedModes": (
                await hass.async_add_executor_job(atrea.getSupportedForcedModes)
            ).items(),
            "status": status,
            "model": (await hass.async_add_executor_job(atrea.getModel)),
            "params": (await hass.async_add_executor_job(atrea.getParams, False)),
            "translations": (await hass.async_add_executor_job(atrea.getTranslations)),
            "configDir": (await hass.async_add_executor_job(atrea.getConfigDir)),
        }
        entry.async_on_unload(hass.data[DOMAIN][entry.entry_id]["update_listener"])

        await hass.async_create_task(
            hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
        )
        return True
