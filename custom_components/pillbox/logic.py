"""Pure core logic (no Home Assistant dependency, so it can be tested on its own)."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, timedelta


def tidy(value: float) -> float | int:
    """Round away float noise (e.g. 0.1 + 0.2) and return whole numbers as int."""
    value = round(float(value), 4)
    return int(value) if value.is_integer() else value


@dataclass
class Medication:
    """A pack with stock and named intakes per day (e.g. morning, evening).

    Each intake has its own dose (tablets, fractions like 0.5 allowed) and can be "as needed":
    such an intake can be checked off like any other, but is never open or due and does not
    count towards the daily consumption.
    """

    name: str
    stock: float
    intakes: list[str] = field(default_factory=lambda: ["Morgens"])
    tablets_per_intake: float = 1  # default dose for intakes without their own
    low_threshold: float = 20
    taken: list[bool] = field(default_factory=list)  # per intake: done today?
    doses: list[float] = field(default_factory=list)  # per intake: tablets
    as_needed: list[bool] = field(default_factory=list)  # per intake: only when needed?
    amounts: list[float] = field(default_factory=list)  # per intake: tablets taken today (0 = open)

    def __post_init__(self) -> None:
        if not self.intakes:
            raise ValueError("At least one intake is required")
        n = len(self.intakes)
        # Adapt the stored status to the (possibly changed) number of intakes.
        self.taken = (list(self.taken) + [False] * n)[:n]
        self.doses = (list(self.doses) + [self.tablets_per_intake] * n)[:n]
        self.as_needed = (list(self.as_needed) + [False] * n)[:n]
        # Taken without a stored amount (older state) -> the intake's dose.
        amounts = (list(self.amounts) + [0] * n)[:n]
        self.amounts = [(a or d) if t else 0 for t, a, d in zip(self.taken, amounts, self.doses)]

    def _due(self) -> list[int]:
        """Indexes of the regular (not "as needed") intakes."""
        return [i for i, a in enumerate(self.as_needed) if not a]

    @property
    def intakes_per_day(self) -> int:
        """Regular intakes per day ("as needed" ones are not counted)."""
        return len(self._due())

    @property
    def taken_today(self) -> int:
        return sum(self.taken)

    @property
    def daily_consumption(self) -> float:
        return tidy(sum(self.doses[i] for i in self._due()))

    @property
    def complete_today(self) -> bool:
        return all(self.taken[i] for i in self._due())

    @property
    def low_stock(self) -> bool:
        return self.stock < self.low_threshold

    @property
    def open_intakes(self) -> list[str]:
        return [self.intakes[i] for i in self._due() if not self.taken[i]]

    def next_open(self) -> int | None:
        """Index of the next open regular intake, None if everything is done today."""
        return next((i for i in self._due() if not self.taken[i]), None)

    def set_intake(self, index: int, taken: bool, amount: float | None = None) -> bool:
        """Check off an intake (stock down by its dose or `amount`) or undo it (the amount goes back).

        `amount` only applies to today, e.g. 0.75 instead of the usual 1. On an intake already
        taken it corrects the amount. False if nothing changes.
        """
        if not taken:
            if not self.taken[index]:
                return False
            self.stock = tidy(self.stock + self.amounts[index])
            self.taken[index], self.amounts[index] = False, 0
            return True
        if self.taken[index] and amount is None:
            return False
        new = tidy(self.doses[index] if amount is None else amount)
        old = self.amounts[index] if self.taken[index] else 0
        if self.taken[index] and new == old:
            return False
        self.stock = tidy(max(0, self.stock + old - new))
        self.taken[index], self.amounts[index] = True, new
        return True

    def take(self) -> bool:
        """Record the next open intake. False if everything has been taken today.

        A pack with only "as needed" intakes records the next one not taken yet.
        """
        index = self.next_open()
        if index is None and not self._due():
            index = next((i for i, t in enumerate(self.taken) if not t), None)
        return index is not None and self.set_intake(index, True)

    def refill(self, stock: float) -> None:
        """Set the remaining stock after a new pack."""
        self.stock = tidy(max(0, stock))

    def reset_day(self) -> None:
        self.taken = [False] * len(self.intakes)
        self.amounts = [0] * len(self.intakes)

    def last_covered_day(self, today: date) -> date | None:
        """Last day the stock still covers (None = already too low today, or only "as needed")."""
        if self.daily_consumption <= 0:
            return None
        need_today = sum(self.doses[i] for i in self._due() if not self.taken[i])
        if self.stock < need_today:
            return None
        # Divide first and round, so e.g. 0.9 / 0.3 gives 3 days and not 2 (float noise).
        return today + timedelta(days=math.floor(tidy((self.stock - need_today) / self.daily_consumption)))

    def days_left(self, today: date) -> int | None:
        """Days the stock still lasts (today included while still open); None if only "as needed"."""
        if self.daily_consumption <= 0:
            return None
        last = self.last_covered_day(today)
        if last is None:
            return 0
        days = (last - today).days
        return days if self.complete_today else days + 1
