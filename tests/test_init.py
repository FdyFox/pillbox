"""Integrationstests gegen ein echtes Home Assistant (pytest-homeassistant-custom-component)."""
from datetime import datetime

import pytest
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.pillbox.const import DOMAIN, STORAGE_KEY

SLOTS = {"1": "Morgens", "2": "Mittags", "3": "Abends", "4": "Nachts"}
MED_DATA = {
    "name": "Vitamin D",
    "stock": 53,
    "intakes": ["1|"],
    "tablets_per_intake": 1,
    "low_threshold": 20,
    "tag_id": "tag-vitamin_d",
}
SUB_ID = "sub1"


def _at(s: str) -> datetime:
    return datetime.fromisoformat(s).replace(tzinfo=dt_util.get_default_time_zone())


def _sub(sub_id, data, kind="medication", title=None):
    return ConfigSubentryData(
        data=data, subentry_id=sub_id, subentry_type=kind, title=title or data["name"], unique_id=None
    )


def _make_entry(hass, data=MED_DATA, subs=None, options=None) -> MockConfigEntry:
    e = MockConfigEntry(
        domain=DOMAIN,
        title="Pillbox",
        unique_id=DOMAIN,
        options={"slots": SLOTS} if options is None else options,
        subentries_data=subs if subs is not None else [_sub(SUB_ID, data)],
    )
    e.add_to_hass(hass)
    return e


@pytest.fixture
def entry(hass: HomeAssistant) -> MockConfigEntry:
    return _make_entry(hass)


def _store(hass_storage, entry, data):
    key = f"{STORAGE_KEY}.{entry.entry_id}"
    hass_storage[key] = {"version": 1, "key": key, "data": data}


async def _setup(hass, entry):
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


def _state(hass, entity_id):
    s = hass.states.get(entity_id)
    assert s is not None, f"{entity_id} fehlt, vorhanden: {sorted(hass.states.async_entity_ids())}"
    return s.state


async def _call(hass, domain, service, entity_id, **data):
    await hass.services.async_call(domain, service, {"entity_id": entity_id, **data}, blocking=True)
    await hass.async_block_till_done()


async def _scan(hass, tag):
    hass.bus.async_fire("tag_scanned", {"tag_id": tag})
    await hass.async_block_till_done()


# --- Ein Medikament ohne Personen ---------------------------------------------


async def test_entities_created(hass, entry, freezer):
    freezer.move_to(_at("2026-11-18 07:00:00"))
    await _setup(hass, entry)
    assert _state(hass, "number.vitamin_d_stock") == "53"
    assert _state(hass, "switch.vitamin_d_morgens") == "off"
    assert _state(hass, "sensor.vitamin_d_intakes_today") == "0"
    assert _state(hass, "binary_sensor.vitamin_d_complete_today") == "off"
    assert _state(hass, "sensor.vitamin_d_days_left") == "53"
    assert _state(hass, "sensor.vitamin_d_runs_out_on") == "2027-01-09"
    assert _state(hass, "binary_sensor.vitamin_d_low_stock") == "off"
    assert _state(hass, "button.vitamin_d_take") == "unknown"


async def test_tag_scan_takes(hass, entry, freezer):
    freezer.move_to(_at("2026-11-18 09:00:00"))
    await _setup(hass, entry)
    await _scan(hass, "tag-vitamin_d")
    assert _state(hass, "number.vitamin_d_stock") == "52"
    assert _state(hass, "switch.vitamin_d_morgens") == "on"
    assert _state(hass, "binary_sensor.vitamin_d_complete_today") == "on"
    assert _state(hass, "sensor.vitamin_d_days_left") == "52"
    assert _state(hass, "sensor.vitamin_d_runs_out_on") == "2027-01-09"
    await _scan(hass, "tag-vitamin_d")  # zweiter Scan am selben Tag zählt nicht
    assert _state(hass, "number.vitamin_d_stock") == "52"


