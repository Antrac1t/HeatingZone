"""Sensor platform for Heating Zone shared system state."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


@dataclass(kw_only=True)
class HeatingZoneSensorDescription(SensorEntityDescription):
    """Describe a Heating Zone system sensor."""

    value_key: str


SENSORS: tuple[HeatingZoneSensorDescription, ...] = (
    HeatingZoneSensorDescription(
        key="tuv_top_temp",
        name="TUV horni teplota",
        value_key="tuv_top_temp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    HeatingZoneSensorDescription(
        key="tuv_bottom_temp",
        name="TUV dolni teplota",
        value_key="tuv_bottom_temp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    HeatingZoneSensorDescription(
        key="tuv_avg_temp",
        name="TUV prumerna teplota",
        value_key="tuv_avg_temp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    HeatingZoneSensorDescription(
        key="tuv_target_temp",
        name="TUV cilova teplota",
        value_key="tuv_target_temp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    HeatingZoneSensorDescription(
        key="tuv_current_temp",
        name="TUV aktualni teplota",
        value_key="tuv_current_temp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    HeatingZoneSensorDescription(
        key="tuv_energy_to_target_kwh",
        name="TUV energie do cile",
        value_key="tuv_energy_to_target_kwh",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    ),
    HeatingZoneSensorDescription(
        key="buffer_top_temp",
        name="AN horni teplota",
        value_key="buffer_top_temp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    HeatingZoneSensorDescription(
        key="buffer_mid_temp",
        name="AN stredni teplota",
        value_key="buffer_mid_temp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    HeatingZoneSensorDescription(
        key="buffer_bottom_temp",
        name="AN dolni teplota",
        value_key="buffer_bottom_temp",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
    ),
    HeatingZoneSensorDescription(
        key="buffer_usable_energy_kwh",
        name="AN vyuzitelna energie",
        value_key="buffer_usable_energy_kwh",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
    ),
    HeatingZoneSensorDescription(
        key="nt_remaining_time",
        name="NT zbyvajici cas",
        value_key="nt_remaining_time",
    ),
    HeatingZoneSensorDescription(
        key="heating_requesting_zone_count",
        name="Pocet zon s pozadavkem",
        value_key="heating_requesting_zone_count",
    ),
    HeatingZoneSensorDescription(
        key="system_demand_state",
        name="Systemovy pozadavek",
        value_key="system_demand_state",
    ),
    HeatingZoneSensorDescription(
        key="system_recommended_action",
        name="Doporucena akce systemu",
        value_key="system_recommended_action",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Heating Zone shared sensors."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        HeatingZoneSystemSensor(coordinator, entry, description)
        for description in SENSORS
    )


class HeatingZoneSystemSensor(CoordinatorEntity, SensorEntity):
    """Shared Heating Zone system sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator,
        entry: ConfigEntry,
        description: HeatingZoneSensorDescription,
    ) -> None:
        """Initialize sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._entry = entry
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_{description.key}"
        self._attr_name = description.name

    @property
    def native_value(self) -> Any:
        """Return current value from coordinator data."""
        return self.coordinator.data.get(self.entity_description.value_key)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return diagnostic context for the system sensor."""
        return {
            "system_name": self._entry.title,
            "heating_requesting_zones": self.coordinator.data.get("heating_requesting_zones", []),
            "heating_demand_binary_sensor": self.coordinator.data.get("heating_demand_binary_sensor"),
            "tuv_demand_binary_sensor": self.coordinator.data.get("tuv_demand_binary_sensor"),
            "tuv_setpoint_entity": self._entry.data.get("tuv_setpoint_entity"),
            "tuv_current_temp_sensor": self.coordinator.data.get("tuv_current_temp_sensor"),
            "tuv_top_temp_sensor": self._entry.data.get("tuv_top_temp_sensor"),
            "tuv_bottom_temp_sensor": self._entry.data.get("tuv_bottom_temp_sensor"),
            "buffer_top_temp_sensor": self._entry.data.get("buffer_top_temp_sensor"),
            "buffer_mid_temp_sensor": self._entry.data.get("buffer_mid_temp_sensor"),
            "buffer_bottom_temp_sensor": self._entry.data.get("buffer_bottom_temp_sensor"),
            "nt_binary_sensor": self._entry.data.get("nt_binary_sensor"),
            "nt_remaining_time_sensor": self._entry.data.get("nt_remaining_time_sensor"),
        }
