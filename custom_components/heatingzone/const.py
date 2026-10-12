"""Constants for the Heating Zone integration."""

DOMAIN = "heating_zone"
NAME = "Topne zony"
VERSION = "1.0.0"

DEFAULT_NAME = "System topnych zon"

# Configuration keys
CONF_HEAT_SOURCE_SWITCH = "heat_source_switch"
CONF_HEAT_MODE_ENTITY = "heat_mode_entity"
CONF_HEATING_MODE_VALUE = "heating_mode_value"
CONF_IDLE_MODE_VALUE = "idle_mode_value"
CONF_CONTROL_HEAT_SOURCE = "control_heat_source"
CONF_BUFFER_TOP_TEMP_SENSOR = "buffer_top_temp_sensor"
CONF_BUFFER_BOTTOM_TEMP_SENSOR = "buffer_bottom_temp_sensor"
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
DEFAULT_MIN_BUFFER_TOP_TEMP = 0.0  # °C; 0 disables the buffer temperature check

# Update interval
UPDATE_INTERVAL = 30  # seconds

# Attributes
ATTR_ZONE_NAME = "zone_name"
ATTR_ACTIVE_VALVES = "active_valves"
ATTR_FLOOR_TEMPS = "floor_temperatures"
