"""Low stock and "complete today" (all intakes of the day done)."""
from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PillboxConfigEntry
from .entity import PillboxEntity, add_per_medication


async def async_setup_entry(
    hass: HomeAssistant, entry: PillboxConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    add_per_medication(
        entry,
        async_add_entities,
        lambda m, s: [LowStockSensor(m, s, "low_stock"), CompleteTodaySensor(m, s, "complete_today")],
    )


class LowStockSensor(PillboxEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    @property
    def is_on(self) -> bool:
        return self.med.low_stock


class CompleteTodaySensor(PillboxEntity, BinarySensorEntity):
    _attr_icon = "mdi:check-all"

    @property
    def is_on(self) -> bool:
        return self.med.complete_today
