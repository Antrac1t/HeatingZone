"""Constants for Thermozona Gas integration."""

DOMAIN = "thermozona_gas"

# Control modes
CONTROL_MODE_ONOFF = "onoff"
CONTROL_MODE_PWM = "pwm"

# Configuration keys
CONF_BOILER_SWITCH = "boiler_switch"
CONF_OPENTHERM_DEVICE = "opentherm_device"
CONF_OPENTHERM_TEMP = "opentherm_temp_sensor"
CONF_OPENTHERM_RETURN = "opentherm_return_sensor"
CONF_OPENTHERM_MODULATION = "opentherm_modulation_sensor"
CONF_VALVE_OPEN_TIME = "valve_open_time"
CONF_CONTROL_MODE = "control_mode"
CONF_MAIN_CIRCUITS = "main_circuits"
CONF_ZONES = "zones"

# Zone configuration keys
CONF_ZONE_NAME = "name"
CONF_ZONE_MAIN_CIRCUIT = "main_circuit"
CONF_ZONE_SUB_VALVES = "sub_valves"
CONF_ZONE_ROOM_SENSOR = "room_sensor"
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
DEFAULT_PWM_PERIOD = 1800  # 30 minutes

# Update interval
UPDATE_INTERVAL = 30  # seconds

# Attributes
ATTR_ZONE_NAME = "zone_name"
ATTR_MAIN_CIRCUIT = "main_circuit"
ATTR_ACTIVE_VALVES = "active_valves"
ATTR_FLOOR_TEMPS = "floor_temperatures"
ATTR_OPENTHERM_TEMP = "supply_temperature"
ATTR_OPENTHERM_RETURN = "return_temperature"
ATTR_OPENTHERM_MODULATION = "modulation"
