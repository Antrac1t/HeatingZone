"""Climate platform for Thermozona Gas."""
from __future__ import annotations

import logging
from typing import Any
from datetime import timedelta

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
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Jak často kontrolovat teplotu a řídit topení
CONTROL_INTERVAL = timedelta(seconds=30)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up climate entities."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    zones = entry.options.get("zones", [])
    
    if not zones:
        _LOGGER.info("No zones configured yet")
        return
    
    _LOGGER.info("Setting up %d climate zones", len(zones))
    
    entities = []
    for zone in zones:
        zone_name = zone.get("name", "Unknown")
        _LOGGER.debug("Creating climate entity for zone: %s", zone_name)
        entities.append(ThermoZonaClimate(coordinator, zone, entry))
    
    async_add_entities(entities)


class ThermoZonaClimate(CoordinatorEntity, ClimateEntity):
    """Representation of a Thermozona heating zone."""

    _attr_has_entity_name = True
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(self, coordinator, zone_config, entry):
        """Initialize the climate entity."""
        super().__init__(coordinator)
        self._zone_config = zone_config
        self._entry = entry
        
        zone_name = zone_config.get("name", "Unknown Zone")
        self._attr_name = zone_name
        
        # Vytvořit unique_id z názvu zóny
        safe_name = zone_name.lower().replace(" ", "_").replace("-", "_")
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_{safe_name}"
        
        self._target_temperature = zone_config.get("target_temp", 21.0)
        self._hvac_mode = HVACMode.OFF
        self._is_heating = False
        self._control_task = None
        
        _LOGGER.info(
            "Initialized zone '%s' with %d valves, target: %.1f°C",
            zone_name,
            len(zone_config.get("valves", [])),
            self._target_temperature
        )

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()
        
        # Start automatic control loop
        self._control_task = async_track_time_interval(
            self.hass,
            self._async_control_loop,
            CONTROL_INTERVAL
        )
        
        _LOGGER.info("Zone %s: Control loop started (every %s)", 
                    self._attr_name, CONTROL_INTERVAL)

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed from hass."""
        if self._control_task:
            self._control_task()
            _LOGGER.info("Zone %s: Control loop stopped", self._attr_name)
        await super().async_will_remove_from_hass()

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

    @property
    def hvac_action(self) -> HVACAction:
        """Return current HVAC action."""
        if self._hvac_mode == HVACMode.OFF:
            return HVACAction.OFF
        
        if self._is_heating:
            return HVACAction.HEATING
        
        return HVACAction.IDLE

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional attributes."""
        attrs = {
            "zone_name": self._zone_config["name"],
            "hysteresis": self._zone_config.get("hysteresis", 0.5),
            "valves_count": len(self._zone_config.get("valves", [])),
            "heating": self._is_heating,
        }
        
        # Valve states
        valve_states = {}
        for idx, valve in enumerate(self._zone_config.get("valves", [])):
            valve_entity = valve["valve"]
            state = self.hass.states.get(valve_entity)
            if state:
                valve_states[f"valve_{idx + 1}"] = state.state
        
        if valve_states:
            attrs["valve_states"] = valve_states
        
        # Floor temperatures
        floor_temps = {}
        for idx, valve in enumerate(self._zone_config.get("valves", [])):
            if valve.get("floor_sensor"):
                state = self.hass.states.get(valve["floor_sensor"])
                if state and state.state not in ("unknown", "unavailable"):
                    try:
                        floor_temps[f"valve_{idx + 1}"] = float(state.state)
                    except (ValueError, TypeError):
                        pass
        
        if floor_temps:
            attrs["floor_temperatures"] = floor_temps
        
        # OpenTherm data
        if self.coordinator.data:
            if "opentherm_temp" in self.coordinator.data:
                attrs["supply_temperature"] = self.coordinator.data["opentherm_temp"]
            if "opentherm_return" in self.coordinator.data:
                attrs["return_temperature"] = self.coordinator.data["opentherm_return"]
            if "opentherm_modulation" in self.coordinator.data:
                attrs["modulation"] = self.coordinator.data["opentherm_modulation"]
        
        return attrs

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if temp := kwargs.get(ATTR_TEMPERATURE):
            old_temp = self._target_temperature
            self._target_temperature = temp
            _LOGGER.info("Zone %s: Target temperature changed from %.1f°C to %.1f°C", 
                        self._attr_name, old_temp, temp)
            # Okamžitě vyhodnotit změnu
            await self._async_control_zone()
            self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new HVAC mode."""
        old_mode = self._hvac_mode
        self._hvac_mode = hvac_mode
        
        if old_mode != hvac_mode:
            _LOGGER.info("Zone %s: HVAC mode changed from %s to %s", 
                        self._attr_name, old_mode, hvac_mode)
            await self._async_control_zone()
        
        self.async_write_ha_state()

    async def _async_control_loop(self, now=None) -> None:
        """Periodic control loop."""
        if self._hvac_mode == HVACMode.HEAT:
            await self._async_control_zone()

    async def _async_control_zone(self) -> None:
        """Control heating for this zone."""
        if self._hvac_mode == HVACMode.OFF:
            if self._is_heating:
                _LOGGER.info("Zone %s: Turning OFF (HVAC mode OFF)", self._attr_name)
                await self._async_turn_off_zone()
                self._is_heating = False
            return

        current_temp = self.current_temperature
        if current_temp is None:
            _LOGGER.warning("Zone %s: No temperature reading from %s", 
                          self._attr_name, self._zone_config["room_sensor"])
            return

        hysteresis = self._zone_config.get("hysteresis", 0.5)
        target = self._target_temperature
        
        # Hysteresis control logic
        should_heat = False
        
        if not self._is_heating:
            # Start heating if below target - hysteresis
            if current_temp < target - hysteresis:
                should_heat = True
        else:
            # Continue heating until above target + hysteresis
            if current_temp < target + hysteresis:
                should_heat = True
        
        # Apply control
        if should_heat and not self._is_heating:
            _LOGGER.info(
                "Zone %s: START heating (%.1f°C < %.1f°C - %.1f)",
                self._attr_name, current_temp, target, hysteresis
            )
            await self._async_turn_on_zone()
            self._is_heating = True
            self.async_write_ha_state()
        elif not should_heat and self._is_heating:
            _LOGGER.info(
                "Zone %s: STOP heating (%.1f°C >= %.1f°C + %.1f)",
                self._attr_name, current_temp, target, hysteresis
            )
            await self._async_turn_off_zone()
            self._is_heating = False
            self.async_write_ha_state()

    async def _async_turn_on_zone(self) -> None:
        """Turn on heating for this zone."""
        # Turn on boiler
        boiler_switch = self._entry.data.get("boiler_switch")
        if boiler_switch:
            _LOGGER.debug("Zone %s: Turning ON boiler %s", self._attr_name, boiler_switch)
            await self.hass.services.async_call(
                "switch", "turn_on", {"entity_id": boiler_switch}, blocking=True
            )

        # Turn on valves (check floor temp limits)
        for idx, valve_config in enumerate(self._zone_config.get("valves", [])):
            valve_switch = valve_config["valve"]
            
            # Check floor temperature limit
            if valve_config.get("floor_sensor"):
                floor_state = self.hass.states.get(valve_config["floor_sensor"])
                if floor_state and floor_state.state not in ("unknown", "unavailable"):
                    try:
                        floor_temp = float(floor_state.state)
                        max_floor_temp = valve_config.get("max_floor_temp", 30)
                        if floor_temp >= max_floor_temp:
                            _LOGGER.warning(
                                "Zone %s: Floor temp %.1f°C >= %.1f°C max, skipping valve %s",
                                self._attr_name, floor_temp, max_floor_temp, valve_switch
                            )
                            continue
                    except (ValueError, TypeError):
                        pass
            
            _LOGGER.debug("Zone %s: Turning ON valve %s", self._attr_name, valve_switch)
            await self.hass.services.async_call(
                "switch", "turn_on", {"entity_id": valve_switch}, blocking=True
            )

    async def _async_turn_off_zone(self) -> None:
        """Turn off heating for this zone."""
        # Turn off valves first
        for valve_config in self._zone_config.get("valves", []):
            valve_switch = valve_config["valve"]
            
            # Check if valve is needed by other zones
            if await self._is_valve_needed_by_other_zone(valve_switch):
                _LOGGER.debug(
                    "Zone %s: Valve %s needed by another zone, keeping ON",
                    self._attr_name, valve_switch
                )
                continue
            
            _LOGGER.debug("Zone %s: Turning OFF valve %s", self._attr_name, valve_switch)
            await self.hass.services.async_call(
                "switch", "turn_off", {"entity_id": valve_switch}, blocking=True
            )

        # Check if boiler can be turned off
        # IMPORTANT: Check after a small delay to ensure other zones have updated
        if not await self._is_any_zone_heating():
            boiler_switch = self._entry.data.get("boiler_switch")
            if boiler_switch:
                _LOGGER.info("Zone %s: All zones inactive, turning OFF boiler %s", 
                           self._attr_name, boiler_switch)
                await self.hass.services.async_call(
                    "switch", "turn_off", {"entity_id": boiler_switch}, blocking=True
                )
            else:
                _LOGGER.debug("Zone %s: Other zones still heating, keeping boiler ON", 
                            self._attr_name)

    async def _is_valve_needed_by_other_zone(self, valve_switch: str) -> bool:
        """Check if valve is needed by another zone that is heating."""
        all_zones = self._entry.options.get("zones", [])
        
        for zone in all_zones:
            # Skip this zone
            if zone["name"] == self._zone_config["name"]:
                continue
            
            # Create expected entity_id
            safe_name = zone["name"].lower().replace(" ", "_").replace("-", "_")
            zone_entity_id = f"climate.{safe_name}"
            zone_state = self.hass.states.get(zone_entity_id)
            
            if zone_state and zone_state.attributes.get("heating"):
                # Check if this zone uses the valve
                for v in zone.get("valves", []):
                    if v["valve"] == valve_switch:
                        _LOGGER.debug(
                            "Valve %s is needed by zone %s (heating=%s)",
                            valve_switch, zone["name"], zone_state.attributes.get("heating")
                        )
                        return True
        
        return False

    async def _is_any_zone_heating(self) -> bool:
        """Check if any zone is currently actively heating."""
        all_zones = self._entry.options.get("zones", [])
        
        heating_zones = []
        for zone in all_zones:
            safe_name = zone["name"].lower().replace(" ", "_").replace("-", "_")
            zone_entity_id = f"climate.{safe_name}"
            zone_state = self.hass.states.get(zone_entity_id)
            
            if zone_state:
                # Check actual heating state, not just HVAC mode
                is_heating = zone_state.attributes.get("heating", False)
                if is_heating:
                    heating_zones.append(zone["name"])
        
        if heating_zones:
            _LOGGER.debug("Zones currently heating: %s", ", ".join(heating_zones))
            return True
        else:
            _LOGGER.debug("No zones are currently heating")
            return False

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
