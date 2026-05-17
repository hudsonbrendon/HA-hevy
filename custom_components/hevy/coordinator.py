"""DataUpdateCoordinator for hevy."""

from __future__ import annotations

import asyncio
from datetime import UTC, date, datetime, timedelta
from itertools import pairwise
from typing import TYPE_CHECKING, Any

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    HevyApiClientAuthenticationError,
    HevyApiClientError,
)
from .const import (
    DEFAULT_WORKOUTS_COUNT,
    DOMAIN,
    EVENT_WORKOUT_COMPLETED,
    EVENT_WORKOUT_DELETED,
    LOGGER,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import HevyConfigEntry


def _set_volume_kg(workout_set: dict[str, Any]) -> float:
    """Return volume (weight * reps) for a single set, treating None as 0."""
    weight = workout_set.get("weight_kg") or 0
    reps = workout_set.get("reps") or 0
    return float(weight) * float(reps)


def _workout_duration_seconds(workout: dict[str, Any]) -> float:
    """Return duration in seconds between start_time and end_time, 0 if missing."""
    start = workout.get("start_time")
    end_raw = workout.get("_end_time_raw")
    if not start or not end_raw:
        return 0.0
    try:
        end = datetime.fromisoformat(end_raw)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, (end - start).total_seconds())


def _event_payload(record: dict[str, Any]) -> dict[str, Any]:
    """Build the HA event payload for a workout record."""
    start = record.get("start_time")
    return {
        "id": record.get("id"),
        "title": record.get("title"),
        "start_time": start.isoformat() if start else None,
        "duration_min": round((record.get("duration_seconds") or 0) / 60, 1),
        "volume_kg": round(record.get("volume_kg") or 0, 1),
        "total_reps": record.get("total_reps", 0),
        "exercise_count": record.get("exercise_count", 0),
    }


def _compute_streaks(workout_dates: set[date], today: date) -> tuple[int, int]:
    """Compute (current_streak_days, longest_streak_days) from a set of dates."""
    if not workout_dates:
        return 0, 0

    sorted_dates = sorted(workout_dates, reverse=True)

    current = 0
    cursor = today
    if sorted_dates[0] not in (today, today - timedelta(days=1)):
        current = 0
    else:
        cursor = sorted_dates[0]
        current = 1
        for d in sorted_dates[1:]:
            if d == cursor - timedelta(days=1):
                cursor = d
                current += 1
            else:
                break

    longest = 1
    run = 1
    for prev, nxt in pairwise(sorted_dates):
        if prev - nxt == timedelta(days=1):
            run += 1
            longest = max(longest, run)
        else:
            run = 1
    return current, longest


class HevyDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API."""

    config_entry: HevyConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        update_interval: timedelta,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass=hass,
            logger=LOGGER,
            name=DOMAIN,
            update_interval=update_interval,
        )
        self.name = name
        self.data: dict[str, Any] = {}
        self._primed = False

    async def _async_update_data(self) -> dict[str, Any]:
        """Update data via library."""
        client = self.config_entry.runtime_data.client
        try:
            (
                workout_count_data,
                workouts_data,
                user_data,
                measurements_data,
            ) = await asyncio.gather(
                client.async_get_workout_count(),
                client.async_get_workouts(page=1, page_size=DEFAULT_WORKOUTS_COUNT),
                self._safe_fetch(client.async_get_user_info()),
                self._safe_fetch(client.async_get_body_measurements(page_size=10)),
            )
        except HevyApiClientAuthenticationError as exception:
            raise ConfigEntryAuthFailed(exception) from exception
        except HevyApiClientError as exception:
            raise UpdateFailed(exception) from exception

        previous_workouts = self.data.get("workouts", {}) if self.data else {}
        new_state = self._build_state(
            workout_count_data, workouts_data, user_data, measurements_data
        )
        self._fire_workout_events(previous_workouts, new_state["workouts"])
        self._primed = True
        return new_state

    def _fire_workout_events(
        self,
        previous: dict[str, dict[str, Any]],
        current: dict[str, dict[str, Any]],
    ) -> None:
        """Fire HA events for workouts added/removed since the last poll."""
        # First successful refresh primes the cache without firing events so
        # the integration doesn't spam HA on startup with one event per
        # cached workout.
        if not self._primed:
            return
        for workout_id, record in current.items():
            if workout_id not in previous:
                self.hass.bus.async_fire(
                    EVENT_WORKOUT_COMPLETED, _event_payload(record)
                )
        for workout_id, record in previous.items():
            if workout_id not in current:
                self.hass.bus.async_fire(
                    EVENT_WORKOUT_DELETED,
                    {"id": workout_id, "title": record.get("title")},
                )

    def _build_state(
        self,
        workout_count_data: dict[str, Any],
        workouts_data: dict[str, Any],
        user_data: dict[str, Any] | None,
        measurements_data: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Merge API responses into the coordinator state dictionary."""
        today = datetime.now(tz=UTC).date()
        processed, aggregates = self._process_workouts(
            workouts_data.get("workouts", []), today
        )
        current_streak, longest_streak = _compute_streaks(
            aggregates["workout_dates"], today
        )
        last_workout = (
            max(processed.values(), key=lambda w: w["start_time"])
            if processed
            else None
        )
        user_info = (user_data or {}).get("data") or {}
        measurements_list = (measurements_data or {}).get("body_measurements", [])
        latest_measurement = (
            max(measurements_list, key=lambda m: m.get("date", ""))
            if measurements_list
            else None
        )
        return {
            "workout_count": workout_count_data.get("workout_count", 0),
            "workouts": processed,
            "name": self.name,
            "today_count": aggregates["today_count"],
            "week_count": aggregates["week_count"],
            "month_count": aggregates["month_count"],
            "year_count": aggregates["year_count"],
            "user": user_info,
            "latest_measurement": latest_measurement,
            "last_workout": last_workout,
            "volume_today_kg": aggregates["volume_today"],
            "volume_week_kg": aggregates["volume_week"],
            "volume_month_kg": aggregates["volume_month"],
            "volume_year_kg": aggregates["volume_year"],
            "duration_today_min": aggregates["duration_today_s"] / 60,
            "duration_week_min": aggregates["duration_week_s"] / 60,
            "duration_month_min": aggregates["duration_month_s"] / 60,
            "current_streak_days": current_streak,
            "longest_streak_days": longest_streak,
            "unique_exercises_7d": len(aggregates["templates_7d"]),
            "unique_exercises_30d": len(aggregates["templates_30d"]),
        }

    def _process_workouts(
        self, workouts: list[dict[str, Any]], today: date
    ) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
        """Process workouts into records + aggregate counters."""
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        processed: dict[str, dict[str, Any]] = {}
        agg: dict[str, Any] = {
            "today_count": 0,
            "week_count": 0,
            "month_count": 0,
            "year_count": 0,
            "volume_today": 0.0,
            "volume_week": 0.0,
            "volume_month": 0.0,
            "volume_year": 0.0,
            "duration_today_s": 0.0,
            "duration_week_s": 0.0,
            "duration_month_s": 0.0,
            "workout_dates": set(),
            "templates_7d": set(),
            "templates_30d": set(),
        }
        for workout in workouts:
            record = self._build_workout_record(workout, agg, week_ago, month_ago)
            processed[record["id"]] = record
            self._update_aggregates(record, agg, today)
        return processed, agg

    def _build_workout_record(
        self,
        workout: dict[str, Any],
        agg: dict[str, Any],
        week_ago: date,
        month_ago: date,
    ) -> dict[str, Any]:
        """Build the processed record for a single workout, updating template sets."""
        start_time = datetime.fromisoformat(workout["start_time"])
        workout_date = start_time.date()
        agg["workout_dates"].add(workout_date)
        exercises_data: dict[str, dict[str, Any]] = {}
        volume_kg = 0.0
        total_reps = 0
        for exercise in workout.get("exercises", []):
            template_id = exercise.get("exercise_template_id", "")
            sets = exercise.get("sets", [])
            exercise_volume = sum(_set_volume_kg(s) for s in sets)
            exercise_reps = sum(s.get("reps") or 0 for s in sets)
            volume_kg += exercise_volume
            total_reps += exercise_reps
            exercises_data[f"{exercise['index']}_{exercise['title']}"] = {
                "title": exercise["title"],
                "template_id": template_id,
                "sets": len(sets),
                "total_reps": exercise_reps,
                "volume_kg": exercise_volume,
                "max_weight_kg": max(
                    (s.get("weight_kg") or 0 for s in sets), default=0
                ),
            }
            if template_id and workout_date >= week_ago:
                agg["templates_7d"].add(template_id)
            if template_id and workout_date >= month_ago:
                agg["templates_30d"].add(template_id)
        record = {
            "id": workout["id"],
            "title": workout["title"],
            "start_time": start_time,
            "_end_time_raw": workout.get("end_time"),
            "exercises": exercises_data,
            "volume_kg": volume_kg,
            "total_reps": total_reps,
            "exercise_count": len(exercises_data),
        }
        record["duration_seconds"] = _workout_duration_seconds(record)
        return record

    @staticmethod
    def _update_aggregates(
        record: dict[str, Any], agg: dict[str, Any], today: date
    ) -> None:
        """Update aggregate counters based on a workout record's date bucket."""
        workout_date = record["start_time"].date()
        volume = record["volume_kg"]
        duration_s = record["duration_seconds"]
        if workout_date == today:
            agg["today_count"] += 1
            agg["volume_today"] += volume
            agg["duration_today_s"] += duration_s
        if (today - workout_date).days < 7:
            agg["week_count"] += 1
            agg["volume_week"] += volume
            agg["duration_week_s"] += duration_s
        if workout_date.year == today.year and workout_date.month == today.month:
            agg["month_count"] += 1
            agg["volume_month"] += volume
            agg["duration_month_s"] += duration_s
        if workout_date.year == today.year:
            agg["year_count"] += 1
            agg["volume_year"] += volume

    async def _safe_fetch(self, coro: Any) -> dict[str, Any] | None:
        """Await a coroutine and swallow non-auth errors (returns None on failure)."""
        try:
            return await coro
        except HevyApiClientAuthenticationError:
            raise
        except HevyApiClientError as err:
            LOGGER.warning("Optional Hevy endpoint failed: %s", err)
            return None
