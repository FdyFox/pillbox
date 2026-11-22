"""Tests for the core logic. Run: python -m pytest -q"""
import sys
from datetime import date
from pathlib import Path

import importlib.util

spec = importlib.util.spec_from_file_location(
    "logic", Path(__file__).parent.parent / "custom_components" / "pillbox" / "logic.py"
)
logic = importlib.util.module_from_spec(spec)
sys.modules["logic"] = logic
spec.loader.exec_module(logic)
Medication = logic.Medication

TODAY = date(2026, 11, 18)


def test_vitamin_d_not_taken_yet():
    m = Medication("Vitamin D", stock=53)
    assert m.last_covered_day(TODAY) == date(2027, 1, 9)
    assert m.days_left(TODAY) == 53


def test_vitamin_d_taken_today():
    m = Medication("Vitamin D", stock=53)
    assert m.take() is True
    assert m.stock == 52
    assert m.last_covered_day(TODAY) == date(2027, 1, 9)
    assert m.days_left(TODAY) == 52


def test_second_take_same_day_is_ignored():
    m = Medication("Vitamin D", stock=53)
    assert m.take() is True
    assert m.take() is False
    assert m.stock == 52


def test_reset_day_allows_new_take():
    m = Medication("Vitamin D", stock=10)
    m.take()
    m.reset_day()
    assert m.take() is True
    assert m.stock == 8


def test_low_stock_threshold():
    m = Medication("Vitamin D", stock=20)
    assert m.low_stock is False
    m.take()
    assert m.low_stock is True


def test_multiple_intakes_and_tablets():
    m = Medication("Magnesium", stock=12, tablets_per_intake=2, intakes=["Morgens", "Mittags"])
    assert m.daily_consumption == 4
    assert m.days_left(TODAY) == 3
    m.take()
    assert m.stock == 10
    assert m.complete_today is False
    m.take()
    assert m.stock == 8
    assert m.complete_today is True
    assert m.days_left(TODAY) == 2


def test_empty_stock():
    m = Medication("Vitamin D", stock=0)
    assert m.last_covered_day(TODAY) is None
    assert m.days_left(TODAY) == 0
    assert m.take() is True  # counter stays at 0
    assert m.stock == 0


def test_refill():
    m = Medication("Vitamin D", stock=3)
    m.refill(60)
    assert m.stock == 60


def test_named_intakes_switch_and_undo():
    m = Medication("Magnesium", stock=10, intakes=["Morgens", "Abends"])
    assert m.set_intake(1, True) is True  # evening first
    assert m.stock == 9
    assert m.open_intakes == ["Morgens"]
    assert m.next_open() == 0
    assert m.set_intake(1, True) is False  # already done, no second deduction
    assert m.set_intake(1, False) is True  # undo -> tablet goes back
    assert m.stock == 10
    assert m.taken_today == 0


def test_take_marks_next_open():
    m = Medication("Magnesium", stock=10, intakes=["Morgens", "Abends"])
    m.set_intake(0, True)
    assert m.take() is True
    assert m.taken == [True, True]
    assert m.take() is False
    assert m.stock == 8


def test_stored_status_adapts_to_changed_intakes():
    m = Medication("X", stock=5, intakes=["Morgens", "Mittags", "Abends"], taken=[True])
    assert m.taken == [True, False, False]
    m = Medication("X", stock=5, intakes=["Morgens"], taken=[True, True])
    assert m.taken == [True]


# --- Doses per intake and "as needed" ----------------------------------------


def test_half_tablets():
    m = Medication("Magnesium", stock=10, tablets_per_intake=0.5)
    assert m.daily_consumption == 0.5
    assert m.days_left(TODAY) == 20
    assert m.take() is True
    assert m.stock == 9.5
    assert m.last_covered_day(TODAY) == date(2026, 12, 7)  # 9.5 / 0.5 = 19 more days
    assert m.days_left(TODAY) == 19
    m.set_intake(0, False)
    assert m.stock == 10 and isinstance(m.stock, int)


def test_own_dose_per_intake():
    m = Medication("Magnesium", stock=10, intakes=["Morning · Anna", "Morning · Ben"], doses=[0.25, 1])
    assert m.daily_consumption == 1.25
    assert m.days_left(TODAY) == 8
    m.set_intake(0, True)
    assert m.stock == 9.75
    m.take()
    assert m.stock == 8.75
    assert m.days_left(TODAY) == 7  # 8.75 / 1.25 = 7


def test_no_float_noise():
    m = Medication("X", stock=0.9, doses=[0.3])
    assert m.days_left(TODAY) == 3
    for _ in range(3):
        m.take()
        m.reset_day()
    assert m.stock == 0


def test_as_needed_is_never_open():
    m = Medication("Magnesium", stock=10, intakes=["Morning", "Evening"], as_needed=[False, True])
    assert m.intakes_per_day == 1
    assert m.daily_consumption == 1
    assert m.open_intakes == ["Morning"]
    assert m.take() is True
    assert m.complete_today is True
    assert m.take() is False  # the "as needed" intake is not taken by the pack's tag
    assert m.days_left(TODAY) == 9
    # ... but can be checked off by hand and then counts down the stock.
    assert m.set_intake(1, True) is True
    assert m.stock == 8
    assert m.taken_today == 2
    assert m.days_left(TODAY) == 8


def test_only_as_needed():
    m = Medication("Vitamin D", stock=10, as_needed=[True])
    assert m.daily_consumption == 0
    assert m.complete_today is True
    assert m.days_left(TODAY) is None
    assert m.last_covered_day(TODAY) is None
    assert m.take() is True  # tag on such a pack: record it
    assert m.stock == 9
    assert m.take() is False


def test_take_other_amount_today():
    m = Medication("Magnesium", stock=10)
    assert m.set_intake(0, True, 0.75) is True
    assert m.stock == 9.25 and m.amounts == [0.75]
    assert m.set_intake(0, True) is False  # already taken, amount kept
    assert m.set_intake(0, True, 0.5) is True  # correct the amount
    assert m.stock == 9.5
    assert m.set_intake(0, False) is True  # undo returns exactly what was taken
    assert m.stock == 10 and m.amounts == [0]
    assert m.days_left(TODAY) == 10  # coverage still uses the dose


def test_stored_taken_without_amount_uses_dose():
    m = Medication("X", stock=5, doses=[0.5], taken=[True])
    assert m.amounts == [0.5]
    m.reset_day()
    assert m.amounts == [0]
