components/thermozona_gas/coordinator.py
"""Data coordinator for Thermozona Gas."""
import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.config_entries import ConfigEntry

from .const import (
    DOMAIN,
    UPDATE_INTERVAL,
    CONF_OPENTHERM_TEMP,
    CONF_OPENTHERM_RETURN,
    CONF_OPENTHERM_MODULATION,
)

_LOGGER = logging.getLogger(__name__)


class ThermoZonaCoordinator(DataUpdateCoordinator):
    """Coordinator to manage Thermozona data updates."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL),
        )
        self.entry = entry
        self.config = entry.data

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from sensors."""
        try:
            data = {}
            
            # Get OpenTherm data if configured
            if self.config.get(CONF_OPENTHERM_TEMP):
                state = self.hass.states.get(self.config[CONF_OPENTHERM_TEMP])
                if state:
                    data["opentherm_temp"] = float(state.state)
            
            if self.config.get(CONF_OPENTHERM_RETURN):
                state = self.hass.states.get(self.config[CONF_OPENTHERM_RETURN])
                if state:
                    data["opentherm_return"] = float(state.state)
            
            if self.config.get(CONF_OPENTHERM_MODULATION):
                state = self.hass.states.get(self.config[CONF_OPENTHERM_MODULATION])
                if state:
                    data["opentherm_modulation"] = float(state.state)
            
            return data
            
        except Exception as err:
            raise UpdateFailed(f"Error fetching data: {err}") from err
