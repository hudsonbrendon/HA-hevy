"""Tests for the HevySensorEntityDescription value_fn / attributes_fn lambdas.

Descriptions are pure functions over the coordinator state dict, so they can
be invoked directly without instantiating the HevySensor entity.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from custom_components.hevy.sensor import (
    ALL_DESCRIPTIONS,
    BODY_FAT_DESCRIPTION,
    BODY_WEIGHT_DESCRIPTION,
    DURATION_AGGREGATE_DESCRIPTIONS,
    LAST_WORKOUT_DURATION_DESCRIPTION,
    LAST_WORKOUT_START_DESCRIPTION,
    LAST_WORKOUT_TITLE_DESCRIPTION,
    LAST_WORKOUT_VOLUME_DESCRIPTION,
    LEAN_MASS_DESCRIPTION,
    MONTH_COUNT_DESCRIPTION,
    STREAK_DESCRIPTIONS,
    TODAY_COUNT_DESCRIPTION,
    USER_NAME_DESCRIPTION,
    VARIETY_DESCRIPTIONS,
    VOLUME_AGGREGATE_DESCRIPTIONS,
    WEEK_COUNT_DESCRIPTION,
    WORKOUT_COUNT_DESCRIPTION,
    YEAR_COUNT_DESCRIPTION,
)


@pytest.fixture
def full_state() -> dict[str, Any]:
    return {
        "workout_count": 42,
        "today_count": 1,
        "week_count": 3,
        "month_count": 12,
        "year_count": 150,
        "last_workout": {
            "title": "Push Day",
            "start_time": datetime(2026, 5, 17, 9, 0, tzinfo=UTC),
            "duration_seconds": 4500.0,
            "volume_kg": 3020.0,
            "exercise_count": 5,
            "total_reps": 80,
        },
        "latest_measurement": {
            "date": "2026-05-15",
            "weight_kg": 82.0,
            "fat_percent": 18.5,
            "lean_mass_kg": 65.0,
        },
        "user": {
            "id": "u1",
            "name": "Hudson",
            "url": "https://hevy.com/hudson",
        },
        "volume_today_kg": 3020.123,
        "volume_week_kg": 9000.0,
        "volume_month_kg": 18000.0,
        "volume_year_kg": 100000.0,
        "duration_today_min": 75.0,
        "duration_week_min": 240.0,
        "duration_month_min": 900.0,
        "current_streak_days": 5,
        "longest_streak_days": 14,
        "unique_exercises_7d": 12,
        "unique_exercises_30d": 28,
    }


class TestCountValueFns:
    def test_workout_count(self, full_state: dict) -> None:
        assert WORKOUT_COUNT_DESCRIPTION.value_fn(full_state) == 42

    def test_today_count_default_zero(self) -> None:
        assert TODAY_COUNT_DESCRIPTION.value_fn({}) == 0

    def test_week_month_year(self, full_state: dict) -> None:
        assert WEEK_COUNT_DESCRIPTION.value_fn(full_state) == 3
        assert MONTH_COUNT_DESCRIPTION.value_fn(full_state) == 12
        assert YEAR_COUNT_DESCRIPTION.value_fn(full_state) == 150


class TestLastWorkoutValueFns:
    def test_title(self, full_state: dict) -> None:
        assert LAST_WORKOUT_TITLE_DESCRIPTION.value_fn(full_state) == "Push Day"

    def test_title_none_when_no_last_workout(self) -> None:
        assert LAST_WORKOUT_TITLE_DESCRIPTION.value_fn({}) is None

    def test_title_none_when_last_workout_none(self) -> None:
        assert LAST_WORKOUT_TITLE_DESCRIPTION.value_fn({"last_workout": None}) is None

    def test_start(self, full_state: dict) -> None:
        result = LAST_WORKOUT_START_DESCRIPTION.value_fn(full_state)
        assert result == datetime(2026, 5, 17, 9, 0, tzinfo=UTC)

    def test_duration_min_converted(self, full_state: dict) -> None:
        # 4500s / 60 = 75 min
        assert LAST_WORKOUT_DURATION_DESCRIPTION.value_fn(full_state) == 75.0

    def test_duration_none_when_zero_seconds(self) -> None:
        state = {"last_workout": {"duration_seconds": 0}}
        assert LAST_WORKOUT_DURATION_DESCRIPTION.value_fn(state) is None

    def test_duration_none_when_missing(self) -> None:
        assert LAST_WORKOUT_DURATION_DESCRIPTION.value_fn({}) is None

    def test_volume(self, full_state: dict) -> None:
        assert LAST_WORKOUT_VOLUME_DESCRIPTION.value_fn(full_state) == 3020.0

    def test_volume_none_when_no_last_workout(self) -> None:
        assert LAST_WORKOUT_VOLUME_DESCRIPTION.value_fn({}) is None


class TestLastWorkoutAttributes:
    def test_attrs_when_populated(self, full_state: dict) -> None:
        attrs = LAST_WORKOUT_TITLE_DESCRIPTION.attributes_fn(full_state)
        assert attrs == {"exercise_count": 5, "total_reps": 80}

    def test_attrs_default_zero_when_missing(self) -> None:
        attrs = LAST_WORKOUT_TITLE_DESCRIPTION.attributes_fn({})
        assert attrs == {"exercise_count": 0, "total_reps": 0}


class TestVolumeAggregates:
    def test_round_to_one_decimal(self, full_state: dict) -> None:
        # The volume_today description is the first in the tuple (today/week/month/year)
        today_desc = VOLUME_AGGREGATE_DESCRIPTIONS[0]
        assert today_desc.key == "volume_today_kg"
        assert today_desc.value_fn(full_state) == pytest.approx(3020.1)

    def test_default_zero_when_missing(self) -> None:
        for desc in VOLUME_AGGREGATE_DESCRIPTIONS:
            assert desc.value_fn({}) == 0

    def test_all_periods_present(self) -> None:
        keys = [d.key for d in VOLUME_AGGREGATE_DESCRIPTIONS]
        assert keys == [
            "volume_today_kg",
            "volume_week_kg",
            "volume_month_kg",
            "volume_year_kg",
        ]


class TestDurationAggregates:
    def test_returns_rounded_minutes(self, full_state: dict) -> None:
        today_desc = DURATION_AGGREGATE_DESCRIPTIONS[0]
        assert today_desc.key == "duration_today_min"
        assert today_desc.value_fn(full_state) == 75.0

    def test_no_year_aggregate(self) -> None:
        # Only today/week/month exposed for duration (year would be misleading)
        keys = [d.key for d in DURATION_AGGREGATE_DESCRIPTIONS]
        assert "duration_year_min" not in keys
        assert len(DURATION_AGGREGATE_DESCRIPTIONS) == 3


class TestStreaks:
    def test_current_and_longest(self, full_state: dict) -> None:
        current, longest = STREAK_DESCRIPTIONS
        assert current.value_fn(full_state) == 5
        assert longest.value_fn(full_state) == 14

    def test_default_zero(self) -> None:
        for desc in STREAK_DESCRIPTIONS:
            assert desc.value_fn({}) == 0


class TestVariety:
    def test_values(self, full_state: dict) -> None:
        seven, thirty = VARIETY_DESCRIPTIONS
        assert seven.value_fn(full_state) == 12
        assert thirty.value_fn(full_state) == 28


class TestBodyMeasurementDescriptions:
    def test_weight(self, full_state: dict) -> None:
        assert BODY_WEIGHT_DESCRIPTION.value_fn(full_state) == 82.0

    def test_weight_none_when_no_measurement(self) -> None:
        assert BODY_WEIGHT_DESCRIPTION.value_fn({}) is None

    def test_weight_attrs_include_date(self, full_state: dict) -> None:
        attrs = BODY_WEIGHT_DESCRIPTION.attributes_fn(full_state)
        assert attrs == {"date": "2026-05-15"}

    def test_weight_attrs_empty_date_when_no_measurement(self) -> None:
        attrs = BODY_WEIGHT_DESCRIPTION.attributes_fn({})
        assert attrs == {"date": None}

    def test_fat(self, full_state: dict) -> None:
        assert BODY_FAT_DESCRIPTION.value_fn(full_state) == 18.5

    def test_lean_mass(self, full_state: dict) -> None:
        assert LEAN_MASS_DESCRIPTION.value_fn(full_state) == 65.0


class TestUserDescription:
    def test_name(self, full_state: dict) -> None:
        assert USER_NAME_DESCRIPTION.value_fn(full_state) == "Hudson"

    def test_name_none_when_no_user(self) -> None:
        assert USER_NAME_DESCRIPTION.value_fn({}) is None

    def test_attrs(self, full_state: dict) -> None:
        attrs = USER_NAME_DESCRIPTION.attributes_fn(full_state)
        assert attrs == {
            "user_id": "u1",
            "profile_url": "https://hevy.com/hudson",
        }


class TestRegistry:
    def test_all_descriptions_have_unique_keys(self) -> None:
        keys = [d.key for d in ALL_DESCRIPTIONS]
        assert len(keys) == len(set(keys)), f"duplicate keys: {keys}"

    def test_all_descriptions_have_value_fn(self) -> None:
        for desc in ALL_DESCRIPTIONS:
            assert callable(desc.value_fn), f"{desc.key} missing value_fn"

    def test_value_fns_handle_empty_state(self) -> None:
        # No description should raise on empty state — must degrade to None/0.
        for desc in ALL_DESCRIPTIONS:
            result = desc.value_fn({})
            assert result is None or isinstance(result, int | float | str), (
                f"{desc.key} returned unexpected type: {type(result).__name__}"
            )

    def test_attributes_fns_handle_empty_state(self) -> None:
        for desc in ALL_DESCRIPTIONS:
            if desc.attributes_fn is None:
                continue
            attrs = desc.attributes_fn({})
            assert isinstance(attrs, dict), f"{desc.key} attrs not dict"
