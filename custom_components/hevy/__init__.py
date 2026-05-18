from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.loader import async_get_integration

from .api import HevyApiClient
from .const import (
    CONF_API_KEY,
    CONF_NAME,
    CONF_SCAN_INTERVAL,
    CONF_WORKOUTS_COUNT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_WORKOUTS_COUNT,
)
from .coordinator import HevyDataUpdateCoordinator
from .data import HevyData
from .services import async_register_services, async_unregister_services

if TYPE_CHECKING:
    from .data import HevyConfigEntry

# Create an alias for ConfigEntry to use in function signatures
HevyConfigEntry = ConfigEntry

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.CALENDAR,
]


# https://developers.home-assistant.io/docs/config_entries_index/#setting-up-an-entry
async def async_setup_entry(
    hass: HomeAssistant,
    entry: HevyConfigEntry,
) -> bool:
    """Set up this integration using UI."""
    scan_minutes = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    workouts_count = entry.options.get(CONF_WORKOUTS_COUNT, DEFAULT_WORKOUTS_COUNT)
    coordinator = HevyDataUpdateCoordinator(
        hass=hass,
        name=entry.data[CONF_NAME],
        update_interval=timedelta(minutes=scan_minutes),
        workouts_count=workouts_count,
    )
    entry.runtime_data = HevyData(
        client=HevyApiClient(
            api_key=entry.data[CONF_API_KEY],
            session=async_get_clientsession(hass),
        ),
        integration=await async_get_integration(hass, entry.domain),
        coordinator=coordinator,
    )

    # https://developers.home-assistant.io/docs/integration_fetching_data#coordinated-single-api-poll-for-data-for-all-entities
    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    async_register_services(hass)

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: HevyConfigEntry,
) -> bool:
    """Handle removal of an entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    async_unregister_services(hass)
    return unloaded


async def async_reload_entry(
    hass: HomeAssistant,
    entry: HevyConfigEntry,
) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
