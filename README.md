<p align="center"><img src="assets/pillbox-logo.png" alt="Pillbox" width="600"></p>

# Pillbox

> [!NOTE]
> This integration was developed with the help of AI (Claude by Anthropic): code, tests and documentation were written with AI assistance and are reviewed by me and used in my own Home Assistant. Pillbox is a memory aid, not a medical device.

Home Assistant integration (Marketplace / HACS) that tracks medication intakes and stock.
One NFC tag scan is enough: check off the intake, count down the stock, calculate how long it lasts. Reminders come via a blueprint.

> Status: **v0.1.0**. Runs in my own Home Assistant; tests run against HA 2025.7 to 2026.2.

[![Validate](https://github.com/FdyFox/pillbox/actions/workflows/validate.yml/badge.svg)](https://github.com/FdyFox/pillbox/actions/workflows/validate.yml)

The user interface is available in English and German.

## Goals

- Add medications in the UI, without helpers, templates or naming conventions.
- One pack per strength, each with its own stock and coverage.
- Several people can share a pack (e.g. siblings on the same medication), each with their own NFC tag.
- Freely named times of day ("Morning", "Noon", ...).
- Flexible reminders via blueprint, with their own time and recipient per intake.
- Real entities and services, so dashboards and automations can easily build on them.
- A ready-made dashboard card: who still has to take what today, and how long each pack lasts.

## Scope

**In Pillbox, the pack is the center, not the person.** A medication has one pack with stock per strength; people and times of day are attached to the packs. This gives you coverage ("lasts until ...") and shared packs for several people.

Pillbox is a **daily checklist with a stock counter**, not a scheduler. An intake like "Morning" means "sometime in the morning": Pillbox only asks whether it has been done today and how long the pack will last. There is no "due", no "missed" and no adherence statistics. Clock times only come into play if you use the optional reminder blueprint.

This fits everyday medication, where the point is not to forget and to reorder in time.

If you need fixed intake times (e.g. exactly every 12 hours), with snooze, skip, escalation to relatives and adherence statistics, [pill-reminder](https://github.com/GuidoJeuken-6512/pill-reminder) is the better fit. There the person is the center, with their schedule; pill-reminder does not cover stock or NFC tags.

## Installation

- **Marketplace (Home Assistant 2026.11+):** Settings → Marketplace → "Add from link" → `FdyFox/pillbox`. Then open "Pillbox" in the list, install it and restart Home Assistant if asked.
- **HACS (before 2026.11):** HACS → Custom repositories → `https://github.com/FdyFox/pillbox`, type "Integration". Then install "Pillbox" and restart Home Assistant.
- **Manual:** copy `custom_components/pillbox/` to `/config/custom_components/pillbox/` and restart Home Assistant.

Then: Settings → Devices & services → Add integration → "Pillbox".

Requires Home Assistant 2025.7 or newer (tested with 2025.7 to 2026.2). Home Assistant shows the integration's own icon from 2026.3 on.

## Structure

On the integration page it looks like this:

```text
Pillbox                      ⚙ times of day
├ People                     ⚙ edit people
│  ├ Anna                    device
│  └ Ben                     device
└ Magnesium                  ⚙ edit medication
   ├ Magnesium 10 mg         device (pack)
   └ Magnesium 20 mg         device (pack)
```

- **Pillbox** (one entry). The gear icon sets the **times of day**: up to 6, default "Morning, Noon, Evening, Night" (in German "Morgens, Mittags, Abends, Nachts"). They can be renamed at any time; a time that is still used by a pack cannot be removed.
- **People** (optional, one subentry for everyone). Each person is a device.
- **Medication** (one subentry per medication). Each strength is a **pack** and its own device.

### People

"Add people" first asks for the names, then shows one page per person. Later you edit everyone via the gear icon at "People": add or remove names, and change name, HA person and tag per person. Renaming keeps a person's intakes; removing a person removes their intakes from the packs.

| Field | Meaning |
| --- | --- |
| `name` | e.g. "Anna" |
| `ha_person` | optional link to a person in HA |
| `tag_id` | The person's NFC tag. A scan checks off all of their open intakes at the earliest open time of day, across all packs |

### Medication and packs

"Add medication" first asks for name and strengths, then shows one page per strength for the pack. Editing via the gear icon at the medication works the same way; a new strength adds a pack, a removed one deletes it. **This is also where you link people to medications**: on the pack's page, in the "Intakes" field.

| Field | Meaning | Default |
| --- | --- | --- |
| `name` | Display name, e.g. "Magnesium" | – |
| `strengths` | Strengths, e.g. "10 mg", "20 mg". Empty = a single pack without strength | – |

Per pack:

| Field | Meaning | Default |
| --- | --- | --- |
| `stock` | Stock in tablets. Changing it overwrites the counted stock | – |
| `intakes` | Who takes it when: time of day with person, e.g. "Morning · Anna". Without people, only the time | first time of day (without people) |
| `tag_id` | NFC tag on the pack; a scan records the next open intake of this pack. Dropdown with all HA tags | – |
| `tablets_per_intake` | Tablets per intake (collapsed section "Dosage and warning") | 1 |
| `low_threshold` | Low stock warning threshold (same section) | 20 |

An NFC tag belongs to exactly one person or pack; the form rejects duplicate assignments.

### Example: siblings sharing a pack

- People "Anna" (tag on her cup) and "Ben".
- Medication "Magnesium" with the strengths 10 mg and 20 mg:
  - Pack 10 mg: Morning · Anna, Morning · Ben, Noon · Anna.
  - Pack 20 mg: Morning · Ben.

Anna scans in the morning → only "Morning · Anna" on 10 mg; at noon she scans again → "Noon · Anna". Ben scans in the morning → 10 mg and 20 mg at once. Both count down the same 10 mg stock.

## Entities

### Per pack

| Platform | Entity | Purpose |
| --- | --- | --- |
| `number` | `…_stock` | Stock in tablets, directly editable (new pack → type in the remaining amount) |
| `sensor` | `…_days_left` | Days the stock still lasts (unit `d`) |
| `sensor` | `…_runs_out_on` | Date (`device_class: date`) until which the stock lasts |
| `sensor` | `…_intakes_today` | Number of intakes done today; attributes `taken`, `open`, `total` |
| `binary_sensor` | `…_complete_today` | On when all intakes of the pack are done today |
| `binary_sensor` | `…_low_stock` | `problem` when the stock is below the threshold |
| `button` | `…_take` | Record the next open intake (like the tag on the pack) |
| `switch` | `…_<time>`, e.g. `…_morning` | One switch per intake **without a person** (see below) |

### Per person

| Platform | Entity | Purpose |
| --- | --- | --- |
| `switch` | `<person>_<pack>_<time>`, e.g. `switch.anna_magnesium_10_mg_morning` | One switch per intake of the person, across all packs. This way the person's device page shows what is still open today |
| `sensor` | `…_open_intakes` | Open intakes today across all packs; attributes `next_slot`, `next`, `open`, `taken` |
| `button` | `…_take_now` | Like the person's tag: check off all intakes at the next open time of day |

**Intake switches:** on = taken (stock drops by "tablets per intake"), off = undone (stock goes back up). Attributes `medication`, `intake`, `slot`, `slot_id`, `person`, `ha_person`.

Entity IDs follow the device, e.g. `number.magnesium_10_mg_stock`. Pillbox never changes existing entity IDs: renaming times of day or people, or merging older entries, only changes the display name.

### Day and storage

- Day change at 04:00: an intake between midnight and 04:00 still counts for the previous day. If Home Assistant was off at that time, the change is caught up on startup.
- Stock and status are stored per pack in `.storage/pillbox.state.<entry_id>`.

## Services

| Service | Fields | Effect |
| --- | --- | --- |
| `pillbox.take` | `device_id`: pack or person devices | Pack: records the next open intake. Person: checks off all of their open intakes at the next open time of day (like their tag) |
| `pillbox.refill` | `device_id`: pack devices; `add` **or** `stock` | `add`: adds tablets (e.g. a new pack of 50); `stock`: sets the stock |

```yaml
action: pillbox.refill
data:
  device_id: <device id of "Magnesium 10 mg">
  add: 50
```

## Dashboard card

The integration ships a card and loads it automatically; no resource needs to be added. Add it via the card picker ("Pillbox") and set the options in the card editor; no YAML needed.

- **People:** all intakes of the day as chips (done ✓ / open), the next time of day highlighted, and a "Take now" button. Tapping a chip checks the intake off or undoes it.
- **Packs:** stock, days left and "lasts until"; packs with low stock are shown in red. Optionally with **−** / **+** buttons for the stock.

Options (all optional, all available in the editor):

| Option | Meaning | Default |
| --- | --- | --- |
| `title` | Card title | "Pillbox" |
| `hide_people` | Hide the people section | `false` |
| `people` | Only these people (device IDs), in this order | all, alphabetically |
| `hide_done_people` | Hide people with nothing left to take today; if everyone is done, a short note is shown | `false` |
| `hide_take_now` | Hide the "Take now" button | `false` |
| `hide_packs` | Hide the packs section | `false` |
| `packs` | Only these packs (device IDs), in this order | all, alphabetically |
| `low_stock_only` | Only packs with low stock | `false` |
| `packs_sort` | `name` or `days_left` (shortest first) | `name` |
| `hide_columns` | Any of `stock`, `days_left`, `runs_out` | none |
| `stock_buttons` | Show **−** / **+** next to each pack's stock to adjust it by hand (e.g. a dropped tablet, a partial refill). Only changes the stock, not the intakes; the stock column is always shown then | `false` |
| `stock_step` | Tablets per press on **−** / **+** | `1` |

```yaml
type: custom:pillbox-card
title: Medication
hide_done_people: true
packs_sort: days_left
hide_columns: [stock]
```

The older keys `show_people` / `show_packs` still work. The card's texts follow the user's language (English or German).

## Events

- `pillbox_low_stock` (`medication`, e.g. "Magnesium 10 mg"): when the stock drops below the warning threshold, whether by an intake or a manual change (stock entity, `pillbox.refill`, card buttons), for your own automations.
- Pillbox listens to `tag_scanned` and compares with the tags of people and packs.

## Reminder (blueprint)

[`blueprints/automation/pillbox/intake_reminder.yaml`](blueprints/automation/pillbox/intake_reminder.yaml), one automation per intake:

- Inputs: intake switch, time Mon–Fri and Sat–Sun, notify action (e.g. `notify.mobile_app_phone`), repeat interval in minutes (0 = once), last reminder (default 22:00), title, message and button text.
- Reminds from the given time while the switch is off and stops as soon as the intake is done.
- With `notify.mobile_app_*`: a "Taken" button in the notification checks off the intake directly; done reminders are removed from the phone.

Defaults: title = medication and strength, message "<intake>: not taken yet.", button "Taken". All three can be changed via the inputs, e.g. to another language; `{{ medication }}` and `{{ intake }}` can be used in title and message.

Import: Settings → Automations → Blueprints → "Import blueprint" with the file's GitHub URL, or copy the file to `/config/blueprints/automation/pillbox/`.

## Calculation

Per pack:

- Daily consumption = number of intakes × `tablets_per_intake`.
- Need today = open intakes × `tablets_per_intake`.
- Last covered day = today + (stock − need today) // daily consumption.
- Example: 53 tablets, 1 per day, still open today → lasts until today + 52 days; taken today (52 tablets) → same date.

## Roadmap

1. **v0.1** Packs per strength, people with NFC tags, shared packs, times of day, day reset, `low_stock` event, services, dashboard card, translations (de/en), reminder blueprint, tests and CI.
2. Next: prescription reminder (low stock → request a prescription), feedback from daily use.

## Development

```bash
uv venv .venv -p 3.13
uv pip install -p .venv -r requirements_test.txt
.venv/bin/python -m pytest -q      # core logic, integration, services, card and blueprint tests against HA
scripts/deploy_hass.sh -n          # dry run: copy to the HA instance (access in .env, template .env.example)
scripts/deploy_hass.sh -r          # copy and restart HA
```

Layout: `custom_components/pillbox/` (`logic.py` pure logic, `__init__.py` manager, setup and migration of older entries, `services.py`, `entity.py` common base, one file per platform, `config_flow.py`, `frontend/pillbox-card.js`, `translations/` de/en, `brand/` icon), `blueprints/`, `assets/` (logo sources), `scripts/`, `tests/`.

GitHub Actions run the tests, Home Assistant's `hassfest` and the repository validation (`hacs/action`, also used by the Marketplace) on every push.

Notes for contributors (including AI agents) are in [AGENTS.md](AGENTS.md).

## License

Pillbox is licensed under the [GNU General Public License v3.0](LICENSE).
