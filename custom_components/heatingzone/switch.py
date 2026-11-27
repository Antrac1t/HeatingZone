"""Switch platform for Heating Zone runtime controls."""
from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import HeatingZoneCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Heating Zone dashboard switches."""
    coordinator: HeatingZoneCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([HeatingOnlyLowCostSwitch(coordinator, entry)])


class HeatingOnlyLowCostSwitch(CoordinatorEntity, SwitchEntity):
    """Dashboard switch restricting zone heating to NT or FVE."""

    _attr_has_entity_name = True
    _attr_name = "Topení zón pouze při NT nebo FVE"
    _attr_suggested_object_id = "heating_only_low_cost"
    _attr_icon = "mdi:transmission-tower"

    def __init__(
        self, coordinator: HeatingZoneCoordinator, entry: ConfigEntry
    ) -> None:
        """Initialize the switch entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_heating_only_low_cost"

    @property
    def is_on(self) -> bool:
        """Return whether the NT/FVE-only heating rule is enabled."""
        return self.coordinator.heating_only_low_cost

    async def async_turn_on(self, **kwargs) -> None:
        """Enable zone heating only during NT or FVE."""
        await self.coordinator.async_set_heating_only_low_cost(True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        """Allow zone heating regardless of tariff or FVE state."""
        await self.coordinator.async_set_heating_only_low_cost(False)
        self.async_write_ha_state()
