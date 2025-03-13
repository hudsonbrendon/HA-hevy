from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.const import Platform
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.loader import async_get_integration

from .api import HevyApiClient
from .const import CONF_API_KEY, CONF_NAME, DEFAULT_SCAN_INTERVAL
from .coordinator import HevyDataUpdateCoordinator
from .data import HevyData

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from .data import HevyConfigEntry

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
]


# https://developers.home-assistant.io/docs/config_entries_index/#setting-up-an-entry
async def async_setup_entry(
    hass: HomeAssistant,
    entry: HevyConfigEntry,
) -> bool:
    """Set up this integration using UI."""
    coordinator = HevyDataUpdateCoordinator(
        hass=hass,
        name=entry.data[CONF_NAME],
        update_interval=timedelta(minutes=DEFAULT_SCAN_INTERVAL),
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

    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: HevyConfigEntry,
) -> bool:
    """Handle removal of an entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(
    hass: HomeAssistant,
    entry: HevyConfigEntry,
) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
