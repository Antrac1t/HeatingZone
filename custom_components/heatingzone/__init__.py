"""The Heating Zone integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import HeatingZoneCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.CLIMATE]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Heating Zone from a config entry."""
    _LOGGER.info("Setting up Heating Zone for %s", entry.data.get("name"))
    
    hass.data.setdefault(DOMAIN, {})
    
    coordinator = HeatingZoneCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    
    hass.data[DOMAIN][entry.entry_id] = coordinator
    
    # Setup platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # ✅ DŮLEŽITÉ: Přidat update listener pro automatický reload
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    
    _LOGGER.info("Heating Zone setup complete for %s", entry.data.get("name"))
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading Heating Zone for %s", entry.data.get("name"))
    
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
        _LOGGER.info("Heating Zone unloaded successfully")
    
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options change."""
    _LOGGER.info("🔄 Reloading Heating Zone due to configuration change")
    await hass.config_entries.async_reload(entry.entry_id)
