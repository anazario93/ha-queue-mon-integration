"""Config flow for Asterisk Queue Monitor."""

from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_USERNAME, CONF_PASSWORD

from .const import DOMAIN, DEFAULT_PORT, CONF_REFRESH_INTERVAL, DEFAULT_REFRESH_INTERVAL, CONF_SECRET


class AsteriskQueueMonitorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for the integration."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Configure AMI access."""
        errors = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            port = user_input[CONF_PORT]
            username = user_input[CONF_USERNAME].strip()
            secret = user_input[CONF_PASSWORD]
            await self.async_set_unique_id(f"{host}:{port}:{username}")
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"Asterisk Queue Monitor ({host})",
                data={
                    CONF_HOST: host,
                    CONF_PORT: port,
                    CONF_USERNAME: username,
                    CONF_SECRET: secret,
                },
            )

        schema = vol.Schema({
            vol.Required(CONF_HOST): str,
            vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): str,
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    def async_get_options_flow(config_entry):
        return AsteriskQueueMonitorOptionsFlow(config_entry)


class AsteriskQueueMonitorOptionsFlow(config_entries.OptionsFlow):
    """Options flow for refresh frequency."""

    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        schema = vol.Schema({
            vol.Optional(
                CONF_REFRESH_INTERVAL,
                default=self.config_entry.options.get(CONF_REFRESH_INTERVAL, DEFAULT_REFRESH_INTERVAL),
            ): vol.All(int, vol.Range(min=1, max=120)),
        })
        return self.async_show_form(step_id="init", data_schema=schema)
