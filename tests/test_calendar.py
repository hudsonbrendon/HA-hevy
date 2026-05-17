"""Tests for HevyCalendar entity + _workout_event helper."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from custom_components.hevy.calendar import HevyCalendar, _workout_event


def _workout(
    workout_id: str,
    title: str,
    start: datetime,
    duration_s: float = 3600,
    *,
    volume_kg: float = 1000.0,
    total_reps: int = 30,
    exercise_count: int = 3,
) -> dict[str, Any]:
    return {
        "id": workout_id,
        "title": title,
        "start_time": start,
        "duration_seconds": duration_s,
        "volume_kg": volume_kg,
        "total_reps": total_reps,
        "exercise_count": exercise_count,
    }


class TestWorkoutEvent:
    def test_full_record_maps_fields(self) -> None:
        start = datetime(2026, 5, 17, 9, 0, tzinfo=UTC)
        event = _workout_event(_workout("w1", "Push Day", start, 5400))
        assert event.start == start
        assert event.end == start + timedelta(seconds=5400)
        assert event.summary == "Push Day"
        assert event.uid == "w1"
        assert "3 exercises" in event.description
        assert "30 reps" in event.description
        assert "1000.0 kg" in event.description

    def test_zero_duration_falls_back_to_one_hour(self) -> None:
        start = datetime(2026, 5, 17, 9, 0, tzinfo=UTC)
        event = _workout_event(_workout("w1", "Push", start, 0))
        assert event.end == start + timedelta(hours=1)

    def test_missing_start_returns_none(self) -> None:
        assert _workout_event({"id": "w1", "title": "X"}) is None

    def test_missing_title_uses_workout_fallback(self) -> None:
        start = datetime(2026, 5, 17, tzinfo=UTC)
        event = _workout_event({"id": "w1", "start_time": start})
        assert event.summary == "Workout"

    def test_empty_optional_fields_omit_description(self) -> None:
        start = datetime(2026, 5, 17, tzinfo=UTC)
        event = _workout_event(
            {
                "id": "w1",
                "title": "Cardio",
                "start_time": start,
                "duration_seconds": 600,
                "volume_kg": 0,
                "total_reps": 0,
                "exercise_count": 0,
            }
        )
        assert event.description is None


@pytest.fixture
def calendar(entity_coordinator: Any) -> Any:
    return HevyCalendar(entity_coordinator)


class TestHevyCalendarEntity:
    def test_event_property_uses_last_workout(self, calendar: Any) -> None:
        start = datetime(2026, 5, 17, 9, 0, tzinfo=UTC)
        calendar.coordinator.data = {
            "last_workout": _workout("w1", "Push Day", start),
        }
        event = calendar.event
        assert event is not None
        assert event.summary == "Push Day"
        assert event.uid == "w1"

    def test_event_none_when_no_last_workout(self, calendar: Any) -> None:
        calendar.coordinator.data = {}
        assert calendar.event is None

    def test_event_none_when_data_is_none(self, calendar: Any) -> None:
        calendar.coordinator.data = None
        assert calendar.event is None

    def test_unique_id_includes_entry_id(self, calendar: Any) -> None:
        assert calendar._attr_unique_id == "entry-123_workouts_calendar"

    @pytest.mark.asyncio
    async def test_async_get_events_filters_by_window(self, calendar: Any) -> None:
        w1_start = datetime(2026, 5, 17, 9, 0, tzinfo=UTC)
        w2_start = datetime(2026, 5, 10, 9, 0, tzinfo=UTC)
        w3_start = datetime(2026, 4, 1, 9, 0, tzinfo=UTC)
        calendar.coordinator.data = {
            "workouts": {
                "w1": _workout("w1", "Push", w1_start),
                "w2": _workout("w2", "Pull", w2_start),
                "w3": _workout("w3", "Old", w3_start),
            }
        }
        # Window covering May only
        events = await calendar.async_get_events(
            None,
            datetime(2026, 5, 1, tzinfo=UTC),
            datetime(2026, 6, 1, tzinfo=UTC),
        )
        uids = [e.uid for e in events]
        assert uids == ["w2", "w1"]  # sorted by start ascending

    @pytest.mark.asyncio
    async def test_async_get_events_empty_when_no_workouts(self, calendar: Any) -> None:
        calendar.coordinator.data = {"workouts": {}}
        events = await calendar.async_get_events(
            None,
            datetime(2026, 5, 1, tzinfo=UTC),
            datetime(2026, 6, 1, tzinfo=UTC),
        )
        assert events == []

    @pytest.mark.asyncio
    async def test_async_get_events_excludes_end_boundary(self, calendar: Any) -> None:
        # start_date inclusive, end_date exclusive
        boundary = datetime(2026, 5, 17, 9, 0, tzinfo=UTC)
        calendar.coordinator.data = {
            "workouts": {
                "in": _workout(
                    "in",
                    "Inside",
                    boundary,
                ),
                "edge": _workout(
                    "edge",
                    "On end boundary",
                    boundary + timedelta(hours=1),
                ),
            }
        }
        events = await calendar.async_get_events(
            None,
            boundary,
            boundary + timedelta(hours=1),
        )
        uids = [e.uid for e in events]
        assert uids == ["in"]
