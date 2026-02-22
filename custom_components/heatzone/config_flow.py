"""Config flow for Thermozona Gas integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    DOMAIN,
    CONF_OUTSIDE_TEMP_SENSOR,
    CONF_OPENTHERM_DEVICE,
    CONF_HEATING_BASE_OFFSET,
    CONF_WEATHER_SLOPE_HEAT,
    CONF_MIN_WATER_TEMP,
    CONF_MAX_WATER_TEMP,
    CONF_ZONES,
    CONF_ZONE_NAME,
    CONF_CIRCUITS,
    CONF_TEMP_SENSOR,
    CONF_TEMP_SUPPLY,
    CONF_TEMP_RETURN,
    CONF_TEMP_FLOOR,
    CONF_CONTROL_MODE,
    CONF_HYSTERESIS,
    CONF_PWM_CYCLE_TIME,
    CONF_PWM_KP,
    CONF_PWM_KI,
    CONF_VALVE_OPEN_TIME,
    CONF_VALVE_CLOSE_TIME,
    CONF_MAX_FLOOR_TEMP,
    DEFAULT_HEATING_BASE_OFFSET,
    DEFAULT_WEATHER_SLOPE_HEAT,
    DEFAULT_MIN_WATER_TEMP,
    DEFAULT_MAX_WATER_TEMP,
    DEFAULT_CONTROL_MODE,
    DEFAULT_HYSTERESIS,
    DEFAULT_PWM_CYCLE_TIME,
    DEFAULT_PWM_KP,
    DEFAULT_PWM_KI,
    DEFAULT_VALVE_OPEN_TIME,
    DEFAULT_VALVE_CLOSE_TIME,
    DEFAULT_MAX_FLOOR_TEMP,
)

_LOGGER = logging.getLogger(__name__)


class ThermozonaGasConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Thermozona Gas."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()
            
            return self.async_create_entry(
                title="Thermozona Gas",
                data=user_input,
                options={CONF_ZONES: {}},
            )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_OUTSIDE_TEMP_SENSOR): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional(CONF_OPENTHERM_DEVICE): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="climate")
                ),
                vol.Optional(
                    CONF_HEATING_BASE_OFFSET,
                    default=DEFAULT_HEATING_BASE_OFFSET,
                ): vol.All(vol.Coerce(float), vol.Range(min=0, max=10)),
                vol.Optional(
                    CONF_WEATHER_SLOPE_HEAT,
                    default=DEFAULT_WEATHER_SLOPE_HEAT,
                ): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=1.0)),
                vol.Optional(
                    CONF_MIN_WATER_TEMP,
                    default=DEFAULT_MIN_WATER_TEMP,
                ): vol.All(vol.Coerce(float), vol.Range(min=25, max=40)),
                vol.Optional(
                    CONF_MAX_WATER_TEMP,
                    default=DEFAULT_MAX_WATER_TEMP,
                ): vol.All(vol.Coerce(float), vol.Range(min=35, max=55)),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get options flow."""
        return ThermozonaGasOptionsFlow(config_entry)


class ThermozonaGasOptionsFlow(config_entries.OptionsFlow):
    """Handle options for zones."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        self.config_entry = config_entry
        self._current_zone_id = None
        self._zone_name = None

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["add_zone", "list_zones"],
        )

    async def async_step_list_zones(self, user_input=None):
        """Show list of zones."""
        zones = self.config_entry.options.get(CONF_ZONES, {})
        
        if not zones:
            message = "No zones configured. Use 'Add Zone' to create one."
        else:
            zone_list = [f"{zid}: {data.get(CONF_ZONE_NAME, zid)}" 
                         for zid, data in zones.items()]
            message = f"Configured zones ({len(zones)}):\n" + "\n".join(zone_list)
        
        return self.async_show_form(
            step_id="list_zones",
            data_schema=vol.Schema({}),
            description_placeholders={"message": message},
        )

    async def async_step_add_zone(self, user_input=None):
        """Add zone - step 1."""
        errors = {}

        if user_input is not None:
            zone_id = user_input["zone_id"].lower().replace(" ", "_")
            zones = self.config_entry.options.get(CONF_ZONES, {})
            
            if zone_id in zones:
                errors["base"] = "zone_exists"
            else:
                self._current_zone_id = zone_id
                self._zone_name = user_input[CONF_ZONE_NAME]
                return await self.async_step_zone_config()

        return self.async_show_form(
            step_id="add_zone",
            data_schema=vol.Schema({
                vol.Required("zone_id"): str,
                vol.Required(CONF_ZONE_NAME): str,
            }),
            errors=errors,
        )

    async def async_step_zone_config(self, user_input=None):
        """Configure zone details."""
        if user_input is not None:
            zones = dict(self.config_entry.options.get(CONF_ZONES, {}))
            
            zone_data = {
                CONF_ZONE_NAME: self._zone_name,
                **user_input,
            }
            
            zones[self._current_zone_id] = zone_data
            
            return self.async_create_entry(
                title="",
                data={**self.config_entry.options, CONF_ZONES: zones},
            )

        data_schema = vol.Schema(
            {
                vol.Required(CONF_CIRCUITS): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="switch", multiple=True)
                ),
                vol.Required(CONF_TEMP_SENSOR): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
                ),
                vol.Optional(CONF_TEMP_SUPPLY): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
                ),
                vol.Optional(CONF_TEMP_RETURN): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
                ),
                vol.Optional(CONF_TEMP_FLOOR): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
                ),
                vol.Optional(CONF_CONTROL_MODE, default=DEFAULT_CONTROL_MODE): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=["bang_bang", "pwm"])
                ),
                vol.Optional(CONF_HYSTERESIS, default=DEFAULT_HYSTERESIS): vol.All(
                    vol.Coerce(float), vol.Range(min=0.1, max=2.0)
                ),
                vol.Optional(CONF_PWM_CYCLE_TIME, default=DEFAULT_PWM_CYCLE_TIME): vol.All(
                    vol.Coerce(int), vol.Range(min=10, max=30)
                ),
                vol.Optional(CONF_PWM_KP, default=DEFAULT_PWM_KP): vol.All(
                    vol.Coerce(float), vol.Range(min=10, max=50)
                ),
                vol.Optional(CONF_PWM_KI, default=DEFAULT_PWM_KI): vol.All(
                    vol.Coerce(float), vol.Range(min=0.5, max=5.0)
                ),
                vol.Optional(CONF_VALVE_OPEN_TIME, default=DEFAULT_VALVE_OPEN_TIME): vol.All(
                    vol.Coerce(int), vol.Range(min=30, max=300)
                ),
                vol.Optional(CONF_VALVE_CLOSE_TIME, default=DEFAULT_VALVE_CLOSE_TIME): vol.All(
                    vol.Coerce(int), vol.Range(min=30, max=300)
                ),
                vol.Optional(CONF_MAX_FLOOR_TEMP, default=DEFAULT_MAX_FLOOR_TEMP): vol.All(
                    vol.Coerce(float), vol.Range(min=25, max=35)
                ),
            }
        )

        return self.async_show_form(
            step_id="zone_config",
            data_schema=data_schema,
        )
