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
