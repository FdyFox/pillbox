"""Reine Kernlogik (ohne Home-Assistant-Abhängigkeit, dadurch einzeln testbar)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta


@dataclass
class Medication:
    """Ein Medikament mit Vorrat und benannten Einnahmen pro Tag (z. B. Morgens, Abends)."""

    name: str
    stock: int
    intakes: list[str] = field(default_factory=lambda: ["Morgens"])
    tablets_per_intake: int = 1
    low_threshold: int = 20
    taken: list[bool] = field(default_factory=list)  # je Einnahme: heute erledigt?

    def __post_init__(self) -> None:
        if not self.intakes:
            raise ValueError("Mindestens eine Einnahme nötig")
        # Gespeicherten Status an die (evtl. geänderte) Zahl der Einnahmen anpassen.
        self.taken = (list(self.taken) + [False] * len(self.intakes))[: len(self.intakes)]

    @property
    def intakes_per_day(self) -> int:
        return len(self.intakes)

    @property
    def taken_today(self) -> int:
        return sum(self.taken)

    @property
    def daily_consumption(self) -> int:
        return self.tablets_per_intake * self.intakes_per_day

    @property
    def complete_today(self) -> bool:
        return all(self.taken)

    @property
    def low_stock(self) -> bool:
        return self.stock < self.low_threshold

    @property
    def open_intakes(self) -> list[str]:
        return [n for n, t in zip(self.intakes, self.taken) if not t]

    def next_open(self) -> int | None:
        """Index der nächsten offenen Einnahme, None wenn heute alles erledigt ist."""
        return next((i for i, t in enumerate(self.taken) if not t), None)

    def set_intake(self, index: int, taken: bool) -> bool:
        """Einnahme abhaken (Vorrat runter) oder zurücknehmen (Vorrat wieder hoch).

        False, wenn sich nichts ändert (schon im gewünschten Zustand).
        """
        if self.taken[index] == taken:
            return False
        self.taken[index] = taken
        if taken:
            self.stock = max(0, self.stock - self.tablets_per_intake)
        else:
            self.stock += self.tablets_per_intake
        return True

    def take(self) -> bool:
        """Nächste offene Einnahme erfassen. False, wenn heute schon alles genommen ist."""
        index = self.next_open()
        return index is not None and self.set_intake(index, True)

    def refill(self, stock: int) -> None:
        """Restmenge nach neuer Packung setzen."""
        self.stock = max(0, int(stock))

    def reset_day(self) -> None:
        self.taken = [False] * len(self.intakes)

    def last_covered_day(self, today: date) -> date | None:
        """Letzter Tag, für den der Vorrat noch reicht (None = heute schon zu knapp)."""
        if self.daily_consumption <= 0:
            return None
        need_today = len(self.open_intakes) * self.tablets_per_intake
        if self.stock < need_today:
            return None
        return today + timedelta(days=(self.stock - need_today) // self.daily_consumption)

    def days_left(self, today: date) -> int:
        """Tage, die der Vorrat noch trägt (heute mitgezählt, solange noch offen)."""
        last = self.last_covered_day(today)
        if last is None:
            return 0
        days = (last - today).days
        return days if self.complete_today else days + 1
