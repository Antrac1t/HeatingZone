"""Sensor platform for Heating Zone."""
import logging

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature, UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from datetime import timedelta

from .const import DOMAIN, CONF_ZONES, CONF_TEMP_SUPPLY, CONF_TEMP_RETURN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=1)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities."""
    boiler = hass.data[DOMAIN][entry.entry_id]["boiler"]
    zones = entry.options.get(CONF_ZONES, {})
    
    entities = []
    
    # Global sensors
    entities.append(BoilerStatusSensor(entry.entry_id, boiler))
    entities.append(FlowTemperatureSensor(entry.entry_id, boiler))
    
    # Per-zone sensors
    for zone_id, zone_config in zones.items():
        # Delta T sensor (if supply and return available)
        if CONF_TEMP_SUPPLY in zone_config and CONF_TEMP_RETURN in zone_config:
            entities.append(
                ZoneDeltaTSensor(
                    hass,
                    entry.entry_id,
                    zone_id,
                    zone_config,
                )
            )
            entities.append(
                ZonePowerSensor(
                    hass,
                    entry.entry_id,
                    zone_id,
                    zone_config,
                )
            )
    
    if entities:
        async_add_entities(entities)


class BoilerStatusSensor(SensorEntity):
    """Boiler status sensor."""

    def __init__(self, entry_id: str, boiler) -> None:
        """Initialize."""
        self._boiler = boiler
        self._attr_name = "Thermozona Gas Boiler Status"
        self._attr_unique_id = f"{DOMAIN}_boiler_status_{entry_id}"
        self._attr_icon = "mdi:water-boiler"
        
    @property
    def native_value(self):
        """Return the state."""
        return self._boiler.boiler_status


class FlowTemperatureSensor(SensorEntity):
    """Flow temperature sensor."""

    def __init__(self, entry_id: str, boiler) -> None:
        """Initialize."""
        self._boiler = boiler
        self._attr_name = "Thermozona Gas Flow Temperature"
        self._attr_unique_id = f"{DOMAIN}_flow_temp_{entry_id}"
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_icon = "mdi:thermometer-water"
        
    @property
    def native_value(self):
        """Return the state."""
        return round(self._boiler.target_flow_temperature, 1)


class ZoneDeltaTSensor(SensorEntity):
    """Zone Delta T sensor (supply - return)."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        zone_id: str,
        zone_config: dict,
    ) -> None:
        """Initialize."""
        self.hass = hass
        self._supply_sensor = zone_config.get(CONF_TEMP_SUPPLY)
        self._return_sensor = zone_config.get(CONF_TEMP_RETURN)
        zone_name = zone_config.get("zone_name", zone_id)
        
        self._attr_name = f"Thermozona {zone_name} Delta T"
        self._attr_unique_id = f"{DOMAIN}_delta_t_{entry_id}_{zone_id}"
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_icon = "mdi:delta"
        
    @property
    def native_value(self):
        """Return Delta T."""
        supply_state = self.hass.states.get(self._supply_sensor)
        return_state = self.hass.states.get(self._return_sensor)
        
        if not supply_state or not return_state:
            return None
            
        if supply_state.state in ("unknown", "unavailable"):
            return None
        if return_state.state in ("unknown", "unavailable"):
            return None
            
        try:
            supply = float(supply_state.state)
            ret = float(return_state.state)
            delta = supply - ret
            return round(delta, 1)
        except (ValueError, TypeError):
            return None
    
    @property
    def extra_state_attributes(self):
        """Return phase classification."""
        delta = self.native_value
        if delta is None:
            return {}
        
        # Classify heating phase
        if delta > 15:
            phase = "COLD_START"
            description = "Intenzivní zahřívání"
        elif delta > 10:
            phase = "WARMING"
            description = "Aktivní dotápění"
        elif delta > 7:
            phase = "NEAR_SETPOINT"
            description = "Blízko cíle"
        else:
            phase = "STEADY"
            description = "Ustálený stav"
        
        return {
            "heating_phase": phase,
            "phase_description": description,
        }


class ZonePowerSensor(SensorEntity):
    """Zone power sensor (estimated from Delta T)."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        zone_id: str,
        zone_config: dict,
    ) -> None:
        """Initialize."""
        self.hass = hass
        self._supply_sensor = zone_config.get(CONF_TEMP_SUPPLY)
        self._return_sensor = zone_config.get(CONF_TEMP_RETURN)
        zone_name = zone_config.get("zone_name", zone_id)
        
        self._attr_name = f"Thermozona {zone_name} Power"
        self._attr_unique_id = f"{DOMAIN}_power_{entry_id}_{zone_id}"
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_native_unit_of_measurement = UnitOfPower.KILO_WATT
        self._attr_icon = "mdi:flash"
        
    @property
    def native_value(self):
        """Return estimated power from Delta T."""
        supply_state = self.hass.states.get(self._supply_sensor)
        return_state = self.hass.states.get(self._return_sensor)
        
        if not supply_state or not return_state:
            return None
            
        if supply_state.state in ("unknown", "unavailable"):
            return None
        if return_state.state in ("unknown", "unavailable"):
            return None
            
        try:
            supply = float(supply_state.state)
            ret = float(return_state.state)
            delta_t = supply - ret
            
            # Estimate flow rate from delta T (rough approximation)
            # Typical: 1-2 l/min for underfloor heating
            # Higher delta T = lower flow or colder floor
            if delta_t > 15:
                flow_rate = 2.0  # l/min (high power, cold start)
            elif delta_t > 10:
                flow_rate = 1.5
            elif delta_t > 5:
                flow_rate = 1.2
            else:
                flow_rate = 1.0
            
            # P = m_dot × c × ΔT
            # m_dot in kg/s, c = 4.186 kJ/(kg·K)
            m_dot = (flow_rate / 60.0) * 1.0  # kg/s (water density ~ 1 kg/l)
            power_w = m_dot * 4186 * delta_t
            power_kw = power_w / 1000.0
            
            return round(power_kw, 2)
        except (ValueError, TypeError):
            return None
    
    @property
    def extra_state_attributes(self):
        """Return additional attributes."""
        power = self.native_value
        if power is None:
            return {}
        
        return {
            "note": "Estimated from Delta T (flow rate assumed)",
            "accuracy": "±30%",
        }
