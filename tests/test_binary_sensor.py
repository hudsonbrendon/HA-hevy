"""Tests for binary_sensor is_on_fn lambdas + HevyBinarySensor entity."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import MagicMock

import pytest

from custom_components.hevy.binary_sensor import (
    WORKOUT_TODAY_DESCRIPTION,
    WORKOUT_WEEK_DESCRIPTION,
    HevyBinarySensor,
)


def _state(workouts: dict[str, dict]) -> dict[str, Any]:
    """Helper to build a coordinator state with given workouts dict."""
    return {"workouts": workouts}


@pytest.fixture
def today_utc() -> datetime:
    """Real datetime.now is used by binary_sensor lambdas — anchor 'today'."""
    return datetime.now(tz=UTC)


class TestWorkoutTodayLambda:
    def test_true_when_workout_today(self, today_utc: datetime) -> None:
        state = _state({"w1": {"id": "w1", "start_time": today_utc}})
        assert WORKOUT_TODAY_DESCRIPTION.is_on_fn(state) is True

    def test_false_when_only_yesterday(self, today_utc: datetime) -> None:
        yesterday = today_utc - timedelta(days=1)
        state = _state({"w1": {"id": "w1", "start_time": yesterday}})
        assert WORKOUT_TODAY_DESCRIPTION.is_on_fn(state) is False

    def test_false_when_no_workouts(self) -> None:
        assert WORKOUT_TODAY_DESCRIPTION.is_on_fn(_state({})) is False

    def test_false_when_workouts_key_missing(self) -> None:
        assert WORKOUT_TODAY_DESCRIPTION.is_on_fn({}) is False

    def test_workout_without_start_time_uses_default(self) -> None:
        # Missing start_time defaults to datetime.min (epoch-ish) → never == today
        state = _state({"w1": {"id": "w1"}})
        assert WORKOUT_TODAY_DESCRIPTION.is_on_fn(state) is False


class TestWorkoutWeekLambda:
    def test_true_when_within_seven_days(self, today_utc: datetime) -> None:
        recent = today_utc - timedelta(days=3)
        state = _state({"w1": {"id": "w1", "start_time": recent}})
        assert WORKOUT_WEEK_DESCRIPTION.is_on_fn(state) is True

    def test_false_when_eight_days_old(self, today_utc: datetime) -> None:
        old = today_utc - timedelta(days=8)
        state = _state({"w1": {"id": "w1", "start_time": old}})
        assert WORKOUT_WEEK_DESCRIPTION.is_on_fn(state) is False

    def test_today_counts_as_within_week(self, today_utc: datetime) -> None:
        state = _state({"w1": {"id": "w1", "start_time": today_utc}})
        assert WORKOUT_WEEK_DESCRIPTION.is_on_fn(state) is True

    def test_empty_workouts(self) -> None:
        assert WORKOUT_WEEK_DESCRIPTION.is_on_fn(_state({})) is False


class TestHevyBinarySensorEntity:
    def test_is_on_dispatches_to_description_lambda(self, today_utc: datetime) -> None:
        coord = MagicMock()
        coord.data = _state({"w1": {"id": "w1", "start_time": today_utc}})

        sensor = HevyBinarySensor.__new__(HevyBinarySensor)
        sensor.coordinator = coord
        sensor.entity_description = WORKOUT_TODAY_DESCRIPTION

        assert sensor.is_on is True

    def test_is_on_false_for_empty(self) -> None:
        coord = MagicMock()
        coord.data = _state({})

        sensor = HevyBinarySensor.__new__(HevyBinarySensor)
        sensor.coordinator = coord
        sensor.entity_description = WORKOUT_WEEK_DESCRIPTION

        assert sensor.is_on is False

    def test_description_metadata(self) -> None:
        # The MOTION device class is intentional (occupancy-style trigger).
        assert WORKOUT_TODAY_DESCRIPTION.key == "workout_today"
        assert WORKOUT_TODAY_DESCRIPTION.translation_key == "workout_today"
        assert WORKOUT_WEEK_DESCRIPTION.key == "workout_this_week"
