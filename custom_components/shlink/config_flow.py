"""Config flow for Shlink."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY, CONF_URL
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import ShlinkApi, ShlinkApiError, ShlinkAuthError
from .const import CONF_VERIFY_SSL, DOMAIN


class ShlinkConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Shlink."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            url = user_input[CONF_URL].strip().rstrip("/")
            api_key = user_input[CONF_API_KEY].strip()
            verify_ssl = user_input[CONF_VERIFY_SSL]

            session = async_get_clientsession(self.hass, verify_ssl=verify_ssl)
            api = ShlinkApi(session, url, api_key, verify_ssl)

            try:
                links = await api.get_short_urls()
            except ShlinkAuthError:
                errors["base"] = "invalid_auth"
            except ShlinkApiError:
                errors["base"] = "cannot_connect"
            else:
                await self.async_set_unique_id(url.lower())
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Shlink",
                    data={
                        CONF_URL: url,
                        CONF_API_KEY: api_key,
                        CONF_VERIFY_SSL: verify_ssl,
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_URL,
                    default=(user_input or {}).get(CONF_URL, "http://"),
                ): str,
                vol.Required(
                    CONF_API_KEY,
                    default=(user_input or {}).get(CONF_API_KEY, ""),
                ): str,
                vol.Required(
                    CONF_VERIFY_SSL,
                    default=(user_input or {}).get(CONF_VERIFY_SSL, True),
                ): bool,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )
