"""Thermozona Gas integration - UI config only."""
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform

from .const import DOMAIN
from .boiler import GasBoilerController

PLATFORMS = [Platform.CLIMATE, Platform.SENSOR, Platform.NUMBER]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up Thermozona Gas component (no YAML)."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Thermozona Gas from UI config entry."""
    hass.data.setdefault(DOMAIN, {})
    
    # Create boiler controller
    boiler = GasBoilerController(
        hass=hass,
        outside_temp_sensor=entry.data.get("outside_temp_sensor"),
        opentherm_device=entry.data.get("opentherm_device"),
        heating_base_offset=entry.data.get("heating_base_offset", 3.0),
        flow_curve_offset=entry.data.get("flow_curve_offset", 0.0),
        weather_slope_heat=entry.data.get("weather_slope_heat", 0.25),
        min_water_temp=entry.data.get("min_water_temp", 30.0),
        max_water_temp=entry.data.get("max_water_temp", 45.0),
    )
    
    await boiler.async_setup()
    
    hass.data[DOMAIN][entry.entry_id] = {
        "config": entry.data,
        "boiler": boiler,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Update boiler when options change
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        # Cleanup boiler
        data = hass.data[DOMAIN].pop(entry.entry_id)
        if "boiler" in data:
            await data["boiler"].async_shutdown()
    
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
