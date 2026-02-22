"""Climate platform for Thermozona Gas."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
    HVACAction,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature, ATTR_TEMPERATURE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, CONF_ZONES

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up climate entities."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    # Čteme zóny z options (ne z data)
    zones = entry.options.get(CONF_ZONES, [])
    
    entities = [ThermoZonaClimate(coordinator, zone, entry) for zone in zones]
    async_add_entities(entities)
    
    # Listener pro změny v options
    @callback
    def async_update_entity(hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Update entities when options change."""
        hass.async_create_task(
            hass.config_entries.async_reload(entry.entry_id)
        )
    
    entry.async_on_unload(entry.add_update_listener(async_update_entity))


class ThermoZonaClimate(CoordinatorEntity, ClimateEntity):
    """Representation of a Thermozona heating zone."""

    _attr_has_entity_name = True
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]

    def __init__(self, coordinator, zone_config, entry):
        """Initialize the climate entity."""
        super().__init__(coordinator)
        self._zone_config = zone_config
        self._entry = entry
        self._attr_name = zone_config["name"]
        self._attr_unique_id = f"{entry.entry_id}_{zone_config['name']}"
        self._target_temperature = zone_config.get("target_temp", 21.0)
        self._hvac_mode = HVACMode.OFF

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        state = self.hass.states.get(self._zone_config["room_sensor"])
        if state and state.state not in ("unknown", "unavailable"):
            try:
                return float(state.state)
            except (ValueError, TypeError):
                return None
        return None

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature."""
        return self._target_temperature

    @property
    def hvac_mode(self) -> HVACMode:
        """Return current HVAC mode."""
        return self._hvac_mode

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if temp := kwargs.get(ATTR_TEMPERATURE):
            self._target_temperature = temp
            self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new HVAC mode."""
        self._hvac_mode = hvac_mode
        self.async_write_ha_state()
