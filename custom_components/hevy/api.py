"""Hevy API Client."""

from __future__ import annotations

import socket
from typing import Any

import aiohttp
import async_timeout

from .const import BASE_URL, DEFAULT_WORKOUTS_COUNT


class HevyApiClientError(Exception):
    """Exception to indicate a general API error."""


class HevyApiClientCommunicationError(
    HevyApiClientError,
):
    """Exception to indicate a communication error."""


class HevyApiClientAuthenticationError(
    HevyApiClientError,
):
    """Exception to indicate an authentication error."""


def _verify_response_or_raise(response: aiohttp.ClientResponse) -> None:
    """Verify that the response is valid."""
    if response.status in (401, 403):
        msg = "Invalid API key"
        raise HevyApiClientAuthenticationError(
            msg,
        )
    response.raise_for_status()


class HevyApiClient:
    """Hevy API Client."""

    def __init__(
        self,
        api_key: str,
        session: aiohttp.ClientSession,
    ) -> None:
        """Initialize Hevy API Client."""
        self._api_key = api_key
        self._session = session
        self._headers = {
            "accept": "application/json",
            "api-key": api_key,
        }

    async def async_get_workout_count(self) -> dict[str, Any]:
        """Get workout count from the API."""
        return await self._api_wrapper(
            method="get",
            url=f"{BASE_URL}/workouts/count",
        )

    async def async_get_workouts(
        self, page: int = 1, page_size: int = DEFAULT_WORKOUTS_COUNT
    ) -> dict[str, Any]:
        """Get workouts from the API."""
        return await self._api_wrapper(
            method="get",
            url=f"{BASE_URL}/workouts",
            params={"page": page, "pageSize": page_size},
        )

    async def async_get_user_info(self) -> dict[str, Any]:
        """Get authenticated user info."""
        return await self._api_wrapper(
            method="get",
            url=f"{BASE_URL}/user/info",
        )

    async def async_get_body_measurements(
        self, page: int = 1, page_size: int = 10
    ) -> dict[str, Any]:
        """Get body measurements (paginated, max 10 per page)."""
        return await self._api_wrapper(
            method="get",
            url=f"{BASE_URL}/body_measurements",
            params={"page": page, "pageSize": page_size},
        )

    async def _api_wrapper(
        self,
        method: str,
        url: str,
        params: dict | None = None,
        data: dict | None = None,
    ) -> Any:
        """Get information from the API."""
        try:
            async with async_timeout.timeout(10):
                response = await self._session.request(
                    method=method,
                    url=url,
                    headers=self._headers,
                    params=params,
                    json=data,
                )
                _verify_response_or_raise(response)
                return await response.json()

        except TimeoutError as exception:
            msg = f"Timeout error fetching information - {exception}"
            raise HevyApiClientCommunicationError(
                msg,
            ) from exception
        except (aiohttp.ClientError, socket.gaierror) as exception:
            msg = f"Error fetching information - {exception}"
            raise HevyApiClientCommunicationError(
                msg,
            ) from exception
        except HevyApiClientError:
            raise
        except Exception as exception:  # pylint: disable=broad-except
            msg = f"Something really wrong happened! - {exception}"
            raise HevyApiClientError(
                msg,
            ) from exception
