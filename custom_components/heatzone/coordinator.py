"""Data coordinator for Thermozona Gas."""
from __future__ import annotations

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
            
            if self.config.get(CONF_OPENTHERM_TEMP):
                state = self.hass.states.get(self.config[CONF_OPENTHERM_TEMP])
                if state and state.state not in ("unknown", "unavailable"):
                    try:
                        data["opentherm_temp"] = float(state.state)
                    except (ValueError, TypeError):
                        pass
            
            if self.config.get(CONF_OPENTHERM_RETURN):
                state = self.hass.states.get(self.config[CONF_OPENTHERM_RETURN])
                if state and state.state not in ("unknown", "unavailable"):
                    try:
                        data["opentherm_return"] = float(state.state)
                    except (ValueError, TypeError):
                        pass
            
            if self.config.get(CONF_OPENTHERM_MODULATION):
                state = self.hass.states.get(self.config[CONF_OPENTHERM_MODULATION])
                if state and state.state not in ("unknown", "unavailable"):
                    try:
                        data["opentherm_modulation"] = float(state.state)
                    except (ValueError, TypeError):
                        pass
            
            return data
            
        except Exception as err:
            raise UpdateFailed(f"Error fetching data: {err}") from err
