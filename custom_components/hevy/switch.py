"""Switch platform for HA hevy."""  # noqa: CPY001

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .data import HevyConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,  # noqa: ARG001 Unused function argument: `hass`
    entry: HevyConfigEntry,  # noqa: ARG001 Unused function argument: `entry`
    async_add_entities: AddEntitiesCallback,  # noqa: ARG001 Unused function argument: `async_add_entities`
) -> None:
    """Set up the switch platform."""
    return
