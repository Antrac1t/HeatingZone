"""PWM controller for Thermozona Gas."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from homeassistant.components.climate import HVACMode

_LOGGER = logging.getLogger(__name__)


class PWMController:
    """PWM controller with PI regulation."""

    def __init__(
        self,
        cycle_time_minutes: int = 20,
        min_on_time_minutes: int = 6,
        min_off_time_minutes: int = 5,
        kp: float = 30.0,
        ki: float = 2.0,
        valve_open_time_seconds: int = 120,
        valve_close_time_seconds: int = 120,
    ) -> None:
        """Initialize PWM controller."""
        self.cycle_time = timedelta(minutes=cycle_time_minutes)
        self.min_on_time = timedelta(minutes=min_on_time_minutes)
        self.min_off_time = timedelta(minutes=min_off_time_minutes)
        self.kp = kp
        self.ki = ki
        self.valve_open_time = valve_open_time_seconds
        self.valve_close_time = valve_close_time_seconds
        
        # State
        self.integral = 0.0
        self.last_update: datetime | None = None
        self.cycle_start: datetime | None = None
        self.duty_cycle = 0.0  # 0-100%
        self.on_time = timedelta()
        
    def reset(self) -> None:
        """Reset controller state."""
        self.integral = 0.0
        self.last_update = None
        self.cycle_start = None
        self.duty_cycle = 0.0
        
    def calculate_duty_cycle(
        self,
        current_temp: float,
        target_temp: float,
        now: datetime | None = None,
    ) -> float:
        """Calculate PI duty cycle (0-100%)."""
        if now is None:
            now = datetime.now(timezone.utc)
        
        # Calculate error
        error = target_temp - current_temp
        
        # Calculate time delta
        if self.last_update is None:
            dt_minutes = 1.0
        else:
            dt_seconds = (now - self.last_update).total_seconds()
            dt_minutes = max(dt_seconds / 60.0, 0.1)
        
        # Update integral with anti-windup
        self.integral += error * dt_minutes
        
        # Anti-windup: limit integral
        if self.ki != 0:
            max_integral = 100.0 / abs(self.ki)
            self.integral = max(-max_integral, min(max_integral, self.integral))
        
        # Calculate PI output
        p_output = self.kp * error
        i_output = self.ki * self.integral
        duty = p_output + i_output
        
        # Clamp to 0-100%
        duty = max(0.0, min(100.0, duty))
        
        self.duty_cycle = duty
        self.last_update = now
        
        _LOGGER.debug(
            "PWM: error=%.2f, P=%.1f, I=%.1f, duty=%.1f%%",
            error, p_output, i_output, duty
        )
        
        return duty
    
    def calculate_on_time(self, duty_cycle: float) -> timedelta:
        """Calculate actual ON time with valve compensation."""
        # Base on time from duty cycle
        raw_on = self.cycle_time.total_seconds() * (duty_cycle / 100.0)
        
        # Add valve dead time (open + close)
        valve_dead_time = self.valve_open_time + self.valve_close_time
        compensated_on = raw_on + valve_dead_time
        
        # Apply min/max constraints
        min_on_seconds = self.min_on_time.total_seconds()
        min_off_seconds = self.min_off_time.total_seconds()
        cycle_seconds = self.cycle_time.total_seconds()
        
        # If too short, either go to 0 or min_on
        if 0 < compensated_on < min_on_seconds:
            if duty_cycle < 5:
                compensated_on = 0
            else:
                compensated_on = min_on_seconds
        
        # If off time would be too short, extend on time
        off_time = cycle_seconds - compensated_on
        if 0 < off_time < min_off_seconds:
            if duty_cycle > 95:
                compensated_on = cycle_seconds
            else:
                compensated_on = cycle_seconds - min_off_seconds
        
        # Final clamp
        compensated_on = max(0, min(cycle_seconds, compensated_on))
        
        self.on_time = timedelta(seconds=compensated_on)
        
        _LOGGER.debug(
            "PWM: raw_on=%.0fs, compensated=%.0fs (valve_dead=%.0fs)",
            raw_on, compensated_on, valve_dead_time
        )
        
        return self.on_time
    
    def should_be_on(self, now: datetime | None = None) -> bool:
        """Check if circuits should be ON in current cycle."""
        if now is None:
            now = datetime.now(timezone.utc)
        
        # Initialize cycle if needed
        if self.cycle_start is None:
            self.cycle_start = now
        
        # Check if we need new cycle
        elapsed = now - self.cycle_start
        if elapsed >= self.cycle_time:
            # Start new cycle
            self.cycle_start = now
            elapsed = timedelta()
        
        # Are we in ON period?
        return elapsed < self.on_time
    
    def get_state(self) -> dict:
        """Get current PWM state for debugging."""
        return {
            "duty_cycle": round(self.duty_cycle, 1),
            "integral": round(self.integral, 2),
            "on_time_minutes": round(self.on_time.total_seconds() / 60, 1),
            "cycle_start": self.cycle_start.isoformat() if self.cycle_start else None,
        }
