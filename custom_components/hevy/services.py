"""Service handlers for the Hevy integration."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .api import HevyApiClientConflictError, HevyApiClientError
from .const import DOMAIN, LOGGER

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, ServiceCall

SERVICE_LOG_BODY_MEASUREMENT = "log_body_measurement"
SERVICE_REFRESH = "refresh"

ATTR_ENTRY_ID = "entry_id"
ATTR_DATE = "date"
ATTR_WEIGHT_KG = "weight_kg"
ATTR_FAT_PERCENT = "fat_percent"
ATTR_LEAN_MASS_KG = "lean_mass_kg"

_OPTIONAL_MEASUREMENT_FIELDS = (
    ATTR_WEIGHT_KG,
    ATTR_FAT_PERCENT,
    ATTR_LEAN_MASS_KG,
    "neck_cm",
    "shoulder_cm",
    "chest_cm",
    "left_bicep_cm",
    "right_bicep_cm",
    "left_forearm_cm",
    "right_forearm_cm",
    "abdomen",
    "waist",
    "hips",
    "left_thigh",
    "right_thigh",
    "left_calf",
    "right_calf",
)

LOG_BODY_MEASUREMENT_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ENTRY_ID): cv.string,
        vol.Optional(ATTR_DATE): cv.date,
        **{
            vol.Optional(field): vol.Coerce(float)
            for field in _OPTIONAL_MEASUREMENT_FIELDS
        },
    }
)

REFRESH_SCHEMA = vol.Schema({vol.Optional(ATTR_ENTRY_ID): cv.string})


def _resolve_entry(hass: HomeAssistant, entry_id: str | None) -> Any:
    """Look up the Hevy config entry matching entry_id, or the only one."""
    entries = hass.config_entries.async_entries(DOMAIN)
    if not entries:
        msg = "No Hevy integration is configured."
        raise ServiceValidationError(msg)
    if entry_id is not None:
        for entry in entries:
            if entry.entry_id == entry_id:
                return entry
        msg = f"No Hevy config entry with id {entry_id!r}."
        raise ServiceValidationError(msg)
    if len(entries) > 1:
        msg = "Multiple Hevy integrations configured; pass 'entry_id' to target one."
        raise ServiceValidationError(msg)
    return entries[0]


def _build_measurement_payload(
    call_data: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    """Extract (date_str, body) from the service call data."""
    raw_date = call_data.get(ATTR_DATE) or datetime.now(tz=UTC).date()
    if isinstance(raw_date, date) and not isinstance(raw_date, datetime):
        date_str = raw_date.isoformat()
    elif isinstance(raw_date, datetime):
        date_str = raw_date.date().isoformat()
    else:
        date_str = str(raw_date)
    body = {
        field: call_data[field]
        for field in _OPTIONAL_MEASUREMENT_FIELDS
        if field in call_data
    }
    if not body:
        msg = "log_body_measurement requires at least one measurement field."
        raise ServiceValidationError(msg)
    body["date"] = date_str
    return date_str, body


async def _handle_log_body_measurement(hass: HomeAssistant, call: ServiceCall) -> None:
    entry = _resolve_entry(hass, call.data.get(ATTR_ENTRY_ID))
    date_str, body = _build_measurement_payload(call.data)
    client = entry.runtime_data.client
    try:
        await client.async_create_body_measurement(body)
    except HevyApiClientConflictError:
        # Entry already exists for the date → overwrite via PUT.
        put_body = {k: v for k, v in body.items() if k != "date"}
        try:
            await client.async_update_body_measurement(date_str, put_body)
        except HevyApiClientError as err:
            msg = f"Failed to update body measurement for {date_str}: {err}"
            raise HomeAssistantError(msg) from err
    except HevyApiClientError as err:
        msg = f"Failed to log body measurement: {err}"
        raise HomeAssistantError(msg) from err
    await entry.runtime_data.coordinator.async_request_refresh()


async def _handle_refresh(hass: HomeAssistant, call: ServiceCall) -> None:
    entry = _resolve_entry(hass, call.data.get(ATTR_ENTRY_ID))
    LOGGER.debug("Refreshing Hevy coordinator for entry %s", entry.entry_id)
    await entry.runtime_data.coordinator.async_request_refresh()


def async_register_services(hass: HomeAssistant) -> None:
    """Register integration-level services if not already registered."""
    if hass.services.has_service(DOMAIN, SERVICE_LOG_BODY_MEASUREMENT):
        return

    async def log_body(call: ServiceCall) -> None:
        await _handle_log_body_measurement(hass, call)

    async def refresh(call: ServiceCall) -> None:
        await _handle_refresh(hass, call)

    hass.services.async_register(
        DOMAIN,
        SERVICE_LOG_BODY_MEASUREMENT,
        log_body,
        schema=LOG_BODY_MEASUREMENT_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REFRESH,
        refresh,
        schema=REFRESH_SCHEMA,
    )


def async_unregister_services(hass: HomeAssistant) -> None:
    """Drop services when the last config entry is removed."""
    if hass.config_entries.async_entries(DOMAIN):
        return
    hass.services.async_remove(DOMAIN, SERVICE_LOG_BODY_MEASUREMENT)
    hass.services.async_remove(DOMAIN, SERVICE_REFRESH)
