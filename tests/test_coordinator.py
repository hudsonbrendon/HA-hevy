"""Tests for HevyDataUpdateCoordinator pure helpers and state builder."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from custom_components.hevy.coordinator import (
    _compute_streaks,
    _set_volume_kg,
    _workout_duration_seconds,
)

TODAY = datetime(2026, 5, 17, tzinfo=UTC).date()


class TestSetVolumeKg:
    def test_normal_set(self) -> None:
        assert _set_volume_kg({"weight_kg": 100, "reps": 10}) == 1000.0

    def test_none_weight_returns_zero(self) -> None:
        assert _set_volume_kg({"weight_kg": None, "reps": 10}) == 0.0

    def test_none_reps_returns_zero(self) -> None:
        assert _set_volume_kg({"weight_kg": 50, "reps": None}) == 0.0

    def test_empty_set_returns_zero(self) -> None:
        assert _set_volume_kg({}) == 0.0

    def test_float_weight_supported(self) -> None:
        assert _set_volume_kg({"weight_kg": 12.5, "reps": 8}) == 100.0


class TestWorkoutDurationSeconds:
    def test_valid_pair(self) -> None:
        record = {
            "start_time": datetime(2026, 5, 17, 10, 0, tzinfo=UTC),
            "_end_time_raw": "2026-05-17T11:30:00+00:00",
        }
        assert _workout_duration_seconds(record) == 5400.0

    def test_missing_start_or_end(self) -> None:
        assert (
            _workout_duration_seconds({"start_time": None, "_end_time_raw": None})
            == 0.0
        )

    def test_invalid_end_returns_zero(self) -> None:
        record = {
            "start_time": datetime(2026, 5, 17, 10, 0, tzinfo=UTC),
            "_end_time_raw": "not-a-date",
        }
        assert _workout_duration_seconds(record) == 0.0

    def test_negative_duration_clamped(self) -> None:
        record = {
            "start_time": datetime(2026, 5, 17, 12, 0, tzinfo=UTC),
            "_end_time_raw": "2026-05-17T10:00:00+00:00",
        }
        assert _workout_duration_seconds(record) == 0.0


class TestComputeStreaks:
    def test_three_consecutive_including_today(self) -> None:
        dates = {TODAY, TODAY - timedelta(days=1), TODAY - timedelta(days=2)}
        assert _compute_streaks(dates, TODAY) == (3, 3)

    def test_streak_starting_yesterday(self) -> None:
        dates = {TODAY - timedelta(days=1), TODAY - timedelta(days=2)}
        assert _compute_streaks(dates, TODAY) == (2, 2)

    def test_gap_breaks_current_streak(self) -> None:
        dates = {
            TODAY - timedelta(days=1),
            TODAY - timedelta(days=3),
            TODAY - timedelta(days=4),
        }
        assert _compute_streaks(dates, TODAY) == (1, 2)

    def test_stale_last_workout_zero_current(self) -> None:
        dates = {TODAY - timedelta(days=5), TODAY - timedelta(days=6)}
        assert _compute_streaks(dates, TODAY) == (0, 2)

    def test_empty(self) -> None:
        assert _compute_streaks(set(), TODAY) == (0, 0)

    def test_single_workout_today(self) -> None:
        assert _compute_streaks({TODAY}, TODAY) == (1, 1)


@pytest.mark.usefixtures("freeze_coordinator_clock")
class TestBuildState:
    def test_volume_aggregates(
        self,
        coordinator: Any,
        workout_count_fixture: dict,
        workouts_fixture: dict,
        user_fixture: dict,
        measurements_fixture: dict,
    ) -> None:
        state = coordinator._build_state(
            workout_count_fixture,
            workouts_fixture,
            user_fixture,
            measurements_fixture,
        )
        assert state["volume_today_kg"] == pytest.approx(3020.0)
        assert state["volume_week_kg"] == pytest.approx(3720.0)
        assert state["volume_month_kg"] == pytest.approx(3720.0)
        assert state["volume_year_kg"] == pytest.approx(4220.0)

    def test_duration_aggregates(
        self,
        coordinator: Any,
        workout_count_fixture: dict,
        workouts_fixture: dict,
        user_fixture: dict,
        measurements_fixture: dict,
    ) -> None:
        state = coordinator._build_state(
            workout_count_fixture,
            workouts_fixture,
            user_fixture,
            measurements_fixture,
        )
        assert state["duration_today_min"] == pytest.approx(75.0)
        assert state["duration_week_min"] == pytest.approx(135.0)
        assert state["duration_month_min"] == pytest.approx(135.0)

    def test_workout_counts(
        self,
        coordinator: Any,
        workout_count_fixture: dict,
        workouts_fixture: dict,
        user_fixture: dict,
        measurements_fixture: dict,
    ) -> None:
        state = coordinator._build_state(
            workout_count_fixture,
            workouts_fixture,
            user_fixture,
            measurements_fixture,
        )
        assert state["today_count"] == 1
        assert state["week_count"] == 2
        assert state["month_count"] == 2
        assert state["year_count"] == 3
        assert state["workout_count"] == 42

    def test_streak_from_workouts(
        self,
        coordinator: Any,
        workout_count_fixture: dict,
        workouts_fixture: dict,
        user_fixture: dict,
        measurements_fixture: dict,
    ) -> None:
        state = coordinator._build_state(
            workout_count_fixture,
            workouts_fixture,
            user_fixture,
            measurements_fixture,
        )
        assert state["current_streak_days"] == 2
        assert state["longest_streak_days"] == 2

    def test_variety_window(
        self,
        coordinator: Any,
        workout_count_fixture: dict,
        workouts_fixture: dict,
        user_fixture: dict,
        measurements_fixture: dict,
    ) -> None:
        state = coordinator._build_state(
            workout_count_fixture,
            workouts_fixture,
            user_fixture,
            measurements_fixture,
        )
        assert state["unique_exercises_7d"] == 3
        # T4 from April 1st is >30d before May 17 → excluded from 30d window
        assert state["unique_exercises_30d"] == 3

    def test_user_and_measurement_extracted(
        self,
        coordinator: Any,
        workout_count_fixture: dict,
        workouts_fixture: dict,
        user_fixture: dict,
        measurements_fixture: dict,
    ) -> None:
        state = coordinator._build_state(
            workout_count_fixture,
            workouts_fixture,
            user_fixture,
            measurements_fixture,
        )
        assert state["user"]["name"] == "Hudson"
        assert state["latest_measurement"]["date"] == "2026-05-15"
        assert state["latest_measurement"]["weight_kg"] == pytest.approx(82.0)

    def test_last_workout_summary(
        self,
        coordinator: Any,
        workout_count_fixture: dict,
        workouts_fixture: dict,
        user_fixture: dict,
        measurements_fixture: dict,
    ) -> None:
        state = coordinator._build_state(
            workout_count_fixture,
            workouts_fixture,
            user_fixture,
            measurements_fixture,
        )
        lw = state["last_workout"]
        assert lw["title"] == "Push Day"
        assert lw["volume_kg"] == pytest.approx(3020.0)
        assert lw["exercise_count"] == 2
        assert lw["total_reps"] == 43
        assert lw["duration_seconds"] == pytest.approx(4500.0)


@pytest.mark.usefixtures("freeze_coordinator_clock")
class TestBuildStateDegraded:
    def test_user_and_measurements_none_does_not_crash(
        self,
        coordinator: Any,
        workout_count_fixture: dict,
        workouts_fixture: dict,
    ) -> None:
        state = coordinator._build_state(
            workout_count_fixture, workouts_fixture, None, None
        )
        assert state["user"] == {}
        assert state["latest_measurement"] is None
        # Volume/duration still computed from required workouts payload.
        assert state["volume_today_kg"] == pytest.approx(3020.0)

    def test_empty_workouts(
        self,
        coordinator: Any,
        user_fixture: dict,
        measurements_fixture: dict,
    ) -> None:
        state = coordinator._build_state(
            {"workout_count": 0},
            {"workouts": []},
            user_fixture,
            measurements_fixture,
        )
        assert state["today_count"] == 0
        assert state["current_streak_days"] == 0
        assert state["last_workout"] is None
        assert state["unique_exercises_7d"] == 0
        # Latest measurement still surfaces even when no workouts.
        assert state["latest_measurement"]["date"] == "2026-05-15"
