"""Sensor platform for hevy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, UnitOfMass, UnitOfTime

from .entity import HevyEntity, HevyWorkoutEntity

if TYPE_CHECKING:
    from datetime import datetime

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import HevyDataUpdateCoordinator
    from .data import HevyConfigEntry


@dataclass
class HevySensorEntityDescriptionRequired:
    """Required properties for HevySensorEntityDescription."""

    value_fn: callable[[dict[str, Any]], Any]


@dataclass
class HevySensorEntityDescription(
    SensorEntityDescription, HevySensorEntityDescriptionRequired
):
    """Hevy sensor entity description."""

    attributes_fn: callable[[dict[str, Any]], dict[str, Any]] | None = None


WORKOUT_COUNT_DESCRIPTION: Final = HevySensorEntityDescription(
    key="workout_count",
    translation_key="workout_count",
    icon="mdi:weight-lifter",
    state_class=SensorStateClass.MEASUREMENT,
    value_fn=lambda data: data.get("workout_count"),
)

TODAY_COUNT_DESCRIPTION: Final = HevySensorEntityDescription(
    key="today_count",
    translation_key="today_count",
    icon="mdi:calendar-today",
    state_class=SensorStateClass.MEASUREMENT,
    value_fn=lambda data: data.get("today_count", 0),
)

WEEK_COUNT_DESCRIPTION: Final = HevySensorEntityDescription(
    key="week_count",
    translation_key="week_count",
    icon="mdi:calendar-week",
    state_class=SensorStateClass.MEASUREMENT,
    value_fn=lambda data: data.get("week_count", 0),
)

MONTH_COUNT_DESCRIPTION: Final = HevySensorEntityDescription(
    key="month_count",
    translation_key="month_count",
    icon="mdi:calendar-month",
    state_class=SensorStateClass.MEASUREMENT,
    value_fn=lambda data: data.get("month_count", 0),
)

YEAR_COUNT_DESCRIPTION: Final = HevySensorEntityDescription(
    key="year_count",
    translation_key="year_count",
    icon="mdi:calendar",
    state_class=SensorStateClass.MEASUREMENT,
    value_fn=lambda data: data.get("year_count", 0),
)


def _last_workout_field(field: str) -> callable[[dict[str, Any]], Any]:
    def _get(data: dict[str, Any]) -> Any:
        lw = data.get("last_workout") or {}
        return lw.get(field)

    return _get


def _last_workout_duration_min(data: dict[str, Any]) -> float | None:
    lw = data.get("last_workout") or {}
    seconds = lw.get("duration_seconds")
    if not seconds:
        return None
    return round(seconds / 60, 1)


def _measurement_field(field: str) -> callable[[dict[str, Any]], Any]:
    def _get(data: dict[str, Any]) -> Any:
        m = data.get("latest_measurement") or {}
        return m.get(field)

    return _get


LAST_WORKOUT_TITLE_DESCRIPTION: Final = HevySensorEntityDescription(
    key="last_workout_title",
    translation_key="last_workout_title",
    icon="mdi:dumbbell",
    value_fn=_last_workout_field("title"),
    attributes_fn=lambda data: {
        "exercise_count": (data.get("last_workout") or {}).get("exercise_count", 0),
        "total_reps": (data.get("last_workout") or {}).get("total_reps", 0),
    },
)

LAST_WORKOUT_START_DESCRIPTION: Final = HevySensorEntityDescription(
    key="last_workout_start",
    translation_key="last_workout_start",
    icon="mdi:calendar-clock",
    device_class=SensorDeviceClass.TIMESTAMP,
    value_fn=_last_workout_field("start_time"),
)

LAST_WORKOUT_DURATION_DESCRIPTION: Final = HevySensorEntityDescription(
    key="last_workout_duration",
    translation_key="last_workout_duration",
    icon="mdi:timer",
    device_class=SensorDeviceClass.DURATION,
    native_unit_of_measurement=UnitOfTime.MINUTES,
    state_class=SensorStateClass.MEASUREMENT,
    value_fn=_last_workout_duration_min,
)

LAST_WORKOUT_VOLUME_DESCRIPTION: Final = HevySensorEntityDescription(
    key="last_workout_volume",
    translation_key="last_workout_volume",
    icon="mdi:weight-kilogram",
    device_class=SensorDeviceClass.WEIGHT,
    native_unit_of_measurement=UnitOfMass.KILOGRAMS,
    state_class=SensorStateClass.MEASUREMENT,
    value_fn=lambda data: (data.get("last_workout") or {}).get("volume_kg"),
)

VOLUME_AGGREGATE_DESCRIPTIONS: Final = tuple(
    HevySensorEntityDescription(
        key=f"volume_{period}_kg",
        translation_key=f"volume_{period}",
        icon="mdi:weight-kilogram",
        device_class=SensorDeviceClass.WEIGHT,
        native_unit_of_measurement=UnitOfMass.KILOGRAMS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data, key=f"volume_{period}_kg": round(data.get(key, 0), 1),
    )
    for period in ("today", "week", "month", "year")
)

DURATION_AGGREGATE_DESCRIPTIONS: Final = tuple(
    HevySensorEntityDescription(
        key=f"duration_{period}_min",
        translation_key=f"duration_{period}",
        icon="mdi:timer-outline",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data, key=f"duration_{period}_min": round(data.get(key, 0), 1),
    )
    for period in ("today", "week", "month")
)

STREAK_DESCRIPTIONS: Final = (
    HevySensorEntityDescription(
        key="current_streak_days",
        translation_key="current_streak_days",
        icon="mdi:fire",
        native_unit_of_measurement="d",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("current_streak_days", 0),
    ),
    HevySensorEntityDescription(
        key="longest_streak_days",
        translation_key="longest_streak_days",
        icon="mdi:trophy",
        native_unit_of_measurement="d",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("longest_streak_days", 0),
    ),
)

VARIETY_DESCRIPTIONS: Final = (
    HevySensorEntityDescription(
        key="unique_exercises_7d",
        translation_key="unique_exercises_7d",
        icon="mdi:shape-outline",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("unique_exercises_7d", 0),
    ),
    HevySensorEntityDescription(
        key="unique_exercises_30d",
        translation_key="unique_exercises_30d",
        icon="mdi:shape",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.get("unique_exercises_30d", 0),
    ),
)

BODY_WEIGHT_DESCRIPTION: Final = HevySensorEntityDescription(
    key="body_weight_kg",
    translation_key="body_weight",
    icon="mdi:scale-bathroom",
    device_class=SensorDeviceClass.WEIGHT,
    native_unit_of_measurement=UnitOfMass.KILOGRAMS,
    state_class=SensorStateClass.MEASUREMENT,
    value_fn=_measurement_field("weight_kg"),
    attributes_fn=lambda data: {
        "date": (data.get("latest_measurement") or {}).get("date"),
    },
)

BODY_FAT_DESCRIPTION: Final = HevySensorEntityDescription(
    key="body_fat_percent",
    translation_key="body_fat_percent",
    icon="mdi:percent",
    native_unit_of_measurement=PERCENTAGE,
    state_class=SensorStateClass.MEASUREMENT,
    value_fn=_measurement_field("fat_percent"),
)

LEAN_MASS_DESCRIPTION: Final = HevySensorEntityDescription(
    key="lean_mass_kg",
    translation_key="lean_mass",
    icon="mdi:human",
    device_class=SensorDeviceClass.WEIGHT,
    native_unit_of_measurement=UnitOfMass.KILOGRAMS,
    state_class=SensorStateClass.MEASUREMENT,
    value_fn=_measurement_field("lean_mass_kg"),
)

USER_NAME_DESCRIPTION: Final = HevySensorEntityDescription(
    key="user_name",
    translation_key="user_name",
    icon="mdi:account",
    value_fn=lambda data: (data.get("user") or {}).get("name"),
    attributes_fn=lambda data: {
        "user_id": (data.get("user") or {}).get("id"),
        "profile_url": (data.get("user") or {}).get("url"),
    },
)

ALL_DESCRIPTIONS: Final = (
    WORKOUT_COUNT_DESCRIPTION,
    TODAY_COUNT_DESCRIPTION,
    WEEK_COUNT_DESCRIPTION,
    MONTH_COUNT_DESCRIPTION,
    YEAR_COUNT_DESCRIPTION,
    LAST_WORKOUT_TITLE_DESCRIPTION,
    LAST_WORKOUT_START_DESCRIPTION,
    LAST_WORKOUT_DURATION_DESCRIPTION,
    LAST_WORKOUT_VOLUME_DESCRIPTION,
    *VOLUME_AGGREGATE_DESCRIPTIONS,
    *DURATION_AGGREGATE_DESCRIPTIONS,
    *STREAK_DESCRIPTIONS,
    *VARIETY_DESCRIPTIONS,
    BODY_WEIGHT_DESCRIPTION,
    BODY_FAT_DESCRIPTION,
    LEAN_MASS_DESCRIPTION,
    USER_NAME_DESCRIPTION,
)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001 Unused function argument: `hass`
    entry: HevyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""
    coordinator = entry.runtime_data.coordinator

    entities: list[SensorEntity] = [
        HevySensor(coordinator=coordinator, entity_description=description)
        for description in ALL_DESCRIPTIONS
    ]

    if coordinator.data and "workouts" in coordinator.data:
        for workout_id, workout_data in coordinator.data["workouts"].items():
            entities.append(HevyWorkoutDateSensor(coordinator, workout_id))
            entities.extend(
                HevyExerciseSensor(
                    coordinator=coordinator,
                    workout_id=workout_id,
                    exercise_key=exercise_key,
                )
                for exercise_key in workout_data.get("exercises", {})
            )

    async_add_entities(entities)


class HevySensor(HevyEntity, SensorEntity):
    """Hevy Sensor class."""

    entity_description: HevySensorEntityDescription

    def __init__(
        self,
        coordinator: HevyDataUpdateCoordinator,
        entity_description: HevySensorEntityDescription,
    ) -> None:
        """Initialize the sensor class."""
        super().__init__(coordinator)
        self.entity_description = entity_description
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_{entity_description.key}"
        )
        self._attr_has_entity_name = True

    @property
    def native_value(self) -> Any:
        """Return the native value of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return optional attributes provided by the description."""
        if self.entity_description.attributes_fn is None:
            return None
        attrs = self.entity_description.attributes_fn(self.coordinator.data)
        return {k: v for k, v in attrs.items() if v is not None}


class HevyWorkoutDateSensor(HevyWorkoutEntity, SensorEntity):
    """Sensor showing the workout date."""

    def __init__(
        self,
        coordinator: HevyDataUpdateCoordinator,
        workout_id: str,
    ) -> None:
        """Initialize the workout date sensor."""
        super().__init__(coordinator, workout_id)
        self._attr_translation_key = "workout_date"
        self._attr_has_entity_name = True
        self._attr_unique_id = f"{workout_id}_date"
        self._attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self) -> datetime | None:
        """Return the native value of the sensor."""
        workout_data = self.workout_data
        return workout_data.get("start_time") if workout_data else None


class HevyExerciseSensor(HevyWorkoutEntity, SensorEntity):
    """Sensor showing exercise data."""

    _attr_device_class = SensorDeviceClass.WEIGHT
    _attr_native_unit_of_measurement = UnitOfMass.KILOGRAMS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: HevyDataUpdateCoordinator,
        workout_id: str,
        exercise_key: str,
    ) -> None:
        """Initialize the exercise sensor."""
        super().__init__(coordinator, workout_id)
        self._exercise_key = exercise_key
        exercise_data = self.workout_data.get("exercises", {}).get(exercise_key, {})
        self._attr_unique_id = f"{workout_id}_{exercise_key}"
        self._attr_name = exercise_data.get("title", "Unknown Exercise")

    @property
    def native_value(self) -> float | None:
        """Return the heaviest weight in the exercise."""
        if not self.available or not self.workout_data:
            return None
        exercise_data = self.workout_data.get("exercises", {}).get(self._exercise_key)
        if not exercise_data:
            return None
        return exercise_data.get("max_weight_kg")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes about the exercise."""
        if not self.available or not self.workout_data:
            return {}
        exercise_data = self.workout_data.get("exercises", {}).get(
            self._exercise_key, {}
        )
        return {
            "sets": exercise_data.get("sets", 0),
            "total_reps": exercise_data.get("total_reps", 0),
            "volume_kg": round(exercise_data.get("volume_kg", 0), 1),
        }
