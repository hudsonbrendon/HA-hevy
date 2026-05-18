"""Tests for HevyFlowHandler — user setup + reauth."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.hevy.api import (
    HevyApiClientAuthenticationError,
    HevyApiClientCommunicationError,
)
from custom_components.hevy.config_flow import HevyFlowHandler
from custom_components.hevy.const import CONF_API_KEY, CONF_NAME


def _make_handler(
    *,
    entry_id: str = "entry-abc",
    test_credentials_side_effect: Any = None,
) -> HevyFlowHandler:
    handler = HevyFlowHandler()
    handler.hass = MagicMock()
    handler.hass.config_entries.async_get_entry = MagicMock(
        return_value=SimpleNamespace(
            entry_id=entry_id, data={CONF_API_KEY: "old-key", CONF_NAME: "Hudson"}
        )
    )
    handler.hass.config_entries.async_update_entry = MagicMock()
    handler.hass.config_entries.async_reload = AsyncMock()
    handler.context = {"entry_id": entry_id}
    handler._test_credentials = AsyncMock(side_effect=test_credentials_side_effect)
    return handler


@pytest.mark.asyncio
class TestReauthConfirm:
    async def test_initial_call_shows_form(self) -> None:
        handler = _make_handler()
        result = await handler.async_step_reauth_confirm()
        assert result["type"] == "form"
        assert result["step_id"] == "reauth_confirm"
        assert result["errors"] == {}

    async def test_auth_error_keeps_form_with_error(self) -> None:
        handler = _make_handler(
            test_credentials_side_effect=HevyApiClientAuthenticationError("bad")
        )
        result = await handler.async_step_reauth_confirm(
            user_input={CONF_API_KEY: "still-bad"}
        )
        assert result["type"] == "form"
        assert result["errors"] == {"base": "auth"}

    async def test_connection_error_shown(self) -> None:
        handler = _make_handler(
            test_credentials_side_effect=HevyApiClientCommunicationError("network")
        )
        result = await handler.async_step_reauth_confirm(
            user_input={CONF_API_KEY: "key"}
        )
        assert result["errors"] == {"base": "connection"}

    async def test_success_updates_entry_and_reloads(self) -> None:
        handler = _make_handler(entry_id="entry-abc")
        result = await handler.async_step_reauth_confirm(
            user_input={CONF_API_KEY: "new-key"}
        )

        handler.hass.config_entries.async_update_entry.assert_called_once()
        update_kwargs = handler.hass.config_entries.async_update_entry.call_args.kwargs
        assert update_kwargs["data"][CONF_API_KEY] == "new-key"
        assert update_kwargs["data"][CONF_NAME] == "Hudson"
        assert update_kwargs["unique_id"] == "new-key"

        handler.hass.config_entries.async_reload.assert_awaited_once_with("entry-abc")
        assert result == {"type": "abort", "reason": "reauth_successful"}

    async def test_step_reauth_routes_to_confirm(self) -> None:
        handler = _make_handler()
        result = await handler.async_step_reauth({"api_key": "old-key"})
        # First call goes straight to confirm (which shows form when no input).
        assert result["type"] == "form"
        assert result["step_id"] == "reauth_confirm"
