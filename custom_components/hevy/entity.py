"""HevyEntity class."""  # noqa: CPY001

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass

from .const import ATTRIBUTION, DOMAIN
from .coordinator import HevyDataUpdateCoordinator


class HevyEntity(CoordinatorEntity[HevyDataUpdateCoordinator]):
    """HevyEntity class."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True  # Use the device name as the entity name prefix

    def __init__(self, coordinator: HevyDataUpdateCoordinator) -> None:
        """Initialize."""
        super().__init__(coordinator)
        name = coordinator.name
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={
                (
                    DOMAIN,
                    f"{name}_{coordinator.config_entry.entry_id}",
                ),
            },
            name=f"{name}",  # Simplified name
            manufacturer="Hevy",
        )


class HevyWorkoutEntity(CoordinatorEntity[HevyDataUpdateCoordinator]):
    """Hevy Workout entity class."""

    _attr_attribution = ATTRIBUTION
    _workout_id: str

    def __init__(
        self,
        coordinator: HevyDataUpdateCoordinator,
        workout_id: str,
    ) -> None:
        """Initialize the workout entity."""
        super().__init__(coordinator)
        self._workout_id = workout_id
        self._attr_device_info = self._get_device_info()

    def _get_device_info(self) -> DeviceInfo:
        """Get device info for this workout."""
        name = self.coordinator.name
        workout_data = self.coordinator.data.get("workouts", {}).get(
            self._workout_id, {}
        )
        workout_title = workout_data.get("title", "Unknown Workout")
        workout_date = (
            workout_data.get("start_time", "").strftime("%Y-%m-%d")
            if workout_data.get("start_time")
            else ""
        )

        return DeviceInfo(
            identifiers={(DOMAIN, f"{name}_{self._workout_id}")},
            name=f"{name} Hevy Workout: {workout_title} ({workout_date})",
            manufacturer="Hevy",
            model="Workout",
            via_device=(DOMAIN, f"{name}_{self.coordinator.config_entry.entry_id}"),
        )

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if not self.coordinator.last_update_success:
            return False

        return self._workout_id in self.coordinator.data.get("workouts", {})

    @property
    def workout_data(self) -> dict[str, Any]:
        """Return the workout data."""
        return self.coordinator.data.get("workouts", {}).get(self._workout_id, {})


class HevyWorkoutDateSensor(HevyWorkoutEntity, SensorEntity):
    """Sensor showing the workout date."""

    def __init__(
        self,
        coordinator: HevyDataUpdateCoordinator,
        workout_id: str,
    ) -> None:
        """Initialize the workout date sensor."""
        super().__init__(coordinator, workout_id)
        name = coordinator.name
        self._attr_translation_key = "workout_date"
        self._attr_unique_id = f"{name}_{workout_id}_date"
        self._attr_device_class = SensorDeviceClass.TIMESTAMP
