"""DataUpdateCoordinator for Heating Zone integration."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntrya"""DataUpdateCoordinator for Heating Zone integration."""
from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

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

    def _liters_delta_to_kwh(self, volume_liters: float, delta_temp: float) -> float:
        """Convert water volume and temperature delta to stored energy in kWh."""
        if delta_temp <= 0 or volume_liters <= 0:
            return 0.0
        return volume_liters * 0.001163 * delta_temp

    def _is_zone_enabled(self, zone_name: str) -> bool:
        """Return whether the matching climate zone is enabled."""
        for state in self.hass.states.async_all("climate"):
            if state.attributes.get("zone_name") != zone_name:
                continue
            return state.state != "off"
        return True

    def _get_zone_heating_requests(self) -> tuple[bool, list[str]]:
        """Return whether any configured zone currently requests heating."""
        requesting_zones: list[str] = []

        for zone in self.entry.options.get("zones", []):
            zone_name = zone.get("name", "Neznama zona")
            if not self._is_zone_enabled(zone_name):
                continue

            current_temp = self._get_float_state(zone.get("room_sensor"))
            if current_temp is None:
                continue

            target_temp = float(zone.get("target_temp", 21.0))
            hysteresis = float(zone.get("hysteresis", 0.5))
            if current_temp < target_temp - hysteresis:
                requesting_zones.append(zone_name)

        return bool(requesting_zones), requesting_zones

    async def _async_update_data(self) -> dict[str, Any]:
        """Return shared runtime data for heating source, TUV, NT, and buffer state."""
        entry_data = self.entry.data

        nt_binary_sensor = entry_data.get("nt_binary_sensor")
        nt_state = self.hass.states.get(nt_binary_sensor) if nt_binary_sensor else None
        nt_active = bool(nt_state and nt_state.state == "on")

        tuv_top_temp = self._get_float_state(entry_data.get("tuv_top_temp_sensor"))
        tuv_bottom_temp = self._get_float_state(entry_data.get("tuv_bottom_temp_sensor"))
        tuv_target_temp = float(entry_data.get("tuv_target_temp", 50.0))
        tuv_min_ready_temp = float(entry_data.get("tuv_min_ready_temp", 45.0))
        tuv_emergency_min_temp = float(entry_data.get("tuv_emergency_min_temp", 40.0))
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
        min_buffer_top_temp = float(entry_data.get("min_buffer_top_temp", 0.0))

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
        if min_buffer_top_temp > 0:
            buffer_ready_for_heating = (
                buffer_top_temp is not None and buffer_top_temp >= min_buffer_top_temp
            )

        heating_demand_active, heating_requesting_zones = self._get_zone_heating_requests()
        tuv_ready = bool(tuv_top_temp is not None and tuv_top_temp >= tuv_min_ready_temp)
        tuv_emergency = bool(tuv_top_temp is not None and tuv_top_temp < tuv_emergency_min_temp)
        tuv_demand = bool(tuv_top_temp is not None and not tuv_ready)
        has_nt_config = bool(nt_binary_sensor)
        tuv_should_heat = bool(
            tuv_demand and (
                tuv_emergency
                or nt_active
                or not has_nt_config
            )
        )

        if tuv_demand:
            system_demand_state = "ohrev_tuv"
        elif heating_demand_active:
            system_demand_state = "topeni"
        else:
            system_demand_state = "nic"

        if tuv_should_heat:
            system_recommended_action = "ohrivat_tuv"
        elif tuv_demand and not nt_active and has_nt_config:
            system_recommended_action = "cekat_na_nt_s_tuv"
        elif heating_demand_active:
            system_recommended_action = "topit_zony"
        else:
            system_recommended_action = "nic"

        return {
            "nt_active": nt_active,
            "nt_remaining_time": self.hass.states.get(entry_data.get("nt_remaining_time_sensor")).state
            if entry_data.get("nt_remaining_time_sensor") and self.hass.states.get(entry_data.get("nt_remaining_time_sensor"))
            else None,
            "tuv_top_temp": tuv_top_temp,
            "tuv_bottom_temp": tuv_bottom_temp,
            "tuv_avg_temp": round(tuv_avg_temp, 2) if tuv_avg_temp is not None else None,
            "tuv_target_temp": tuv_target_temp,
            "tuv_min_ready_temp": tuv_min_ready_temp,
            "tuv_emergency_min_temp": tuv_emergency_min_temp,
            "tuv_ready": tuv_ready,
            "tuv_emergency": tuv_emergency,
            "tuv_demand": tuv_demand,
            "tuv_should_heat": tuv_should_heat,
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
            "heating_demand_active": heating_demand_active,
            "heating_requesting_zones": heating_requesting_zones,
            "heating_requesting_zone_count": len(heating_requesting_zones),
            "system_demand_state": system_demand_state,
            "system_recommended_action": system_recommended_action,
        }

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

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

    def _liters_delta_to_kwh(self, volume_liters: float, delta_temp: float) -> float:
        """Convert water volume and temperature delta to stored energy in kWh."""
        if delta_temp <= 0 or volume_liters <= 0:
            return 0.0
        return volume_liters * 0.001163 * delta_temp

    async def _async_update_data(self) -> dict[str, Any]:
        """Return shared runtime data for heating source, TUV, NT, and buffer state."""
        entry_data = self.entry.data

        nt_binary_sensor = entry_data.get("nt_binary_sensor")
        nt_state = self.hass.states.get(nt_binary_sensor) if nt_binary_sensor else None
        nt_active = bool(nt_state and nt_state.state == "on")

        tuv_top_temp = self._get_float_state(entry_data.get("tuv_top_temp_sensor"))
        tuv_bottom_temp = self._get_float_state(entry_data.get("tuv_bottom_temp_sensor"))
        tuv_target_temp = float(entry_data.get("tuv_target_temp", 50.0))
        tuv_min_ready_temp = float(entry_data.get("tuv_min_ready_temp", 45.0))
        tuv_emergency_min_temp = float(entry_data.get("tuv_emergency_min_temp", 40.0))
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
        min_buffer_top_temp = float(entry_data.get("min_buffer_top_temp", 0.0))

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
        if min_buffer_top_temp > 0:
            buffer_ready_for_heating = (
                buffer_top_temp is not None and buffer_top_temp >= min_buffer_top_temp
            )

        return {
            "nt_active": nt_active,
            "nt_remaining_time": self.hass.states.get(entry_data.get("nt_remaining_time_sensor")).state
            if entry_data.get("nt_remaining_time_sensor") and self.hass.states.get(entry_data.get("nt_remaining_time_sensor"))
            else None,
            "tuv_top_temp": tuv_top_temp,
            "tuv_bottom_temp": tuv_bottom_temp,
            "tuv_avg_temp": round(tuv_avg_temp, 2) if tuv_avg_temp is not None else None,
            "tuv_target_temp": tuv_target_temp,
            "tuv_min_ready_temp": tuv_min_ready_temp,
            "tuv_emergency_min_temp": tuv_emergency_min_temp,
            "tuv_ready": bool(tuv_top_temp is not None and tuv_top_temp >= tuv_min_ready_temp),
            "tuv_emergency": bool(tuv_top_temp is not None and tuv_top_temp < tuv_emergency_min_temp),
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
        }
