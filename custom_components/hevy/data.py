"""Custom types for hevy."""  # noqa: CPY001

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.loader import Integration

    from .api import HevyApiClient
    from .coordinator import HevyDataUpdateCoordinator


type HevyConfigEntry = ConfigEntry[HevyData]


@dataclass
class HevyData:
    """Data for the Hevy integration."""

    client: HevyApiClient
    coordinator: HevyDataUpdateCoordinator
    integration: Integration
