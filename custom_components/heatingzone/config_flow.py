"""Config flow for Heating Zone integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    DEFAULT_BUFFER_MIN_USABLE_TEMP,
    DEFAULT_BUFFER_VOLUME_LITERS,
    DEFAULT_MIN_BUFFER_TOP_TEMP,
    DEFAULT_CONTROL_HEAT_SOURCE,
    DEFAULT_SUSPEND_CIRCULATION_DURING_TUV,
    DEFAULT_HEATING_DEMAND_BINARY_SENSOR,
    DEFAULT_HYSTERESIS,
    DEFAULT_MAX_FLOOR_TEMP,
    DEFAULT_MIN_OFF_TIME,
    DEFAULT_MIN_RUN_TIME,
    DEFAULT_NAME,
    DEFAULT_TARGET_TEMP,
    DEFAULT_TUV_CURRENT_TEMP_SENSOR,
    DEFAULT_TUV_DEMAND_BINARY_SENSOR,
    DEFAULT_TUV_EMERGENCY_MIN_TEMP,
    DEFAULT_TUV_MIN_READY_TEMP,
    DEFAULT_TUV_MODE_VALUE,
    DEFAULT_TUV_SETPOINT_ENTITY,
    DEFAULT_TUV_TEMP_DIFF_ENTITY,
    DEFAULT_TUV_TARGET_TEMP,
    DEFAULT_TUV_VOLUME_LITERS,
    DEFAULT_VALVE_OPEN_TIME,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _optional_entity_key(defaults: dict[str, Any], key: str) -> vol.Marker:
    """Build an optional key without passing None as a default."""
    default_value = defaults.get(key)
    if default_value is None:
        return vol.Optional(key)
    return vol.Optional(key, default=default_value)


class HeatingZoneConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Heating Zone."""

    VERSION = 1

    def _build_system_schema(
        self,
        defaults: dict[str, Any] | None = None,
        *,
        include_name: bool,
    ) -> vol.Schema:
        """Build schema for shared heat source settings."""
        defaults = defaults or {}
        schema: dict[Any, Any] = {}

        if include_name:
            schema[
                vol.Required("name", default=defaults.get("name", DEFAULT_NAME))
            ] = str

        schema[vol.Required("heat_source_switch")] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain="switch")
        )
        schema[_optional_entity_key(defaults, "heat_mode_entity")] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain="select")
        )
        schema[
            vol.Optional(
                "heating_mode_value",
                default=defaults.get("heating_mode_value", "Heating Only"),
            )
        ] = str
        schema[
            vol.Optional(
                "tuv_mode_value",
                default=defaults.get("tuv_mode_value", DEFAULT_TUV_MODE_VALUE),
            )
        ] = str
        schema[
            vol.Optional(
                "idle_mode_value",
                default=defaults.get("idle_mode_value", ""),
            )
        ] = str
        schema[
            vol.Optional(
                "control_heat_source",
                default=defaults.get("control_heat_source", DEFAULT_CONTROL_HEAT_SOURCE),
            )
        ] = bool
        schema[
            vol.Optional(
                "suspend_circulation_during_tuv",
                default=defaults.get(
                    "suspend_circulation_during_tuv",
                    DEFAULT_SUSPEND_CIRCULATION_DURING_TUV,
                ),
            )
        ] = bool
        schema[_optional_entity_key(defaults, "nt_binary_sensor")] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain="binary_sensor")
        )
        schema[_optional_entity_key(defaults, "nt_remaining_time_sensor")] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        )
        schema[
            _optional_entity_key(
                {**defaults, "heating_demand_binary_sensor": defaults.get("heating_demand_binary_sensor", DEFAULT_HEATING_DEMAND_BINARY_SENSOR)},
                "heating_demand_binary_sensor",
            )
        ] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain="binary_sensor")
        )
        schema[
            _optional_entity_key(
                {**defaults, "tuv_demand_binary_sensor": defaults.get("tuv_demand_binary_sensor", DEFAULT_TUV_DEMAND_BINARY_SENSOR)},
                "tuv_demand_binary_sensor",
            )
        ] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain="binary_sensor")
        )
        schema[
            _optional_entity_key(
                {**defaults, "tuv_setpoint_entity": defaults.get("tuv_setpoint_entity", DEFAULT_TUV_SETPOINT_ENTITY)},
                "tuv_setpoint_entity",
            )
        ] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain="number")
        )
        schema[
            _optional_entity_key(
                {**defaults, "tuv_temp_diff_entity": defaults.get("tuv_temp_diff_entity", DEFAULT_TUV_TEMP_DIFF_ENTITY)},
                "tuv_temp_diff_entity",
            )
        ] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain="number")
        )
        schema[
            _optional_entity_key(
                {**defaults, "tuv_current_temp_sensor": defaults.get("tuv_current_temp_sensor", DEFAULT_TUV_CURRENT_TEMP_SENSOR)},
                "tuv_current_temp_sensor",
            )
        ] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        )
        schema[_optional_entity_key(defaults, "tuv_top_temp_sensor")] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        )
        schema[_optional_entity_key(defaults, "tuv_bottom_temp_sensor")] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        )
        schema[
            vol.Optional(
                "tuv_volume_liters",
                default=defaults.get("tuv_volume_liters", DEFAULT_TUV_VOLUME_LITERS),
            )
        ] = selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=50,
                max=500,
                step=10,
                unit_of_measurement="l",
                mode=selector.NumberSelectorMode.BOX,
            )
        )
        schema[
            vol.Optional(
                "tuv_target_temp",
                default=defaults.get("tuv_target_temp", DEFAULT_TUV_TARGET_TEMP),
            )
        ] = selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=30,
                max=65,
                step=0.5,
                unit_of_measurement="°C",
                mode=selector.NumberSelectorMode.BOX,
            )
        )
        schema[
            vol.Optional(
                "tuv_min_ready_temp",
                default=defaults.get("tuv_min_ready_temp", DEFAULT_TUV_MIN_READY_TEMP),
            )
        ] = selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=25,
                max=65,
                step=0.5,
                unit_of_measurement="°C",
                mode=selector.NumberSelectorMode.BOX,
            )
        )
        schema[
            vol.Optional(
                "tuv_emergency_min_temp",
                default=defaults.get("tuv_emergency_min_temp", DEFAULT_TUV_EMERGENCY_MIN_TEMP),
            )
        ] = selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=20,
                max=60,
                step=0.5,
                unit_of_measurement="°C",
                mode=selector.NumberSelectorMode.BOX,
            )
        )
        schema[_optional_entity_key(defaults, "buffer_top_temp_sensor")] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        )
        schema[_optional_entity_key(defaults, "buffer_mid_temp_sensor")] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        )
        schema[_optional_entity_key(defaults, "buffer_bottom_temp_sensor")] = selector.EntitySelector(
            selector.EntitySelectorConfig(domain="sensor")
        )
        schema[
            vol.Optional(
                "buffer_volume_liters",
                default=defaults.get("buffer_volume_liters", DEFAULT_BUFFER_VOLUME_LITERS),
            )
        ] = selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=100,
                max=2000,
                step=10,
                unit_of_measurement="l",
                mode=selector.NumberSelectorMode.BOX,
            )
        )
        schema[
            vol.Optional(
                "buffer_min_usable_temp",
                default=defaults.get("buffer_min_usable_temp", DEFAULT_BUFFER_MIN_USABLE_TEMP),
            )
        ] = selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=20,
                max=60,
                step=0.5,
                unit_of_measurement="°C",
                mode=selector.NumberSelectorMode.BOX,
            )
        )
        schema[
            vol.Optional(
                "min_buffer_top_temp",
                default=defaults.get("min_buffer_top_temp", DEFAULT_MIN_BUFFER_TOP_TEMP),
            )
        ] = selector.NumberSelector(
            selector.NumberSelectorConfig(
                min=0,
                max=80,
                step=0.5,
                unit_of_measurement="°C",
                mode=selector.NumberSelectorMode.BOX,
            )
        )
        schema[
            vol.Optional(
                "valve_open_time",
                default=defaults.get("valve_open_time", DEFAULT_VALVE_OPEN_TIME),
            )
        ] = vol.All(vol.Coerce(int), vol.Range(min=30, max=600))
        schema[
            vol.Optional(
                "min_run_time",
                default=defaults.get("min_run_time", DEFAULT_MIN_RUN_TIME),
            )
        ] = vol.All(vol.Coerce(int), vol.Range(min=1, max=120))
        schema[
            vol.Optional(
                "min_off_time",
                default=defaults.get("min_off_time", DEFAULT_MIN_OFF_TIME),
            )
        ] = vol.All(vol.Coerce(int), vol.Range(min=1, max=120))

        return vol.Schema(schema)

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
                data=user_input,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=self._build_system_schema(include_name=True),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return HeatingZoneOptionsFlow(config_entry)


class HeatingZoneOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Heating Zone."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._zones: list[dict[str, Any]] = []
        self._current_zone_index: int | None = None
        self._current_zone: dict[str, Any] = {}
        self._valves: list[dict[str, Any]] = []
        self._editing_valve_idx: int | None = None

    def _build_system_schema(self) -> vol.Schema:
        """Build schema for editing shared heat source settings."""
        defaults = dict(self.config_entry.data)
        return HeatingZoneConfigFlow._build_system_schema(self, defaults, include_name=False)

    def _build_heat_source_schema(self) -> vol.Schema:
        """Build schema for heat source settings."""
        defaults = dict(self.config_entry.data)
        return vol.Schema(
            {
                vol.Required(
                    "heat_source_switch",
                    default=defaults.get("heat_source_switch"),
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="switch")
                ),
                _optional_entity_key(defaults, "heat_mode_entity"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="select")
                ),
                vol.Optional(
                    "heating_mode_value",
                    default=defaults.get("heating_mode_value", "Heating Only"),
                ): str,
                vol.Optional(
                    "tuv_mode_value",
                    default=defaults.get("tuv_mode_value", DEFAULT_TUV_MODE_VALUE),
                ): str,
                vol.Optional(
                    "idle_mode_value",
                    default=defaults.get("idle_mode_value", ""),
                ): str,
                vol.Optional(
                    "control_heat_source",
                    default=defaults.get("control_heat_source", DEFAULT_CONTROL_HEAT_SOURCE),
                ): bool,
                vol.Optional(
                    "suspend_circulation_during_tuv",
                    default=defaults.get(
                        "suspend_circulation_during_tuv",
                        DEFAULT_SUSPEND_CIRCULATION_DURING_TUV,
                    ),
                ): bool,
            }
        )

    def _build_tariff_schema(self) -> vol.Schema:
        """Build schema for low tariff settings."""
        defaults = dict(self.config_entry.data)
        return vol.Schema(
            {
                _optional_entity_key(defaults, "nt_binary_sensor"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="binary_sensor")
                ),
                _optional_entity_key(defaults, "nt_remaining_time_sensor"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
            }
        )

    def _build_tuv_schema(self) -> vol.Schema:
        """Build schema for TUV settings."""
        defaults = dict(self.config_entry.data)
        return vol.Schema(
            {
                _optional_entity_key(
                    {**defaults, "heating_demand_binary_sensor": defaults.get("heating_demand_binary_sensor", DEFAULT_HEATING_DEMAND_BINARY_SENSOR)},
                    "heating_demand_binary_sensor",
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="binary_sensor")
                ),
                _optional_entity_key(
                    {**defaults, "tuv_demand_binary_sensor": defaults.get("tuv_demand_binary_sensor", DEFAULT_TUV_DEMAND_BINARY_SENSOR)},
                    "tuv_demand_binary_sensor",
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="binary_sensor")
                ),
                _optional_entity_key(
                    {**defaults, "tuv_setpoint_entity": defaults.get("tuv_setpoint_entity", DEFAULT_TUV_SETPOINT_ENTITY)},
                    "tuv_setpoint_entity",
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="number")
                ),
                _optional_entity_key(
                    {**defaults, "tuv_temp_diff_entity": defaults.get("tuv_temp_diff_entity", DEFAULT_TUV_TEMP_DIFF_ENTITY)},
                    "tuv_temp_diff_entity",
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="number")
                ),
                _optional_entity_key(
                    {**defaults, "tuv_current_temp_sensor": defaults.get("tuv_current_temp_sensor", DEFAULT_TUV_CURRENT_TEMP_SENSOR)},
                    "tuv_current_temp_sensor",
                ): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                _optional_entity_key(defaults, "tuv_top_temp_sensor"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                _optional_entity_key(defaults, "tuv_bottom_temp_sensor"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional(
                    "tuv_volume_liters",
                    default=defaults.get("tuv_volume_liters", DEFAULT_TUV_VOLUME_LITERS),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=50,
                        max=500,
                        step=10,
                        unit_of_measurement="l",
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Optional(
                    "tuv_target_temp",
                    default=defaults.get("tuv_target_temp", DEFAULT_TUV_TARGET_TEMP),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=30,
                        max=65,
                        step=0.5,
                        unit_of_measurement="°C",
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Optional(
                    "tuv_min_ready_temp",
                    default=defaults.get("tuv_min_ready_temp", DEFAULT_TUV_MIN_READY_TEMP),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=25,
                        max=65,
                        step=0.5,
                        unit_of_measurement="°C",
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Optional(
                    "tuv_emergency_min_temp",
                    default=defaults.get("tuv_emergency_min_temp", DEFAULT_TUV_EMERGENCY_MIN_TEMP),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=20,
                        max=60,
                        step=0.5,
                        unit_of_measurement="°C",
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
            }
        )

    def _build_buffer_schema(self) -> vol.Schema:
        """Build schema for buffer tank settings."""
        defaults = dict(self.config_entry.data)
        return vol.Schema(
            {
                _optional_entity_key(defaults, "buffer_top_temp_sensor"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                _optional_entity_key(defaults, "buffer_mid_temp_sensor"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                _optional_entity_key(defaults, "buffer_bottom_temp_sensor"): selector.EntitySelector(
                    selector.EntitySelectorConfig(domain="sensor")
                ),
                vol.Optional(
                    "buffer_volume_liters",
                    default=defaults.get("buffer_volume_liters", DEFAULT_BUFFER_VOLUME_LITERS),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=100,
                        max=2000,
                        step=10,
                        unit_of_measurement="l",
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
                vol.Optional(
                    "buffer_min_usable_temp",
                    default=defaults.get("buffer_min_usable_temp", DEFAULT_BUFFER_MIN_USABLE_TEMP),
                ): selector.NumberSelector(
                    selector.NumberSelectorConfig(
                        min=20,
                        max=60,
                        step=0.5,
                        unit_of_measurement="°C",
                        mode=selector.NumberSelectorMode.BOX,
                    )
                ),
            }
        )

    def _build_timing_schema(self) -> vol.Schema:
        """Build schema for timing and anti-cycling settings."""
        defaults = dict(self.config_entry.data)
        return vol.Schema(
            {
                vol.Optional(
                    "valve_open_time",
                    default=defaults.get("valve_open_time", DEFAULT_VALVE_OPEN_TIME),
                ): vol.All(vol.Coerce(int), vol.Range(min=30, max=600)),
                vol.Optional(
                    "min_run_time",
                    default=defaults.get("min_run_time", DEFAULT_MIN_RUN_TIME),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=120)),
                vol.Optional(
                    "min_off_time",
                    default=defaults.get("min_off_time", DEFAULT_MIN_OFF_TIME),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=120)),
            }
        )

    def _update_shared_settings(self, user_input: dict[str, Any]) -> None:
        """Update shared config entry data and reload integration."""
        updated_data = dict(self.config_entry.data)
        updated_data.update(user_input)

        self.hass.config_entries.async_update_entry(
            self.config_entry,
            data=updated_data,
            options={"zones": self._zones},
        )
        self.hass.async_create_task(
            self.hass.config_entries.async_reload(self.config_entry.entry_id)
        )

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage zones."""
        self._zones = list(self.config_entry.options.get("zones", []))
        
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "edit_heat_source",
                "edit_tariff",
                "edit_tuv",
                "edit_buffer",
                "edit_timing",
                "add_zone",
                "edit_zone",
                "delete_zone",
                "finish",
            ],
        )

    async def async_step_edit_heat_source(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Edit heat source settings."""
        if user_input is not None:
            self._update_shared_settings(user_input)
            return await self.async_step_init()

        return self.async_show_form(
            step_id="edit_heat_source",
            data_schema=self._build_heat_source_schema(),
        )

    async def async_step_edit_tariff(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Edit tariff settings."""
        if user_input is not None:
            self._update_shared_settings(user_input)
            return await self.async_step_init()

        return self.async_show_form(
            step_id="edit_tariff",
            data_schema=self._build_tariff_schema(),
        )

    async def async_step_edit_tuv(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Edit TUV settings."""
        if user_input is not None:
            self._update_shared_settings(user_input)
            return await self.async_step_init()

        return self.async_show_form(
            step_id="edit_tuv",
            data_schema=self._build_tuv_schema(),
        )

    async def async_step_edit_buffer(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Edit buffer tank settings."""
        if user_input is not None:
            self._update_shared_settings(user_input)
            return await self.async_step_init()

        return self.async_show_form(
            step_id="edit_buffer",
            data_schema=self._build_buffer_schema(),
        )

    async def async_step_edit_timing(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Edit timing settings."""
        if user_input is not None:
            self._update_shared_settings(user_input)
            return await self.async_step_init()

        return self.async_show_form(
            step_id="edit_timing",
            data_schema=self._build_timing_schema(),
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
            self._current_zone = dict(self._zones[self._current_zone_index])
            self._valves = list(self._current_zone.get("valves", []))
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
        
        defaults = self._current_zone

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
                        "circulation_pump",
                        description={"suggested_value": defaults.get("circulation_pump")}
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain="switch")
                    ),
                    vol.Optional(
                        "target_temp",
                        description={"suggested_value": defaults.get("target_temp", DEFAULT_TARGET_TEMP)}
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            min=5,
                            max=30,
                            step=0.2,
                            unit_of_measurement="°C",
                            mode=selector.NumberSelectorMode.BOX,
                        )
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_zone_control(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Configure simple ON/OFF control settings."""
        defaults = self._current_zone

        if user_input is not None:
            self._current_zone.update(user_input)
            return await self.async_step_zone_valves()

        return self.async_show_form(
            step_id="zone_control",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        "hysteresis",
                        description={"suggested_value": defaults.get("hysteresis", DEFAULT_HYSTERESIS)}
                    ): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=2.0)),
                }
            ),
        )

    async def async_step_zone_valves(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Manage valves for the zone."""
        valve_list = "\n".join(
            f"• {v['valve']}" for v in self._valves
        ) if self._valves else "No valves configured"

        menu_options = ["add_valve"]
        if self._valves:
            menu_options.extend(["edit_valve", "delete_valve"])
        menu_options.append("done_valves")

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
            self._valves.append(dict(user_input))
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
                    vol.Optional("max_floor_temp", default=DEFAULT_MAX_FLOOR_TEMP): vol.All(
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
            self._editing_valve_idx = int(user_input["valve_index"])
            return await self.async_step_edit_valve_details()

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
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Edit valve details."""
        if user_input is not None:
            self._valves[self._editing_valve_idx] = dict(user_input)
            return await self.async_step_zone_valves()

        valve = self._valves[self._editing_valve_idx]

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
                        description={"suggested_value": valve.get("max_floor_temp", DEFAULT_MAX_FLOOR_TEMP)}
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

    async def async_step_done_valves(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Save the zone."""
        if not self._valves:
            # Pokud nejsou ventily, vrátit zpět na správu ventilů
            _LOGGER.warning("No valves configured for zone %s", self._current_zone.get("name"))
            return await self.async_step_zone_valves()
        
        self._current_zone["valves"] = self._valves

        if self._current_zone_index is not None:
            self._zones[self._current_zone_index] = self._current_zone
            _LOGGER.info("Updated zone: %s", self._current_zone.get("name"))
        else:
            self._zones.append(self._current_zone)
            _LOGGER.info("Added new zone: %s", self._current_zone.get("name"))

        # ✅ Uložit do options a AUTOMATICKY RELOAD
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            options={"zones": self._zones}
        )
        
        # ✅ Trigger reload integrace ihned
        self.hass.async_create_task(
            self.hass.config_entries.async_reload(self.config_entry.entry_id)
        )
        
        _LOGGER.info("Zone saved and integration reload triggered")
        
        # Vrátit se do hlavního menu
        return await self.async_step_init()

    async def async_step_finish(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        """Finish configuration."""
        # ✅ Finální save a reload
        self.hass.config_entries.async_update_entry(
            self.config_entry,
            options={"zones": self._zones}
        )
        
        # ✅ Reload pro aplikování změn
        self.hass.async_create_task(
            self.hass.config_entries.async_reload(self.config_entry.entry_id)
        )
        
        _LOGGER.info("Configuration finished, integration reloaded")
        
        return self.async_create_entry(
            title="",
            data={"zones": self._zones},
        )
