"""Stock as a directly editable number (new pack -> type in the remaining amount)."""
from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PillboxConfigEntry
from .entity import PillboxEntity, add_per_medication


async def async_setup_entry(
    hass: HomeAssistant, entry: PillboxConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    add_per_medication(entry, async_add_entities, lambda m, s: [StockNumber(m, s, "stock")])


class StockNumber(PillboxEntity, NumberEntity):
    _attr_icon = "mdi:pill-multiple"
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 0
    _attr_native_max_value = 10000
    _attr_native_step = 0.25  # halves and quarters of split tablets
    _attr_native_unit_of_measurement = "Stk"

    @property
    def native_value(self) -> float:
        return self.med.stock

    async def async_set_native_value(self, value: float) -> None:
        await self.manager.async_refill(self.sub_id, value)
