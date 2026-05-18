"""Shared test fixtures.

Stubs out the Home Assistant runtime so coordinator/api logic can be tested
without installing the full HA core.
"""

from __future__ import annotations

import sys
import types
from dataclasses import dataclass
from datetime import UTC, date, datetime
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


class _StubCoordinatorEntity:
    """Minimal stand-in for CoordinatorEntity.

    Generic subscript like CoordinatorEntity[HevyDataUpdateCoordinator] is
    supported via __class_getitem__ so the import works at class-definition
    time.
    """

    def __init__(self, coordinator: Any) -> None:
        self.coordinator = coordinator

    def __class_getitem__(cls, _item: Any) -> type:
        return cls


class _StubUpdateFailed(Exception):
    """Stub for UpdateFailed."""


class _StubConfigEntryAuthFailed(Exception):
    """Stub for ConfigEntryAuthFailed."""


class _StubHomeAssistantError(Exception):
    """Stub for HomeAssistantError."""


class _StubServiceValidationError(_StubHomeAssistantError):
    """Stub for ServiceValidationError."""


class _StubEntityCategory:
    DIAGNOSTIC = "diagnostic"
    CONFIG = "config"


class _StubBinarySensorDeviceClass:
    MOTION = "motion"
    OCCUPANCY = "occupancy"


class _StubSensorDeviceClass:
    WEIGHT = "weight"
    DURATION = "duration"
    TIMESTAMP = "timestamp"


class _StubSensorStateClass:
    MEASUREMENT = "measurement"
    TOTAL_INCREASING = "total_increasing"


class _StubUnitOfMass:
    KILOGRAMS = "kg"
    POUNDS = "lb"


class _StubUnitOfTime:
    MINUTES = "min"
    SECONDS = "s"


@dataclass(kw_only=True)
class _StubBaseDescription:
    """Dataclass base mirroring HA's *EntityDescription so subclasses compose.

    Real HA descriptions use kw_only=True dataclasses; mirroring that lets the
    @dataclass decorator on HevySensorEntityDescription/etc. merge fields
    cleanly without ordering errors.
    """

    key: str = ""
    translation_key: str | None = None
    icon: str | None = None
    name: str | None = None
    device_class: Any = None
    state_class: Any = None
    native_unit_of_measurement: str | None = None
    entity_category: Any = None


class _StubSensorEntity:
    pass


class _StubBinarySensorEntity:
    pass


class _StubCalendarEntity:
    pass


class _StubConfigFlow:
    """Minimal stand-in for config_entries.ConfigFlow."""

    hass: Any = None
    context: dict[str, Any]
    VERSION: int = 1

    def __init_subclass__(cls, **kwargs: Any) -> None:
        # ConfigFlow uses `class HevyFlowHandler(ConfigFlow, domain="hevy"):`
        # — accept and discard subclass kwargs in the stub.
        super().__init_subclass__()

    async def async_set_unique_id(self, unique_id: str) -> None:
        self._unique_id = unique_id

    def _abort_if_unique_id_configured(self) -> None:
        pass

    def async_show_form(self, **kwargs: Any) -> dict[str, Any]:
        return {"type": "form", **kwargs}

    def async_create_entry(self, **kwargs: Any) -> dict[str, Any]:
        return {"type": "create_entry", **kwargs}

    def async_abort(self, *, reason: str) -> dict[str, Any]:
        return {"type": "abort", "reason": reason}


class _StubOptionsFlow:
    """Minimal stand-in for config_entries.OptionsFlow."""

    def async_show_form(self, **kwargs: Any) -> dict[str, Any]:
        return {"type": "form", **kwargs}

    def async_create_entry(self, **kwargs: Any) -> dict[str, Any]:
        return {"type": "create_entry", **kwargs}


class _StubTextSelectorType:
    TEXT = "text"
    PASSWORD = "password"  # noqa: S105 (stub mirroring HA enum)


def _passthrough_selector(*args: Any, **kwargs: Any) -> Any:
    """Return a placeholder mirroring the args/kwargs for assertions."""
    if args:
        return args[0]
    return kwargs


@dataclass
class _StubCalendarEvent:
    start: Any
    end: Any
    summary: str
    description: str | None = None
    uid: str | None = None
    location: str | None = None


def _device_info(**kwargs: Any) -> dict[str, Any]:
    """Stand-in for homeassistant.helpers.device_registry.DeviceInfo."""
    return dict(kwargs)


def _parse_date(value: Any) -> Any:
    """Minimal cv.date stand-in (passes through date/datetime, parses str)."""
    if isinstance(value, datetime | date):
        return value
    return datetime.strptime(str(value), "%Y-%m-%d").replace(tzinfo=UTC).date()


