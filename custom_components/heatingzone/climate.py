"""Climate platform for Heating Zone."""
from __future__ import annotations

import logging
from typing import Any
from datetime import timedelta, datetime
import asyncio

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
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


# Jak často kontrolovat teplotu a řídit topení
CONTROL_INTERVAL = timedelta(seconds=30)
TARGET_TEMPERATURE_STEP = 0.2


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


class ThermoZonaClimate(CoordinatorEntity, ClimateEntity, RestoreEntity):
    """Representation of a Thermozona heating zone."""

    _attr_has_entity_name = True
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = TARGET_TEMPERATURE_STEP
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

        last_state = await self.async_get_last_state()
        if last_state:
            if last_state.state in (HVACMode.HEAT, HVACMode.OFF):
                self._hvac_mode = HVACMode(last_state.state)

            restored_target = last_state.attributes.get(ATTR_TEMPERATURE)
            if restored_target is None:
                restored_target = last_state.attributes.get("target_temp")

            if restored_target is not None:
                try:
                    self._target_temperature = float(restored_target)
                except (TypeError, ValueError):
                    pass
        
        # Start automatic control loop
        self._control_task = async_track_time_interval(
            self.hass,
            self._async_control_loop,
            CONTROL_INTERVAL
        )

        await self._async_control_zone()
        await self._async_ensure_zone_circulation()
        await self._check_and_control_heat_source()
        self.async_write_ha_state()
        
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
            "current_temp": self.current_temperature,
            "target_temp": self._target_temperature,
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

        attrs["heat_source_switch"] = self._get_heat_source_switch()
        attrs["heat_mode_entity"] = self._entry.data.get("heat_mode_entity")
        attrs["heating_mode_value"] = self._entry.data.get("heating_mode_value", "Heating Only")
        attrs["tuv_mode_value"] = self._entry.data.get("tuv_mode_value", "")
        attrs["idle_mode_value"] = self._entry.data.get("idle_mode_value", "")
        attrs["control_heat_source"] = self._is_direct_heat_source_control_enabled()
        attrs["nt_active"] = self.coordinator.data.get("nt_active") if self.coordinator.data else None
        attrs["nt_remaining_time"] = self.coordinator.data.get("nt_remaining_time") if self.coordinator.data else None
        attrs["tuv_demand_binary_sensor"] = self.coordinator.data.get("tuv_demand_binary_sensor") if self.coordinator.data else self._entry.data.get("tuv_demand_binary_sensor")
        attrs["tuv_setpoint_entity"] = self.coordinator.data.get("tuv_setpoint_entity") if self.coordinator.data else self._entry.data.get("tuv_setpoint_entity")
        attrs["tuv_temp_diff_entity"] = self.coordinator.data.get("tuv_temp_diff_entity") if self.coordinator.data else self._entry.data.get("tuv_temp_diff_entity")
        attrs["tuv_top_temp_sensor"] = self._entry.data.get("tuv_top_temp_sensor")
        attrs["tuv_bottom_temp_sensor"] = self._entry.data.get("tuv_bottom_temp_sensor")
        attrs["tuv_target_temp"] = self.coordinator.data.get("tuv_target_temp") if self.coordinator.data else None
        attrs["tuv_min_ready_temp"] = self.coordinator.data.get("tuv_min_ready_temp") if self.coordinator.data else None
        attrs["tuv_temp_diff"] = self.coordinator.data.get("tuv_temp_diff") if self.coordinator.data else None
        attrs["tuv_restart_temp"] = self.coordinator.data.get("tuv_restart_temp") if self.coordinator.data else None
        attrs["tuv_emergency_min_temp"] = self.coordinator.data.get("tuv_emergency_min_temp") if self.coordinator.data else None
        attrs["tuv_ready"] = self.coordinator.data.get("tuv_ready") if self.coordinator.data else None
        attrs["tuv_emergency"] = self.coordinator.data.get("tuv_emergency") if self.coordinator.data else None
        attrs["tuv_energy_to_target_kwh"] = self.coordinator.data.get("tuv_energy_to_target_kwh") if self.coordinator.data else None
        attrs["buffer_top_temp_sensor"] = self._entry.data.get("buffer_top_temp_sensor")
        attrs["buffer_mid_temp_sensor"] = self._entry.data.get("buffer_mid_temp_sensor")
        attrs["buffer_bottom_temp_sensor"] = self._entry.data.get("buffer_bottom_temp_sensor")
        attrs["buffer_top_temp"] = self.coordinator.data.get("buffer_top_temp") if self.coordinator.data else self._get_buffer_top_temperature()
        attrs["buffer_mid_temp"] = self.coordinator.data.get("buffer_mid_temp") if self.coordinator.data else None
        attrs["buffer_bottom_temp"] = self.coordinator.data.get("buffer_bottom_temp") if self.coordinator.data else self._get_buffer_bottom_temperature()
        attrs["buffer_min_usable_temp"] = self.coordinator.data.get("buffer_min_usable_temp") if self.coordinator.data else None
        attrs["min_buffer_top_temp"] = self._entry.data.get("min_buffer_top_temp", 0.0)
        attrs["buffer_ready_for_pump"] = self.coordinator.data.get("buffer_ready_for_heating") if self.coordinator.data else self._is_buffer_ready_for_circulation()
        attrs["buffer_usable_energy_kwh"] = self.coordinator.data.get("buffer_usable_energy_kwh") if self.coordinator.data else None
        attrs["valve_open_time"] = self._entry.data.get("valve_open_time", 120)
        attrs["min_run_time"] = self._entry.data.get("min_run_time", 15)
        attrs["min_off_time"] = self._entry.data.get("min_off_time", 10)
        attrs["circulation_pump"] = self._get_circulation_pump()
        
        return attrs

    def _get_heat_source_switch(self) -> str | None:
        """Return configured heat source switch with backward compatibility."""
        return self._entry.data.get("heat_source_switch") or self._entry.data.get("boiler_switch")

    def _get_heat_mode_entity(self) -> str | None:
        """Return configured heat mode select entity."""
        return self._entry.data.get("heat_mode_entity")

    def _get_circulation_pump(self) -> str | None:
        """Return configured circulation pump for this zone."""
        return self._zone_config.get("circulation_pump")

    def _is_direct_heat_source_control_enabled(self) -> bool:
        """Return whether room demand should switch the shared heat source."""
        return self._entry.data.get("control_heat_source", True)

    def _get_float_state(self, entity_id: str | None) -> float | None:
        """Return a numeric entity state when available."""
        if not entity_id:
            return None

        state = self.hass.states.get(entity_id)
        if not state or state.state in ("unknown", "unavailable"):
            return None

        try:
            return float(state.state)
        except (ValueError, TypeError):
            return None

    def _get_buffer_top_temperature(self) -> float | None:
        """Return current upper buffer tank temperature."""
        return self._get_float_state(self._entry.data.get("buffer_top_temp_sensor"))

    def _get_buffer_bottom_temperature(self) -> float | None:
        """Return current lower buffer tank temperature."""
        return self._get_float_state(self._entry.data.get("buffer_bottom_temp_sensor"))

    def _is_buffer_ready_for_circulation(self) -> bool:
        """Return whether the buffer tank is warm enough to start circulation pumps."""
        min_buffer_top_temp = float(self._entry.data.get("min_buffer_top_temp", 0.0))
        if min_buffer_top_temp <= 0:
            return True

        buffer_top_temp = self._get_buffer_top_temperature()
        return buffer_top_temp is not None and buffer_top_temp >= min_buffer_top_temp

    def _uses_buffer_tank(self) -> bool:
        """Return whether this installation is configured to use a buffer tank."""
        return any(
            (
                self._entry.data.get("buffer_top_temp_sensor"),
                self._entry.data.get("buffer_bottom_temp_sensor"),
                float(self._entry.data.get("min_buffer_top_temp", 0.0)) > 0,
            )
        )

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set new target temperature."""
        if temp := kwargs.get(ATTR_TEMPERATURE):
            old_temp = self._target_temperature
            self._target_temperature = temp
            current = self.current_temperature
            
            _LOGGER.info(
                "Zone %s: Target changed %.1f°C → %.1f°C (current: %.1f°C, heating: %s)",
                self._attr_name, old_temp, temp, current or 0, self._is_heating
            )
            
            # Okamžitě vyhodnotit změnu
            await self._async_control_zone()
            self.async_write_ha_state()
            
            # Dát ostatním zónám čas aktualizovat se
            await asyncio.sleep(0.5)
            
            # Force check shared heat source state
            await self._check_and_control_heat_source()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new HVAC mode."""
        old_mode = self._hvac_mode
        self._hvac_mode = hvac_mode
        
        if old_mode != hvac_mode:
            _LOGGER.info("Zone %s: HVAC mode changed from %s to %s", 
                        self._attr_name, old_mode, hvac_mode)
            await self._async_control_zone()
            
            # Force check shared heat source after mode change
            await asyncio.sleep(0.5)
            await self._check_and_control_heat_source()
        
        self.async_write_ha_state()

    async def _async_control_loop(self, now=None) -> None:
        """Periodic control loop."""
        await self._async_control_zone()
        await self._async_ensure_zone_circulation()
        await self._check_and_control_heat_source()
        if not self._is_heating:
            await self._async_sync_inactive_zone_outputs()

    async def _async_control_zone(self) -> None:
        """Control heating for this zone."""
        if self._hvac_mode == HVACMode.OFF:
            if self._is_heating:
                _LOGGER.info("Zone %s: Turning OFF (HVAC mode OFF)", self._attr_name)
                # Set flag BEFORE calling turn_off to avoid race condition
                self._is_heating = False
                await self._async_turn_off_zone()
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
            self._is_heating = True
            await self._async_turn_on_zone()
            self.async_write_ha_state()
        elif not should_heat and self._is_heating:
            _LOGGER.info(
                "Zone %s: STOP heating (%.1f°C >= %.1f°C + %.1f)",
                self._attr_name, current_temp, target, hysteresis
            )
            # Set flag FIRST before turning off
            self._is_heating = False
            self.async_write_ha_state()
            await self._async_turn_off_zone()

    async def _async_turn_on_zone(self) -> None:
        """Turn on heating for this zone."""
        valves_opened = False

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
            
            _LOGGER.info("Zone %s: ✅ Turning ON valve %s", self._attr_name, valve_switch)
            await self.hass.services.async_call(
                "switch", "turn_on", {"entity_id": valve_switch}, blocking=True
            )
            valves_opened = True

        if valves_opened:
            valve_open_time = self._entry.data.get("valve_open_time", 120)
            _LOGGER.info(
                "Zone %s: Waiting %ss for valve opening before heat source check",
                self._attr_name,
                valve_open_time,
            )
            await asyncio.sleep(valve_open_time)

            circulation_pump = self._get_circulation_pump()
            if circulation_pump and self._is_buffer_ready_for_circulation():
                _LOGGER.info("Zone %s: Turning ON circulation pump %s", self._attr_name, circulation_pump)
                await self.hass.services.async_call(
                    "switch", "turn_on", {"entity_id": circulation_pump}, blocking=True
                )
            elif circulation_pump:
                _LOGGER.info(
                    "Zone %s: Buffer top temperature is below minimum, keeping circulation pump %s OFF",
                    self._attr_name,
                    circulation_pump,
                )

        await self._check_and_control_heat_source()

    async def _async_ensure_zone_circulation(self) -> None:
        """Ensure an active zone can start its circulation pump once the buffer is ready."""
        if not self._is_heating:
            return

        circulation_pump = self._get_circulation_pump()
        if not circulation_pump:
            return

        pump_state = self.hass.states.get(circulation_pump)
        if pump_state and pump_state.state == "on":
            return

        if not self._is_buffer_ready_for_circulation():
            return

        _LOGGER.info(
            "Zone %s: Buffer temperature is ready, turning ON circulation pump %s",
            self._attr_name,
            circulation_pump,
        )
        await self.hass.services.async_call(
            "switch", "turn_on", {"entity_id": circulation_pump}, blocking=True
        )

    async def _async_turn_off_zone(self) -> None:
        """Turn off heating for this zone."""
        _LOGGER.info("Zone %s: 🛑 Turning off zone heating", self._attr_name)

        any_other_zone_heating = await self._is_any_other_zone_heating()
        if not any_other_zone_heating:
            await self._check_and_control_heat_source()

        heat_source_switch = self._get_heat_source_switch()
        heat_source_state = self.hass.states.get(heat_source_switch) if heat_source_switch else None
        heat_source_is_on = bool(heat_source_state and heat_source_state.state == "on")
        should_defer_zone_shutdown = (
            self._is_direct_heat_source_control_enabled()
            and not self._uses_buffer_tank()
            and heat_source_is_on
            and not any_other_zone_heating
        )
        
        # Turn off valves first
        for valve_config in self._zone_config.get("valves", []):
            valve_switch = valve_config["valve"]
            
            # Check if valve is needed by other zones
            if await self._is_valve_needed_by_other_zone(valve_switch):
                _LOGGER.info(
                    "Zone %s: Valve %s needed by another zone, keeping ON",
                    self._attr_name, valve_switch
                )
                continue

            if should_defer_zone_shutdown:
                _LOGGER.info(
                    "Zone %s: Heat source still ON, deferring valve close for %s",
                    self._attr_name,
                    valve_switch,
                )
                continue
            
            _LOGGER.info("Zone %s: ❌ Turning OFF valve %s", self._attr_name, valve_switch)
            await self.hass.services.async_call(
                "switch", "turn_off", {"entity_id": valve_switch}, blocking=True
            )

        circulation_pump = self._get_circulation_pump()
        if circulation_pump and not should_defer_zone_shutdown:
            if not await self._is_pump_needed_by_other_zone(circulation_pump):
                _LOGGER.info("Zone %s: Turning OFF circulation pump %s", self._attr_name, circulation_pump)
                await self.hass.services.async_call(
                    "switch", "turn_off", {"entity_id": circulation_pump}, blocking=True
                )

        await self._check_and_control_heat_source()

    async def _async_sync_inactive_zone_outputs(self) -> None:
        """Ensure inactive zones do not leave valves or pumps running."""
        heat_source_switch = self._get_heat_source_switch()
        heat_source_state = self.hass.states.get(heat_source_switch) if heat_source_switch else None
        if (
            self._is_direct_heat_source_control_enabled()
            and not self._uses_buffer_tank()
            and heat_source_state
            and heat_source_state.state == "on"
        ):
            return

        for valve_config in self._zone_config.get("valves", []):
            valve_switch = valve_config["valve"]
            if await self._is_valve_needed_by_other_zone(valve_switch):
                continue

            valve_state = self.hass.states.get(valve_switch)
            if valve_state and valve_state.state == "on":
                _LOGGER.info(
                    "Zone %s: Deferred OFF for valve %s after heat source stop",
                    self._attr_name,
                    valve_switch,
                )
                await self.hass.services.async_call(
                    "switch", "turn_off", {"entity_id": valve_switch}, blocking=True
                )

        circulation_pump = self._get_circulation_pump()
        if circulation_pump and not await self._is_pump_needed_by_other_zone(circulation_pump):
            pump_state = self.hass.states.get(circulation_pump)
            if pump_state and pump_state.state == "on":
                _LOGGER.info(
                    "Zone %s: Deferred OFF for circulation pump %s after heat source stop",
                    self._attr_name,
                    circulation_pump,
                )
                await self.hass.services.async_call(
                    "switch", "turn_off", {"entity_id": circulation_pump}, blocking=True
                )

    async def _check_and_control_heat_source(self) -> None:
        """Refresh coordinator state and re-evaluate shared heat source control."""
        if not self._is_direct_heat_source_control_enabled():
            _LOGGER.debug(
                "Zone %s: Direct heat source control disabled, skipping shared heat source switching",
                self._attr_name,
            )
            return

        await self.coordinator.async_refresh()

    async def _async_turn_on_heat_source(self, heat_source_switch: str) -> None:
        """Turn on shared heat source, respecting anti-cycling settings."""
        async with self.coordinator.heat_source_lock:
            heat_source_state = self.hass.states.get(heat_source_switch)
            if heat_source_state and heat_source_state.state == "on":
                return

            min_off_time = timedelta(minutes=self._entry.data.get("min_off_time", 10))
            last_off = self.coordinator.last_heat_source_off
            if last_off and datetime.now() - last_off < min_off_time:
                remaining = (min_off_time - (datetime.now() - last_off)).total_seconds()
                _LOGGER.info(
                    "Heat source %s start delayed for %.0fs by min_off_time",
                    heat_source_switch,
                    remaining,
                )
                return

            heat_mode_entity = self._get_heat_mode_entity()
            heating_mode_value = self._entry.data.get("heating_mode_value", "Heating Only")
            if heat_mode_entity and heating_mode_value:
                await self.hass.services.async_call(
                    "select",
                    "select_option",
                    {"entity_id": heat_mode_entity, "option": heating_mode_value},
                    blocking=True,
                )

            _LOGGER.info("🔥 Turning ON heat source %s", heat_source_switch)
            await self.hass.services.async_call(
                "switch", "turn_on", {"entity_id": heat_source_switch}, blocking=True
            )
            self.coordinator.last_heat_source_on = datetime.now()

    async def _async_turn_off_heat_source(self, heat_source_switch: str) -> None:
        """Turn off shared heat source, respecting minimum runtime."""
        async with self.coordinator.heat_source_lock:
            heat_source_state = self.hass.states.get(heat_source_switch)
            if not heat_source_state or heat_source_state.state != "on":
                return

            min_run_time = timedelta(minutes=self._entry.data.get("min_run_time", 15))
            last_on = self.coordinator.last_heat_source_on
            if last_on and datetime.now() - last_on < min_run_time:
                remaining = (min_run_time - (datetime.now() - last_on)).total_seconds()
                _LOGGER.info(
                    "Heat source %s stop delayed for %.0fs by min_run_time",
                    heat_source_switch,
                    remaining,
                )
                return

            _LOGGER.info("❄️ Turning OFF heat source %s", heat_source_switch)
            await self.hass.services.async_call(
                "switch", "turn_off", {"entity_id": heat_source_switch}, blocking=True
            )

            heat_mode_entity = self._get_heat_mode_entity()
            idle_mode_value = self._entry.data.get("idle_mode_value")
            if heat_mode_entity and idle_mode_value:
                await self.hass.services.async_call(
                    "select",
                    "select_option",
                    {"entity_id": heat_mode_entity, "option": idle_mode_value},
                    blocking=True,
                )

            self.coordinator.last_heat_source_off = datetime.now()

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

    async def _is_any_other_zone_heating(self) -> bool:
        """Check if any zone except this one is actively heating."""
        all_zones = self._entry.options.get("zones", [])

        for zone in all_zones:
            if zone["name"] == self._zone_config["name"]:
                continue

            safe_name = zone["name"].lower().replace(" ", "_").replace("-", "_")
            zone_entity_id = f"climate.{safe_name}"
            zone_state = self.hass.states.get(zone_entity_id)
            if zone_state and zone_state.attributes.get("heating", False):
                return True

        return False

    async def _is_pump_needed_by_other_zone(self, circulation_pump: str) -> bool:
        """Check if the circulation pump is still needed by another heating zone."""
        all_zones = self._entry.options.get("zones", [])

        for zone in all_zones:
            if zone["name"] == self._zone_config["name"]:
                continue

            if zone.get("circulation_pump") != circulation_pump:
                continue

            safe_name = zone["name"].lower().replace(" ", "_").replace("-", "_")
            zone_entity_id = f"climate.{safe_name}"
            zone_state = self.hass.states.get(zone_entity_id)
            if zone_state and zone_state.attributes.get("heating", False):
                return True

        return False

    async def _is_any_zone_heating(self) -> bool:
        """Check if any zone is currently actively heating."""
        all_zones = self._entry.options.get("zones", [])
        
        heating_zones = []
        idle_zones = []
        
        for zone in all_zones:
            safe_name = zone["name"].lower().replace(" ", "_").replace("-", "_")
            zone_entity_id = f"climate.{safe_name}"
            zone_state = self.hass.states.get(zone_entity_id)
            
            if zone_state:
                is_heating = zone_state.attributes.get("heating", False)
                hvac_mode = zone_state.state
                current = zone_state.attributes.get("current_temp")
                target = zone_state.attributes.get("target_temp")
                
                _LOGGER.debug(
                    "Zone %s: mode=%s, heating=%s, current=%.1f°C, target=%.1f°C",
                    zone["name"], hvac_mode, is_heating, current or 0, target or 0
                )
                
                if is_heating:
                    heating_zones.append(zone["name"])
                else:
                    idle_zones.append(zone["name"])
        
        if heating_zones:
            _LOGGER.info("🔥 Zones HEATING: %s", ", ".join(heating_zones))
            return True
        else:
            _LOGGER.info("❄️ NO zones heating (idle: %s)", ", ".join(idle_zones) if idle_zones else "none")
            return False

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
