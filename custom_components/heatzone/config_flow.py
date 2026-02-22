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
                vol.Optional("opentherm_return_sensor"): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="sensor", device_class=["temperature"]
                    )
                ),
                vol.Optional("opentherm_modulation_sensor"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
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
        self._current_zone_valves: list = []
        self._temp_zone_basic: dict = {}

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Main options menu."""
        if user_input is not None:
            action = user_input.get("action")
            
            if action == "add_zone":
                self._zone_index = None
                self._current_zone_valves = []
                self._temp_zone_basic = {}
                return await self.async_step_zone_basic()
            elif action == "list_zones":
                return await self.async_step_list_zones()
        
        zones = self._config_entry.options.get("zones", [])
        zones_count = len(zones)
        
        actions = {
            "add_zone": f"➕ Přidat zónu (aktuálně: {zones_count})",
            "list_zones": "📋 Spravovat zóny",
        }
        
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required("action"): vol.In(actions)
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
                zone = zones[self._zone_index]
                self._current_zone_valves = list(zone.get("valves", []))
                # Store basic zone info for editing
                self._temp_zone_basic = {
                    "zone_name": zone.get("name", ""),
                    "room_sensor": zone.get("room_sensor"),
                    "target_temp": zone.get("target_temp", DEFAULT_TARGET_TEMP),
                    "hysteresis": zone.get("hysteresis", DEFAULT_HYSTERESIS),
                }
                return await self.async_step_zone_basic()
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
            valve_count = len(zone.get("valves", []))
            actions[f"edit_{idx}"] = f"✏️ {name} ({valve_count} ventilů)"
            actions[f"delete_{idx}"] = f"🗑️ {name}"

        zones_info = "\n".join([
            f"{i+1}. {z.get('name', 'Bez názvu')} - "
            f"{z.get('target_temp', 21)}°C, "
            f"ventilů: {len(z.get('valves', []))}"
            for i, z in enumerate(zones)
        ])

        return self.async_show_form(
            step_id="list_zones",
            data_schema=vol.Schema({
                vol.Required("action"): vol.In(actions)
            }),
            description_placeholders={"info": zones_info}
        )

    async def async_step_zone_basic(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Configure basic zone settings."""
        if user_input is not None:
            # Uložit základní info
            self._temp_zone_basic = user_input
            return await self.async_step_zone_valves()

        # Get defaults (either from editing or empty)
        defaults = self._temp_zone_basic

        schema_dict = {
            vol.Required(
                "zone_name",
                description={"suggested_value": defaults.get("zone_name", "")}
            ): cv.string,
            vol.Required(
                "room_sensor",
                description={"suggested_value": defaults.get("room_sensor")}
            ): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain=["sensor"],
                    device_class=["temperature"]
                )
            ),
            vol.Optional(
                "target_temp",
                description={"suggested_value": defaults.get("target_temp", DEFAULT_TARGET_TEMP)}
            ): vol.All(vol.Coerce(float), vol.Range(min=15, max=30)),
            vol.Optional(
                "hysteresis",
                description={"suggested_value": defaults.get("hysteresis", DEFAULT_HYSTERESIS)}
            ): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=2.0)),
        }

        return self.async_show_form(
            step_id="zone_basic",
            data_schema=vol.Schema(schema_dict),
            description_placeholders={
                "info": "Základní nastavení zóny - název a pokojový teploměr"
            }
        )

    async def async_step_zone_valves(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Manage valves for zone."""
        if user_input is not None:
            action = user_input.get("action")
            
            if action == "add_valve":
                return await self.async_step_add_valve()
            elif action == "done":
                # Save complete zone
                zones = list(self._config_entry.options.get("zones", []))
                
                zone = {
                    "name": self._temp_zone_basic.get("zone_name", "Nová zóna"),
                    "room_sensor": self._temp_zone_basic.get("room_sensor"),
                    "target_temp": self._temp_zone_basic.get("target_temp", DEFAULT_TARGET_TEMP),
                    "hysteresis": self._temp_zone_basic.get("hysteresis", DEFAULT_HYSTERESIS),
                    "valves": self._current_zone_valves
                }
                
                if self._zone_index is not None:
                    zones[self._zone_index] = zone
                else:
                    zones.append(zone)
                
                new_options = dict(self._config_entry.options)
                new_options["zones"] = zones
                
                # Reset temporary data
                self._zone_index = None
                self._current_zone_valves = []
                self._temp_zone_basic = {}
                
                return self.async_create_entry(title="", data=new_options)
            elif action and action.startswith("delete_"):
                valve_idx = int(action.split("_")[1])
                self._current_zone_valves.pop(valve_idx)
                return await self.async_step_zone_valves()

        # Build actions
        actions = {
            "add_valve": "➕ Přidat ventil",
            "done": "✅ Hotovo"
        }
        
        for idx, valve in enumerate(self._current_zone_valves):
            valve_name = valve.get("valve", "Neznámý")
            # Extract friendly name from entity_id
            friendly_name = valve_name.split(".")[-1] if "." in valve_name else valve_name
            actions[f"delete_{idx}"] = f"🗑️ Ventil: {friendly_name}"

        valves_info = f"Ventilů v zóně '{self._temp_zone_basic.get('zone_name', 'Nová zóna')}': {len(self._current_zone_valves)}"
        if self._current_zone_valves:
            valves_info += "\n\n" + "\n".join([
                f"{i+1}. {v.get('valve', 'N/A').split('.')[-1]} - "
                f"Max podlaha: {v.get('max_floor_temp', 30)}°C"
                for i, v in enumerate(self._current_zone_valves)
            ])

        return self.async_show_form(
            step_id="zone_valves",
            data_schema=vol.Schema({
                vol.Required("action"): vol.In(actions)
            }),
            description_placeholders={"info": valves_info}
        )

    async def async_step_add_valve(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Add a valve to current zone."""
        if user_input is not None:
            valve = {
                "valve": user_input["valve_switch"],
                "floor_sensor": user_input.get("floor_sensor"),
                "max_floor_temp": user_input.get("max_floor_temp", DEFAULT_MAX_FLOOR_TEMP)
            }
            
            self._current_zone_valves.append(valve)
            return await self.async_step_zone_valves()

        schema_dict = {
            vol.Required("valve_switch"): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["switch"])
            ),
            vol.Optional("floor_sensor"): selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain=["sensor"],
                    device_class=["temperature"]
                )
            ),
            vol.Optional(
                "max_floor_temp",
                description={"suggested_value": DEFAULT_MAX_FLOOR_TEMP}
            ): vol.All(vol.Coerce(float), vol.Range(min=20, max=40)),
        }

        return self.async_show_form(
            step_id="add_valve",
            data_schema=vol.Schema(schema_dict),
            description_placeholders={
                "info": "Přidejte ventil (termohlavici) do této zóny"
            }
        )
