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
SERVICE_CREATE_WORKOUT = "create_workout"

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


def _coerce_iso_datetime(value: Any) -> str:
    """Accept a datetime, date, or ISO 8601 string and return an ISO string."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time(), tzinfo=UTC).isoformat()
    if isinstance(value, str):
        # Round-trip to validate format (fromisoformat handles trailing Z).
        try:
            return datetime.fromisoformat(value).isoformat()
        except ValueError as err:
            msg = f"Invalid ISO 8601 timestamp: {value!r}"
            raise vol.Invalid(msg) from err
    msg = f"Expected datetime, date, or ISO string; got {type(value).__name__}"
    raise vol.Invalid(msg)


ATTR_TITLE = "title"
ATTR_DESCRIPTION = "description"
ATTR_START_TIME = "start_time"
ATTR_END_TIME = "end_time"
ATTR_IS_PRIVATE = "is_private"
ATTR_EXERCISES = "exercises"

_SET_TYPES = ("warmup", "normal", "failure", "dropset")

_SET_SCHEMA = vol.Schema(
    {
        vol.Optional("type", default="normal"): vol.In(_SET_TYPES),
        vol.Optional("weight_kg"): vol.Coerce(float),
        vol.Optional("reps"): vol.Coerce(int),
        vol.Optional("distance_meters"): vol.Coerce(int),
        vol.Optional("duration_seconds"): vol.Coerce(int),
        vol.Optional("custom_metric"): vol.Coerce(float),
        vol.Optional("rpe"): vol.Coerce(float),
    }
)

_EXERCISE_SCHEMA = vol.Schema(
    {
        vol.Required("exercise_template_id"): cv.string,
        vol.Optional("notes"): cv.string,
        vol.Optional("superset_id"): vol.Coerce(int),
        vol.Required("sets"): [_SET_SCHEMA],
    }
)

CREATE_WORKOUT_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_ENTRY_ID): cv.string,
        vol.Required(ATTR_TITLE): cv.string,
        vol.Optional(ATTR_DESCRIPTION): cv.string,
        vol.Required(ATTR_START_TIME): _coerce_iso_datetime,
        vol.Required(ATTR_END_TIME): _coerce_iso_datetime,
        vol.Optional(ATTR_IS_PRIVATE, default=False): cv.boolean,
        vol.Required(ATTR_EXERCISES): vol.All([_EXERCISE_SCHEMA], vol.Length(min=1)),
    }
)


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


def _build_create_workout_body(call_data: dict[str, Any]) -> dict[str, Any]:
    """Translate service-call data into the POST /v1/workouts request body."""
    workout: dict[str, Any] = {
        "title": call_data[ATTR_TITLE],
        "start_time": call_data[ATTR_START_TIME],
        "end_time": call_data[ATTR_END_TIME],
        "is_private": call_data.get(ATTR_IS_PRIVATE, False),
        "exercises": call_data[ATTR_EXERCISES],
    }
    if call_data.get(ATTR_DESCRIPTION):
        workout["description"] = call_data[ATTR_DESCRIPTION]
    return {"workout": workout}


async def _handle_create_workout(hass: HomeAssistant, call: ServiceCall) -> None:
    entry = _resolve_entry(hass, call.data.get(ATTR_ENTRY_ID))
    body = _build_create_workout_body(call.data)
    try:
        await entry.runtime_data.client.async_create_workout(body)
    except HevyApiClientError as err:
        msg = f"Failed to create workout: {err}"
        raise HomeAssistantError(msg) from err
    await entry.runtime_data.coordinator.async_request_refresh()


def async_register_services(hass: HomeAssistant) -> None:
    """Register integration-level services if not already registered."""
    if hass.services.has_service(DOMAIN, SERVICE_LOG_BODY_MEASUREMENT):
        return

    async def log_body(call: ServiceCall) -> None:
        await _handle_log_body_measurement(hass, call)

    async def refresh(call: ServiceCall) -> None:
        await _handle_refresh(hass, call)

    async def create_workout(call: ServiceCall) -> None:
        await _handle_create_workout(hass, call)

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
    hass.services.async_register(
        DOMAIN,
        SERVICE_CREATE_WORKOUT,
        create_workout,
        schema=CREATE_WORKOUT_SCHEMA,
    )


def async_unregister_services(hass: HomeAssistant) -> None:
    """Drop services when the last config entry is removed."""
    if hass.config_entries.async_entries(DOMAIN):
        return
    hass.services.async_remove(DOMAIN, SERVICE_LOG_BODY_MEASUREMENT)
    hass.services.async_remove(DOMAIN, SERVICE_REFRESH)
    hass.services.async_remove(DOMAIN, SERVICE_CREATE_WORKOUT)
