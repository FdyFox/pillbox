"""Run the person reminder blueprint as a real automation in HA."""
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import async_mock_service

from custom_components.pillbox.const import DOMAIN

from .test_blueprint import _settle, _tick
from .test_init import _at, _family_entry, _scan
from .test_doses import _entry as _doses_entry


async def _setup(hass, tmp_path, freezer, entry, person: str, slot: str, start="2026-11-18 07:59:00", **extra):
    hass.config.config_dir = str(tmp_path)  # the integration installs the blueprints there
    freezer.move_to(_at(start))
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    device = dr.async_get(hass).async_get_device(identifiers={(DOMAIN, person)})
    calls = async_mock_service(hass, "notify", "mobile_app_test")
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "use_blueprint": {
                    "path": "pillbox/person_reminder.yaml",
                    "input": {
                        "person": device.id,
                        "slot": slot,
                        "notify_action": "notify.mobile_app_test",
                        "time_weekday": "08:00:00",
                        "time_weekend": "10:00:00",
                        "repeat_minutes": 60,
                        **extra,
                    },
                }
            }
        },
    )
    await hass.async_block_till_done()
    return calls, device.id


async def test_lists_everything_open_and_stops_when_done(hass, tmp_path, freezer):
    calls, _ = await _setup(hass, tmp_path, freezer, _family_entry(hass), "ben", "Morgens")
    await _tick(hass, freezer, "2026-11-18 08:00:00")
    assert len(calls) == 1
    assert calls[0].data["title"] == "Ben: Morgens"
    assert calls[0].data["message"] == "Still to take:\n• Magnesium 10 mg\n• Magnesium 20 mg"
    # Only what is still open is listed in the next reminder.
    await hass.services.async_call("switch", "turn_on", {"entity_id": "switch.ben_magnesium_20_mg_morgens"}, blocking=True)
    await _tick(hass, freezer, "2026-11-18 09:00:01")
    assert calls[-1].data["message"] == "Still to take:\n• Magnesium 10 mg"
    # Ben's tag checks off the rest -> the reminder is removed, no further ones.
    await _scan(hass, "tag-ben")
    await _settle(hass)
    assert calls[-1].data["message"] == "clear_notification"
    n = len(calls)
    await _tick(hass, freezer, "2026-11-18 10:00:02")
    assert len(calls) == n


async def test_next_slot_and_taken_button(hass, tmp_path, freezer):
    calls, device_id = await _setup(hass, tmp_path, freezer, _family_entry(hass), "anna", "")
    await _tick(hass, freezer, "2026-11-18 08:00:00")
    # Empty time of day = the next one with something open (morning, not noon).
    assert calls[0].data["title"] == "Anna: Morgens"
    assert calls[0].data["message"] == "Still to take:\n• Magnesium 10 mg"
    action = calls[0].data["data"]["actions"][0]
    assert action == {"action": f"PILLBOX_PERSON_{device_id}", "title": "Taken"}
    hass.bus.async_fire("mobile_app_notification_action", {"action": action["action"]})
    await _settle(hass)
    assert hass.states.get("switch.anna_magnesium_10_mg_morgens").state == "on"
    assert hass.states.get("switch.anna_magnesium_10_mg_mittags").state == "off"


async def test_doses_and_as_needed(hass, tmp_path, freezer):
    calls, _ = await _setup(hass, tmp_path, freezer, _doses_entry(hass), "anna", "Morgens")
    await _tick(hass, freezer, "2026-11-18 08:00:00")
    assert calls[0].data["message"] == "Still to take:\n• Magnesium 10 mg (½)"


async def test_as_needed_only_no_reminder(hass, tmp_path, freezer):
    calls, _ = await _setup(hass, tmp_path, freezer, _doses_entry(hass), "ben", "Abends")
    await _tick(hass, freezer, "2026-11-18 08:00:00")
    assert calls == []


async def test_alarm_mode(hass, tmp_path, freezer):
    calls, device_id = await _setup(hass, tmp_path, freezer, _family_entry(hass), "ben", "Morgens", alarm=True)
    await _tick(hass, freezer, "2026-11-18 08:00:00")
    data = calls[0].data["data"]
    assert data["channel"] == "alarm_stream" and data["ttl"] == 0 and data["priority"] == "high"
    assert data["push"]["sound"] == {"name": "default", "critical": 1, "volume": 1.0}
    assert data["push"]["interruption-level"] == "critical"
    assert data["tag"] == f"PILLBOX_PERSON_{device_id}" and data["actions"][0]["title"] == "Taken"


async def test_no_alarm_by_default(hass, tmp_path, freezer):
    calls, _ = await _setup(hass, tmp_path, freezer, _family_entry(hass), "ben", "Morgens")
    await _tick(hass, freezer, "2026-11-18 08:00:00")
    assert "channel" not in calls[0].data["data"] and "push" not in calls[0].data["data"]


