"""Climate platform for Thermozona Gas."""
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

from .const import (
    DOMAIN,
    CONF_ZONES,
    CONF_ZONE_NAME,
    CONF_ZONE_ROOM_SENSOR,
    CONF_ZONE_TARGET_TEMP,
    CONF_ZONE_HYSTERESIS,
    CONF_ZONE_MAIN_CIRCUIT,
    CONF_ZONE_SUB_VALVES,
    CONF_BOILER_SWITCH,
    CONF_VALVE_OPEN_TIME,
    CONF_MAIN_CIRCUITS,
    DEFAULT_TARGET_TEMP,
    DEFAULT_HYSTERESIS,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up climate entities."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    zones = entry.data.get(CONF_ZONES, [])

    entities = []
    for zone_config in zones:
        entities.append(ThermoZonaClimate(coordinator, zone_config, entry))

    async_add_entities(entities)


class ThermoZonaClimate(CoordinatorEntity, ClimateEntity):
    """Representation of a Thermozona heating zone."""

    _attr_has_entity_name = True
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE | ClimateEntityFeature.TURN_OFF | ClimateEntityFeature.TURN_ON
    )
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]

    def __init__(self, coordinator, zone_config, entry):
        """Initialize the climate entity."""
        super().__init__(coordinator)
        self._zone_config = zone_config
        self._entry = entry
        self._attr_name = zone_config[CONF_ZONE_NAME]
        self._attr_unique_id = f"{entry.entry_id}_{zone_config[CONF_ZONE_NAME]}"
        
        self._target_temperature = zone_config.get(CONF_ZONE_TARGET_TEMP, DEFAULT_TARGET_TEMP)
        self._hysteresis = zone_config.get(CONF_ZONE_HYSTERESIS, DEFAULT_HYSTERESIS)
        self._hvac_mode = HVACMode.OFF
        self._is_heating = False

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature."""
        room_sensor = self._zone_config[CONF_ZONE_ROOM_SENSOR]
        state = self.hass.states.get(room_sensor)
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
            "zone_name": self._zone_config[CONF_ZONE_NAME],
            "hysteresis": self._hysteresis,
        }
        
        # Add main circuit info
        if self._zone_config.get(CONF_ZONE_MAIN_CIRCUIT):
            attrs["main_circuit"] = self._zone_config[CONF_ZONE_MAIN_CIRCUIT]
        
        # Add floor temperatures
        floor_temps = {}
        for idx, valve in enumerate(self._zone_config.get(CONF_ZONE_SUB_VALVES, [])):
            if valve.get("floor_sensor"):
                state = self.hass.states.get(valve["floor_sensor"])
                if state and state.state not in ("unknown", "unavailable"):
                    try:
                        floor_temps[f"sub_circuit_{idx + 1}"] = float(state.state)
                    except (ValueError, TypeError):
                        pass
        
        if floor_temps:
            attrs["floor_temperatures"] = floor_temps
        
        # Add OpenTherm data
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
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        
        self._target_temperature = temperature
        await self._async_control_zone()
        self.async_write_ha_state()

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set new HVAC mode."""
        self._hvac_mode = hvac_mode
        await self._async_control_zone()
        self.async_write_ha_state()

    async def _async_control_zone(self) -> None:
        """Control heating for this zone."""
        if self._hvac_mode == HVACMode.OFF:
            await self._async_turn_off_zone()
            self._is_heating = False
            return

        current_temp = self.current_temperature
        if current_temp is None:
            _LOGGER.warning("Cannot control zone %s: no temperature reading", self._attr_name)
            return

        # Simple hysteresis control
        if current_temp < self._target_temperature - self._hysteresis:
            # Need heating
            await self._async_turn_on_zone()
            self._is_heating = True
        elif current_temp > self._target_temperature + self._hysteresis:
            # Too hot
            await self._async_turn_off_zone()
            self._is_heating = False

    async def _async_turn_on_zone(self) -> None:
        """Turn on heating for this zone."""
        # Turn on boiler
        boiler_switch = self._entry.data[CONF_BOILER_SWITCH]
        await self.hass.services.async_call(
            "switch", "turn_on", {"entity_id": boiler_switch}, blocking=True
        )

        # Turn on main circuit if configured
        main_circuit = self._zone_config.get(CONF_ZONE_MAIN_CIRCUIT)
        if main_circuit and main_circuit != "none":
            main_circuits = self._entry.data.get(CONF_MAIN_CIRCUITS, {})
            if main_circuit in main_circuits:
                circuit_switch = main_circuits[main_circuit]
                await self.hass.services.async_call(
                    "switch", "turn_on", {"entity_id": circuit_switch}, blocking=True
                )

        # Turn on sub-valves (check floor temp limits)
        for valve_config in self._zone_config.get(CONF_ZONE_SUB_VALVES, []):
            valve_switch = valve_config["valve"]
            
            # Check floor temperature limit
            if valve_config.get("floor_sensor"):
                floor_state = self.hass.states.get(valve_config["floor_sensor"])
                if floor_state and floor_state.state not in ("unknown", "unavailable"):
                    try:
                        floor_temp = float(floor_state.state)
                        max_floor_temp = valve_config.get("max_floor_temp", 30)
                        if floor_temp >= max_floor_temp:
                            _LOGGER.info(
                                "Floor temp %.1f >= %.1f, not opening valve %s",
                                floor_temp,
                                max_floor_temp,
                                valve_switch,
                            )
                            continue
                    except (ValueError, TypeError):
                        pass
            
            await self.hass.services.async_call(
                "switch", "turn_on", {"entity_id": valve_switch}, blocking=True
            )

    async def _async_turn_off_zone(self) -> None:
        """Turn off heating for this zone."""
        # Turn off sub-valves
        for valve_config in self._zone_config.get(CONF_ZONE_SUB_VALVES, []):
            valve_switch = valve_config["valve"]
            await self.hass.services.async_call(
                "switch", "turn_off", {"entity_id": valve_switch}, blocking=True
            )

        # Turn off main circuit if configured
        main_circuit = self._zone_config.get(CONF_ZONE_MAIN_CIRCUIT)
        if main_circuit and main_circuit != "none":
            main_circuits = self._entry.data.get(CONF_MAIN_CIRCUITS, {})
            if main_circuit in main_circuits:
                circuit_switch = main_circuits[main_circuit]
                await self.hass.services.async_call(
                    "switch", "turn_off", {"entity_id": circuit_switch}, blocking=True
                )

        # Check if any other zone needs heating before turning off boiler
        # TODO: Implement check for other zones

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self.async_write_ha_state()
