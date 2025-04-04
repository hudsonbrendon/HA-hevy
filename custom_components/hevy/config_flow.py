"""Adds config flow for Hevy."""

from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .api import (
    HevyApiClient,
    HevyApiClientAuthenticationError,
    HevyApiClientCommunicationError,
    HevyApiClientError,
)
from .const import CONF_API_KEY, CONF_NAME, DOMAIN, LOGGER


class HevyFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Hevy."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by the user."""
        _errors = {}
        if user_input is not None:
            try:
                await self._test_credentials(
                    api_key=user_input[CONF_API_KEY],
                )
            except HevyApiClientAuthenticationError as exception:
                LOGGER.warning(exception)
                _errors["base"] = "auth"
            except HevyApiClientCommunicationError as exception:
                LOGGER.error(exception)
                _errors["base"] = "connection"
            except HevyApiClientError as exception:
                LOGGER.exception(exception)
                _errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(user_input[CONF_API_KEY])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"Hevy - {user_input[CONF_NAME]}",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_NAME,
                        default=(user_input or {}).get(CONF_NAME, vol.UNDEFINED),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT,
                        ),
                    ),
                    vol.Required(
                        CONF_API_KEY,
                        default=(user_input or {}).get(CONF_API_KEY, vol.UNDEFINED),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD,
                        ),
                    ),
                },
            ),
            errors=_errors,
        )

    async def _test_credentials(self, api_key: str) -> None:
        """Validate API key."""
        client = HevyApiClient(
            api_key=api_key,
            session=async_create_clientsession(self.hass),
        )
        await client.async_get_workout_count()
