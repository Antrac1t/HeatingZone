"""Config flow for Thermozona Gas."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv
from homeassistant.data_entry_flow import FlowResult

from .const import (
    DOMAIN,
    CONTROL_MODE_ONOFF,
    CONTROL_MODE_PWM,
    DEFAULT_VALVE_OPEN_TIME,
)


class ThermoZonaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle config flow."""

    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle initial step - pouze základní nastavení kotle."""
        errors = {}

        if user_input is not None:
            # Zkontrolovat, zda už integrace neexistuje
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
            description_placeholders={
                "info": "Nastavte základní parametry kondenzačního kotle"
            }
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
        self._zones = list(config_entry.options.get("zones", []))
        self._main_circuits = dict(config_entry.options.get("main_circuits", {}))
        self._edit_mode = False
        self._edit_index = None

    async def async_step_init(self, user_input=None) -> FlowResult:
        """Manage the options - hlavní menu."""
        return self.async_show_menu(
            step_id="init",
            menu_options=["main_circuits", "zones", "zone_add"],
        )

    async def async_step_main_circuits(self, user_input=None) -> FlowResult:
        """Spravovat hlavní okruhy."""
        if user_input is not None:
            circuits = {}
            if user_input.get("circuit_1_switch"):
                circuits["circuit_1"] = user_input["circuit_1_switch"]
            if user_input.get("circuit_2_switch"):
                circuits["circuit_2"] = user_input["circuit_2_switch"]
            if user_input.get("kitchen_switch"):
                circuits["kitchen"] = user_input["kitchen_switch"]
            if user_input.get("bathroom_switch"):
                circuits["bathroom"] = user_input["bathroom_switch"]

            self._main_circuits = circuits
            return await self._update_options()

        data_schema = vol.Schema(
            {
                vol.Optional(
                    "circuit_1_switch", 
                    default=self._main_circuits.get("circuit_1")
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="switch")
                ),
                vol.Optional(
                    "circuit_2_switch",
                    default=self._main_circuits.get("circuit_2")
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="switch")
                ),
                vol.Optional(
                    "kitchen_switch",
                    default=self._main_circuits.get("kitchen")
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="switch")
                ),
                vol.Optional(
                    "bathroom_switch",
                    default=self._main_circuits.get("bathroom")
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="switch")
                ),
            }
        )

        return self.async_show_form(
            step_id="main_circuits",
            data_schema=data_schema,
            description_placeholders={
                "info": "Nastavte hlavní rozdělovací okruhy"
            }
        )

    async def async_step_zones(self, user_input=None) -> FlowResult:
        """Zobrazit seznam zón."""
        if user_input is not None:
            if user_input.get("action") == "add":
                return await self.async_step_zone_add()
            elif user_input.get("action") == "done":
                return await self._update_options()
            elif user_input.get("action").startswith("edit_"):
                self._edit_mode = True
                self._edit_index = int(user_input["action"].split("_")[1])
                return await self.async_step_zone_add()
            elif user_input.get("action").startswith("delete_"):
                delete_index = int(user_input["action"].split("_")[1])
                self._zones.pop(delete_index)
                return await self.async_step_zones()

        # Sestavit seznam akcí
        actions = {"add": "➕ Přidat novou zónu", "done": "✅ Hotovo"}
        
        for idx, zone in enumerate(self._zones):
            actions[f"edit_{idx}"] = f"✏️ Upravit: {zone['name']}"
            actions[f"delete_{idx}"] = f"🗑️ Smazat: {zone['name']}"

        data_schema = vol.Schema({
            vol.Required("action"): vol.In(actions)
        })

        zones_info = f"Počet zón: {len(self._zones)}"
        if self._zones:
            zones_info += "\n\n" + "\n".join([
                f"• {z['name']} (🌡️ {z.get('target_temp', 21)}°C, "
                f"ventilů: {len(z.get('sub_valves', []))})"
                for z in self._zones
            ])

        return self.async_show_form(
            step_id="zones",
            data_schema=data_schema,
            description_placeholders={"zones": zones_info}
        )

    async def async_step_zone_add(self, user_input=None) -> FlowResult:
        """Přidat nebo upravit zónu."""
        errors = {}

        if user_input is not None:
            zone = {
                "name": user_input["zone_name"],
                "main_circuit": user_input.get("main_circuit", "none"),
                "room_sensor": user_input["room_temp_sensor"],
                "target_temp": user_input.get("target_temp", 21.0),
                "hysteresis": user_input.get("hysteresis", 0.5),
                "sub_valves": [],
            }

            # Přidat pod-ventily
            for i in range(1, 5):
                if user_input.get(f"sub_valve_{i}"):
                    zone["sub_valves"].append({
                        "valve": user_input[f"sub_valve_{i}"],
                        "floor_sensor": user_input.get(f"floor_sensor_{i}"),
                        "max_floor_temp": user_input.get(f"max_floor_temp_{i}", 30.0),
                    })

            if self._edit_mode and self._edit_index is not None:
                self._zones[self._edit_index] = zone
                self._edit_mode = False
                self._edit_index = None
            else:
                self._zones.append(zone)

            return await self.async_step_zones()

        # Předvyplnění při editaci
        defaults = {}
        if self._edit_mode and self._edit_index is not None:
            zone = self._zones[self._edit_index]
            defaults = {
                "zone_name": zone["name"],
                "main_circuit": zone.get("main_circuit", "none"),
                "room_temp_sensor": zone["room_sensor"],
                "target_temp": zone.get("target_temp", 21.0),
                "hysteresis": zone.get("hysteresis", 0.5),
            }
            for idx, valve in enumerate(zone.get("sub_valves", []), 1):
                defaults[f"sub_valve_{idx}"] = valve["valve"]
                defaults[f"floor_sensor_{idx}"] = valve.get("floor_sensor")
                defaults[f"max_floor_temp_{idx}"] = valve.get("max_floor_temp", 30.0)

        # Připravit seznam okruhů
        main_circuits = {"none": "Žádný hlavní okruh"}
        main_circuits.update({k: k.replace("_", " ").title() for k in self._main_circuits.keys()})

        data_schema = vol.Schema(
            {
                vol.Required("zone_name", default=defaults.get("zone_name", "")): cv.string,
                vol.Optional("main_circuit", default=defaults.get("main_circuit", "none")): vol.In(main_circuits),
                vol.Required("room_temp_sensor", default=defaults.get("room_temp_sensor")): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
                ),
                vol.Optional("target_temp", default=defaults.get("target_temp", 21.0)): vol.All(
                    vol.Coerce(float), vol.Range(min=15, max=30)
                ),
                vol.Optional("hysteresis", default=defaults.get("hysteresis", 0.5)): vol.All(
                    vol.Coerce(float), vol.Range(min=0.1, max=2.0)
                ),
                # 4 pod-ventily
                vol.Optional("sub_valve_1", default=defaults.get("sub_valve_1")): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="switch")
                ),
                vol.Optional("floor_sensor_1", default=defaults.get("floor_sensor_1")): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
                ),
                vol.Optional("max_floor_temp_1", default=defaults.get("max_floor_temp_1", 30.0)): vol.All(
                    vol.Coerce(float), vol.Range(min=20, max=40)
                ),
                vol.Optional("sub_valve_2", default=defaults.get("sub_valve_2")): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="switch")
                ),
                vol.Optional("floor_sensor_2", default=defaults.get("floor_sensor_2")): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
                ),
                vol.Optional("max_floor_temp_2", default=defaults.get("max_floor_temp_2", 30.0)): vol.All(
                    vol.Coerce(float), vol.Range(min=20, max=40)
                ),
                vol.Optional("sub_valve_3", default=defaults.get("sub_valve_3")): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="switch")
                ),
                vol.Optional("floor_sensor_3", default=defaults.get("floor_sensor_3")): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
                ),
                vol.Optional("max_floor_temp_3", default=defaults.get("max_floor_temp_3", 30.0)): vol.All(
                    vol.Coerce(float), vol.Range(min=20, max=40)
                ),
                vol.Optional("sub_valve_4", default=defaults.get("sub_valve_4")): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="switch")
                ),
                vol.Optional("floor_sensor_4", default=defaults.get("floor_sensor_4")): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor", device_class="temperature")
                ),
                vol.Optional("max_floor_temp_4", default=defaults.get("max_floor_temp_4", 30.0)): vol.All(
                    vol.Coerce(float), vol.Range(min=20, max=40)
                ),
            }
        )

        title = "Upravit zónu" if self._edit_mode else "Přidat novou zónu"

        return self.async_show_form(
            step_id="zone_add",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={"info": title}
        )

    async def _update_options(self) -> FlowResult:
        """Update config entry options."""
        return self.async_create_entry(
            title="",
            data={
                "zones": self._zones,
                "main_circuits": self._main_circuits,
            }
        )
