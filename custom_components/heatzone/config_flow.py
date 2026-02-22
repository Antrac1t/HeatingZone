"""Config flow for Thermozona Gas integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class ThermoZonaGasConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Thermozona Gas."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            await self.async_set_unique_id(user_input["name"])
            self._abort_if_unique_id_configured()
            
            return self.async_create_entry(
                title=user_input["name"],
                data={
                    "name": user_input["name"],
                    "boiler_switch": user_input["boiler_switch"],
                    "opentherm_temp": user_input.get("opentherm_temp"),
                    "opentherm_return": user_input.get("opentherm_return"),
                    "opentherm_modulation": user_input.get("opentherm_modulation"),
                    "valve_open_time": user_input.get("valve_open_time", 90),
                },
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("name", default="Thermozona Gas Heating"): str,
                    vol.Required("boiler_switch"): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="switch")
                    ),
                    vol.Optional("opentherm_temp"): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor")
                    ),
                    vol.Optional("opentherm_return"): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor")
                    ),
                    vol.Optional("opentherm_modulation"): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor")
                    ),
                    vol.Optional("valve_open_time", default=90): vol.All(
                        vol.Coerce(int), vol.Range(min=30, max=300)
                    ),
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return ThermoZonaGasOptionsFlow(config_entry)


class ThermoZonaGasOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Thermozona Gas."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry
        self._zones: list[dict[str, Any]] = []
        self._current_zone_index: int | None = None
        self._current_zone: dict[str, Any] = {}
        self._valves: list[dict[str, Any]] = []

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage zones."""
        self._zones = self.config_entry.options.get("zones", [])
        
        return self.async_show_menu(
            step_id="init",
            menu_options=["add_zone", "edit_zone", "delete_zone", "finish"],
        )

    async def async_step_add_zone(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Add a new zone."""
        self._current_zone_index = None
        self._current_zone = {}
        self._valves = []
        return await self.async_step_zone_basic()

    async def async_step_edit_zone(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Edit existing zone."""
        if not self._zones:
            return await self.async_step_init()

        if user_input is not None:
            self._current_zone_index = int(user_input["zone"])
            self._current_zone = self._zones[self._current_zone_index].copy()
            self._valves = self._current_zone.get("valves", [])
            return await self.async_step_zone_basic()

        zone_options = {
            str(idx): zone["name"] for idx, zone in enumerate(self._zones)
        }

        return self.async_show_form(
            step_id="edit_zone",
            data_schema=vol.Schema(
                {
                    vol.Required("zone"): vol.In(zone_options),
                }
            ),
        )

    async def async_step_delete_zone(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Delete a zone."""
        if not self._zones:
            return await self.async_step_init()

        if user_input is not None:
            zone_idx = int(user_input["zone"])
            deleted_name = self._zones[zone_idx]["name"]
            self._zones.pop(zone_idx)
            
            return self.async_create_entry(
                title="",
                data={"zones": self._zones},
            )

        zone_options = {
            str(idx): zone["name"] for idx, zone in enumerate(self._zones)
        }

        return self.async_show_form(
            step_id="delete_zone",
            data_schema=vol.Schema(
                {
                    vol.Required("zone"): vol.In(zone_options),
                }
            ),
        )

    async def async_step_zone_basic(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Configure basic zone settings."""
        errors: dict[str, str] = {}
        
        defaults = self._current_zone if self._current_zone else {}

        if user_input is not None:
            self._current_zone.update(user_input)
            return await self.async_step_zone_control()

        return self.async_show_form(
            step_id="zone_basic",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "name",
                        description={"suggested_value": defaults.get("name", "")}
                    ): str,
                    vol.Required(
                        "room_sensor",
                        description={"suggested_value": defaults.get("room_sensor")}
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor")
                    ),
                    vol.Optional(
                        "room_size",
                        description={"suggested_value": defaults.get("room_size", 20)}
                    ): vol.All(vol.Coerce(float), vol.Range(min=5, max=100)),
                    vol.Optional(
                        "target_temp",
                        description={"suggested_value": defaults.get("target_temp", 21.0)}
                    ): vol.All(vol.Coerce(float), vol.Range(min=5, max=30)),
                }
            ),
            errors=errors,
        )

    async def async_step_zone_control(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Configure control mode and PWM settings."""
        defaults = self._current_zone if self._current_zone else {}

        if user_input is not None:
            self._current_zone.update(user_input)
            
            # If bang_bang mode, skip PWM settings
            if user_input.get("control_mode") == "bang_bang":
                return await self.async_step_zone_valves()
            else:
                return await self.async_step_zone_pwm()

        return self.async_show_form(
            step_id="zone_control",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "control_mode",
                        description={"suggested_value": defaults.get("control_mode", "bang_bang")}
                    ): vol.In({
                        "bang_bang": "Bang-Bang (ON/OFF)",
                        "pwm": "PWM (Proportional)"
                    }),
                    vol.Optional(
                        "hysteresis",
                        description={"suggested_value": defaults.get("hysteresis", 0.5)}
                    ): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=2.0)),
                }
            ),
        )

    async def async_step_zone_pwm(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Configure PWM parameters."""
        defaults = self._current_zone if self._current_zone else {}

        if user_input is not None:
            self._current_zone.update(user_input)
            return await self.async_step_zone_valves()

        return self.async_show_form(
            step_id="zone_pwm",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        "pwm_cycle_time",
                        description={
                            "suggested_value": defaults.get("pwm_cycle_time", 15)
                        }
                    ): vol.All(vol.Coerce(int), vol.Range(min=5, max=30)),
                    vol.Optional(
                        "pwm_min_on_time",
                        description={
                            "suggested_value": defaults.get("pwm_min_on_time", 3)
                        }
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=10)),
                    vol.Optional(
                        "pwm_min_off_time",
                        description={
                            "suggested_value": defaults.get("pwm_min_off_time", 3)
                        }
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=10)),
                    vol.Optional(
                        "pwm_kp",
                        description={
                            "suggested_value": defaults.get("pwm_kp", 30.0)
                        }
                    ): vol.All(vol.Coerce(float), vol.Range(min=1.0, max=100.0)),
                    vol.Optional(
                        "pwm_ki",
                        description={
                            "suggested_value": defaults.get("pwm_ki", 2.0)
                        }
                    ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=10.0)),
                }
            ),
            description_placeholders={
                "info": (
                    "PWM Parameters:\n"
                    "• Cycle time: Duration of one PWM cycle (5-30 min)\n"
                    "• Min ON time: Minimum valve opening duration (1-10 min)\n"
                    "• Min OFF time: Minimum valve closing duration (1-10 min)\n"
                    "• Kp: Proportional gain (higher = more aggressive)\n"
                    "• Ki: Integral gain (reduces steady-state error)"
                )
            }
        )

    async def async_step_zone_valves(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage valves for the zone."""
        if user_input is not None:
            action = user_input.get("action")
            
            if action == "add":
                return await self.async_step_add_valve()
            elif action == "edit" and self._valves:
                return await self.async_step_edit_valve()
            elif action == "delete" and self._valves:
                return await self.async_step_delete_valve()
            elif action == "done":
                return await self.async_step_save_zone()

        valve_list = "\n".join(
            f"• {v['valve']}" for v in self._valves
        ) if self._valves else "No valves configured"

        menu_options = ["add"]
        if self._valves:
            menu_options.extend(["edit", "delete"])
        menu_options.append("done")

        return self.async_show_menu(
            step_id="zone_valves",
            menu_options=menu_options,
            description_placeholders={
                "zone_name": self._current_zone.get("name", "Zone"),
                "valve_list": valve_list,
            }
        )

    async def async_step_add_valve(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Add a valve to the zone."""
        if user_input is not None:
            self._valves.append(user_input)
            return await self.async_step_zone_valves()

        return self.async_show_form(
            step_id="add_valve",
            data_schema=vol.Schema(
                {
                    vol.Required("valve"): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="switch")
                    ),
                    vol.Optional("floor_sensor"): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor")
                    ),
                    vol.Optional("max_floor_temp", default=30): vol.All(
                        vol.Coerce(float), vol.Range(min=20, max=40)
                    ),
                }
            ),
        )

    async def async_step_edit_valve(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Edit a valve."""
        if user_input is not None:
            if "valve_index" in user_input:
                valve_idx = int(user_input["valve_index"])
                return await self.async_step_edit_valve_details(valve_idx)

        valve_options = {
            str(idx): valve["valve"] for idx, valve in enumerate(self._valves)
        }

        return self.async_show_form(
            step_id="edit_valve",
            data_schema=vol.Schema(
                {
                    vol.Required("valve_index"): vol.In(valve_options),
                }
            ),
        )

    async def async_step_edit_valve_details(
        self, valve_idx: int, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Edit valve details."""
        if user_input is not None:
            self._valves[valve_idx] = user_input
            return await self.async_step_zone_valves()

        valve = self._valves[valve_idx]

        return self.async_show_form(
            step_id="edit_valve_details",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        "valve",
                        description={"suggested_value": valve.get("valve")}
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="switch")
                    ),
                    vol.Optional(
                        "floor_sensor",
                        description={"suggested_value": valve.get("floor_sensor")}
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="sensor")
                    ),
                    vol.Optional(
                        "max_floor_temp",
                        description={"suggested_value": valve.get("max_floor_temp", 30)}
                    ): vol.All(vol.Coerce(float), vol.Range(min=20, max=40)),
                }
            ),
        )

    async def async_step_delete_valve(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Delete a valve."""
        if user_input is not None:
            valve_idx = int(user_input["valve_index"])
            self._valves.pop(valve_idx)
            return await self.async_step_zone_valves()

        valve_options = {
            str(idx): valve["valve"] for idx, valve in enumerate(self._valves)
        }

        return self.async_show_form(
            step_id="delete_valve",
            data_schema=vol.Schema(
                {
                    vol.Required("valve_index"): vol.In(valve_options),
                }
            ),
        )

    async def async_step_save_zone(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Save the zone."""
        self._current_zone["valves"] = self._valves

        if self._current_zone_index is not None:
            self._zones[self._current_zone_index] = self._current_zone
        else:
            self._zones.append(self._current_zone)

        return self.async_create_entry(
            title="",
            data={"zones": self._zones},
        )

    async def async_step_finish(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Finish configuration."""
        return self.async_create_entry(
            title="",
            data={"zones": self._zones},
        )
