"""DataUpdateCoordinator for Heating Zone integration."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    DEFAULT_HEATING_DEMAND_BINARY_SENSOR,
    DEFAULT_TUV_CURRENT_TEMP_SENSOR,
    DEFAULT_TUV_DEMAND_BINARY_SENSOR,
    DEFAULT_TUV_SETPOINT_ENTITY,
    DEFAULT_TUV_TARGET_TEMP,
    DEFAULT_TUV_TEMP_DIFF_ENTITY,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class HeatingZoneCoordinator(DataUpdateCoordinator):
    """Heating Zone coordinator."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )
        self.entry = entry
        self.heat_source_lock = asyncio.Lock()
        self.last_heat_source_on = None
        self.last_heat_source_off = None
        self._tuv_nt_completion_active = False

    def _get_heat_source_switch(self) -> str | None:
        """Return configured heat source switch with backward compatibility."""
        return self.entry.data.get("heat_source_switch") or self.entry.data.get("boiler_switch")

    def _get_heat_mode_entity(self) -> str | None:
        """Return configured heat mode select entity."""
        return self.entry.data.get("heat_mode_entity")

    def _is_direct_heat_source_control_enabled(self) -> bool:
        """Return whether shared heat source control is enabled."""
        return self.entry.data.get("control_heat_source", True)

    def _get_fve_grid_switch(self) -> str | None:
        """Return the optional switch indicating whether the heat pump runs from FVE or grid."""
        return self.entry.data.get("fve_grid_switch")

    def _is_fve_active(self) -> bool:
        """Return whether the heat pump is currently supplied from FVE."""
        fve_grid_switch = self._get_fve_grid_switch()
        switch_state = self._get_bool_state(fve_grid_switch)
        if switch_state is None:
            return False

        if self.entry.data.get("fve_active_when_on", True):
            return bool(switch_state)
        return not bool(switch_state)

    def _get_zone_climate_state(self, zone_name: str):
        """Return the matching climate state for a configured zone."""
        for state in self.hass.states.async_all("climate"):
            if state.attributes.get("zone_name") == zone_name:
                return state
        return None

    def _get_float_state(self, entity_id: str | None) -> float | None:
        """Return a numeric entity state when available."""
        if not entity_id:
            return None

        state = self.hass.states.get(entity_id)
        if not state or state.state in ("unknown", "unavailable"):
            return None

        try:
            return float(state.state)
        except (TypeError, ValueError):
            return None

    def _get_bool_state(self, entity_id: str | None) -> bool | None:
        """Return a boolean entity state when available."""
        if not entity_id:
            return None

        state = self.hass.states.get(entity_id)
        if not state or state.state in ("unknown", "unavailable"):
            return None

        if state.state == "on":
            return True
        if state.state == "off":
            return False
        return None

    def _get_existing_entity_id(self, configured_entity_id: str | None, fallback_entity_id: str) -> str | None:
        """Return configured entity id or a known fallback when it exists in HA."""
        if configured_entity_id:
            return configured_entity_id
        if self.hass.states.get(fallback_entity_id):
            return fallback_entity_id
        return None

    def _get_tuv_demand_binary_sensor(self) -> str | None:
        """Return the TUV demand binary sensor entity."""
        return self._get_existing_entity_id(
            self.entry.data.get("tuv_demand_binary_sensor"),
            DEFAULT_TUV_DEMAND_BINARY_SENSOR,
        )

    def _get_heating_demand_binary_sensor(self) -> str | None:
        """Return the heating demand binary sensor entity."""
        return self._get_existing_entity_id(
            self.entry.data.get("heating_demand_binary_sensor"),
            DEFAULT_HEATING_DEMAND_BINARY_SENSOR,
        )

    def _get_tuv_setpoint_entity(self) -> str | None:
        """Return the TUV setpoint entity."""
        return self._get_existing_entity_id(
            self.entry.data.get("tuv_setpoint_entity"),
            DEFAULT_TUV_SETPOINT_ENTITY,
        )

    def _get_tuv_current_temp_sensor(self) -> str | None:
        """Return the current TUV temperature sensor entity."""
        return self._get_existing_entity_id(
            self.entry.data.get("tuv_current_temp_sensor"),
            DEFAULT_TUV_CURRENT_TEMP_SENSOR,
        )

    def _get_tuv_temp_diff_entity(self) -> str | None:
        """Return the TUV hysteresis entity from the heat pump."""
        return self._get_existing_entity_id(
            self.entry.data.get("tuv_temp_diff_entity"),
            DEFAULT_TUV_TEMP_DIFF_ENTITY,
        )

    def _uses_heat_pump_tuv_demand(self) -> bool:
        """Return whether TUV demand should follow the heat pump entities."""
        return self._get_tuv_demand_binary_sensor() is not None

    def _get_tuv_target_temp(self) -> float:
        """Return TUV target temperature from the heat pump or configured fallback."""
        setpoint_entity = self._get_tuv_setpoint_entity()
        setpoint = self._get_float_state(setpoint_entity)
        if setpoint is not None:
            return float(setpoint)
        return float(self.entry.data.get("tuv_target_temp", DEFAULT_TUV_TARGET_TEMP))

    def _get_tuv_temp_diff(self, tuv_target_temp: float, tuv_min_ready_temp: float) -> float:
        """Return TUV hysteresis from the heat pump or a derived fallback."""
        temp_diff = self._get_float_state(self._get_tuv_temp_diff_entity())
        if temp_diff is not None:
            return max(0.0, float(temp_diff))
        return max(0.0, float(tuv_target_temp) - float(tuv_min_ready_temp))

    def _get_average_temperature(self, *values: float | None) -> float | None:
        """Return an average from available temperature values."""
        available_values = [value for value in values if value is not None]
        if not available_values:
            return None
        return sum(available_values) / len(available_values)

    def _liters_delta_to_kwh(self, volume_liters: float, delta_temp: float) -> float:
        """Convert water volume and temperature delta to stored energy in kWh."""
        if delta_temp <= 0 or volume_liters <= 0:
            return 0.0
        return volume_liters * 0.001163 * delta_temp

    def _is_zone_enabled(self, zone_name: str) -> bool:
        """Return whether the matching climate zone is enabled."""
        state = self._get_zone_climate_state(zone_name)
        if state is not None:
            return state.state != "off"
        return True

    def _get_zone_heating_requests(self) -> tuple[bool, list[str]]:
        """Return whether any configured zone currently requests heating."""
        requesting_zones: list[str] = []

        for zone in self.entry.options.get("zones", []):
            zone_name = zone.get("name", "Neznama zona")
            climate_state = self._get_zone_climate_state(zone_name)
            if climate_state is not None and climate_state.state == "off":
                continue
            if climate_state is None and not self._is_zone_enabled(zone_name):
                continue

            current_temp = self._get_float_state(zone.get("room_sensor"))
            if current_temp is None:
                continue

            target_temp = climate_state.attributes.get("temperature") if climate_state else None
            if target_temp is None and climate_state:
                target_temp = climate_state.attributes.get("target_temp")
            if target_temp is None:
                target_temp = zone.get("target_temp", 21.0)

            try:
                target_temp = float(target_temp)
            except (TypeError, ValueError):
                target_temp = float(zone.get("target_temp", 21.0))

            hysteresis = float(zone.get("hysteresis", 0.5))
            zone_is_heating = bool(climate_state and climate_state.attributes.get("heating"))
            threshold = target_temp + hysteresis if zone_is_heating else target_temp - hysteresis
            if current_temp < threshold:
                requesting_zones.append(zone_name)

        return bool(requesting_zones), requesting_zones

    def _has_any_enabled_zone(self) -> bool:
        """Return whether at least one configured heating zone is enabled."""
        for zone in self.entry.options.get("zones", []):
            zone_name = zone.get("name", "Neznama zona")
            if self._is_zone_enabled(zone_name):
                return True
        return False

    async def _async_set_heat_mode(self, mode_value: str | None) -> None:
        """Set the heat source mode when configured."""
        heat_mode_entity = self._get_heat_mode_entity()
        if not heat_mode_entity or not mode_value:
            return

        current_state = self.hass.states.get(heat_mode_entity)
        if current_state and current_state.state == mode_value:
            return

        await self.hass.services.async_call(
            "select",
            "select_option",
            {"entity_id": heat_mode_entity, "option": mode_value},
            blocking=True,
        )

    async def _async_sync_tuv_setpoint(self, data: dict[str, Any]) -> None:
        """Ensure the TUV setpoint matches the configured target."""
        if self._uses_heat_pump_tuv_demand():
            return

        tuv_setpoint_entity = self._get_tuv_setpoint_entity()
        tuv_target_temp = data.get("tuv_target_temp")
        if not tuv_setpoint_entity or tuv_target_temp is None:
            return

        current_setpoint = self._get_float_state(tuv_setpoint_entity)
        if current_setpoint is not None and abs(current_setpoint - float(tuv_target_temp)) < 0.01:
            return

        await self.hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": tuv_setpoint_entity, "value": float(tuv_target_temp)},
            blocking=True,
        )

    async def _async_turn_on_heat_source(self, heat_source_switch: str, mode_value: str | None) -> None:
        """Turn on shared heat source, respecting anti-cycling settings."""
        async with self.heat_source_lock:
            heat_source_state = self.hass.states.get(heat_source_switch)
            heat_source_is_on = bool(heat_source_state and heat_source_state.state == "on")

            if heat_source_is_on:
                await self._async_set_heat_mode(mode_value)
                return

            min_off_time = timedelta(minutes=self.entry.data.get("min_off_time", 10))
            last_off = self.last_heat_source_off
            if last_off and datetime.now() - last_off < min_off_time:
                remaining = (min_off_time - (datetime.now() - last_off)).total_seconds()
                _LOGGER.info(
                    "Heat source %s start delayed for %.0fs by min_off_time",
                    heat_source_switch,
                    remaining,
                )
                return

            await self._async_set_heat_mode(mode_value)

            _LOGGER.info("Turning ON heat source %s", heat_source_switch)
            await self.hass.services.async_call(
                "switch", "turn_on", {"entity_id": heat_source_switch}, blocking=True
            )
            self.last_heat_source_on = datetime.now()

    async def _async_turn_off_heat_source(self, heat_source_switch: str) -> None:
        """Turn off shared heat source, respecting minimum runtime."""
        async with self.heat_source_lock:
            heat_source_state = self.hass.states.get(heat_source_switch)
            if not heat_source_state or heat_source_state.state != "on":
                return

            min_run_time = timedelta(minutes=self.entry.data.get("min_run_time", 15))
            last_on = self.last_heat_source_on
            if last_on and datetime.now() - last_on < min_run_time:
                remaining = (min_run_time - (datetime.now() - last_on)).total_seconds()
                _LOGGER.info(
                    "Heat source %s stop delayed for %.0fs by min_run_time",
                    heat_source_switch,
                    remaining,
                )
                return

            _LOGGER.info("Turning OFF heat source %s", heat_source_switch)
            await self.hass.services.async_call(
                "switch", "turn_off", {"entity_id": heat_source_switch}, blocking=True
            )

            idle_mode_value = self.entry.data.get("idle_mode_value")
            if idle_mode_value:
                await self._async_set_heat_mode(idle_mode_value)

            self.last_heat_source_off = datetime.now()

    async def async_control_heat_source(self, data: dict[str, Any]) -> None:
        """Apply shared heat source control for TUV and zone heating."""
        if not self._is_direct_heat_source_control_enabled():
            return

        heat_source_switch = self._get_heat_source_switch()
        if not heat_source_switch:
            _LOGGER.warning("No heat source switch configured")
            return

        if data.get("tuv_should_heat"):
            await self._async_sync_tuv_setpoint(data)
            await self._async_turn_on_heat_source(
                heat_source_switch,
                self.entry.data.get("tuv_mode_value"),
            )
            return

        if data.get("heating_request_active"):
            await self._async_turn_on_heat_source(
                heat_source_switch,
                self.entry.data.get("heating_mode_value", "Heating Only"),
            )
            return

        if data.get("heating_cycle_active"):
            await self._async_turn_on_heat_source(
                heat_source_switch,
                self.entry.data.get("heating_mode_value", "Heating Only"),
            )
            return

        await self._async_turn_off_heat_source(heat_source_switch)

    async def _async_update_data(self) -> dict[str, Any]:
        """Return shared runtime data for heating source, TUV, NT, and buffer state."""
        entry_data = self.entry.data

        nt_binary_sensor = entry_data.get("nt_binary_sensor")
        nt_state = self.hass.states.get(nt_binary_sensor) if nt_binary_sensor else None
        nt_active = bool(nt_state and nt_state.state == "on")
        fve_active = self._is_fve_active()
        low_cost_power_active = bool(nt_active or fve_active)

        tuv_current_temp = self._get_float_state(self._get_tuv_current_temp_sensor())
        tuv_top_temp = self._get_float_state(entry_data.get("tuv_top_temp_sensor"))
        tuv_bottom_temp = self._get_float_state(entry_data.get("tuv_bottom_temp_sensor"))
        tuv_target_temp = self._get_tuv_target_temp()
        tuv_min_ready_temp = float(entry_data.get("tuv_min_ready_temp", 45.0))
        tuv_emergency_min_temp = float(entry_data.get("tuv_emergency_min_temp", 40.0))
        tuv_temp_diff = self._get_tuv_temp_diff(tuv_target_temp, tuv_min_ready_temp)
        tuv_restart_temp = max(0.0, tuv_target_temp - tuv_temp_diff)
        tuv_volume_liters = float(entry_data.get("tuv_volume_liters", 200))
        tuv_avg_temp = None
        if tuv_top_temp is not None and tuv_bottom_temp is not None:
            tuv_avg_temp = (tuv_top_temp + tuv_bottom_temp) / 2
        elif tuv_top_temp is not None:
            tuv_avg_temp = tuv_top_temp
        elif tuv_bottom_temp is not None:
            tuv_avg_temp = tuv_bottom_temp

        buffer_top_temp = self._get_float_state(entry_data.get("buffer_top_temp_sensor"))
        buffer_mid_temp = self._get_float_state(entry_data.get("buffer_mid_temp_sensor"))
        buffer_bottom_temp = self._get_float_state(entry_data.get("buffer_bottom_temp_sensor"))
        buffer_volume_liters = float(entry_data.get("buffer_volume_liters", 500))
        buffer_min_usable_temp = float(entry_data.get("buffer_min_usable_temp", 30.0))

        buffer_usable_energy_kwh = 0.0
        if buffer_top_temp is not None and buffer_mid_temp is not None and buffer_bottom_temp is not None:
            quarter_volume = buffer_volume_liters * 0.25
            half_volume = buffer_volume_liters * 0.5
            buffer_usable_energy_kwh = round(
                self._liters_delta_to_kwh(quarter_volume, buffer_top_temp - buffer_min_usable_temp)
                + self._liters_delta_to_kwh(quarter_volume, buffer_mid_temp - buffer_min_usable_temp)
                + self._liters_delta_to_kwh(
                    half_volume,
                    ((buffer_mid_temp + buffer_bottom_temp) / 2) - buffer_min_usable_temp,
                ),
                3,
            )
        elif buffer_top_temp is not None and buffer_bottom_temp is not None:
            avg_temp = (buffer_top_temp + buffer_bottom_temp) / 2
            buffer_usable_energy_kwh = round(
                self._liters_delta_to_kwh(buffer_volume_liters, avg_temp - buffer_min_usable_temp),
                3,
            )

        buffer_ready_for_heating = True

        heating_request_active, heating_requesting_zones = self._get_zone_heating_requests()
        any_zone_enabled = self._has_any_enabled_zone()
        heating_cycle_active = bool(
            any_zone_enabled and self._get_bool_state(self._get_heating_demand_binary_sensor())
        )
        tuv_control_temp = self._get_average_temperature(tuv_current_temp, tuv_top_temp)
        if tuv_control_temp is None:
            tuv_control_temp = tuv_current_temp
        if tuv_control_temp is None:
            tuv_control_temp = tuv_top_temp
        if tuv_control_temp is None:
            tuv_control_temp = tuv_bottom_temp

        tuv_ready_temp = tuv_current_temp
        if tuv_ready_temp is None:
            tuv_ready_temp = tuv_control_temp

        tuv_ready = bool(tuv_ready_temp is not None and tuv_ready_temp >= tuv_min_ready_temp)
        tuv_emergency = bool(tuv_control_temp is not None and tuv_control_temp < tuv_emergency_min_temp)
        hp_tuv_demand = self._get_bool_state(self._get_tuv_demand_binary_sensor())
        tuv_recharge_needed = bool(tuv_control_temp is not None and tuv_control_temp <= tuv_restart_temp)

        if not low_cost_power_active or tuv_ready:
            self._tuv_nt_completion_active = False
        elif tuv_recharge_needed or tuv_emergency or bool(hp_tuv_demand):
            self._tuv_nt_completion_active = True

        tuv_nt_completion_needed = bool(self._tuv_nt_completion_active and not tuv_ready)
        tuv_demand = bool(tuv_recharge_needed or tuv_emergency or tuv_nt_completion_needed)
        has_nt_config = bool(nt_binary_sensor)
        tuv_cycle_active = bool(hp_tuv_demand)
        tuv_should_heat = bool(
            tuv_cycle_active or (
                tuv_demand and (
                tuv_emergency
                or low_cost_power_active
                or not has_nt_config
                )
            )
        )

        if tuv_should_heat:
            system_demand_state = "ohrev_tuv"
        elif heating_request_active or heating_cycle_active:
            system_demand_state = "topeni"
        else:
            system_demand_state = "nic"

        if tuv_should_heat:
            system_recommended_action = "ohrivat_tuv"
        elif tuv_demand and not low_cost_power_active and has_nt_config and not heating_request_active and not heating_cycle_active:
            system_recommended_action = "cekat_na_nt_s_tuv"
        elif heating_request_active or heating_cycle_active:
            system_recommended_action = "topit_zony"
        else:
            system_recommended_action = "nic"

        data = {
            "nt_active": nt_active,
            "fve_grid_switch": self._get_fve_grid_switch(),
            "fve_active": fve_active,
            "low_cost_power_active": low_cost_power_active,
            "nt_remaining_time": self.hass.states.get(entry_data.get("nt_remaining_time_sensor")).state
            if entry_data.get("nt_remaining_time_sensor") and self.hass.states.get(entry_data.get("nt_remaining_time_sensor"))
            else None,
            "heating_demand_binary_sensor": self._get_heating_demand_binary_sensor(),
            "tuv_current_temp_sensor": self._get_tuv_current_temp_sensor(),
            "tuv_current_temp": tuv_current_temp,
            "tuv_control_temp": round(tuv_control_temp, 2) if tuv_control_temp is not None else None,
            "tuv_ready_temp": round(tuv_ready_temp, 2) if tuv_ready_temp is not None else None,
            "tuv_top_temp": tuv_top_temp,
            "tuv_bottom_temp": tuv_bottom_temp,
            "tuv_avg_temp": round(tuv_avg_temp, 2) if tuv_avg_temp is not None else None,
            "tuv_target_temp": tuv_target_temp,
            "tuv_min_ready_temp": tuv_min_ready_temp,
            "tuv_temp_diff": tuv_temp_diff,
            "tuv_restart_temp": round(tuv_restart_temp, 2),
            "tuv_emergency_min_temp": tuv_emergency_min_temp,
            "tuv_ready": tuv_ready,
            "tuv_emergency": tuv_emergency,
            "tuv_demand": tuv_demand,
            "tuv_recharge_needed": tuv_recharge_needed,
            "tuv_nt_completion_needed": tuv_nt_completion_needed,
            "tuv_cycle_active": tuv_cycle_active,
            "tuv_should_heat": tuv_should_heat,
            "tuv_demand_binary_sensor": self._get_tuv_demand_binary_sensor(),
            "tuv_setpoint_entity": self._get_tuv_setpoint_entity(),
            "tuv_temp_diff_entity": self._get_tuv_temp_diff_entity(),
            "tuv_energy_to_target_kwh": round(
                self._liters_delta_to_kwh(tuv_volume_liters, tuv_target_temp - (tuv_avg_temp or tuv_target_temp)),
                3,
            ),
            "buffer_top_temp": buffer_top_temp,
            "buffer_mid_temp": buffer_mid_temp,
            "buffer_bottom_temp": buffer_bottom_temp,
            "buffer_min_usable_temp": buffer_min_usable_temp,
            "buffer_ready_for_heating": buffer_ready_for_heating,
            "buffer_usable_energy_kwh": buffer_usable_energy_kwh,
            "heating_request_active": heating_request_active,
            "heating_demand_active": heating_request_active,
            "heating_cycle_active": heating_cycle_active,
            "heating_requesting_zones": heating_requesting_zones,
            "heating_requesting_zone_count": len(heating_requesting_zones),
            "system_demand_state": system_demand_state,
            "system_recommended_action": system_recommended_action,
        }

        try:
            await self.async_control_heat_source(data)
        except Exception:
            _LOGGER.exception("Failed to apply shared heat source control")

        return data
