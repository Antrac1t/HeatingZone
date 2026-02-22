"""Config flow for Thermozona Gas."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector
import homeassistant.helpers.config_validation as cv

from .const import (
    DOMAIN,
    CONTROL_MODE_ONOFF,
    CONTROL_MODE_PWM,
    DEFAULT_HYSTERESIS,
    DEFAULT_VALVE_OPEN_TIME,
    DEFAULT_TARGET_TEMP,
    DEFAULT_MAX_FLOOR_TEMP,
)


class ThermoZonaConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle config flow."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize."""
        self._data: dict = {}
        self._zones: list = []

    async def async_step_user(self, user_input=None):
        """Handle initial step."""
        errors = {}

        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_main_circuits()

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

    async def async_step_main_circuits(self, user_input=None):
        """Configure main heating circuits."""
        errors = {}

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

            self._data["main_circuits"] = circuits
            return await self.async_step_add_zone()

        data_schema = vol.Schema(
            {
                vol.Optional("circuit_1_switch"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="switch")
                ),
                vol.Optional("circuit_2_switch"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="switch")
                ),
                vol.Optional("kitchen_switch"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="switch")
                ),
                vol.Optional("bathroom_switch"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="switch")
                ),
            }
        )

        return self.async_show_form(
            step_id="main_circuits",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_add_zone(self, user_input=None):
        """Ask if user wants to add a zone."""
        if user_input is not None:
            if not user_input.get("add_zone"):
                self._data["zones"] = self._zones
                return self.async_create_entry(
                    title="Thermozona Gas", 
                    data=self._data
                )
            return await self.async_step_zone_config()

        data_schema = vol.Schema(
            {
                vol.Required("add_zone", default=len(self._zones) == 0): cv.boolean,
            }
        )

        return self.async_show_form(
            step_id="add_zone",
            data_schema=data_schema,
        )

    async def async_step_zone_config(self, user_input=None):
        """Configure a heating zone."""
        errors = {}

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
                valve_key = f"sub_valve_{i}"
                floor_key = f"floor_sensor_{i}"
                max_temp_key = f"max_floor_temp_{i}"

                if user_input.get(valve_key):
                    sub_valve = {
                        "valve": user_input[valve_key],
                        "floor_sensor": user_input.get(floor_key),
                        "max_floor_temp": user_input.get(
                            max_temp_key, DEFAULT_MAX_FLOOR_TEMP
                        ),
                    }
                    zone["sub_valves"].append(sub_valve)

            self._zones.append(zone)
            return await self.async_step_add_zone()

        main_circuits = {"none": "Žádný"}
        if self._data.get("main_circuits"):
            for key in self._data["main_circuits"].keys():
                main_circuits[key] = key.replace("_", " ").title()

        data_schema = vol.Schema(
            {
                vol.Required("zone_name"): cv.string,
                vol.Optional("main_circuit", default="none"): vol.In(main_circuits),
                vol.Required("room_temp_sensor"): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="sensor", device_class="temperature"
                    )
                ),
                vol.Optional("target_temp", default=DEFAULT_TARGET_TEMP): vol.All(
                    vol.Coerce(float), vol.Range(min=15, max=30)
                ),
                vol.Optional("hysteresis", default=DEFAULT_HYSTERESIS): vol.All(
                    vol.Coerce(float), vol.Range(min=0.1, max=2.0)
                ),
                vol.Optional("sub_valve_1"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="switch")
                ),
                vol.Optional("floor_sensor_1"): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="sensor", device_class="temperature"
                    )
                ),
                vol.Optional(
                    "max_floor_temp_1", default=DEFAULT_MAX_FLOOR_TEMP
                ): vol.All(vol.Coerce(float), vol.Range(min=20, max=40)),
                vol.Optional("sub_valve_2"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="switch")
                ),
                vol.Optional("floor_sensor_2"): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="sensor", device_class="temperature"
                    )
                ),
                vol.Optional(
                    "max_floor_temp_2", default=DEFAULT_MAX_FLOOR_TEMP
                ): vol.All(vol.Coerce(float), vol.Range(min=20, max=40)),
                vol.Optional("sub_valve_3"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="switch")
                ),
                vol.Optional("floor_sensor_3"): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="sensor", device_class="temperature"
                    )
                ),
                vol.Optional(
                    "max_floor_temp_3", default=DEFAULT_MAX_FLOOR_TEMP
                ): vol.All(vol.Coerce(float), vol.Range(min=20, max=40)),
                vol.Optional("sub_valve_4"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="switch")
                ),
                vol.Optional("floor_sensor_4"): selector.EntitySelector(
                    selector.EntitySelectorConfig(
                        domain="sensor", device_class="temperature"
                    )
                ),
                vol.Optional(
                    "max_floor_temp_4", default=DEFAULT_MAX_FLOOR_TEMP
                ): vol.All(vol.Coerce(float), vol.Range(min=20, max=40)),
            }
        )

        return self.async_show_form(
            step_id="zone_config",
            data_schema=data_schema,
            errors=errors,
        )
