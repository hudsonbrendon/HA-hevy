"""Adds config flow for Hevy."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_create_clientsession

if TYPE_CHECKING:
    from collections.abc import Mapping

from .api import (
    HevyApiClient,
    HevyApiClientAuthenticationError,
    HevyApiClientCommunicationError,
    HevyApiClientError,
)
from .const import (
    CONF_API_KEY,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_WORKOUTS_COUNT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_WORKOUTS_COUNT,
    DOMAIN,
    LOGGER,
    MAX_SCAN_INTERVAL,
    MAX_WORKOUTS_COUNT,
    MIN_SCAN_INTERVAL,
    MIN_WORKOUTS_COUNT,
)


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

    async def async_step_reauth(
        self,
        entry_data: Mapping[str, Any],  # noqa: ARG002
    ) -> config_entries.ConfigFlowResult:
        """Handle a reauth triggered by ConfigEntryAuthFailed in the coordinator."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self,
        user_input: dict | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Prompt the user for a fresh API key and update the existing entry."""
        errors: dict[str, str] = {}
        if user_input is not None:
            try:
                await self._test_credentials(api_key=user_input[CONF_API_KEY])
            except HevyApiClientAuthenticationError as exception:
                LOGGER.warning(exception)
                errors["base"] = "auth"
            except HevyApiClientCommunicationError as exception:
                LOGGER.error(exception)
                errors["base"] = "connection"
            except HevyApiClientError as exception:
                LOGGER.exception(exception)
                errors["base"] = "unknown"
            else:
                entry = self.hass.config_entries.async_get_entry(
                    self.context["entry_id"]
                )
                self.hass.config_entries.async_update_entry(
                    entry,
                    data={**entry.data, CONF_API_KEY: user_input[CONF_API_KEY]},
                    unique_id=user_input[CONF_API_KEY],
                )
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reauth_successful")

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_API_KEY): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.PASSWORD,
                        ),
                    ),
                }
            ),
            errors=errors,
        )

    async def _test_credentials(self, api_key: str) -> None:
        """Validate API key."""
        client = HevyApiClient(
            api_key=api_key,
            session=async_create_clientsession(self.hass),
        )
        await client.async_get_workout_count()

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> HevyOptionsFlow:
        """Return the options flow handler."""
        return HevyOptionsFlow(config_entry)


class HevyOptionsFlow(config_entries.OptionsFlow):
    """Handle tweaking polling interval and page size after setup."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage the integration options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=current.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    ): vol.All(
                        vol.Coerce(int),
                        vol.Range(min=MIN_SCAN_INTERVAL, max=MAX_SCAN_INTERVAL),
                    ),
                    vol.Optional(
                        CONF_WORKOUTS_COUNT,
                        default=current.get(
                            CONF_WORKOUTS_COUNT, DEFAULT_WORKOUTS_COUNT
                        ),
                    ): vol.All(
                        vol.Coerce(int),
                        vol.Range(min=MIN_WORKOUTS_COUNT, max=MAX_WORKOUTS_COUNT),
                    ),
                }
            ),
        )
