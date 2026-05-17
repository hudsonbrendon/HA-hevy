"""Binary sensor platform for hevy."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
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
    translation_key="workout_today",
    device_class=BinarySensorDeviceClass.MOTION,
    icon="mdi:weight-lifter",
    entity_category=EntityCategory.DIAGNOSTIC,
    is_on_fn=lambda data: any(
        [
            workout.get("start_time", datetime.min.replace(tzinfo=UTC)).date()
            == datetime.now(tz=UTC).date()
            for workout in data.get("workouts", {}).values()
        ]
    ),
)

WORKOUT_WEEK_DESCRIPTION: Final = HevyBinarySensorEntityDescription(
    key="workout_this_week",
    translation_key="workout_this_week",
    device_class=BinarySensorDeviceClass.MOTION,
    icon="mdi:calendar-week",
    entity_category=EntityCategory.DIAGNOSTIC,
    is_on_fn=lambda data: any(
        (
            datetime.now(tz=UTC).date()
            - workout.get("start_time", datetime.min.replace(tzinfo=UTC)).date()
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

        # Create a simpler unique_id
        self._attr_unique_id = (
            f"{coordinator.config_entry.entry_id}_{entity_description.key}"
        )

        # Enable entity naming with translations
        self._attr_has_entity_name = True

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self.entity_description.is_on_fn(self.coordinator.data)
