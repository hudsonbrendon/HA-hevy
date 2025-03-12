"""Binary sensor platform for hevy."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Final

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.helpers.entity import EntityCategory

from .entity import HevyEntity

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import HevyDataUpdateCoordinator
    from .data import HevyConfigEntry


@dataclass
class HevyBinarySensorEntityDescriptionRequired:
    """Required properties for HevyBinarySensorEntityDescription."""

    is_on_fn: callable[[dict[str, Any]], bool]  # Corrected: Added return type bool


@dataclass
class HevyBinarySensorEntityDescription(
    BinarySensorEntityDescription, HevyBinarySensorEntityDescriptionRequired
):
    """Hevy binary sensor entity description."""

    entity_category: EntityCategory | None = None


WORKOUT_TODAY_DESCRIPTION: Final = HevyBinarySensorEntityDescription(
    key="workout_today",
    name="Workout Today",
    device_class=BinarySensorDeviceClass.MOTION,  # Changed from ACTIVITY to MOTION
    icon="mdi:weight-lifter",
    entity_category=EntityCategory.DIAGNOSTIC,
    is_on_fn=lambda data: any(
        (
            workout.get("start_time", datetime.min).date() == datetime.now().date()
            for workout in data.get("workouts", {}).values()
        )
    ),
)

WORKOUT_WEEK_DESCRIPTION: Final = HevyBinarySensorEntityDescription(
    key="workout_this_week",
    name="Workout This Week",
    device_class=BinarySensorDeviceClass.MOTION,  # Changed from ACTIVITY to MOTION
    icon="mdi:calendar-week",
    entity_category=EntityCategory.DIAGNOSTIC,
    is_on_fn=lambda data: any(
        (
            datetime.now().date() - workout.get("start_time", datetime.min).date()
            < timedelta(days=7)
            for workout in data.get("workouts", {}).values()
        )
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001 Unused function argument: `hass`
    entry: HevyConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary sensor platform."""
    coordinator = entry.runtime_data.coordinator

    # Add entities for all defined binary sensor types
    entities = [
        HevyBinarySensor(
            coordinator=coordinator,
            entity_description=entity_description,
        )
        for entity_description in [
            WORKOUT_TODAY_DESCRIPTION,
            WORKOUT_WEEK_DESCRIPTION,
        ]
    ]

    async_add_entities(entities)


class HevyBinarySensor(HevyEntity, BinarySensorEntity):
    """Hevy Binary Sensor class."""

    entity_description: HevyBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: HevyDataUpdateCoordinator,
        entity_description: HevyBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor class."""
        super().__init__(coordinator)
        self.entity_description = entity_description

        name = coordinator.name
        self._attr_name = f"{name} {entity_description.name}"
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_{name}_{entity_description.key}"
        )

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self.entity_description.is_on_fn(self.coordinator.data)