async def test_switch_takes_and_undo_refunds(hass, entry, freezer):
    freezer.move_to(_at("2026-11-18 09:00:00"))
    await _setup(hass, entry)
    await _call(hass, "switch", "turn_on", "switch.vitamin_d_morgens")
    assert _state(hass, "number.vitamin_d_stock") == "52"
    await _call(hass, "switch", "turn_off", "switch.vitamin_d_morgens")
    assert _state(hass, "number.vitamin_d_stock") == "53"


async def test_two_intakes_without_persons(hass, freezer):
    entry = _make_entry(
        hass, {**MED_DATA, "name": "Magnesium", "stock": 20, "intakes": ["3|", "1|"], "tablets_per_intake": 2}
    )
    freezer.move_to(_at("2026-11-18 09:00:00"))
    await _setup(hass, entry)
    assert _state(hass, "sensor.magnesium_days_left") == "5"
    await _scan(hass, "tag-vitamin_d")  # Reihenfolge nach Tageszeit, nicht nach Eingabe
    assert _state(hass, "switch.magnesium_morgens") == "on"
    assert _state(hass, "switch.magnesium_abends") == "off"
    assert _state(hass, "number.magnesium_stock") == "18"
    count = hass.states.get("sensor.magnesium_intakes_today")
    assert count.state == "1"
    assert count.attributes["open"] == ["Abends"]
    await _call(hass, "button", "press", "button.magnesium_take")
    assert _state(hass, "switch.magnesium_abends") == "on"
    assert _state(hass, "binary_sensor.magnesium_complete_today") == "on"


async def test_button_and_number(hass, entry, freezer):
    freezer.move_to(_at("2026-11-18 09:00:00"))
    await _setup(hass, entry)
    await _call(hass, "button", "press", "button.vitamin_d_take")
    assert _state(hass, "number.vitamin_d_stock") == "52"
    await _call(hass, "number", "set_value", "number.vitamin_d_stock", value=15)
    assert _state(hass, "number.vitamin_d_stock") == "15"
    assert _state(hass, "binary_sensor.vitamin_d_low_stock") == "on"


async def test_low_stock_event(hass, freezer):
    entry = _make_entry(hass, {**MED_DATA, "strength": "1000 IE"})
    freezer.move_to(_at("2026-11-18 09:00:00"))
    events = []
    hass.bus.async_listen(f"{DOMAIN}_low_stock", events.append)
    await _setup(hass, entry)
    await _call(hass, "number", "set_value", "number.vitamin_d_1000_ie_stock", value=20)
    await _call(hass, "button", "press", "button.vitamin_d_1000_ie_take")
    assert [e.data for e in events] == [{"medication": "Vitamin D 1000 IE"}]


# --- Tageswechsel und Speicher ------------------------------------------------


async def test_day_reset_at_4(hass, entry, freezer):
    freezer.move_to(_at("2026-11-18 23:00:00"))
    await _setup(hass, entry)
    await _call(hass, "button", "press", "button.vitamin_d_take")
    freezer.move_to(_at("2026-11-19 02:00:00"))  # nach Mitternacht gilt noch der Vortag
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert _state(hass, "switch.vitamin_d_morgens") == "on"
    freezer.move_to(_at("2026-11-19 04:00:00"))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert _state(hass, "switch.vitamin_d_morgens") == "off"
    assert _state(hass, "number.vitamin_d_stock") == "52"


async def test_missed_reset_is_caught_up(hass, entry, hass_storage, freezer):
    """HA war um 04:00 aus: beim Start wird der Tag trotzdem zurückgesetzt."""
    _store(hass_storage, entry, {"day": "2026-11-17", "meds": {SUB_ID: {"stock": 40, "taken": {"1|": True}, "config_stock": 53}}})
    freezer.move_to(_at("2026-11-18 09:00:00"))
    await _setup(hass, entry)
    assert _state(hass, "number.vitamin_d_stock") == "40"
    assert _state(hass, "switch.vitamin_d_morgens") == "off"