_REDACTED = "**REDACTED**"


def _async_redact_data(data: Any, to_redact: set[str]) -> Any:
    """Mirror of HA's async_redact_data helper for tests (recursive)."""
    if isinstance(data, dict):
        return {
            key: (
                _REDACTED
                if key in to_redact and value is not None
                else _async_redact_data(value, to_redact)
            )
            for key, value in data.items()
        }
    if isinstance(data, list):
        return [_async_redact_data(item, to_redact) for item in data]
    return data


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
        HomeAssistantError=_StubHomeAssistantError,
        ServiceValidationError=_StubServiceValidationError,
    )
    _pkg("homeassistant.helpers")
    _mod(
        "homeassistant.helpers.update_coordinator",
        DataUpdateCoordinator=_StubDataUpdateCoordinator,
        UpdateFailed=_StubUpdateFailed,
        CoordinatorEntity=_StubCoordinatorEntity,
    )
    _mod(
        "homeassistant.helpers.device_registry",
        DeviceInfo=_device_info,
    )
    _mod(
        "homeassistant.helpers.entity",
        EntityCategory=_StubEntityCategory,
    )
    _mod(
        "homeassistant.helpers.config_validation",
        string=str,
        date=_parse_date,
        boolean=bool,
    )
    _mod("homeassistant.core", HomeAssistant=object)
    _mod(
        "homeassistant.config_entries",
        ConfigEntry=object,
        ConfigFlow=_StubConfigFlow,
        OptionsFlow=_StubOptionsFlow,
        ConfigFlowResult=dict,
    )
    _mod(
        "homeassistant",
        config_entries=sys.modules["homeassistant.config_entries"],
    )
    _mod(
        "homeassistant.helpers.selector",
        TextSelector=_passthrough_selector,
        TextSelectorConfig=_passthrough_selector,
        TextSelectorType=_StubTextSelectorType,
    )
    _mod(
        "homeassistant.helpers.aiohttp_client",
        async_get_clientsession=lambda _hass: None,
        async_create_clientsession=lambda _hass: None,
    )
    _mod(
        "homeassistant.const",
        Platform=types.SimpleNamespace(
            SENSOR="sensor",
            BINARY_SENSOR="binary_sensor",
            CALENDAR="calendar",
        ),
        PERCENTAGE="%",
        UnitOfMass=_StubUnitOfMass,
        UnitOfTime=_StubUnitOfTime,
    )
    _mod("homeassistant.loader", async_get_integration=lambda *a, **k: None)
    _pkg("homeassistant.components")
    _mod(
        "homeassistant.components.sensor",
        SensorEntity=_StubSensorEntity,
        SensorEntityDescription=_StubBaseDescription,
        SensorDeviceClass=_StubSensorDeviceClass,
        SensorStateClass=_StubSensorStateClass,
    )
    _mod(
        "homeassistant.components.binary_sensor",
        BinarySensorEntity=_StubBinarySensorEntity,
        BinarySensorEntityDescription=_StubBaseDescription,
        BinarySensorDeviceClass=_StubBinarySensorDeviceClass,
    )
    _mod(
        "homeassistant.components.calendar",
        CalendarEntity=_StubCalendarEntity,
        CalendarEvent=_StubCalendarEvent,
    )
    _mod(
        "homeassistant.components.diagnostics",
        async_redact_data=_async_redact_data,
    )


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

    for submodule in (
        "const",
        "api",
        "data",
        "coordinator",
        "entity",
        "sensor",
        "binary_sensor",
        "calendar",
        "diagnostics",
        "services",
        "config_flow",
    ):
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


class _StubConfigEntry:
    """Minimal stand-in for ConfigEntry used by entity unique_id helpers."""

    def __init__(self, entry_id: str = "entry-123") -> None:
        self.entry_id = entry_id


@pytest.fixture
def coordinator() -> Any:
    """Build a coordinator instance without running __init__ (no HA needed)."""
    from custom_components.hevy.coordinator import HevyDataUpdateCoordinator

    coord = HevyDataUpdateCoordinator.__new__(HevyDataUpdateCoordinator)
    coord.name = "Hudson"
    return coord


@pytest.fixture
def entity_coordinator() -> Any:
    """A coordinator wired with `data`, `config_entry`, and update success flag."""
    from custom_components.hevy.coordinator import HevyDataUpdateCoordinator

    coord = HevyDataUpdateCoordinator.__new__(HevyDataUpdateCoordinator)
    coord.name = "Hudson"
    coord.config_entry = _StubConfigEntry()
    coord.last_update_success = True
    coord.data = {}
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