def _phone(hass, name: str) -> str:
    """A Companion app device; its notify action is notify.mobile_app_<slug of the name>."""
    from pytest_homeassistant_custom_component.common import MockConfigEntry

    app = MockConfigEntry(domain="mobile_app", title=name)
    app.add_to_hass(hass)
    return dr.async_get(hass).async_get_or_create(
        config_entry_id=app.entry_id, identifiers={("mobile_app", name)}, name=name
    ).id


async def test_phones_dropdown(hass, tmp_path, freezer):
    entry = _family_entry(hass)
    phone_a, phone_b = _phone(hass, "Anna Phone"), _phone(hass, "Pixel 8")
    calls_a = async_mock_service(hass, "notify", "mobile_app_anna_phone")
    calls_b = async_mock_service(hass, "notify", "mobile_app_pixel_8")
    calls, _ = await _setup(
        hass, tmp_path, freezer, entry, "ben", "Morgens", notify_devices=[phone_a, phone_b], notify_action="", alarm=True
    )
    await _tick(hass, freezer, "2026-11-18 08:00:00")
    assert calls == []
    for c in (calls_a, calls_b):
        assert len(c) == 1
        assert c[0].data["message"] == "Still to take:\n• Magnesium 10 mg\n• Magnesium 20 mg"
        assert c[0].data["data"]["channel"] == "alarm_stream"
    await _scan(hass, "tag-ben")
    await _settle(hass)
    assert calls_a[-1].data["message"] == "clear_notification" and calls_b[-1].data["message"] == "clear_notification"


async def test_chosen_intakes_include_as_needed(hass, tmp_path, freezer):
    # Ben's evening intake is "as needed": chosen explicitly, it is reminded.
    calls, _ = await _setup(
        hass, tmp_path, freezer, _doses_entry(hass), "ben", "", intakes=["switch.ben_magnesium_10_mg_abends"]
    )
    await _tick(hass, freezer, "2026-11-18 08:00:00")
    assert calls[0].data["title"] == "Ben: Abends"
    assert calls[0].data["message"] == "Still to take:\n• Magnesium 10 mg"


async def test_times_of_day_as_dropdown(hass, tmp_path, freezer):
    entry = _family_entry(hass)
    await _setup(hass, tmp_path, freezer, entry, "ben", "Morgens")
    blueprint = tmp_path / "blueprints/automation/pillbox/person_reminder.yaml"
    assert 'options: ["Morgens", "Mittags", "Abends", "Nachts"]' in blueprint.read_text()
    assert "pillbox:slots" not in blueprint.read_text()
    # Renamed in the Pillbox options -> the blueprint is rewritten.
    hass.config_entries.async_update_entry(entry, options={**entry.options, "slots": {"1": "Früh", "2": "Mittags", "3": "Abends", "4": "Nachts"}})
    await hass.async_block_till_done()
    assert 'options: ["Früh", "Mittags", "Abends", "Nachts"]' in blueprint.read_text()


async def test_medications_inline(hass, tmp_path, freezer):
    calls, _ = await _setup(
        hass, tmp_path, freezer, _family_entry(hass), "ben", "Morgens",
        message="{{ person }}, du musst noch {{ medications_inline }} nehmen.",
    )
    await _tick(hass, freezer, "2026-11-18 08:00:00")
    assert calls[0].data["message"] == "Ben, du musst noch Magnesium 10 mg, Magnesium 20 mg nehmen."


async def test_person_snooze(hass, tmp_path, freezer):
    calls, device_id = await _setup(hass, tmp_path, freezer, _family_entry(hass), "ben", "Morgens", snooze_minutes=30, snooze_title="Später")
    await _tick(hass, freezer, "2026-11-18 08:00:00")
    assert calls[0].data["data"]["actions"][2] == {"action": f"PILLBOX_PERSON_{device_id}_SNOOZE", "title": "Später"}
    hass.bus.async_fire("mobile_app_notification_action", {"action": f"PILLBOX_PERSON_{device_id}_SNOOZE"})
    await _settle(hass)
    await _tick(hass, freezer, "2026-11-18 08:30:01")
    assert len(calls) == 2
    # Taken during the snooze -> no further reminder, removed from the phone.
    hass.bus.async_fire("mobile_app_notification_action", {"action": f"PILLBOX_PERSON_{device_id}_SNOOZE"})
    await _settle(hass)
    await _scan(hass, "tag-ben")
    await _settle(hass)
    assert calls[-1].data["message"] == "clear_notification"
    n = len(calls)
    await _tick(hass, freezer, "2026-11-18 09:30:00")
    assert len(calls) == n