@pytest.mark.parametrize("taken", [{"1|": True}, [True]], ids=["aktuell", "liste"])
async def test_same_day_state_is_kept(hass, entry, hass_storage, freezer, taken):
    _store(hass_storage, entry, {"day": "2026-11-18", "meds": {SUB_ID: {"stock": 40, "taken": taken, "config_stock": 53}}})
    freezer.move_to(_at("2026-11-18 09:00:00"))
    await _setup(hass, entry)
    assert _state(hass, "switch.vitamin_d_morgens") == "on"


async def test_old_store_count_format(hass, entry, hass_storage, freezer):
    _store(hass_storage, entry, {"day": "2026-11-18", "meds": {SUB_ID: {"stock": 40, "taken_today": 1, "config_stock": 53}}})
    freezer.move_to(_at("2026-11-18 09:00:00"))
    await _setup(hass, entry)
    assert _state(hass, "switch.vitamin_d_morgens") == "on"


async def test_reconfigured_stock_wins(hass, entry, hass_storage, freezer):
    _store(hass_storage, entry, {"day": "2026-11-18", "meds": {SUB_ID: {"stock": 40, "taken": {}, "config_stock": 30}}})
    freezer.move_to(_at("2026-11-18 09:00:00"))
    await _setup(hass, entry)
    assert _state(hass, "number.vitamin_d_stock") == "53"


# --- Übernahme alter Einträge ---------------------------------------------------


async def test_migrates_named_intakes_to_slots(hass, freezer):
    old = {**MED_DATA, "intakes": ["Morgens", "Zum Frühstück"], "reminder_weekday": "08:00:00"}
    entry = _make_entry(hass, old)
    freezer.move_to(_at("2026-11-18 09:00:00"))
    await _setup(hass, entry)
    assert entry.options["slots"] == {**SLOTS, "5": "Zum Frühstück"}
    assert entry.subentries[SUB_ID].data["intakes"] == ["1|", "5|"]
    assert "reminder_weekday" not in entry.subentries[SUB_ID].data
    assert _state(hass, "switch.vitamin_d_morgens") == "off"
    assert _state(hass, "switch.vitamin_d_zum_fruhstuck") == "off"


async def test_migrates_count_without_options(hass, freezer):
    old = {k: v for k, v in MED_DATA.items() if k != "intakes"} | {"intakes_per_day": 2}
    entry = _make_entry(hass, old, options={})
    freezer.move_to(_at("2026-11-18 09:00:00"))
    await _setup(hass, entry)
    assert entry.options["slots"] == {"1": "Morning", "2": "Noon", "3": "Evening", "4": "Night"}
    assert _state(hass, "switch.vitamin_d_morning") == "off"
    assert _state(hass, "switch.vitamin_d_evening") == "off"


async def test_removed_intake_removes_switch(hass, freezer):
    entry = _make_entry(hass, {**MED_DATA, "intakes": ["1|", "3|"]})
    freezer.move_to(_at("2026-11-18 09:00:00"))
    await _setup(hass, entry)
    registry = er.async_get(hass)
    assert registry.async_get("switch.vitamin_d_abends") is not None
    hass.config_entries.async_update_subentry(entry, entry.subentries[SUB_ID], data=MED_DATA)
    await hass.async_block_till_done()
    assert registry.async_get("switch.vitamin_d_abends") is None
    assert registry.async_get("switch.vitamin_d_morgens") is not None


# --- Personen und gemeinsame Packungen ----------------------------------------


def _family_entry(hass):
    """Anna und Ben teilen sich Magnesium 10 mg; Ben nimmt morgens zusätzlich 20 mg."""
    return _make_entry(
        hass,
        subs=[
            _sub("anna", {"name": "Anna", "tag_id": "tag-anna"}, "person"),
            _sub("ben", {"name": "Ben", "tag_id": "tag-ben"}, "person"),
            _sub("m10", {"name": "Magnesium", "strength": "10 mg", "stock": 30, "intakes": ["1|anna", "1|ben", "2|anna"]}),
            _sub("m20", {"name": "Magnesium", "strength": "20 mg", "stock": 10, "intakes": ["1|ben"]}),
        ],
    )


