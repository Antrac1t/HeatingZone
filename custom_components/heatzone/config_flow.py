"""Config flow for Thermozona Gas."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv
from homeassistant.data_entry_flow import FlowResult
from typing import Any

from .const import (
    DOMAIN,
    CONTROL_MODE_ONOFF,
    CONTROL_MODE_PWM,
    DEFAULT_VALVE_OPEN_TIME,
    DEFAULT_HYSTERESIS,
    DEFAULT_TARGET_TEMP,
    DEFAULT_MAX_FLOOR_TEMP,
)


class ThermoZonaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle config flow."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle initial step."""
        errors = {}

        if user_input is not None:
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()
            
            return self.async_create_entry(
                title="Thermozona Gas Heating",
                data=user_input
            )

        data_schema = vol.Schema(
            {
                vol.Required("boiler_switch"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="switch")
                ),
                vol.Optional("opentherm_temp_sensor"): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="sensor", device_class=["temperature"]
                    )
                ),
                vol.Required(
                    "valve_open_time", default=DEFAULT_VALVE_OPEN_TIME
                ): vol.All(vol.Coerce(int), vol.Range(min=30, max=300)),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry):
        """Get options flow."""
        return OptionsFlow(config_entry)


class OptionsFlow(config_entries.OptionsFlow):
    """Options flow."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize."""
        super().__init__()
        self._config_entry = config_entry
        self._zone_index: int | None = None

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Main options menu."""
        if user_input is not None:
            action = user_input.get("action")
            
            if action == "add_zone":
                self._zone_index = None
                return await self.async_step_zone_config()
            elif action == "list_zones":
                return await self.async_step_list_zones()
            elif action == "circuits":
                return await self.async_step_circuits()
        
        # Get current zones count
        zones = self._config_entry.options.get("zones", [])
        zones_count = len(zones)
        
        actions = {
            "add_zone": f"➕ Přidat zónu (aktuálně: {zones_count})",
            "list_zones": "📋 Spravovat zóny",
            "circuits": "🔧 Hlavní okruhy",
        }
        
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required("action"): vol.In(actions)
            })
        )

    async def async_step_circuits(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Configure main circuits."""
        if user_input is not None:
            circuits = {}
            for key in ["circuit_1", "circuit_2", "kitchen", "bathroom"]:
                switch_key = f"{key}_switch"
                if user_input.get(switch_key):
                    circuits[key] = user_input[switch_key]
            
            new_options = dict(self._config_entry.options)
            new_options["main_circuits"] = circuits
            
            return self.async_create_entry(title="", data=new_options)

        current_circuits = self._config_entry.options.get("main_circuits", {})

        return self.async_show_form(
            step_id="circuits",
            data_schema=vol.Schema({
                vol.Optional(
                    "circuit_1_switch",
                    description={"suggested_value": current_circuits.get("circuit_1")}
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=["switch"])
                ),
                vol.Optional(
                    "circuit_2_switch",
                    description={"suggested_value": current_circuits.get("circuit_2")}
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=["switch"])
                ),
                vol.Optional(
                    "kitchen_switch",
                    description={"suggested_value": current_circuits.get("kitchen")}
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=["switch"])
                ),
                vol.Optional(
                    "bathroom_switch",
                    description={"suggested_value": current_circuits.get("bathroom")}
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=["switch"])
                ),
            })
        )

    async def async_step_list_zones(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """List zones with edit/delete."""
        zones = list(self._config_entry.options.get("zones", []))
        
        if user_input is not None:
            action = user_input.get("action")
            
            if action == "back":
                return await self.async_step_init()
            elif action and action.startswith("edit_"):
                self._zone_index = int(action.split("_")[1])
                return await self.async_step_zone_config()
            elif action and action.startswith("delete_"):
                zone_idx = int(action.split("_")[1])
                zones.pop(zone_idx)
                
                new_options = dict(self._config_entry.options)
                new_options["zones"] = zones
                
                return self.async_create_entry(title="", data=new_options)

        if not zones:
            return self.async_show_form(
                step_id="list_zones",
                data_schema=vol.Schema({
                    vol.Required("action"): vol.In({"back": "⬅️ Zpět"})
                }),
                description_placeholders={"info": "Zatím nemáte žádné zóny"}
            )

        actions = {"back": "⬅️ Zpět"}
        for idx, zone in enumerate(zones):
            name = zone.get("name", f"Zóna {idx+1}")
            actions[f"edit_{idx}"] = f"✏️ {name}"
            actions[f"delete_{idx}"] = f"🗑️ {name}"

        zones_info = "\n".join([
            f"{i+1}. {z.get('name', 'Bez názvu')} - {z.get('target_temp', 21)}°C"
            for i, z in enumerate(zones)
        ])

        return self.async_show_form(
            step_id="list_zones",
            data_schema=vol.Schema({
                vol.Required("action"): vol.In(actions)
            }),
            description_placeholders={"info": zones_info}
        )

    async def async_step_zone_config(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Configure zone."""
        zones = list(self._config_entry.options.get("zones", []))
        
        if user_input is not None:
            zone = {
                "name": user_input["zone_name"],
                "room_sensor": user_input["room_sensor"],
                "target_temp": user_input.get("target_temp", DEFAULT_TARGET_TEMP),
                "hysteresis": user_input.get("hysteresis", DEFAULT_HYSTERESIS),
                "main_circuit": user_input.get("main_circuit", "none"),
                "sub_valves": []
            }
            
            # Add sub-valves
            for i in range(1, 5):
                if user_input.get(f"valve_{i}"):
                    zone["sub_valves"].append({
                        "valve": user_input[f"valve_{i}"],
                        "floor_sensor": user_input.get(f"floor_{i}"),
                        "max_floor_temp": user_input.get(f"max_temp_{i}", DEFAULT_MAX_FLOOR_TEMP)
                    })
            
            if self._zone_index is not None:
                zones[self._zone_index] = zone
            else:
                zones.append(zone)
            
            new_options = dict(self._config_entry.options)
            new_options["zones"] = zones
            
            return self.async_create_entry(title="", data=new_options)

        # Get existing zone data if editing
        zone_data = {}
        if self._zone_index is not None and self._zone_index < len(zones):
            zone_data = zones[self._zone_index]

        # Prepare circuits list
        circuits_dict = {"none": "Žádný"}
        configured_circuits = self._config_entry.options.get("main_circuits", {})
        circuits_dict.update({k: k.title() for k in configured_circuits.keys()})

        # Prepare sub-valves defaults
        sub_valves = zone_data.get("sub_valves", [])
        
        schema_dict = {
            vol.Required(
                "zone_name",
                description={"suggested_value": zone_data.get("name", "")}
            ): cv.string,
            vol.Required(
                "room_sensor",
                description={"suggested_value": zone_data.get("room_sensor")}
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain=["sensor"],
                    device_class=["temperature"]
                )
            ),
            vol.Optional(
                "target_temp",
                description={"suggested_value": zone_data.get("target_temp", DEFAULT_TARGET_TEMP)}
            ): vol.All(vol.Coerce(float), vol.Range(min=15, max=30)),
            vol.Optional(
                "hysteresis",
                description={"suggested_value": zone_data.get("hysteresis", DEFAULT_HYSTERESIS)}
            ): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=2.0)),
            vol.Optional(
                "main_circuit",
                description={"suggested_value": zone_data.get("main_circuit", "none")}
            ): vol.In(circuits_dict),
        }
        
        # Add sub-valve fields
        for i in range(1, 5):
            valve_data = sub_valves[i-1] if i-1 < len(sub_valves) else {}
            
            schema_dict[vol.Optional(
                f"valve_{i}",
                description={"suggested_value": valve_data.get("valve")}
            )] = selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["switch"])
            )
            schema_dict[vol.Optional(
                f"floor_{i}",
                description={"suggested_value": valve_data.get("floor_sensor")}
            )] = selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain=["sensor"],
                    device_class=["temperature"]
                )
            )
            schema_dict[vol.Optional(
                f"max_temp_{i}",
                description={"suggested_value": valve_data.get("max_floor_temp", DEFAULT_MAX_FLOOR_TEMP)}
            )] = vol.All(vol.Coerce(float), vol.Range(min=20, max=40))

        return self.async_show_form(
            step_id="zone_config",
            data_schema=vol.Schema(schema_dict)
        )
