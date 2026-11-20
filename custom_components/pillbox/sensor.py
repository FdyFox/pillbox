"""Reichweite des Vorrats (Tage, Datum) und Einnahmen heute."""
from __future__ import annotations

from datetime import date
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import PillboxConfigEntry, logical_today
from .const import parse_key
from .entity import PersonEntity, PillboxEntity, add_per_medication, add_per_person


async def async_setup_entry(
    hass: HomeAssistant, entry: PillboxConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    add_per_medication(
        entry,
        async_add_entities,
        lambda m, s: [
            DaysLeftSensor(m, s, "days_left"),
            RunsOutOnSensor(m, s, "runs_out_on"),
            TakenCountSensor(m, s, "taken_count"),
        ],
    )
    add_per_person(entry, async_add_entities, lambda m, s: [PersonOpenSensor(m, s, "open_intakes")])


class DaysLeftSensor(PillboxEntity, SensorEntity):
    _attr_icon = "mdi:calendar-clock"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTime.DAYS
    _attr_suggested_display_precision = 0

    @property
    def native_value(self) -> int:
        return self.med.days_left(logical_today())


class RunsOutOnSensor(PillboxEntity, SensorEntity):
    _attr_icon = "mdi:calendar-end"
    _attr_device_class = SensorDeviceClass.DATE

    @property
    def native_value(self) -> date | None:
        return self.med.last_covered_day(logical_today())


class TakenCountSensor(PillboxEntity, SensorEntity):
    """Anzahl der heute erledigten Einnahmen; Attribute nennen erledigte und offene."""

    _attr_icon = "mdi:counter"
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int:
        return self.med.taken_today

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        med, name = self.med, self.manager.intake_name
        return {
            "total": med.intakes_per_day,
            "taken": [name(k) for k, t in zip(med.intakes, med.taken) if t],
            "open": [name(k) for k in med.open_intakes],
        }


class PersonOpenSensor(PersonEntity, SensorEntity):
    """Offene Einnahmen der Person heute, über alle Medikamente."""

    _attr_icon = "mdi:account-clock"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def _intakes(self) -> list[tuple[str, str, bool]]:
        return self.manager.person_intakes(self.sub_id)

    @property
    def native_value(self) -> int:
        return sum(1 for *_, taken in self._intakes() if not taken)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        m = self.manager
        label = lambda sub_id, key: f"{m.info[sub_id].device_name} ({m.slot_name(key)})"  # noqa: E731
        next_slot = m.next_slot_for(self.sub_id)
        return {
            "next_slot": m.slots.get(next_slot) if next_slot else None,
            "next": [label(s, k) for s, k, t in self._intakes() if not t and parse_key(k)[0] == next_slot],
            "open": [label(s, k) for s, k, t in self._intakes() if not t],
            "taken": [label(s, k) for s, k, t in self._intakes() if t],
        }
