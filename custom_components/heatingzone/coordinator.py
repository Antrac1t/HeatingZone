"""DataUpdateCoordinator for Heating Zone integration."""
from __future__ import annotations

import asyncio
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
        self.heat_source_lock = asyncio.Lock()
        self.last_heat_source_on = None
        self.last_heat_source_off = None

    async def _async_update_data(self) -> dict[str, Any]:
        """Return shared runtime data for heating source control."""
        return {}
