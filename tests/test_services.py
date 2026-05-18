"""Tests for service handlers (log_body_measurement, refresh)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from custom_components.hevy.api import (
    HevyApiClientConflictError,
    HevyApiClientError,
)
from custom_components.hevy.services import (
    ATTR_DATE,
    ATTR_DESCRIPTION,
    ATTR_END_TIME,
    ATTR_ENTRY_ID,
    ATTR_EXERCISES,
    ATTR_FAT_PERCENT,
    ATTR_IS_PRIVATE,
    ATTR_START_TIME,
    ATTR_TITLE,
    ATTR_WEIGHT_KG,
    _build_create_workout_body,
    _build_measurement_payload,
    _coerce_iso_datetime,
    _handle_create_workout,
    _handle_log_body_measurement,
    _handle_refresh,
    _resolve_entry,
)


def _make_hass(entries: list[Any]) -> Any:
    hass = MagicMock()
    hass.config_entries.async_entries = MagicMock(return_value=entries)
    return hass


def _make_entry(entry_id: str = "abc") -> Any:
    entry = SimpleNamespace()
    entry.entry_id = entry_id
    client = MagicMock()
    client.async_create_body_measurement = AsyncMock()
    client.async_update_body_measurement = AsyncMock()
    client.async_create_workout = AsyncMock()
    coordinator = MagicMock()
    coordinator.async_request_refresh = AsyncMock()
    entry.runtime_data = SimpleNamespace(client=client, coordinator=coordinator)
    return entry


class TestResolveEntry:
    def test_no_entries_raises(self) -> None:
        with pytest.raises(ServiceValidationError):
            _resolve_entry(_make_hass([]), None)

    def test_single_entry_returned_without_id(self) -> None:
        entry = _make_entry("only")
        assert _resolve_entry(_make_hass([entry]), None) is entry

    def test_multiple_entries_require_id(self) -> None:
        e1, e2 = _make_entry("a"), _make_entry("b")
        with pytest.raises(ServiceValidationError):
            _resolve_entry(_make_hass([e1, e2]), None)

    def test_explicit_id_matches(self) -> None:
        e1, e2 = _make_entry("a"), _make_entry("b")
        assert _resolve_entry(_make_hass([e1, e2]), "b") is e2

    def test_unknown_id_raises(self) -> None:
        with pytest.raises(ServiceValidationError):
            _resolve_entry(_make_hass([_make_entry("a")]), "missing")


class TestBuildMeasurementPayload:
    def test_uses_today_when_date_missing(self) -> None:
        date_str, body = _build_measurement_payload({ATTR_WEIGHT_KG: 80})
        today = datetime.now(tz=UTC).date().isoformat()
        assert date_str == today
        assert body == {"date": today, "weight_kg": 80}

    def test_date_object(self) -> None:
        d = date(2026, 5, 1)
        date_str, body = _build_measurement_payload(
            {ATTR_DATE: d, ATTR_WEIGHT_KG: 82.0}
        )
        assert date_str == "2026-05-01"
        assert body["weight_kg"] == 82.0

    def test_datetime_object(self) -> None:
        dt = datetime(2026, 5, 1, 12, 0, tzinfo=UTC)
        date_str, _ = _build_measurement_payload({ATTR_DATE: dt, ATTR_WEIGHT_KG: 80})
        assert date_str == "2026-05-01"

    def test_requires_at_least_one_field(self) -> None:
        with pytest.raises(ServiceValidationError):
            _build_measurement_payload({ATTR_DATE: date(2026, 5, 1)})

    def test_multiple_fields(self) -> None:
        _, body = _build_measurement_payload(
            {
                ATTR_DATE: date(2026, 5, 1),
                ATTR_WEIGHT_KG: 80,
                ATTR_FAT_PERCENT: 18.5,
            }
        )
        assert body == {"date": "2026-05-01", "weight_kg": 80, "fat_percent": 18.5}


@pytest.mark.asyncio
class TestLogBodyMeasurement:
    async def test_happy_path_posts(self) -> None:
        entry = _make_entry()
        hass = _make_hass([entry])
        call = SimpleNamespace(data={ATTR_DATE: date(2026, 5, 1), ATTR_WEIGHT_KG: 80})

        await _handle_log_body_measurement(hass, call)

        entry.runtime_data.client.async_create_body_measurement.assert_awaited_once()
        body = entry.runtime_data.client.async_create_body_measurement.await_args.args[
            0
        ]
        assert body["date"] == "2026-05-01"
        assert body["weight_kg"] == 80
        entry.runtime_data.client.async_update_body_measurement.assert_not_called()
        entry.runtime_data.coordinator.async_request_refresh.assert_awaited_once()

    async def test_409_falls_back_to_put(self) -> None:
        entry = _make_entry()
        entry.runtime_data.client.async_create_body_measurement.side_effect = (
            HevyApiClientConflictError("dup")
        )
        hass = _make_hass([entry])
        call = SimpleNamespace(
            data={ATTR_DATE: date(2026, 5, 1), ATTR_WEIGHT_KG: 80, ATTR_FAT_PERCENT: 18}
        )

        await _handle_log_body_measurement(hass, call)

        entry.runtime_data.client.async_update_body_measurement.assert_awaited_once()
        args = entry.runtime_data.client.async_update_body_measurement.await_args.args
        assert args[0] == "2026-05-01"
        assert "date" not in args[1]
        assert args[1] == {"weight_kg": 80, "fat_percent": 18}
        entry.runtime_data.coordinator.async_request_refresh.assert_awaited_once()

    async def test_put_failure_wraps_as_homeassistant_error(self) -> None:
        entry = _make_entry()
        entry.runtime_data.client.async_create_body_measurement.side_effect = (
            HevyApiClientConflictError("dup")
        )
        entry.runtime_data.client.async_update_body_measurement.side_effect = (
            HevyApiClientError("network")
        )
        hass = _make_hass([entry])
        call = SimpleNamespace(data={ATTR_DATE: date(2026, 5, 1), ATTR_WEIGHT_KG: 80})

        with pytest.raises(HomeAssistantError):
            await _handle_log_body_measurement(hass, call)

    async def test_post_failure_wraps_as_homeassistant_error(self) -> None:
        entry = _make_entry()
        entry.runtime_data.client.async_create_body_measurement.side_effect = (
            HevyApiClientError("boom")
        )
        hass = _make_hass([entry])
        call = SimpleNamespace(data={ATTR_DATE: date(2026, 5, 1), ATTR_WEIGHT_KG: 80})

        with pytest.raises(HomeAssistantError):
            await _handle_log_body_measurement(hass, call)

    async def test_validation_error_when_no_fields(self) -> None:
        entry = _make_entry()
        hass = _make_hass([entry])
        call = SimpleNamespace(data={ATTR_DATE: date(2026, 5, 1)})
        with pytest.raises(ServiceValidationError):
            await _handle_log_body_measurement(hass, call)

    async def test_targets_specific_entry_by_id(self) -> None:
        e1 = _make_entry("a")
        e2 = _make_entry("b")
        hass = _make_hass([e1, e2])
        call = SimpleNamespace(data={ATTR_ENTRY_ID: "b", ATTR_WEIGHT_KG: 80})

        await _handle_log_body_measurement(hass, call)

        e1.runtime_data.client.async_create_body_measurement.assert_not_called()
        e2.runtime_data.client.async_create_body_measurement.assert_awaited_once()


@pytest.mark.asyncio
class TestRefresh:
    async def test_requests_refresh(self) -> None:
        entry = _make_entry()
        hass = _make_hass([entry])
        await _handle_refresh(hass, SimpleNamespace(data={}))
        entry.runtime_data.coordinator.async_request_refresh.assert_awaited_once()


class TestCoerceIsoDatetime:
    def test_datetime_passthrough(self) -> None:
        dt = datetime(2026, 5, 17, 9, 0, tzinfo=UTC)
        assert _coerce_iso_datetime(dt) == dt.isoformat()

    def test_date_to_midnight_utc(self) -> None:
        result = _coerce_iso_datetime(date(2026, 5, 17))
        assert result.startswith("2026-05-17T00:00:00")

    def test_iso_string_normalized(self) -> None:
        assert _coerce_iso_datetime("2026-05-17T09:00:00Z").startswith(
            "2026-05-17T09:00:00"
        )

    def test_invalid_string_raises(self) -> None:
        import voluptuous as vol

        with pytest.raises(vol.Invalid):
            _coerce_iso_datetime("not-a-date")

    def test_invalid_type_raises(self) -> None:
        import voluptuous as vol

        with pytest.raises(vol.Invalid):
            _coerce_iso_datetime(42)


class TestBuildCreateWorkoutBody:
    def test_minimal_workout(self) -> None:
        body = _build_create_workout_body(
            {
                ATTR_TITLE: "Test",
                ATTR_START_TIME: "2026-05-17T09:00:00+00:00",
                ATTR_END_TIME: "2026-05-17T10:00:00+00:00",
                ATTR_EXERCISES: [
                    {"exercise_template_id": "T1", "sets": [{"reps": 10}]}
                ],
            }
        )
        assert body["workout"]["title"] == "Test"
        assert body["workout"]["is_private"] is False
        assert "description" not in body["workout"]
        assert body["workout"]["exercises"][0]["exercise_template_id"] == "T1"

    def test_with_description_and_private(self) -> None:
        body = _build_create_workout_body(
            {
                ATTR_TITLE: "Test",
                ATTR_DESCRIPTION: "Notes",
                ATTR_START_TIME: "x",
                ATTR_END_TIME: "y",
                ATTR_IS_PRIVATE: True,
                ATTR_EXERCISES: [],
            }
        )
        assert body["workout"]["description"] == "Notes"
        assert body["workout"]["is_private"] is True

    def test_empty_description_omitted(self) -> None:
        body = _build_create_workout_body(
            {
                ATTR_TITLE: "Test",
                ATTR_DESCRIPTION: "",
                ATTR_START_TIME: "x",
                ATTR_END_TIME: "y",
                ATTR_EXERCISES: [],
            }
        )
        assert "description" not in body["workout"]


@pytest.mark.asyncio
class TestCreateWorkoutHandler:
    async def test_happy_path_posts_and_refreshes(self) -> None:
        entry = _make_entry()
        hass = _make_hass([entry])
        call = SimpleNamespace(
            data={
                ATTR_TITLE: "Test",
                ATTR_START_TIME: "2026-05-17T09:00:00+00:00",
                ATTR_END_TIME: "2026-05-17T10:00:00+00:00",
                ATTR_EXERCISES: [
                    {"exercise_template_id": "T1", "sets": [{"reps": 10}]}
                ],
            }
        )

        await _handle_create_workout(hass, call)

        entry.runtime_data.client.async_create_workout.assert_awaited_once()
        body = entry.runtime_data.client.async_create_workout.await_args.args[0]
        assert body["workout"]["title"] == "Test"
        entry.runtime_data.coordinator.async_request_refresh.assert_awaited_once()

    async def test_api_error_wraps_as_homeassistant_error(self) -> None:
        from custom_components.hevy.api import HevyApiClientError

        entry = _make_entry()
        entry.runtime_data.client.async_create_workout.side_effect = HevyApiClientError(
            "server boom"
        )
        hass = _make_hass([entry])
        call = SimpleNamespace(
            data={
                ATTR_TITLE: "Test",
                ATTR_START_TIME: "x",
                ATTR_END_TIME: "y",
                ATTR_EXERCISES: [],
            }
        )
        with pytest.raises(HomeAssistantError):
            await _handle_create_workout(hass, call)
