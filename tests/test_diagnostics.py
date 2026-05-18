"""Tests for the diagnostics dump (sanitization + structure)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import MagicMock

import pytest

from custom_components.hevy.diagnostics import (
    _scrub_coordinator_data,
    _summarize_workouts,
    async_get_config_entry_diagnostics,
)


def _workout_record(workout_id: str, title: str = "Push") -> dict[str, Any]:
    return {
        "id": workout_id,
        "title": title,
        "start_time": datetime(2026, 5, 17, 9, 0, tzinfo=UTC),
        "_end_time_raw": "2026-05-17T10:00:00+00:00",
        "exercises": {
            "0_Bench": {"title": "Bench", "sets": 3, "total_reps": 20, "volume_kg": 800}
        },
        "exercise_count": 1,
        "total_reps": 20,
        "volume_kg": 800.0,
        "duration_seconds": 3600,
    }


class TestSummarizeWorkouts:
    def test_drops_exercises_keeps_counters(self) -> None:
        summary = _summarize_workouts({"w1": _workout_record("w1")})
        assert "exercises" not in summary["w1"]
        assert summary["w1"]["title"] == "Push"
        assert summary["w1"]["exercise_count"] == 1
        assert summary["w1"]["total_reps"] == 20
        assert summary["w1"]["volume_kg"] == 800.0
        assert summary["w1"]["duration_seconds"] == 3600

    def test_serializes_datetime(self) -> None:
        summary = _summarize_workouts({"w1": _workout_record("w1")})
        assert summary["w1"]["start_time"] == "2026-05-17T09:00:00+00:00"

    def test_missing_start_time_returns_none(self) -> None:
        record = _workout_record("w1")
        record["start_time"] = None
        summary = _summarize_workouts({"w1": record})
        assert summary["w1"]["start_time"] is None

    def test_empty_input(self) -> None:
        assert _summarize_workouts({}) == {}


class TestScrubCoordinatorData:
    def test_empty(self) -> None:
        assert _scrub_coordinator_data({}) == {}
        assert _scrub_coordinator_data(None) == {}  # type: ignore[arg-type]

    def test_redacts_user_identifiers(self) -> None:
        data = {
            "user": {
                "id": "abc",
                "name": "Hudson",
                "url": "https://hevy.com/hudson",
            },
            "workouts": {},
        }
        scrubbed = _scrub_coordinator_data(data)
        assert scrubbed["user"] == "**REDACTED**"

    def test_summarizes_workouts(self) -> None:
        data = {"workouts": {"w1": _workout_record("w1")}}
        scrubbed = _scrub_coordinator_data(data)
        assert "exercises" not in scrubbed["workouts"]["w1"]

    def test_strips_exercises_from_last_workout(self) -> None:
        last = _workout_record("w1")
        data = {"workouts": {}, "last_workout": last}
        scrubbed = _scrub_coordinator_data(data)
        assert "exercises" not in scrubbed["last_workout"]
        assert scrubbed["last_workout"]["start_time"] == "2026-05-17T09:00:00+00:00"


@pytest.mark.asyncio
class TestAsyncGetConfigEntryDiagnostics:
    async def test_full_diagnostics_structure(self) -> None:
        coord = MagicMock()
        coord.name = "Hudson"
        coord.update_interval = timedelta(minutes=30)
        coord._workouts_count = 10
        coord._primed = True
        coord.last_update_success = True
        coord.data = {
            "workouts": {"w1": _workout_record("w1")},
            "user": {"id": "u1", "name": "Hudson", "url": "https://hevy.com/x"},
            "workout_count": 42,
        }

        entry = MagicMock()
        entry.title = "Hevy - Hudson"
        entry.data = {"api_key": "secret-key", "name": "Hudson"}
        entry.options = {"scan_interval": 30, "workouts_count": 10}
        entry.runtime_data = MagicMock(coordinator=coord)

        result = await async_get_config_entry_diagnostics(None, entry)

        assert result["entry"]["title"] == "Hevy - Hudson"
        assert result["entry"]["data"]["api_key"] == "**REDACTED**"
        assert result["entry"]["data"]["name"] == "Hudson"
        assert result["entry"]["options"] == {"scan_interval": 30, "workouts_count": 10}

        assert result["coordinator"]["name"] == "Hudson"
        assert result["coordinator"]["update_interval_seconds"] == 1800
        assert result["coordinator"]["workouts_count"] == 10
        assert result["coordinator"]["primed"] is True
        assert result["coordinator"]["last_update_success"] is True
        assert result["coordinator"]["data"]["user"] == "**REDACTED**"
        assert "exercises" not in result["coordinator"]["data"]["workouts"]["w1"]

    async def test_handles_none_update_interval(self) -> None:
        coord = MagicMock()
        coord.name = "X"
        coord.update_interval = None
        coord._workouts_count = 10
        coord._primed = False
        coord.last_update_success = False
        coord.data = {}

        entry = MagicMock()
        entry.title = "X"
        entry.data = {"api_key": "k"}
        entry.options = {}
        entry.runtime_data = MagicMock(coordinator=coord)

        result = await async_get_config_entry_diagnostics(None, entry)
        assert result["coordinator"]["update_interval_seconds"] is None
        assert result["coordinator"]["primed"] is False
        assert result["coordinator"]["data"] == {}
