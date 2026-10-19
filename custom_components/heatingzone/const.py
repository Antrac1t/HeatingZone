"""Constants for the Heating Zone integration."""

DOMAIN = "heating_zone"
NAME = "Topne zony"
VERSION = "1.0.0"

DEFAULT_NAME = "System topnych zon"

# Configuration keys
CONF_HEAT_SOURCE_SWITCH = "heat_source_switch"
CONF_HEAT_MODE_ENTITY = "heat_mode_entity"
CONF_HEATING_MODE_VALUE = "heating_mode_value"
CONF_TUV_MODE_VALUE = "tuv_mode_value"
CONF_IDLE_MODE_VALUE = "idle_mode_value"
CONF_CONTROL_HEAT_SOURCE = "control_heat_source"
CONF_SUSPEND_CIRCULATION_DURING_TUV = "suspend_circulation_during_tuv"
CONF_NT_BINARY_SENSOR = "nt_binary_sensor"
CONF_NT_REMAINING_TIME_SENSOR = "nt_remaining_time_sensor"
CONF_FVE_GRID_SWITCH = "fve_grid_switch"
CONF_FVE_ACTIVE_WHEN_ON = "fve_active_when_on"
CONF_HEATING_DEMAND_BINARY_SENSOR = "heating_demand_binary_sensor"
CONF_TUV_DEMAND_BINARY_SENSOR = "tuv_demand_binary_sensor"
CONF_TUV_SETPOINT_ENTITY = "tuv_setpoint_entity"
CONF_TUV_TEMP_DIFF_ENTITY = "tuv_temp_diff_entity"
CONF_TUV_CURRENT_TEMP_SENSOR = "tuv_current_temp_sensor"
CONF_TUV_TOP_TEMP_SENSOR = "tuv_top_temp_sensor"
CONF_TUV_BOTTOM_TEMP_SENSOR = "tuv_bottom_temp_sensor"
CONF_TUV_VOLUME_LITERS = "tuv_volume_liters"
CONF_TUV_TARGET_TEMP = "tuv_target_temp"
CONF_TUV_MIN_READY_TEMP = "tuv_min_ready_temp"
CONF_TUV_EMERGENCY_MIN_TEMP = "tuv_emergency_min_temp"
CONF_BUFFER_TOP_TEMP_SENSOR = "buffer_top_temp_sensor"
CONF_BUFFER_MID_TEMP_SENSOR = "buffer_mid_temp_sensor"
CONF_BUFFER_BOTTOM_TEMP_SENSOR = "buffer_bottom_temp_sensor"
CONF_BUFFER_VOLUME_LITERS = "buffer_volume_liters"
CONF_BUFFER_MIN_USABLE_TEMP = "buffer_min_usable_temp"
CONF_OUTDOOR_TEMP_SENSOR = "outdoor_temp_sensor"
CONF_HEAT_LOSS_COEFFICIENT = "heat_loss_coefficient"
CONF_MIN_BUFFER_TOP_TEMP = "min_buffer_top_temp"
CONF_VALVE_OPEN_TIME = "valve_open_time"
CONF_MIN_RUN_TIME = "min_run_time"
CONF_MIN_OFF_TIME = "min_off_time"
CONF_ZONES = "zones"

# Zone configuration keys
CONF_ZONE_NAME = "name"
CONF_ZONE_MAIN_CIRCUIT = "main_circuit"
CONF_ZONE_SUB_VALVES = "sub_valves"
CONF_ZONE_ROOM_SENSOR = "room_sensor"
CONF_ZONE_CIRCULATION_PUMP = "circulation_pump"
CONF_ZONE_TARGET_TEMP = "target_temp"
CONF_ZONE_HYSTERESIS = "hysteresis"

# Sub-valve keys
CONF_VALVE = "valve"
CONF_FLOOR_SENSOR = "floor_sensor"
CONF_MAX_FLOOR_TEMP = "max_floor_temp"

# Defaults
DEFAULT_VALVE_OPEN_TIME = 120  # seconds
DEFAULT_HYSTERESIS = 0.5  # °C
DEFAULT_TARGET_TEMP = 21.0  # °C
DEFAULT_MAX_FLOOR_TEMP = 30.0  # °C
DEFAULT_MIN_RUN_TIME = 15  # minutes
DEFAULT_MIN_OFF_TIME = 10  # minutes
DEFAULT_CONTROL_HEAT_SOURCE = True
DEFAULT_SUSPEND_CIRCULATION_DURING_TUV = True
DEFAULT_FVE_ACTIVE_WHEN_ON = True
DEFAULT_HEATING_DEMAND_BINARY_SENSOR = "binary_sensor.tepelne_cerpadlo_heating_demand"
DEFAULT_TUV_MODE_VALUE = ""
DEFAULT_TUV_DEMAND_BINARY_SENSOR = "binary_sensor.tepelne_cerpadlo_hot_water_demand"
DEFAULT_TUV_SETPOINT_ENTITY = "number.tepelne_cerpadlo_hot_water_setpoint"
DEFAULT_TUV_TEMP_DIFF_ENTITY = "number.tepelne_cerpadlo_hot_water_temp_diff"
DEFAULT_TUV_CURRENT_TEMP_SENSOR = "sensor.tepelne_cerpadlo_hot_water_temperature"
DEFAULT_TUV_VOLUME_LITERS = 200
DEFAULT_TUV_TARGET_TEMP = 50.0
DEFAULT_TUV_MIN_READY_TEMP = 45.0
DEFAULT_TUV_EMERGENCY_MIN_TEMP = 40.0
DEFAULT_BUFFER_VOLUME_LITERS = 500
DEFAULT_BUFFER_MIN_USABLE_TEMP = 30.0
DEFAULT_HEAT_LOSS_COEFFICIENT = 225.8
DEFAULT_MIN_BUFFER_TOP_TEMP = 0.0  # °C; 0 disables the buffer temperature check

# Update interval
UPDATE_INTERVAL = 30  # seconds

# Attributes
ATTR_ZONE_NAME = "zone_name"
ATTR_ACTIVE_VALVES = "active_valves"
ATTR_FLOOR_TEMPS = "floor_temperatures"
