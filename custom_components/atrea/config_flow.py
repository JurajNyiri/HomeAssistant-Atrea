from homeassistant import config_entries
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, CONF_NAME
from homeassistant.core import callback
from .utils import isAtreaUnit, processFanModes
import voluptuous as vol
from .const import (
    CONF_FAN_MODES,
    DOMAIN,
    LOGGER,
    CONF_PRESETS,
    ALL_PRESET_LIST,
    DEFAULT_FAN_MODE_LIST,
)
from pyatrea import Atrea


@config_entries.HANDLERS.register(DOMAIN)
class FlowHandler(config_entries.ConfigFlow):
    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return AtreaOptionsFlowHandler(config_entry)

    async def async_step_user(self, user_input=None):
        """Handle a flow initialized by the user."""
        LOGGER.debug("[ADD DEVICE] Setup process for tapo initiated by user.")
        return await self.async_step_ip()

    async def async_step_dhcp(self, dhcp_discovery):
        return await self.async_step_auth()

    @callback
    def _async_host_already_configured(self, host):
        """See if we already have an entry matching the host."""
        for entry in self._async_current_entries():
            if entry.data.get(CONF_IP_ADDRESS) == host:
                return True
        return False

    async def async_step_ip(self, user_input=None):
        """Enter IP Address and verify Tapo device"""
        errors = {}
        host = ""
        if user_input is not None:
            LOGGER.debug("[ADD DEVICE] Verifying IP address")
            try:
                host = user_input[CONF_IP_ADDRESS]

                if self._async_host_already_configured(host):
                    LOGGER.debug("[ADD DEVICE][%s] IP already configured.", host)
                    raise Exception("already_configured")

                LOGGER.debug(
                    "[ADD DEVICE][%s] Verifying IP address being atrea unit", host
                )
                if not (await self.hass.async_add_executor_job(isAtreaUnit, host)):
                    raise Exception("not_atrea_unit")

                self.atreaHost = host
                return await self.async_step_auth()

            except Exception as e:
                LOGGER.debug(e)
                if "Failed to establish a new connection" in str(e):
                    errors["base"] = "connection_failed"
                elif "already_configured" in str(e):
                    errors["base"] = "already_configured"
                elif "not_atrea_unit" in str(e):
                    errors["base"] = "not_atrea_unit"
                else:
                    errors["base"] = "unknown"
                    LOGGER.error(e)
                LOGGER.warn(errors)

        LOGGER.debug("[ADD DEVICE] Showing config flow for IP.")
        return self.async_show_form(
            step_id="ip",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_IP_ADDRESS, description={"suggested_value": host}
                    ): str,
                }
            ),
            errors=errors,
        )

    async def async_step_auth(self, user_input=None):
        """Provide authentication data."""
        errors = {}
        name = "Atrea"
        password = ""
        host = self.atreaHost
        if user_input is not None:
            try:
                LOGGER.debug("[ADD DEVICE][%s] Verifying password.", host)
                name = user_input[CONF_NAME]
                password = user_input[CONF_PASSWORD]

                self.atreaPassword = password

                atrea = Atrea(self.atreaHost, self.atreaPassword)
                status = await self.hass.async_add_executor_job(atrea.getStatus)
                if not status:
                    raise Exception("Invalid authentication data")

                LOGGER.debug("[ADD DEVICE][%s] Creating new entry.", host)
                return self.async_create_entry(
                    title=host,
                    data={
                        CONF_IP_ADDRESS: host,
                        CONF_PASSWORD: password,
                        CONF_NAME: name,
                    },
                )

            except Exception as e:
                LOGGER.debug(e)
                if "Failed to establish a new connection" in str(e):
                    errors["base"] = "connection_failed"
                elif str(e) == "Invalid authentication data":
                    errors["base"] = "invalid_auth"
                else:
                    errors["base"] = "unknown"
                    LOGGER.error(e)

        LOGGER.debug(
            "[ADD DEVICE][%s] Showing config flow for password.", host,
        )
        return self.async_show_form(
            step_id="auth",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, description={"suggested_value": name}): str,
                    vol.Required(
                        CONF_PASSWORD, description={"suggested_value": password}
                    ): str,
                }
            ),
            errors=errors,
        )


class AtreaOptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry
        self.options = dict(config_entry.options)

    async def async_step_init(self, user_input=None):
        errors = {}
        host = self.config_entry.data[CONF_IP_ADDRESS]

        name = ""
        if CONF_NAME in self.config_entry.data:
            name = self.config_entry.data[CONF_NAME]

        password = ""
        if CONF_PASSWORD in self.config_entry.data:
            password = self.config_entry.data[CONF_PASSWORD]

        presets = []
        if CONF_PRESETS in self.config_entry.data:
            presets = self.config_entry.data[CONF_PRESETS]

        fan_modes = DEFAULT_FAN_MODE_LIST
        try:
            if CONF_FAN_MODES in self.config_entry.data and processFanModes(
                self.config_entry.data[CONF_FAN_MODES]
            ):
                fan_modes = self.config_entry.data[CONF_FAN_MODES]
        except Exception as e:
            LOGGER.debug("Incorrect fan modes: " + e)
            # pass

        LOGGER.debug(
            "[%s] Opened Atrea options.", self.config_entry.data[CONF_IP_ADDRESS]
        )
        if user_input is not None:
            LOGGER.debug("Verifying user input...")
            try:
                LOGGER.debug("Loading name...")
                if CONF_NAME in user_input:
                    name = user_input[CONF_NAME]

                LOGGER.debug("Loading password...")
                if CONF_PASSWORD in user_input:
                    password = user_input[CONF_PASSWORD]

                LOGGER.debug("Loading fan_modes...")
                if CONF_FAN_MODES in user_input:
                    fan_modes = user_input[CONF_FAN_MODES]

                LOGGER.debug("Verifying format of fan modes...")
                if not processFanModes(fan_modes):
                    raise Exception("Invalid fan mode format")

                LOGGER.debug("Preparing save object: ip, password, name")
                data = {CONF_IP_ADDRESS: host, CONF_PASSWORD: password, CONF_NAME: name}
                LOGGER.debug("Preparing save object: fan_modes")
                data[CONF_FAN_MODES] = fan_modes
                LOGGER.debug("Preparing save object: presets")
                data[CONF_PRESETS] = {}
                for preset in ALL_PRESET_LIST:
                    if preset in user_input:
                        LOGGER.debug("test")
                        data[CONF_PRESETS][preset] = user_input[preset]
                        LOGGER.debug("test2")

                LOGGER.debug("Verifying password...")
                if password != self.config_entry.data[CONF_PASSWORD]:
                    atrea = Atrea(host, password)
                    status = await self.hass.async_add_executor_job(atrea.getStatus)
                    if not status:
                        raise Exception("Invalid authentication data")

                LOGGER.debug("Saving entity...")
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=data,
                )
                return self.async_create_entry(title="", data=None)
            except Exception as e:
                LOGGER.debug(e)
                if "Failed to establish a new connection" in str(e):
                    errors["base"] = "connection_failed"
                elif str(e) == "Invalid authentication data":
                    errors["base"] = "invalid_auth"
                elif str(e) == "Invalid fan mode format":
                    errors["base"] = "invalid_fan_mode"
                else:
                    errors["base"] = "unknown"
                    LOGGER.error(e)

        LOGGER.debug("Preparing form... password, name, fan_modes, presets header")
        spec = {
            vol.Required(CONF_PASSWORD, description={"suggested_value": password}): str,
            vol.Optional(CONF_NAME, description={"suggested_value": name}): str,
            vol.Optional(
                CONF_FAN_MODES, description={"suggested_value": fan_modes}
            ): str,
            vol.Optional(CONF_PRESETS, description={"suggested_value": None}): vol.In(
                []
            ),
        }

        LOGGER.debug("Preparing form... presets")
        for preset in ALL_PRESET_LIST:
            LOGGER.warn(preset)
            if preset in presets:
                spec[
                    vol.Required(
                        preset, description={"suggested_value": presets[preset]}
                    )
                ] = bool
            else:
                spec[vol.Required(preset, description={"suggested_value": True})] = bool

        LOGGER.debug("Returning form.")

        return self.async_show_form(
            step_id="init", data_schema=vol.Schema(spec), errors=errors,
        )
