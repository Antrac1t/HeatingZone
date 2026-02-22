"""Constants for Thermozona Gas integration."""
from typing import Final

DOMAIN: Final = "thermozona_gas"

# Config keys - Global
CONF_OUTSIDE_TEMP_SENSOR: Final = "outside_temp_sensor"
CONF_OPENTHERM_DEVICE: Final = "opentherm_device"
CONF_HEATING_BASE_OFFSET: Final = "heating_base_offset"
CONF_WEATHER_SLOPE_HEAT: Final = "weather_slope_heat"
CONF_MIN_WATER_TEMP: Final = "min_water_temp"
CONF_MAX_WATER_TEMP: Final = "max_water_temp"
CONF_FLOW_CURVE_OFFSET: Final = "flow_curve_offset"

# Config keys - Zones
CONF_ZONES: Final = "zones"
CONF_ZONE_NAME: Final = "zone_name"
CONF_CIRCUITS: Final = "circuits"
CONF_TEMP_SENSOR: Final = "temp_sensor"
CONF_TEMP_SUPPLY: Final = "temp_supply"
CONF_TEMP_RETURN: Final = "temp_return"
CONF_TEMP_FLOOR: Final = "temp_floor"
CONF_CONTROL_MODE: Final = "control_mode"
CONF_HYSTERESIS: Final = "hysteresis"
CONF_PWM_CYCLE_TIME: Final = "pwm_cycle_time"
CONF_PWM_MIN_ON_TIME: Final = "pwm_min_on_time"
CONF_PWM_MIN_OFF_TIME: Final = "pwm_min_off_time"
CONF_PWM_KP: Final = "pwm_kp"
CONF_PWM_KI: Final = "pwm_ki"
CONF_VALVE_OPEN_TIME: Final = "valve_open_time"
CONF_VALVE_CLOSE_TIME: Final = "valve_close_time"
CONF_MAX_FLOOR_TEMP: Final = "max_floor_temp"

# Control modes
CONTROL_MODE_BANG_BANG: Final = "bang_bang"
CONTROL_MODE_PWM: Final = "pwm"

# Defaults - Global
DEFAULT_HEATING_BASE_OFFSET: Final = 3.0
DEFAULT_WEATHER_SLOPE_HEAT: Final = 0.25
DEFAULT_MIN_WATER_TEMP: Final = 30.0
DEFAULT_MAX_WATER_TEMP: Final = 45.0
DEFAULT_FLOW_CURVE_OFFSET: Final = 0.0

# Defaults - Zone
DEFAULT_CONTROL_MODE: Final = CONTROL_MODE_PWM
DEFAULT_HYSTERESIS: Final = 0.3
DEFAULT_PWM_CYCLE_TIME: Final = 20  # minutes
DEFAULT_PWM_MIN_ON_TIME: Final = 6  # minutes
DEFAULT_PWM_MIN_OFF_TIME: Final = 5  # minutes
DEFAULT_PWM_KP: Final = 30.0
DEFAULT_PWM_KI: Final = 2.0
DEFAULT_VALVE_OPEN_TIME: Final = 120  # seconds
DEFAULT_VALVE_CLOSE_TIME: Final = 120  # seconds
DEFAULT_MAX_FLOOR_TEMP: Final = 29.0  # °C
