"""Climate platform for Thermozona Gas - creates thermostat per zone."""
import logging
from datetime import timedelta

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.restore_state import RestoreEntity

from .const import (
    DOMAIN,
    CONF_ZONES,
    CONF_ZONE_NAME,
    CONF_CIRCUITS,
    CONF_TEMP_SENSOR,
    CONF_CONTROL_MODE,
    CONF_HYSTERESIS,
    DEFAULT_HYSTERESIS,
)

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(minutes=1)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up climate entities from zones."""
    zones = entry.options.get(CONF_ZONES, {})
    boiler = hass.data[DOMAIN][entry.entry_id]["boiler"]
    
    entities = []
    for zone_id, zone_config in zones.items():
        entities.append(
            ThermozonaGasZoneClimate(
                hass=hass,
                entry_id=entry.entry_id,
                zone_id=zone_id,
                zone_config=zone_config,
                boiler=boiler,
            )
        )
    
    if entities:
        async_add_entities(entities)


class ThermozonaGasZoneClimate(ClimateEntity, RestoreEntity):
    """Climate entity for one zone."""

    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_min_temp = 5
    _attr_max_temp = 30
    _attr_target_temperature_step = 0.5
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        zone_id: str,
        zone_config: dict,
        boiler,
    ) -> None:
        """Initialize the zone climate."""
        self.hass = hass
        self._zone_id = zone_id
        self._zone_config = zone_config
        self._boiler = boiler
        
        zone_name = zone_config.get(CONF_ZONE_NAME, zone_id)
        self._attr_name = f"Thermozona {zone_name}"
        self._attr_unique_id = f"{DOMAIN}_{entry_id}_{zone_id}"
        
        self._circuits = zone_config.get(CONF_CIRCUITS, [])
        self._temp_sensor = zone_config.get(CONF_TEMP_SENSOR)
        self._control_mode = zone_config.get(CONF_CONTROL_MODE, "bang_bang")
        self._hysteresis = zone_config.get(CONF_HYSTERESIS, DEFAULT_HYSTERESIS)
        
        self._attr_current_temperature = None
        self._attr_target_temperature = 21.0
        self._attr_hvac_mode = HVACMode.OFF
        self._attr_hvac_action = HVACAction.OFF
        
        self._remove_update_handler = None
        
        # PWM controller
        self._pwm = None
        if self._control_mode == "pwm":
            from .pwm import PWMController
            self._pwm = PWMController(
                cycle_time_minutes=zone_config.get("pwm_cycle_time", 20),
                min_on_time_minutes=zone_config.get("pwm_min_on_time", 6),
                min_off_time_minutes=zone_config.get("pwm_min_off_time", 5),
                kp=zone_config.get("pwm_kp", 30.0),
                ki=zone_config.get("pwm_ki", 2.0),
                valve_open_time_seconds=zone_config.get("valve_open_time", 120),
                valve_close_time_seconds=zone_config.get("valve_close_time", 120),
            )
        
        # Register with boiler
        self._boiler.register_thermostat(self)

    async def async_added_to_hass(self) -> None:
        """Run when entity added."""
        await super().async_added_to_hass()
        
        # Restore state
        if last_state := await self.async_get_last_state():
            if ATTR_TEMPERATURE in last_state.attributes:
                try:
                    self._attr_target_temperature = float(
                        last_state.attributes[ATTR_TEMPERATURE]
                    )
                except (TypeError, ValueError):
                    pass
            
            if last_state.state in (HVACMode.HEAT, HVACMode.OFF):
                self._attr_hvac_mode = HVACMode(last_state.state)
        
        # Start periodic updates
        self._remove_update_handler = async_track_time_interval(
            self.hass,
            self._async_update,
            SCAN_INTERVAL,
        )
        
        # Initial update
        await self._async_update(None)

    async def async_will_remove_from_hass(self) -> None:
        """Run when entity will be removed."""
        if self._remove_update_handler:
            self._remove_update_handler()

    async def _async_update(self, now) -> None:
        """Update current temperature and control circuits."""
        # Get current temperature from sensor
        if self._temp_sensor:
            state = self.hass.states.get(self._temp_sensor)
            if state and state.state not in ("unknown", "unavailable"):
                try:
                    self._attr_current_temperature = float(state.state)
                except (ValueError, TypeError):
                    pass
        
        # Control logic
        if self._attr_hvac_mode == HVACMode.HEAT and self._attr_current_temperature:
            await self._async_control_circuits()
        else:
            await self._async_turn_off_circuits()
        
        # Update boiler state
        await self._boiler.async_update_boiler_state()
        
        self.async_write_ha_state()

    async def _async_control_circuits(self) -> None:
        """Control circuits based on temperature."""
        if not self._attr_current_temperature or not self._attr_target_temperature:
            return
        
        if self._control_mode == "pwm" and self._pwm:
            # PWM control
            duty = self._pwm.calculate_duty_cycle(
                self._attr_current_temperature,
                self._attr_target_temperature,
            )
            
            self._pwm.calculate_on_time(duty)
            
            should_be_on = self._pwm.should_be_on()
            
            if should_be_on:
                await self._async_turn_on_circuits()
                self._attr_hvac_action = HVACAction.HEATING
            else:
                await self._async_turn_off_circuits()
                self._attr_hvac_action = HVACAction.IDLE
                
        else:
            # Bang-bang control with hysteresis
            error = self._attr_target_temperature - self._attr_current_temperature
            
            if error > self._hysteresis:
                # Too cold - turn on
                await self._async_turn_on_circuits()
                self._attr_hvac_action = HVACAction.HEATING
            elif error < -self._hysteresis:
                # Too warm - turn off
                await self._async_turn_off_circuits()
                self._attr_hvac_action = HVACAction.IDLE
            # else: keep current state (hysteresis band)

    async def _async_turn_on_circuits(self) -> None:
        """Turn on all circuits."""
        for circuit in self._circuits:
            await self.hass.services.async_call(
                "switch",
                "turn_on",
                {"entity_id": circuit},
                blocking=False,
            )

    async def _async_turn_off_circuits(self) -> None:
        """Turn off all circuits."""
        for circuit in self._circuits:
            await self.hass.services.async_call(
                "switch",
                "turn_off",
                {"entity_id": circuit},
                blocking=False,
            )
        self._attr_hvac_action = HVACAction.OFF

    def _are_circuits_on(self) -> bool:
        """Check if any circuit is on."""
        for circuit in self._circuits:
            state = self.hass.states.get(circuit)
            if state and state.state == "on":
                return True
        return False

    async def async_set_temperature(self, **kwargs) -> None:
        """Set new target temperature."""
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is not None:
            self._attr_target_temperature = temperature
            await self._async_update(None)
            self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set HVAC mode."""
        if hvac_mode not in self._attr_hvac_modes:
            return
        
        self._attr_hvac_mode = hvac_mode
        
        if hvac_mode == HVACMode.OFF:
            await self._async_turn_off_circuits()
            self._attr_hvac_action = HVACAction.OFF
        
        await self._async_update(None)
        self.async_write_ha_state()
