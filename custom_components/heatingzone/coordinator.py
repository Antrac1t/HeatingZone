"""DataUpdateCoordinator for Heating Zone integration."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class HeatingZoneCoordinator(DataUpdateCoordinator):
    """Heating Zone coordinator."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )
        self.entry = entry

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from OpenTherm sensors."""
        data = {}
        
        # Read OpenTherm sensors if configured
        if opentherm_temp := self.entry.data.get("opentherm_temp"):
            state = self.hass.states.get(opentherm_temp)
            if state and state.state not in ("unknown", "unavailable"):
                try:
                    data["opentherm_temp"] = float(state.state)
                except (ValueError, TypeError):
                    pass
        
        if opentherm_return := self.entry.data.get("opentherm_return"):
            state = self.hass.states.get(opentherm_return)
            if state and state.state not in ("unknown", "unavailable"):
                try:
                    data["opentherm_return"] = float(state.state)
                except (ValueError, TypeError):
                    pass
        
        if opentherm_mod := self.entry.data.get("opentherm_modulation"):
            state = self.hass.states.get(opentherm_mod)
            if state and state.state not in ("unknown", "unavailable"):
                try:
                    data["opentherm_modulation"] = float(state.state)
                except (ValueError, TypeError):
                    pass
        
        return data
