"""Binary sensor platform for Heating Zone shared system state."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


@dataclass(frozen=True, kw_only=True)
class HeatingZoneBinarySensorDescription(BinarySensorEntityDescription):
    """Describe a Heating Zone system binary sensor."""

    value_key: str


BINARY_SENSORS: tuple[HeatingZoneBinarySensorDescription, ...] = (
    HeatingZoneBinarySensorDescription(
        key="nt_active",
        name="NT aktivni",
        value_key="nt_active",
    ),
    HeatingZoneBinarySensorDescription(
        key="tuv_ready",
        name="TUV pripravena",
        value_key="tuv_ready",
    ),
    HeatingZoneBinarySensorDescription(
        key="tuv_emergency",
        name="TUV nouzove minimum",
        value_key="tuv_emergency",
    ),
    HeatingZoneBinarySensorDescription(
        key="buffer_ready_for_heating",
        name="AN pripravljena pro topeni",
        value_key="buffer_ready_for_heating",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Heating Zone shared binary sensors."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        HeatingZoneSystemBinarySensor(coordinator, entry, description)
        for description in BINARY_SENSORS
    )


class HeatingZoneSystemBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Shared Heating Zone system binary sensor."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, entry: ConfigEntry, description: HeatingZoneBinarySensorDescription) -> None:
        """Initialize binary sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{DOMAIN}_{entry.entry_id}_{description.key}"
        self._attr_name = description.name

    @property
    def is_on(self) -> bool:
        """Return binary state from coordinator data."""
        return bool(self.coordinator.data.get(self.entity_description.value_key))