async def test_shared_pack_and_person_tags(hass, freezer):
    entry = _family_entry(hass)
    freezer.move_to(_at("2026-11-18 07:30:00"))
    await _setup(hass, entry)
    assert _state(hass, "switch.magnesium_10_mg_anna_morgens") == "off"
    assert _state(hass, "switch.magnesium_10_mg_ben_morgens") == "off"
    assert _state(hass, "switch.magnesium_10_mg_anna_mittags") == "off"
    assert _state(hass, "sensor.magnesium_10_mg_days_left") == "10"  # 3 Tabletten pro Tag
    anna = hass.states.get("sensor.anna_open_intakes")
    assert anna.state == "2"
    assert anna.attributes["next_slot"] == "Morgens"
    assert anna.attributes["next"] == ["Magnesium 10 mg (Morgens)"]

    # Anna morgens: nur ihre Morgen-Einnahme, nicht schon die vom Mittag.
    await _scan(hass, "tag-anna")
    assert _state(hass, "switch.magnesium_10_mg_anna_morgens") == "on"
    assert _state(hass, "switch.magnesium_10_mg_anna_mittags") == "off"
    assert _state(hass, "number.magnesium_10_mg_stock") == "29"
    assert _state(hass, "sensor.anna_open_intakes") == "1"

    # Ben morgens: beide Packungen auf einmal.
    await _scan(hass, "tag-ben")
    assert _state(hass, "switch.magnesium_10_mg_ben_morgens") == "on"
    assert _state(hass, "switch.magnesium_20_mg_ben_morgens") == "on"
    assert _state(hass, "number.magnesium_10_mg_stock") == "28"
    assert _state(hass, "number.magnesium_20_mg_stock") == "9"
    await _scan(hass, "tag-ben")  # nichts mehr offen
    assert _state(hass, "number.magnesium_10_mg_stock") == "28"

    # Anna mittags über den Button der Person.
    await _call(hass, "button", "press", "button.anna_take_now")
    assert _state(hass, "switch.magnesium_10_mg_anna_mittags") == "on"
    assert _state(hass, "number.magnesium_10_mg_stock") == "27"
    assert _state(hass, "sensor.anna_open_intakes") == "0"


async def test_deleted_person_removes_their_intakes(hass, freezer):
    entry = _family_entry(hass)
    freezer.move_to(_at("2026-11-18 07:30:00"))
    await _setup(hass, entry)
    hass.config_entries.async_remove_subentry(entry, "anna")
    await hass.async_block_till_done()
    registry = er.async_get(hass)
    assert registry.async_get("switch.magnesium_10_mg_anna_morgens") is None
    assert _state(hass, "switch.magnesium_10_mg_ben_morgens") == "off"
    assert _state(hass, "sensor.magnesium_10_mg_days_left") == "30"


# --- Formulare ---------------------------------------------------------------


