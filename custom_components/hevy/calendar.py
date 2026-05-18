"""Calendar platform for hevy."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any

from homeassistant.components.calendar import CalendarEntity, CalendarEvent

from .entity import HevyEntity

PARALLEL_UPDATES = 0

if TYPE_CHECKING:
    from datetime import datetime

    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import HevyDataUpdateCoordinator
    from .data import HevyConfigEntry


_DEFAULT_DURATION = timedelta(hours=1)


def _workout_event(workout: dict[str, Any]) -> CalendarEvent | None:
    """Build a CalendarEvent from a processed workout record."""
    start = workout.get("start_time")
    if start is None:
        return None
    duration_s = workout.get("duration_seconds") or 0
    end = (
        start + timedelta(seconds=duration_s)
        if duration_s > 0
        else start + _DEFAULT_DURATION
    )
    description_parts: list[str] = []
    exercise_count = workout.get("exercise_count", 0)
    if exercise_count:
        description_parts.append(f"{exercise_count} exercises")
    total_reps = workout.get("total_reps", 0)
    if total_reps:
        description_parts.append(f"{total_reps} reps")
    volume_kg = workout.get("volume_kg") or 0
    if volume_kg:
        description_parts.append(f"{round(volume_kg, 1)} kg total")
    return CalendarEvent(
        start=start,
        end=end,
        summary=workout.get("title") or "Workout",
        description=" • ".join(description_parts) or None,
        uid=workout.get("id"),
    )


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001
    entry: HevyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the calendar platform."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities([HevyCalendar(coordinator)])


class HevyCalendar(HevyEntity, CalendarEntity):
    """Calendar exposing recent workouts as events."""

    _attr_translation_key = "workouts"
    _attr_icon = "mdi:calendar-check"

    def __init__(self, coordinator: HevyDataUpdateCoordinator) -> None:
        """Initialize the calendar entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_workouts_calendar"

    @property
    def event(self) -> CalendarEvent | None:
        """Return the most recent workout as the 'current' event."""
        last = (self.coordinator.data or {}).get("last_workout")
        if not last:
            return None
        return _workout_event(last)

    async def async_get_events(
        self,
        hass: HomeAssistant,  # noqa: ARG002
        start_date: datetime,
        end_date: datetime,
    ) -> list[CalendarEvent]:
        """Return workouts whose start_time falls in [start_date, end_date)."""
        workouts = (self.coordinator.data or {}).get("workouts", {})
        events: list[CalendarEvent] = []
        for workout in workouts.values():
            start = workout.get("start_time")
            if start is None or start < start_date or start >= end_date:
                continue
            event = _workout_event(workout)
            if event is not None:
                events.append(event)
        events.sort(key=lambda e: e.start)
        return events
