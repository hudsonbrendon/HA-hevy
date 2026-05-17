"""Shared test fixtures.

Stubs out the Home Assistant runtime so coordinator/api logic can be tested
without installing the full HA core.
"""

from __future__ import annotations

import sys
import types
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest


class _StubDataUpdateCoordinator:
    """Minimal stand-in for homeassistant.helpers.update_coordinator."""

    def __init__(
        self,
        hass: Any = None,
        logger: Any = None,
        name: str | None = None,
        update_interval: Any = None,
    ) -> None:
        self.hass = hass
        self.logger = logger
        self.name = name
        self.update_interval = update_interval


class _StubUpdateFailed(Exception):
    """Stub for UpdateFailed."""


class _StubConfigEntryAuthFailed(Exception):
    """Stub for ConfigEntryAuthFailed."""


def _install_ha_stubs() -> None:
    """Insert minimal Home Assistant modules into sys.modules."""

    def _pkg(name: str, **attrs: Any) -> types.ModuleType:
        module = types.ModuleType(name)
        module.__path__ = []
        for key, value in attrs.items():
            setattr(module, key, value)
        sys.modules[name] = module
        return module

    def _mod(name: str, **attrs: Any) -> types.ModuleType:
        module = types.ModuleType(name)
        for key, value in attrs.items():
            setattr(module, key, value)
        sys.modules[name] = module
        return module

    _pkg("homeassistant")
    _mod(
        "homeassistant.exceptions",
        ConfigEntryAuthFailed=_StubConfigEntryAuthFailed,
    )
    _pkg("homeassistant.helpers")
    _mod(
        "homeassistant.helpers.update_coordinator",
        DataUpdateCoordinator=_StubDataUpdateCoordinator,
        UpdateFailed=_StubUpdateFailed,
    )
    _mod("homeassistant.core", HomeAssistant=object)
    _mod("homeassistant.config_entries", ConfigEntry=object)
    _mod(
        "homeassistant.const",
        Platform=types.SimpleNamespace(SENSOR="sensor", BINARY_SENSOR="binary_sensor"),
    )
    _mod(
        "homeassistant.helpers.aiohttp_client",
        async_get_clientsession=lambda _hass: None,
    )
    _mod("homeassistant.loader", async_get_integration=lambda *a, **k: None)


_install_ha_stubs()

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# Pre-register the custom_components.hevy package without executing __init__.py
# (its imports pull in too much HA surface).
def _register_hevy_package() -> None:
    if "custom_components.hevy.coordinator" in sys.modules:
        return
    import importlib.util

    pkg_root = ROOT / "custom_components"
    cc_pkg = types.ModuleType("custom_components")
    cc_pkg.__path__ = [str(pkg_root)]
    sys.modules["custom_components"] = cc_pkg
    hevy_pkg = types.ModuleType("custom_components.hevy")
    hevy_pkg.__path__ = [str(pkg_root / "hevy")]
    sys.modules["custom_components.hevy"] = hevy_pkg

    for submodule in ("const", "api", "data", "coordinator"):
        spec = importlib.util.spec_from_file_location(
            f"custom_components.hevy.{submodule}",
            pkg_root / "hevy" / f"{submodule}.py",
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[f"custom_components.hevy.{submodule}"] = module
        spec.loader.exec_module(module)


_register_hevy_package()


class _FrozenDatetime(datetime):
    """datetime subclass with a fixed now() for deterministic tests."""

    _frozen_now = datetime(2026, 5, 17, 12, 0, tzinfo=UTC)

    @classmethod
    def now(cls, tz: Any = None) -> datetime:  # type: ignore[override]
        return cls._frozen_now.astimezone(tz) if tz else cls._frozen_now


@pytest.fixture
def frozen_today() -> datetime:
    """Return the fixed 'now' used by frozen_datetime."""
    return _FrozenDatetime._frozen_now


@pytest.fixture
def freeze_coordinator_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Patch coordinator.datetime to return a deterministic 'now'."""
    import custom_components.hevy.coordinator as coord_mod

    monkeypatch.setattr(coord_mod, "datetime", _FrozenDatetime)


@pytest.fixture
def coordinator() -> Any:
    """Build a coordinator instance without running __init__ (no HA needed)."""
    from custom_components.hevy.coordinator import HevyDataUpdateCoordinator

    coord = HevyDataUpdateCoordinator.__new__(HevyDataUpdateCoordinator)
    coord.name = "Hudson"
    return coord


@pytest.fixture
def workouts_fixture() -> dict[str, Any]:
    """Three workouts: today, yesterday, last month."""
    return {
        "workouts": [
            {
                "id": "w1",
                "title": "Push Day",
                "start_time": "2026-05-17T09:00:00+00:00",
                "end_time": "2026-05-17T10:15:00+00:00",
                "exercises": [
                    {
                        "index": 0,
                        "title": "Bench Press",
                        "exercise_template_id": "T1",
                        "sets": [
                            {"weight_kg": 80, "reps": 10},
                            {"weight_kg": 90, "reps": 8},
                            {"weight_kg": 100, "reps": 5},
                        ],
                    },
                    {
                        "index": 1,
                        "title": "Overhead Press",
                        "exercise_template_id": "T2",
                        "sets": [
                            {"weight_kg": 50, "reps": 10},
                            {"weight_kg": 50, "reps": 10},
                        ],
                    },
                ],
            },
            {
                "id": "w2",
                "title": "Pull Day",
                "start_time": "2026-05-16T18:00:00+00:00",
                "end_time": "2026-05-16T19:00:00+00:00",
                "exercises": [
                    {
                        "index": 0,
                        "title": "Deadlift",
                        "exercise_template_id": "T3",
                        "sets": [{"weight_kg": 140, "reps": 5}],
                    },
                ],
            },
            {
                "id": "w3",
                "title": "Old workout",
                "start_time": "2026-04-01T08:00:00+00:00",
                "end_time": "2026-04-01T08:45:00+00:00",
                "exercises": [
                    {
                        "index": 0,
                        "title": "Squat",
                        "exercise_template_id": "T4",
                        "sets": [{"weight_kg": 100, "reps": 5}],
                    },
                ],
            },
        ]
    }


@pytest.fixture
def workout_count_fixture() -> dict[str, int]:
    return {"workout_count": 42}


@pytest.fixture
def user_fixture() -> dict[str, Any]:
    return {
        "data": {
            "id": "abc",
            "name": "Hudson",
            "url": "https://hevy.com/hudson",
        }
    }


@pytest.fixture
def measurements_fixture() -> dict[str, Any]:
    return {
        "body_measurements": [
            {
                "date": "2026-05-15",
                "weight_kg": 82.0,
                "fat_percent": 18.0,
                "lean_mass_kg": 65.0,
            },
            {
                "date": "2026-05-10",
                "weight_kg": 82.5,
                "fat_percent": 18.2,
                "lean_mass_kg": 64.8,
            },
        ]
    }
