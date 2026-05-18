"""Diagnostics support for Hevy integration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.diagnostics import async_redact_data

from .const import CONF_API_KEY

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import HevyConfigEntry

TO_REDACT_DATA = {CONF_API_KEY}
TO_REDACT_COORDINATOR = {"user", "url", "profile_url", "user_id", "id"}


def _summarize_workouts(workouts: dict[str, Any]) -> dict[str, Any]:
    """Drop exercise-level detail; keep counts useful for triage."""
    summary: dict[str, Any] = {}
    for workout_id, record in workouts.items():
        summary[workout_id] = {
            "title": record.get("title"),
            "start_time": (
                record.get("start_time").isoformat()
                if record.get("start_time") is not None
                else None
            ),
            "exercise_count": record.get("exercise_count"),
            "total_reps": record.get("total_reps"),
            "volume_kg": record.get("volume_kg"),
            "duration_seconds": record.get("duration_seconds"),
        }
    return summary


def _scrub_coordinator_data(data: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of coordinator data safe for sharing in diagnostics."""
    if not data:
        return {}
    scrubbed = dict(data)
    if "workouts" in scrubbed:
        scrubbed["workouts"] = _summarize_workouts(scrubbed["workouts"])
    if scrubbed.get("last_workout"):
        lw = dict(scrubbed["last_workout"])
        lw.pop("exercises", None)
        if isinstance(lw.get("start_time"), object) and hasattr(
            lw.get("start_time"), "isoformat"
        ):
            lw["start_time"] = lw["start_time"].isoformat()
        scrubbed["last_workout"] = lw
    return async_redact_data(scrubbed, TO_REDACT_COORDINATOR)


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,  # noqa: ARG001
    entry: HevyConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for the config entry, with secrets redacted."""
    coordinator = entry.runtime_data.coordinator
    return {
        "entry": {
            "title": entry.title,
            "data": async_redact_data(dict(entry.data), TO_REDACT_DATA),
            "options": dict(entry.options),
        },
        "coordinator": {
            "name": coordinator.name,
            "update_interval_seconds": (
                coordinator.update_interval.total_seconds()
                if coordinator.update_interval is not None
                else None
            ),
            "workouts_count": coordinator._workouts_count,  # noqa: SLF001
            "primed": coordinator._primed,  # noqa: SLF001
            "last_update_success": getattr(coordinator, "last_update_success", None),
            "data": _scrub_coordinator_data(coordinator.data),
        },
    }
