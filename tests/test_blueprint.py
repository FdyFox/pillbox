"""Run the reminder blueprint as a real automation in HA."""
import asyncio
from datetime import datetime

from homeassistant.config_entries import ConfigSubentryData
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_mock_service,
)

from custom_components.pillbox.const import DOMAIN

SWITCH = "switch.magnesium_morgens"


def _at(s: str) -> datetime:
    return datetime.fromisoformat(s).replace(tzinfo=dt_util.get_default_time_zone())


async def _setup(hass, tmp_path, freezer, start: str, repeat: int = 60, last: str = "22:00:00", **extra):
    hass.config.config_dir = str(tmp_path)  # the integration installs the blueprint there

    freezer.move_to(_at(start))
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=DOMAIN,
        options={"slots": {"1": "Morgens", "2": "Mittags", "3": "Abends", "4": "Nachts"}},
        subentries_data=[
            ConfigSubentryData(
                data={"name": "Magnesium", "stock": 20, "intakes": ["1|", "3|"]},
                subentry_id="s1",
                subentry_type="medication",
                title="Magnesium",
                unique_id=None,
            )
        ],
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    assert (tmp_path / "blueprints/automation/pillbox/intake_reminder.yaml").is_file()
    calls = async_mock_service(hass, "notify", "mobile_app_test")
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "use_blueprint": {
                    "path": "pillbox/intake_reminder.yaml",
                    "input": {
                        "intake_switch": SWITCH,
                        "notify_action": "notify.mobile_app_test",
                        "time_weekday": "08:00:00",
                        "time_weekend": "10:00:00",
                        "repeat_minutes": repeat,
                        "last_reminder": last,
                        **extra,
                    },
                }
            }
        },
    )
    await hass.async_block_till_done()
    return calls


async def _settle(hass):
    """A few loop iterations instead of async_block_till_done (which would wait for the waiting automation)."""
    for _ in range(20):
        await asyncio.sleep(0)


async def _tick(hass, freezer, s: str):
    freezer.move_to(_at(s))
    async_fire_time_changed(hass)
    await _settle(hass)


async def test_reminds_repeats_and_take_button(hass, tmp_path, freezer):
    # 2026-11-18 is a Wednesday.
    calls = await _setup(hass, tmp_path, freezer, "2026-11-18 07:59:00")
    await _tick(hass, freezer, "2026-11-18 08:00:00")
    assert len(calls) == 1
    assert calls[0].data["title"] == "Magnesium"
    assert calls[0].data["message"] == "Morgens: not taken yet."
    assert calls[0].data["data"]["actions"][0]["title"] == "Taken"
    assert calls[0].data["data"]["actions"][0]["action"] == f"PILLBOX_{SWITCH}"

    await _tick(hass, freezer, "2026-11-18 09:00:01")
    assert len(calls) == 2  # repeated after 60 min

    hass.bus.async_fire("mobile_app_notification_action", {"action": f"PILLBOX_{SWITCH}"})
    await _settle(hass)
    assert hass.states.get(SWITCH).state == "on"
    assert hass.states.get("number.magnesium_stock").state == "19"
    # The reminder is removed from the phone, no further ones.
    assert calls[-1].data["message"] == "clear_notification"
    n = len(calls)
    await _tick(hass, freezer, "2026-11-18 10:00:01")
    assert len(calls) == n


async def test_weekend_time_and_no_reminder_if_taken(hass, tmp_path, freezer):
    # 2026-11-21 is a Saturday: nothing at 08:00, reminder at 10:00.
    calls = await _setup(hass, tmp_path, freezer, "2026-11-21 07:59:00")
    await _tick(hass, freezer, "2026-11-21 08:00:00")
    assert calls == []
    await hass.services.async_call("switch", "turn_on", {"entity_id": SWITCH}, blocking=True)
    await _settle(hass)
    await _tick(hass, freezer, "2026-11-21 10:00:00")
    assert calls == []


