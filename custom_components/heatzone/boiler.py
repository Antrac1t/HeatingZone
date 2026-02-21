"""Gas boiler controller for Thermozona Gas integration."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.components.climate import HVACMode
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event

_LOGGER = logging.getLogger(__name__)


class GasBoilerController:
    """Controller for gas condensing boilers with OpenTherm."""

    def __init__(
        self,
        hass: HomeAssistant,
        outside_temp_sensor: str,
        opentherm_device: str | None = None,
        heating_base_offset: float = 3.0,
        flow_curve_offset: float = 0.0,
        weather_slope_heat: float = 0.25,
        min_water_temp: float = 30.0,
        max_water_temp: float = 45.0,
    ) -> None:
        """Initialize the gas boiler controller."""
        self.hass = hass
        self._outside_temp_sensor = outside_temp_sensor
        self._opentherm_device = opentherm_device
        self._heating_base_offset = heating_base_offset
        self._flow_curve_offset = flow_curve_offset
        self._weather_slope_heat = weather_slope_heat
        self._min_water_temp = min_water_temp
        self._max_water_temp = max_water_temp
        
        # State
        self._thermostats: list = []
        self._current_mode: HVACMode = HVACMode.OFF
        self._target_flow_temp: float = 30.0
        self._is_boiler_on: bool = False
        self._last_temp_update: datetime | None = None
        self._valve_close_time: int = 120  # seconds (default for thermoelectric valves)
        
        # Callbacks
        self._remove_outside_temp_listener = None
        
    async def async_setup(self) -> None:
        """Set up the controller."""
        _LOGGER.info("Setting up Gas Boiler Controller")
        
        # Listen to outside temperature changes
        self._remove_outside_temp_listener = async_track_state_change_event(
            self.hass,
            [self._outside_temp_sensor],
            self._async_outside_temp_changed,
        )
        
        # Initial calculation
        await self._async_update_flow_temperature()
    
    async def async_shutdown(self) -> None:
        """Clean up the controller."""
        if self._remove_outside_temp_listener:
            self._remove_outside_temp_listener()
    
    def register_thermostat(self, thermostat: Any) -> None:
        """Register a thermostat with this controller."""
        if thermostat not in self._thermostats:
            self._thermostats.append(thermostat)
            _LOGGER.debug(
                "Registered thermostat %s, total: %d",
                thermostat.name,
                len(self._thermostats),
            )
    
    def get_pwm_zone_info(self, thermostat: Any) -> tuple[int, int]:
        """Return PWM zone index and total count for staggering."""
        try:
            index = self._thermostats.index(thermostat)
            return index, len(self._thermostats)
        except ValueError:
            return 0, 1
    
    @callback
    async def _async_outside_temp_changed(self, event: Any) -> None:
        """Handle outside temperature changes."""
        await self._async_update_flow_temperature()
    
    async def _async_update_flow_temperature(self) -> None:
        """Calculate target flow temperature using weather compensation."""
        outside_temp = self._get_outside_temperature()
        if outside_temp is None:
            _LOGGER.warning("Outside temperature not available")
            return
        
        # Get warmest zone target (for heating)
        warmest_target = self._get_warmest_zone_target()
        if warmest_target is None:
            warmest_target = 20.0  # Default
        
        # Weather compensation curve for gas boiler
        # Lower outdoor temp → higher water temp
        # Formula: T_water = base + offset + (base_room - T_outdoor) * slope
        base_water_temp = warmest_target + self._heating_base_offset
        weather_compensation = (warmest_target - outside_temp) * self._weather_slope_heat
        
        target_temp = base_water_temp + weather_compensation + self._flow_curve_offset
        
        # Clamp to safe limits for underfloor heating
        target_temp = max(self._min_water_temp, min(self._max_water_temp, target_temp))
        
        self._target_flow_temp = target_temp
        self._last_temp_update = datetime.now()
        
        _LOGGER.debug(
            "Flow temperature updated: outdoor=%.1f°C, target=%.1f°C, water=%.1f°C",
            outside_temp,
            warmest_target,
            target_temp,
        )
        
        # Update boiler if it's running
        if self._is_boiler_on and self._opentherm_device:
            await self._async_set_boiler_temperature(target_temp)
    
    def _get_outside_temperature(self) -> float | None:
        """Get current outside temperature."""
        state = self.hass.states.get(self._outside_temp_sensor)
        if state is None or state.state in ("unknown", "unavailable"):
            return None
        try:
            return float(state.state)
        except (ValueError, TypeError):
            return None
    
    def _get_warmest_zone_target(self) -> float | None:
        """Get the warmest target temperature from all zones."""
        targets = []
        for thermostat in self._thermostats:
            if hasattr(thermostat, "target_temperature"):
                if thermostat.target_temperature is not None:
                    targets.append(thermostat.target_temperature)
        
        return max(targets) if targets else None
    
    def _count_active_zones(self) -> int:
        """Count how many zones are currently calling for heat."""
        count = 0
        for thermostat in self._thermostats:
            if hasattr(thermostat, "_are_circuits_on"):
                if thermostat._are_circuits_on():
                    count += 1
        return count
    
    async def async_update_boiler_state(self) -> None:
        """Update boiler on/off state based on zone demands."""
        active_zones = self._count_active_zones()
        
        should_be_on = active_zones > 0
        
        if should_be_on and not self._is_boiler_on:
            # Turn boiler ON
            await self._async_turn_on_boiler()
        elif not should_be_on and self._is_boiler_on:
            # Turn boiler OFF (safely)
            await self._async_turn_off_boiler_safe()
    
    async def _async_turn_on_boiler(self) -> None:
        """Turn on the boiler."""
        if not self._opentherm_device:
            _LOGGER.debug("No OpenTherm device configured, boiler control skipped")
            self._is_boiler_on = True
            return
        
        _LOGGER.info("🔥 Turning ON boiler (target: %.1f°C)", self._target_flow_temp)
        
        # Set HVAC mode to heat
        await self.hass.services.async_call(
            "climate",
            "set_hvac_mode",
            {
                "entity_id": self._opentherm_device,
                "hvac_mode": "heat",
            },
            blocking=True,
        )
        
        # Set target temperature
        await self._async_set_boiler_temperature(self._target_flow_temp)
        
        self._is_boiler_on = True
        self._current_mode = HVACMode.HEAT
    
    async def _async_turn_off_boiler_safe(self) -> None:
        """Turn off boiler safely - wait for valves to close."""
        if not self._is_boiler_on:
            return
        
        _LOGGER.info(
            "❄️ Turning OFF boiler (waiting %.0fs for valves to close)",
            self._valve_close_time,
        )
        
        # Wait for thermoelectric valves to physically close
        # This prevents boiler from heating a closed system
        await self.hass.async_add_executor_job(
            lambda: __import__("time").sleep(self._valve_close_time)
        )
        
        if not self._opentherm_device:
            self._is_boiler_on = False
            return
        
        # Turn off boiler
        await self.hass.services.async_call(
            "climate",
            "set_hvac_mode",
            {
                "entity_id": self._opentherm_device,
                "hvac_mode": "off",
            },
            blocking=True,
        )
        
        self._is_boiler_on = False
        self._current_mode = HVACMode.OFF
        _LOGGER.info("✅ Boiler OFF")
    
    async def _async_set_boiler_temperature(self, temperature: float) -> None:
        """Set boiler target temperature via OpenTherm."""
        if not self._opentherm_device:
            return
        
        await self.hass.services.async_call(
            "climate",
            "set_temperature",
            {
                "entity_id": self._opentherm_device,
                "temperature": temperature,
            },
            blocking=True,
        )
        
        _LOGGER.debug("Set boiler temperature to %.1f°C", temperature)
    
    @property
    def target_flow_temperature(self) -> float:
        """Return the current target flow temperature."""
        return self._target_flow_temp
    
    @property
    def boiler_status(self) -> str:
        """Return boiler status for sensors."""
        if self._is_boiler_on:
            return "heat"
        return "idle"
    
    @property
    def pro_enabled(self) -> bool:
        """Check if Pro features are enabled (simplified - always True for gas)."""
        return True  # No licensing for gas fork
    
    def set_valve_close_time(self, seconds: int) -> None:
        """Set the valve closing time for safe shutdown."""
        self._valve_close_time = max(60, min(300, seconds))  # 1-5 minutes
        _LOGGER.debug("Valve close time set to %ds", self._valve_close_time)
