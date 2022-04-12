from homeassistant import config_entries
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD
from homeassistant.core import callback
from .utils import isAtreaUnit
import voluptuous as vol
from .const import (
    DOMAIN,
    LOGGER,
)
from pyatrea import Atrea


@config_entries.HANDLERS.register(DOMAIN)
class FlowHandler(config_entries.ConfigFlow):
    VERSION = 1

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
        password = ""
        host = self.atreaHost
        if user_input is not None:
            try:
                LOGGER.debug("[ADD DEVICE][%s] Verifying password.", host)
                password = user_input[CONF_PASSWORD]

                self.atreaPassword = password

                atrea = Atrea(self.atreaHost, self.atreaPassword)
                status = await self.hass.async_add_executor_job(atrea.getStatus)
                if not status:
                    raise Exception("Invalid authentication data")

                LOGGER.debug("[ADD DEVICE][%s] Creating new entry.", host)
                return self.async_create_entry(
                    title=host, data={CONF_IP_ADDRESS: host, CONF_PASSWORD: password,},
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
                    vol.Required(
                        CONF_PASSWORD, description={"suggested_value": password}
                    ): str,
                }
            ),
            errors=errors,
        )