async def test_config_person_and_medication_flow(hass):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    entry = result["result"]
    assert entry.options["slots"]["1"] == "Morning"
    await hass.async_block_till_done()
    again = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert again["type"] is FlowResultType.ABORT

    result = await hass.config_entries.subentries.async_init((entry.entry_id, "person"), context={"source": "user"})
    result = await hass.config_entries.subentries.async_configure(result["flow_id"], {"name": " Anna ", "tag_id": "tag-anna"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    anna_id = next(s for s, sub in entry.subentries.items() if sub.title == "Anna")

    result = await hass.config_entries.subentries.async_init((entry.entry_id, "medication"), context={"source": "user"})
    options = next(v for k, v in result["data_schema"].schema.items() if k == "intakes").config["options"]
    assert {"value": f"1|{anna_id}", "label": "Morning · Anna"} in options
    # Mit Personen gibt es keine Einnahmen „ohne Person“ mehr zur Auswahl.
    assert all(not o["value"].endswith("|") for o in options)

    user_input = {
        "name": " Magnesium ",
        "strength": " 10 mg ",
        "stock": 12.0,
        "intakes": [f"1|{anna_id}", f"2|{anna_id}"],
        "advanced": {"tablets_per_intake": 1.0, "low_threshold": 5.0},
    }
    bad = await hass.config_entries.subentries.async_configure(result["flow_id"], {**user_input, "tag_id": "tag-anna"})
    assert bad["errors"] == {"tag_id": "tag_in_use"}
    result = await hass.config_entries.subentries.async_configure(bad["flow_id"], user_input)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    sub = next(s for s in entry.subentries.values() if s.subentry_type == "medication")
    assert sub.title == "Magnesium 10 mg"
    assert dict(sub.data) == {
        "name": "Magnesium",
        "strength": "10 mg",
        "stock": 12,
        "intakes": [f"1|{anna_id}", f"2|{anna_id}"],
        "tablets_per_intake": 1,
        "low_threshold": 5,
    }
    assert _state(hass, "switch.magnesium_10_mg_anna_noon") == "off"
    assert _state(hass, "sensor.magnesium_10_mg_days_left") == "6"


async def test_options_rename_and_protect_slots(hass, entry):
    await _setup(hass, entry)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    # „Morgens“ wird von Vitamin D genutzt -> nicht löschbar.
    bad = await hass.config_entries.options.async_configure(result["flow_id"], {"slot_1": "", "slot_2": "Mittags"})
    assert bad["errors"] == {"slot_1": "slot_in_use"}
    ok = await hass.config_entries.options.async_configure(
        bad["flow_id"], {"slot_1": "Früh", "slot_2": "Mittags", "slot_3": "Abends"}
    )
    assert ok["type"] is FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.options["slots"] == {"1": "Früh", "2": "Mittags", "3": "Abends"}
    # Umbenennen behält die Entität, nur der Name ändert sich.
    assert hass.states.get("switch.vitamin_d_morgens").attributes["friendly_name"] == "Vitamin D Früh"


async def test_reconfigure_prefills_section(hass, entry):
    await _setup(hass, entry)
    result = await entry.start_subentry_reconfigure_flow(hass, SUB_ID)
    advanced = next(v for k, v in result["data_schema"].schema.items() if str(k) == "advanced")
    sub_suggested = {str(k): (k.description or {}).get("suggested_value") for k in advanced.schema.schema}
    assert sub_suggested == {"tablets_per_intake": 1, "low_threshold": 20}


async def test_tag_dropdown_lists_known_tags(hass):
    from homeassistant.helpers import entity_registry as er

    reg = er.async_get(hass)
    reg.async_get_or_create("tag", "tag", "abc-123", original_name="Tag abc-123")
    named = reg.async_get_or_create("tag", "tag", "def-456", original_name="Tag def-456")
    reg.async_update_entity(named.entity_id, name="Badezimmer")

    entry = MockConfigEntry(domain=DOMAIN, title="Pillbox", unique_id=DOMAIN)
    entry.add_to_hass(hass)
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, "medication"), context={"source": "user"}
    )
    tag_sel = next(v for k, v in result["data_schema"].schema.items() if k == "tag_id")
    cfg = tag_sel.config
    assert cfg["options"] == [
        {"value": "def-456", "label": "Badezimmer"},
        {"value": "abc-123", "label": "Tag abc-123"},
    ]
    assert cfg["custom_value"] is True


async def test_existing_title_gets_strength(hass, freezer):
    entry = _make_entry(hass, {**MED_DATA, "strength": "10mg"})
    await _setup(hass, entry)
    assert entry.subentries[SUB_ID].title == "Vitamin D 10mg"
    assert _state(hass, "number.vitamin_d_10mg_stock") == "53"
