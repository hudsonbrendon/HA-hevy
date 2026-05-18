"""Tests for HA event firing on workout add/remove."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.hevy.api import HevyApiClientError
from custom_components.hevy.const import (
    EVENT_WORKOUT_COMPLETED,
    EVENT_WORKOUT_DELETED,
    EVENT_WORKOUT_UPDATED,
)
from custom_components.hevy.coordinator import (
    HevyDataUpdateCoordinator,
    _event_payload,
)


class TestEventPayload:
    def test_full_record(self) -> None:
        record = {
            "id": "w1",
            "title": "Push Day",
            "start_time": datetime(2026, 5, 17, 9, 0, tzinfo=UTC),
            "duration_seconds": 4500.0,
            "volume_kg": 3020.123,
            "total_reps": 80,
            "exercise_count": 5,
        }
        payload = _event_payload(record)
        assert payload == {
            "id": "w1",
            "title": "Push Day",
            "start_time": "2026-05-17T09:00:00+00:00",
            "duration_min": 75.0,
            "volume_kg": 3020.1,
            "total_reps": 80,
            "exercise_count": 5,
        }

    def test_missing_fields_defaults(self) -> None:
        payload = _event_payload({"id": "w1"})
        assert payload["id"] == "w1"
        assert payload["title"] is None
        assert payload["start_time"] is None
        assert payload["duration_min"] == 0.0
        assert payload["volume_kg"] == 0
        assert payload["total_reps"] == 0
        assert payload["exercise_count"] == 0

    def test_none_duration_does_not_crash(self) -> None:
        payload = _event_payload({"id": "w1", "duration_seconds": None})
        assert payload["duration_min"] == 0.0


@pytest.fixture
def coord_with_bus() -> Any:
    coord = HevyDataUpdateCoordinator.__new__(HevyDataUpdateCoordinator)
    coord.name = "Hudson"
    coord.hass = MagicMock()
    coord.hass.bus = MagicMock()
    coord._primed = True
    return coord


def _record(workout_id: str, title: str = "Push Day") -> dict[str, Any]:
    return {
        "id": workout_id,
        "title": title,
        "start_time": datetime(2026, 5, 17, 9, 0, tzinfo=UTC),
        "duration_seconds": 3600,
        "volume_kg": 1000.0,
        "total_reps": 30,
        "exercise_count": 3,
    }


class TestFireWorkoutEvents:
    def test_new_workout_fires_completed(self, coord_with_bus: Any) -> None:
        coord_with_bus._fire_workout_events(
            previous={},
            current={"w1": _record("w1")},
        )
        coord_with_bus.hass.bus.async_fire.assert_called_once()
        event, payload = coord_with_bus.hass.bus.async_fire.call_args.args
        assert event == EVENT_WORKOUT_COMPLETED
        assert payload["id"] == "w1"
        assert payload["title"] == "Push Day"

    def test_removed_workout_fires_deleted(self, coord_with_bus: Any) -> None:
        coord_with_bus._fire_workout_events(
            previous={"w1": _record("w1", title="Pull Day")},
            current={},
        )
        coord_with_bus.hass.bus.async_fire.assert_called_once_with(
            EVENT_WORKOUT_DELETED, {"id": "w1", "title": "Pull Day"}
        )

    def test_unchanged_workouts_fire_nothing(self, coord_with_bus: Any) -> None:
        same = {"w1": _record("w1")}
        coord_with_bus._fire_workout_events(previous=same, current=same)
        coord_with_bus.hass.bus.async_fire.assert_not_called()

    def test_first_refresh_is_silent(self, coord_with_bus: Any) -> None:
        coord_with_bus._primed = False
        coord_with_bus._fire_workout_events(
            previous={},
            current={"w1": _record("w1"), "w2": _record("w2", title="Pull")},
        )
        coord_with_bus.hass.bus.async_fire.assert_not_called()

    def test_simultaneous_new_and_deleted(self, coord_with_bus: Any) -> None:
        coord_with_bus._fire_workout_events(
            previous={"old": _record("old")},
            current={"new": _record("new")},
        )
        calls = coord_with_bus.hass.bus.async_fire.call_args_list
        events = sorted([c.args[0] for c in calls])
        assert events == [EVENT_WORKOUT_COMPLETED, EVENT_WORKOUT_DELETED]

    def test_multiple_new_workouts(self, coord_with_bus: Any) -> None:
        coord_with_bus._fire_workout_events(
            previous={},
            current={
                "w1": _record("w1", title="A"),
                "w2": _record("w2", title="B"),
                "w3": _record("w3", title="C"),
            },
        )
        assert coord_with_bus.hass.bus.async_fire.call_count == 3
        titles = {
            c.args[1]["title"]
            for c in coord_with_bus.hass.bus.async_fire.call_args_list
        }
        assert titles == {"A", "B", "C"}


@pytest.fixture
def coord_with_events_client() -> Any:
    """Coordinator wired with hass.bus and a stubbed events-endpoint client."""
    coord = HevyDataUpdateCoordinator.__new__(HevyDataUpdateCoordinator)
    coord.name = "Hudson"
    coord.hass = MagicMock()
    coord.hass.bus = MagicMock()
    client = MagicMock()
    client.async_get_workout_events = AsyncMock()
    coord.config_entry = SimpleNamespace(runtime_data=SimpleNamespace(client=client))
    coord._primed = True
    coord._events_cursor = "2026-05-17T11:00:00+00:00"
    return coord


@pytest.mark.asyncio
class TestPollWorkoutUpdates:
    async def test_fires_updated_for_cached_workouts(
        self, coord_with_events_client: Any
    ) -> None:
        coord = coord_with_events_client
        coord.config_entry.runtime_data.client.async_get_workout_events.return_value = {
            "events": [
                {"type": "updated", "workout": {"id": "w1"}},
                {"type": "updated", "workout": {"id": "unknown"}},
                {"type": "deleted", "id": "w2"},
            ]
        }

        await coord._poll_workout_updates({"w1": _record("w1"), "w3": _record("w3")})

        # Only w1 fires (cached); 'unknown' workout skipped; deleted skipped.
        coord.hass.bus.async_fire.assert_called_once()
        event, payload = coord.hass.bus.async_fire.call_args.args
        assert event == EVENT_WORKOUT_UPDATED
        assert payload["id"] == "w1"

    async def test_first_run_seeds_cursor_and_skips(self) -> None:
        coord = HevyDataUpdateCoordinator.__new__(HevyDataUpdateCoordinator)
        coord.hass = MagicMock()
        coord.hass.bus = MagicMock()
        client = MagicMock()
        client.async_get_workout_events = AsyncMock()
        coord.config_entry = SimpleNamespace(
            runtime_data=SimpleNamespace(client=client)
        )
        coord._primed = False
        coord._events_cursor = None

        await coord._poll_workout_updates({"w1": _record("w1")})

        client.async_get_workout_events.assert_not_called()
        coord.hass.bus.async_fire.assert_not_called()
        assert coord._events_cursor is not None

    async def test_api_error_does_not_crash(
        self, coord_with_events_client: Any
    ) -> None:
        coord = coord_with_events_client
        coord.config_entry.runtime_data.client.async_get_workout_events.side_effect = (
            HevyApiClientError("boom")
        )

        # Must not raise — events poll is best-effort.
        await coord._poll_workout_updates({"w1": _record("w1")})
        coord.hass.bus.async_fire.assert_not_called()

    async def test_advances_cursor_after_successful_poll(
        self, coord_with_events_client: Any
    ) -> None:
        coord = coord_with_events_client
        before = coord._events_cursor
        coord.config_entry.runtime_data.client.async_get_workout_events.return_value = {
            "events": []
        }
        await coord._poll_workout_updates({})
        assert coord._events_cursor != before

    async def test_no_updated_events_no_fires(
        self, coord_with_events_client: Any
    ) -> None:
        coord = coord_with_events_client
        coord.config_entry.runtime_data.client.async_get_workout_events.return_value = {
            "events": [{"type": "deleted", "id": "w1"}]
        }
        await coord._poll_workout_updates({"w1": _record("w1")})
        coord.hass.bus.async_fire.assert_not_called()
