"""Tests for HevyEntity / HevyWorkoutEntity / HevySensor / HevyExerciseSensor."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from custom_components.hevy.entity import HevyEntity, HevyWorkoutEntity
from custom_components.hevy.sensor import (
    WORKOUT_COUNT_DESCRIPTION,
    HevyExerciseSensor,
    HevySensor,
    HevyWorkoutDateSensor,
)


@pytest.fixture
def populated_coordinator(entity_coordinator: Any) -> Any:
    entity_coordinator.data = {
        "workout_count": 42,
        "workouts": {
            "w1": {
                "id": "w1",
                "title": "Push Day",
                "start_time": datetime(2026, 5, 17, 9, 0, tzinfo=UTC),
                "exercises": {
                    "0_Bench Press": {
                        "title": "Bench Press",
                        "sets": 3,
                        "total_reps": 23,
                        "volume_kg": 2020.0,
                        "max_weight_kg": 100.0,
                    },
                },
            }
        },
    }
    return entity_coordinator


class TestHevyEntity:
    def test_unique_id_uses_entry_id(self, populated_coordinator: Any) -> None:
        ent = HevyEntity(populated_coordinator)
        assert ent._attr_unique_id == "entry-123"

    def test_device_info_identifiers_include_name_and_entry_id(
        self, populated_coordinator: Any
    ) -> None:
        ent = HevyEntity(populated_coordinator)
        info = ent._attr_device_info
        assert info["name"] == "Hudson"
        assert info["manufacturer"] == "Hevy"
        identifiers = info["identifiers"]
        assert ("hevy", "Hudson_entry-123") in identifiers


class TestHevyWorkoutEntity:
    def test_workout_data_reads_from_coordinator(
        self, populated_coordinator: Any
    ) -> None:
        ent = HevyWorkoutEntity(populated_coordinator, "w1")
        assert ent.workout_data["title"] == "Push Day"

    def test_workout_data_empty_for_unknown_id(
        self, populated_coordinator: Any
    ) -> None:
        ent = HevyWorkoutEntity(populated_coordinator, "missing")
        assert ent.workout_data == {}

    def test_available_true_when_workout_present(
        self, populated_coordinator: Any
    ) -> None:
        ent = HevyWorkoutEntity(populated_coordinator, "w1")
        assert ent.available is True

    def test_available_false_when_workout_missing(
        self, populated_coordinator: Any
    ) -> None:
        ent = HevyWorkoutEntity(populated_coordinator, "missing")
        assert ent.available is False

    def test_available_false_when_coordinator_failed(
        self, populated_coordinator: Any
    ) -> None:
        populated_coordinator.last_update_success = False
        ent = HevyWorkoutEntity(populated_coordinator, "w1")
        assert ent.available is False

    def test_device_info_carries_workout_title(
        self, populated_coordinator: Any
    ) -> None:
        ent = HevyWorkoutEntity(populated_coordinator, "w1")
        info = ent._attr_device_info
        assert "Push Day" in info["name"]
        assert info["model"] == "Workout"
        # via_device links back to root device
        assert info["via_device"] == ("hevy", "Hudson_entry-123")


class TestHevySensor:
    def test_native_value_invokes_description_value_fn(
        self, populated_coordinator: Any
    ) -> None:
        sensor = HevySensor(populated_coordinator, WORKOUT_COUNT_DESCRIPTION)
        assert sensor.native_value == 42

    def test_unique_id_combines_entry_and_description_key(
        self, populated_coordinator: Any
    ) -> None:
        sensor = HevySensor(populated_coordinator, WORKOUT_COUNT_DESCRIPTION)
        assert sensor._attr_unique_id == "entry-123_workout_count"

    def test_extra_state_attributes_none_when_no_attributes_fn(
        self, populated_coordinator: Any
    ) -> None:
        sensor = HevySensor(populated_coordinator, WORKOUT_COUNT_DESCRIPTION)
        # workout_count description has no attributes_fn
        assert sensor.extra_state_attributes is None

    def test_extra_state_attributes_strips_none_values(
        self, populated_coordinator: Any
    ) -> None:
        from custom_components.hevy.sensor import USER_NAME_DESCRIPTION

        # No user data → both attrs would be None → dict should be empty
        populated_coordinator.data = {}
        sensor = HevySensor(populated_coordinator, USER_NAME_DESCRIPTION)
        attrs = sensor.extra_state_attributes
        assert attrs == {}


class TestHevyWorkoutDateSensor:
    def test_native_value_returns_start_time(self, populated_coordinator: Any) -> None:
        sensor = HevyWorkoutDateSensor(populated_coordinator, "w1")
        assert sensor.native_value == datetime(2026, 5, 17, 9, 0, tzinfo=UTC)

    def test_native_value_none_when_workout_missing(
        self, populated_coordinator: Any
    ) -> None:
        sensor = HevyWorkoutDateSensor(populated_coordinator, "w1")
        # Wipe workouts after construction
        populated_coordinator.data = {"workouts": {}}
        assert sensor.native_value is None


class TestHevyExerciseSensor:
    def test_native_value_returns_max_weight(self, populated_coordinator: Any) -> None:
        sensor = HevyExerciseSensor(
            coordinator=populated_coordinator,
            workout_id="w1",
            exercise_key="0_Bench Press",
        )
        assert sensor.native_value == 100.0

    def test_native_value_none_when_unavailable(
        self, populated_coordinator: Any
    ) -> None:
        sensor = HevyExerciseSensor(
            coordinator=populated_coordinator,
            workout_id="w1",
            exercise_key="0_Bench Press",
        )
        populated_coordinator.last_update_success = False
        assert sensor.native_value is None

    def test_native_value_none_when_exercise_key_missing(
        self, populated_coordinator: Any
    ) -> None:
        sensor = HevyExerciseSensor(
            coordinator=populated_coordinator,
            workout_id="w1",
            exercise_key="99_Ghost Exercise",
        )
        assert sensor.native_value is None

    def test_extra_state_attributes(self, populated_coordinator: Any) -> None:
        sensor = HevyExerciseSensor(
            coordinator=populated_coordinator,
            workout_id="w1",
            exercise_key="0_Bench Press",
        )
        attrs = sensor.extra_state_attributes
        assert attrs["sets"] == 3
        assert attrs["total_reps"] == 23
        assert attrs["volume_kg"] == 2020.0

    def test_extra_state_attributes_empty_when_unavailable(
        self, populated_coordinator: Any
    ) -> None:
        sensor = HevyExerciseSensor(
            coordinator=populated_coordinator,
            workout_id="w1",
            exercise_key="0_Bench Press",
        )
        populated_coordinator.last_update_success = False
        assert sensor.extra_state_attributes == {}

    def test_name_uses_exercise_title(self, populated_coordinator: Any) -> None:
        sensor = HevyExerciseSensor(
            coordinator=populated_coordinator,
            workout_id="w1",
            exercise_key="0_Bench Press",
        )
        assert sensor._attr_name == "Bench Press"

    def test_name_defaults_when_exercise_missing(
        self, populated_coordinator: Any
    ) -> None:
        sensor = HevyExerciseSensor(
            coordinator=populated_coordinator,
            workout_id="w1",
            exercise_key="99_Ghost",
        )
        assert sensor._attr_name == "Unknown Exercise"
