"""Tests for HevyApiClient (mocked aiohttp session)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest

from custom_components.hevy.api import (
    HevyApiClient,
    HevyApiClientAuthenticationError,
    HevyApiClientCommunicationError,
    HevyApiClientError,
)


def _build_response(*, status: int = 200, json_payload: Any = None) -> MagicMock:
    """Build a mock aiohttp response."""
    response = MagicMock()
    response.status = status
    response.json = AsyncMock(return_value=json_payload or {})
    response.raise_for_status = MagicMock()
    if status >= 400 and status not in (401, 403):
        response.raise_for_status.side_effect = aiohttp.ClientResponseError(
            request_info=MagicMock(),
            history=(),
            status=status,
        )
    return response


def _build_session(response: MagicMock) -> MagicMock:
    session = MagicMock(spec=aiohttp.ClientSession)
    session.request = AsyncMock(return_value=response)
    return session


@pytest.mark.asyncio
class TestEndpointDispatch:
    async def test_workout_count_hits_count_endpoint(self) -> None:
        response = _build_response(json_payload={"workout_count": 7})
        session = _build_session(response)
        client = HevyApiClient(api_key="key", session=session)

        result = await client.async_get_workout_count()

        assert result == {"workout_count": 7}
        kwargs = session.request.await_args.kwargs
        assert kwargs["method"] == "get"
        assert kwargs["url"].endswith("/workouts/count")
        assert kwargs["headers"]["api-key"] == "key"

    async def test_workouts_passes_pagination_params(self) -> None:
        response = _build_response(json_payload={"workouts": []})
        session = _build_session(response)
        client = HevyApiClient(api_key="key", session=session)

        await client.async_get_workouts(page=2, page_size=5)

        kwargs = session.request.await_args.kwargs
        assert kwargs["params"] == {"page": 2, "pageSize": 5}
        assert kwargs["url"].endswith("/workouts")

    async def test_user_info_endpoint(self) -> None:
        response = _build_response(json_payload={"data": {"id": "x"}})
        session = _build_session(response)
        client = HevyApiClient(api_key="key", session=session)

        await client.async_get_user_info()

        assert session.request.await_args.kwargs["url"].endswith("/user/info")

    async def test_body_measurements_passes_pagination(self) -> None:
        response = _build_response(json_payload={"body_measurements": []})
        session = _build_session(response)
        client = HevyApiClient(api_key="key", session=session)

        await client.async_get_body_measurements(page=3, page_size=10)

        kwargs = session.request.await_args.kwargs
        assert kwargs["params"] == {"page": 3, "pageSize": 10}
        assert kwargs["url"].endswith("/body_measurements")


@pytest.mark.asyncio
class TestErrorHandling:
    async def test_401_raises_authentication_error(self) -> None:
        response = _build_response(status=401)
        session = _build_session(response)
        client = HevyApiClient(api_key="bad", session=session)

        with pytest.raises(HevyApiClientAuthenticationError):
            await client.async_get_workout_count()

    async def test_403_raises_authentication_error(self) -> None:
        response = _build_response(status=403)
        session = _build_session(response)
        client = HevyApiClient(api_key="bad", session=session)

        with pytest.raises(HevyApiClientAuthenticationError):
            await client.async_get_workout_count()

    async def test_500_raises_communication_error(self) -> None:
        response = _build_response(status=500)
        session = _build_session(response)
        client = HevyApiClient(api_key="key", session=session)

        with pytest.raises(HevyApiClientCommunicationError):
            await client.async_get_workout_count()

    async def test_timeout_raises_communication_error(self) -> None:
        session = MagicMock(spec=aiohttp.ClientSession)
        session.request = AsyncMock(side_effect=TimeoutError("boom"))
        client = HevyApiClient(api_key="key", session=session)

        with pytest.raises(HevyApiClientCommunicationError):
            await client.async_get_workout_count()

    async def test_client_error_raises_communication_error(self) -> None:
        session = MagicMock(spec=aiohttp.ClientSession)
        session.request = AsyncMock(
            side_effect=aiohttp.ClientConnectionError("network down")
        )
        client = HevyApiClient(api_key="key", session=session)

        with pytest.raises(HevyApiClientCommunicationError):
            await client.async_get_workout_count()

    async def test_unexpected_exception_wrapped(self) -> None:
        session = MagicMock(spec=aiohttp.ClientSession)
        session.request = AsyncMock(side_effect=ValueError("weird"))
        client = HevyApiClient(api_key="key", session=session)

        with pytest.raises(HevyApiClientError):
            await client.async_get_workout_count()