async def test_stops_after_last_reminder(hass, tmp_path, freezer):
    calls = await _setup(hass, tmp_path, freezer, "2026-11-18 07:59:00", last="08:30:00")
    await _tick(hass, freezer, "2026-11-18 08:00:00")
    assert len(calls) == 1
    await _tick(hass, freezer, "2026-11-18 09:00:01")
    assert len(calls) == 1  # next reminder would be after 08:30


async def test_blueprint_is_updated_but_not_rewritten(hass, tmp_path):
    from custom_components.pillbox import _async_install_blueprints

    hass.config.config_dir = str(tmp_path)
    dest = tmp_path / "blueprints/automation/pillbox/intake_reminder.yaml"
    dest.parent.mkdir(parents=True)
    dest.write_text("old version")
    await _async_install_blueprints(hass, ["Morgens"])
    assert dest.read_text() != "old version"
    assert (dest.parent / "person_reminder.yaml").is_file()
    mtime = dest.stat().st_mtime_ns
    await _async_install_blueprints(hass, ["Morgens"])  # unchanged -> not written again
    assert dest.stat().st_mtime_ns == mtime


async def test_intake_reminder_alarm_mode(hass, tmp_path, freezer):
    calls = await _setup(hass, tmp_path, freezer, "2026-11-18 07:59:00", alarm=True)
    await _tick(hass, freezer, "2026-11-18 08:00:00")
    data = calls[0].data["data"]
    assert data["channel"] == "alarm_stream" and data["push"]["sound"]["critical"] == 1
    assert data["actions"][0]["action"] == f"PILLBOX_{SWITCH}"


async def test_intake_reminder_phones_dropdown(hass, tmp_path, freezer):
    from .test_person_reminder import _phone

    phone = _phone(hass, "Anna Phone")
    phone_calls = async_mock_service(hass, "notify", "mobile_app_anna_phone")
    calls = await _setup(hass, tmp_path, freezer, "2026-11-18 07:59:00", notify_devices=[phone])
    await _tick(hass, freezer, "2026-11-18 08:00:00")
    assert len(calls) == 1 and len(phone_calls) == 1  # text field and phone both get it
    assert phone_calls[0].data["data"]["actions"][0]["action"] == f"PILLBOX_{SWITCH}"


async def test_snooze_and_dismiss(hass, tmp_path, freezer):
    calls = await _setup(hass, tmp_path, freezer, "2026-11-18 07:59:00", repeat=0)
    await _tick(hass, freezer, "2026-11-18 08:00:00")
    assert [a["title"] for a in calls[0].data["data"]["actions"]] == ["Taken", "Skip", "Later"]
    assert calls[0].data["data"]["actions"][2]["action"] == f"PILLBOX_{SWITCH}_SNOOZE"

    # "Later": reminded again after 15 minutes, although repetition is off.
    hass.bus.async_fire("mobile_app_notification_action", {"action": f"PILLBOX_{SWITCH}_SNOOZE"})
    await _settle(hass)
    await _tick(hass, freezer, "2026-11-18 08:10:00")
    assert len(calls) == 1
    await _tick(hass, freezer, "2026-11-18 08:15:01")
    assert len(calls) == 2

    # "Skip": removed from the phone, no more reminders today; the intake stays open.
    hass.bus.async_fire("mobile_app_notification_action", {"action": f"PILLBOX_{SWITCH}_DISMISS"})
    await _settle(hass)
    assert calls[-1].data["message"] == "clear_notification"
    n = len(calls)
    await _tick(hass, freezer, "2026-11-18 09:00:00")
    await _tick(hass, freezer, "2026-11-18 12:00:00")
    assert len(calls) == n
    assert hass.states.get(SWITCH).state == "off"


async def test_without_extra_buttons(hass, tmp_path, freezer):
    calls = await _setup(hass, tmp_path, freezer, "2026-11-18 07:59:00", snooze_minutes=0, dismiss_title="")
    await _tick(hass, freezer, "2026-11-18 08:00:00")
    assert [a["title"] for a in calls[0].data["data"]["actions"]] == ["Taken"]
