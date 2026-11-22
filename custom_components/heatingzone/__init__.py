"""The Heating Zone integration."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .coordinator import HeatingZoneCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.CLIMATE, Platform.SENSOR, Platform.BINARY_SENSOR]

BOOST_START_SCHEMA = vol.Schema(
    {
        vol.Required("duration"): vol.All(vol.Coerce(int), vol.Range(min=1, max=720)),
        vol.Optional("system"): str,
    }
)
BOOST_STOP_SCHEMA = vol.Schema({vol.Optional("system"): str})


def _get_service_coordinators(hass: HomeAssistant, call: ServiceCall) -> list[HeatingZoneCoordinator]:
    """Resolve one Heating Zone system for a service call."""
    coordinators = list(hass.data.get(DOMAIN, {}).values())
    system_name = call.data.get("system")
    if system_name:
        coordinators = [
            coordinator
            for coordinator in coordinators
            if system_name
            in {
                str(coordinator.entry.data.get("name", "")),
                str(coordinator.entry.title or ""),
            }
        ]
    elif len(coordinators) > 1:
        raise HomeAssistantError(
            "Several Heating Zone systems are configured; specify the 'system' service field."
        )

    if not coordinators:
        raise HomeAssistantError("No matching Heating Zone system is loaded.")
    if len(coordinators) > 1:
        raise HomeAssistantError("The 'system' field matches more than one Heating Zone system.")
    return coordinators


async def _async_start_boost(hass: HomeAssistant, call: ServiceCall) -> None:
    """Start a timed boost for every zone in the selected system."""
    coordinator = _get_service_coordinators(hass, call)[0]
    await coordinator.async_start_boost(call.data["duration"])


async def _async_stop_boost(hass: HomeAssistant, call: ServiceCall) -> None:
    """Stop a timed boost for the selected system."""
    coordinator = _get_service_coordinators(hass, call)[0]
    await coordinator.async_stop_boost()


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register Heating Zone services."""

    async def handle_boost_start(call: ServiceCall) -> None:
        await _async_start_boost(hass, call)

    async def handle_boost_stop(call: ServiceCall) -> None:
        await _async_stop_boost(hass, call)

    hass.services.async_register(
        DOMAIN,
        "boost_start",
        handle_boost_start,
        schema=BOOST_START_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        "boost_stop",
        handle_boost_stop,
        schema=BOOST_STOP_SCHEMA,
    )
    return True


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

    coordinator = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if coordinator and coordinator.boost_active:
        await coordinator.async_stop_boost()
    
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator = hass.data[DOMAIN].pop(entry.entry_id)
        coordinator.async_shutdown()
        _LOGGER.info("Heating Zone unloaded successfully")
    
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options change."""
    _LOGGER.info("🔄 Reloading Heating Zone due to configuration change")
    await hass.config_entries.async_reload(entry.entry_id)
