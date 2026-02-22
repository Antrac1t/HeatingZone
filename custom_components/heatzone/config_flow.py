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
        """Handle initial step - pouze základní nastavení kotle."""
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
                vol.Optional("opentherm_device"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain=["climate", "water_heater"])
                ),
                vol.Optional("opentherm_temp_sensor"): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="sensor", device_class="temperature"
                    )
                ),
                vol.Optional("opentherm_return_sensor"): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="sensor", device_class="temperature"
                    )
                ),
                vol.Optional("opentherm_modulation_sensor"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Required(
                    "valve_open_time", default=DEFAULT_VALVE_OPEN_TIME
                ): vol.All(vol.Coerce(int), vol.Range(min=30, max=300)),
                vol.Required("control_mode", default=CONTROL_MODE_ONOFF): vol.In(
                    {
                        CONTROL_MODE_ONOFF: "On/Off s hysterezí",
                        CONTROL_MODE_PWM: "PWM řízení"
                    }
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return OptionsFlow(config_entry)


class OptionsFlow(config_entries.OptionsFlow):
    """Handle options flow - zde se budou přidávat zóny."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Manage the options - hlavní menu."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["main_circuits", "list_zones", "basic_settings"],
        )

    async def async_step_basic_settings(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Upravit základní nastavení."""
        if user_input is not None:
            # Sloučit s existujícími daty
            new_data = {**self.config_entry.data, **user_input}
            self.hass.config_entries.async_update_entry(
                self.config_entry, data=new_data
            )
            return self.async_create_entry(title="", data={})

        current_data = self.config_entry.data

        data_schema = vol.Schema(
            {
                vol.Required(
                    "valve_open_time",
                    default=current_data.get("valve_open_time", DEFAULT_VALVE_OPEN_TIME)
                ): vol.All(vol.Coerce(int), vol.Range(min=30, max=300)),
                vol.Required(
                    "control_mode",
                    default=current_data.get("control_mode", CONTROL_MODE_ONOFF)
                ): vol.In(
                    {
                        CONTROL_MODE_ONOFF: "On/Off s hysterezí",
                        CONTROL_MODE_PWM: "PWM řízení"
                    }
                ),
            }
        )

        return self.async_show_form(
            step_id="basic_settings",
            data_schema=data_schema,
        )

    async def async_step_main_circuits(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Spravovat hlavní okruhy."""
        if user_input is not None:
            circuits = {}
            for key in ["circuit_1_switch", "circuit_2_switch", "kitchen_switch", "bathroom_switch"]:
                if user_input.get(key):
                    circuits[key.replace("_switch", "")] = user_input[key]

            return self.async_create_entry(
                title="",
                data={
                    **self.config_entry.options,
                    "main_circuits": circuits
                }
            )

        current_circuits = self.config_entry.options.get("main_circuits", {})

        data_schema = vol.Schema(
            {
                vol.Optional(
                    "circuit_1_switch",
                    default=current_circuits.get("circuit_1")
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="switch")
                ),
                vol.Optional(
                    "circuit_2_switch",
                    default=current_circuits.get("circuit_2")
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="switch")
                ),
                vol.Optional(
                    "kitchen_switch",
                    default=current_circuits.get("kitchen")
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="switch")
                ),
                vol.Optional(
                    "bathroom_switch",
                    default=current_circuits.get("bathroom")
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="switch")
                ),
            }
        )

        return self.async_show_form(
            step_id="main_circuits",
            data_schema=data_schema,
        )

    async def async_step_list_zones(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Zobrazit seznam zón s možností přidat/upravit/smazat."""
        zones = list(self.config_entry.options.get("zones", []))

        if user_input is not None:
            action = user_input.get("action")
            
            if action == "add":
                return await self.async_step_add_zone()
            elif action == "done":
                return self.async_create_entry(title="", data={})
            elif action and action.startswith("edit_"):
                zone_index = int(action.split("_")[1])
                return await self.async_step_edit_zone(zone_index=zone_index)
            elif action and action.startswith("delete_"):
                zone_index = int(action.split("_")[1])
                zones.pop(zone_index)
                return self.async_create_entry(
                    title="",
                    data={
                        **self.config_entry.options,
                        "zones": zones
                    }
                )

        # Sestavit seznam akcí
        actions = {
            "add": "➕ Přidat novou zónu",
            "done": "✅ Hotovo"
        }
        
        for idx, zone in enumerate(zones):
            zone_name = zone.get("name", f"Zóna {idx+1}")
            actions[f"edit_{idx}"] = f"✏️ Upravit: {zone_name}"
            actions[f"delete_{idx}"] = f"🗑️ Smazat: {zone_name}"

        data_schema = vol.Schema({
            vol.Required("action"): vol.In(actions)
        })

        zones_info = f"Nakonfigurováno zón: {len(zones)}"
        if zones:
            zones_info += "\n\n" + "\n".join([
                f"• {z.get('name', 'Bez názvu')} - "
                f"Cíl: {z.get('target_temp', 21)}°C, "
                f"Ventilů: {len(z.get('sub_valves', []))}"
                for z in zones
            ])

        return self.async_show_form(
            step_id="list_zones",
            data_schema=data_schema,
            description_placeholders={"zones": zones_info}
        )

    async def async_step_add_zone(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Přidat novou zónu."""
        if user_input is not None:
            zones = list(self.config_entry.options.get("zones", []))
            
            zone = {
                "name": user_input["zone_name"],
                "main_circuit": user_input.get("main_circuit", "none"),
                "room_sensor": user_input["room_temp_sensor"],
                "target_temp": user_input.get("target_temp", DEFAULT_TARGET_TEMP),
                "hysteresis": user_input.get("hysteresis", DEFAULT_HYSTERESIS),
                "sub_valves": [],
            }

            # Přidat pod-ventily
            for i in range(1, 5):
                if user_input.get(f"sub_valve_{i}"):
                    zone["sub_valves"].append({
                        "valve": user_input[f"sub_valve_{i}"],
                        "floor_sensor": user_input.get(f"floor_sensor_{i}"),
                        "max_floor_temp": user_input.get(f"max_floor_temp_{i}", DEFAULT_MAX_FLOOR_TEMP),
                    })

            zones.append(zone)
            
            return self.async_create_entry(
                title="",
                data={
                    **self.config_entry.options,
                    "zones": zones
                }
            )

        return await self._show_zone_form("add_zone")

    async def async_step_edit_zone(
        self, 
        user_input: dict[str, Any] | None = None, 
        zone_index: int | None = None
    ) -> FlowResult:
        """Upravit existující zónu."""
        zones = list(self.config_entry.options.get("zones", []))
        
        if zone_index is None:
            return await self.async_step_list_zones()

        if user_input is not None:
            zone = {
                "name": user_input["zone_name"],
                "main_circuit": user_input.get("main_circuit", "none"),
                "room_sensor": user_input["room_temp_sensor"],
                "target_temp": user_input.get("target_temp", DEFAULT_TARGET_TEMP),
                "hysteresis": user_input.get("hysteresis", DEFAULT_HYSTERESIS),
                "sub_valves": [],
            }

            for i in range(1, 5):
                if user_input.get(f"sub_valve_{i}"):
                    zone["sub_valves"].append({
                        "valve": user_input[f"sub_valve_{i}"],
                        "floor_sensor": user_input.get(f"floor_sensor_{i}"),
                        "max_floor_temp": user_input.get(f"max_floor_temp_{i}", DEFAULT_MAX_FLOOR_TEMP),
                    })

            zones[zone_index] = zone
            
            return self.async_create_entry(
                title="",
                data={
                    **self.config_entry.options,
                    "zones": zones
                }
            )

        return await self._show_zone_form("edit_zone", zones[zone_index])

    async def _show_zone_form(
        self, 
        step_id: str, 
        zone_data: dict[str, Any] | None = None
    ) -> FlowResult:
        """Zobrazit formulář pro zónu."""
        defaults = zone_data or {}
        
        # Připravit seznam okruhů
        main_circuits = {"none": "Žádný hlavní okruh"}
        configured_circuits = self.config_entry.options.get("main_circuits", {})
        main_circuits.update({
            k: k.replace("_", " ").title() 
            for k in configured_circuits.keys()
        })

        # Předvyplnit pod-ventily
        sub_valves = defaults.get("sub_valves", [])
        valve_defaults = {}
        for idx, valve in enumerate(sub_valves[:4], 1):
            valve_defaults[f"sub_valve_{idx}"] = valve.get("valve")
            valve_defaults[f"floor_sensor_{idx}"] = valve.get("floor_sensor")
            valve_defaults[f"max_floor_temp_{idx}"] = valve.get("max_floor_temp", DEFAULT_MAX_FLOOR_TEMP)

        data_schema = vol.Schema(
            {
                vol.Required(
                    "zone_name", 
                    default=defaults.get("name", "")
                ): cv.string,
                vol.Optional(
                    "main_circuit", 
                    default=defaults.get("main_circuit", "none")
                ): vol.In(main_circuits),
                vol.Required(
                    "room_temp_sensor",
                    default=defaults.get("room_sensor")
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
                ),
                vol.Optional(
                    "target_temp", 
                    default=defaults.get("target_temp", DEFAULT_TARGET_TEMP)
                ): vol.All(vol.Coerce(float), vol.Range(min=15, max=30)),
                vol.Optional(
                    "hysteresis", 
                    default=defaults.get("hysteresis", DEFAULT_HYSTERESIS)
                ): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=2.0)),
                # Ventil 1
                vol.Optional(
                    "sub_valve_1", 
                    default=valve_defaults.get("sub_valve_1")
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="switch")
                ),
                vol.Optional(
                    "floor_sensor_1", 
                    default=valve_defaults.get("floor_sensor_1")
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
                ),
                vol.Optional(
                    "max_floor_temp_1", 
                    default=valve_defaults.get("max_floor_temp_1", DEFAULT_MAX_FLOOR_TEMP)
                ): vol.All(vol.Coerce(float), vol.Range(min=20, max=40)),
                # Ventil 2
                vol.Optional(
                    "sub_valve_2", 
                    default=valve_defaults.get("sub_valve_2")
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="switch")
                ),
                vol.Optional(
                    "floor_sensor_2", 
                    default=valve_defaults.get("floor_sensor_2")
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
                ),
                vol.Optional(
                    "max_floor_temp_2", 
                    default=valve_defaults.get("max_floor_temp_2", DEFAULT_MAX_FLOOR_TEMP)
                ): vol.All(vol.Coerce(float), vol.Range(min=20, max=40)),
                # Ventil 3
                vol.Optional(
                    "sub_valve_3", 
                    default=valve_defaults.get("sub_valve_3")
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="switch")
                ),
                vol.Optional(
                    "floor_sensor_3", 
                    default=valve_defaults.get("floor_sensor_3")
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
                ),
                vol.Optional(
                    "max_floor_temp_3", 
                    default=valve_defaults.get("max_floor_temp_3", DEFAULT_MAX_FLOOR_TEMP)
                ): vol.All(vol.Coerce(float), vol.Range(min=20, max=40)),
                # Ventil 4
                vol.Optional(
                    "sub_valve_4", 
                    default=valve_defaults.get("sub_valve_4")
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="switch")
                ),
                vol.Optional(
                    "floor_sensor_4", 
                    default=valve_defaults.get("floor_sensor_4")
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
                ),
                vol.Optional(
                    "max_floor_temp_4", 
                    default=valve_defaults.get("max_floor_temp_4", DEFAULT_MAX_FLOOR_TEMP)
                ): vol.All(vol.Coerce(float), vol.Range(min=20, max=40)),
            }
        )

        return self.async_show_form(
            step_id=step_id,
            data_schema=data_schema,
        )
