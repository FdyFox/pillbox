<p align="center"><img src="assets/pillbox-logo.png" alt="Pillbox" width="600"></p>

# Pillbox

> [!NOTE]
> This integration was developed with the help of AI (Claude by Anthropic): code, tests and documentation were written with AI assistance and are reviewed by me and used in my own Home Assistant. Pillbox is a memory aid, not a medical device.

Home Assistant integration (Marketplace / HACS) that tracks medication intakes and stock.
One NFC tag scan is enough: check off the intake, count down the stock, calculate how long it lasts. Reminders come via blueprints.

> Status: **v0.2.0**. Runs in my own Home Assistant; tests run against HA 2025.7 to 2026.2.

[![Validate](https://github.com/FdyFox/pillbox/actions/workflows/validate.yml/badge.svg)](https://github.com/FdyFox/pillbox/actions/workflows/validate.yml)

The user interface is available in English and German.

## Goals

- Add medications in the UI, without helpers, templates or naming conventions.
- One pack per strength, each with its own stock and coverage.
- Split tablets (½, ¼, 1½ …) and a different dose per intake, e.g. Anna ½ and Ben 1 from the same pack.
- Intakes taken only as needed, without them counting as open or towards the coverage.
- Several people can share a pack (e.g. siblings on the same medication), each with their own NFC tag.
- Freely named times of day ("Morning", "Noon", ...).
- Flexible reminders via blueprints: per intake or per person ("still to take: …"), with their own time and recipient, optionally as a phone alarm.
- Real entities and services, so dashboards and automations can easily build on them.
- A ready-made dashboard card: who still has to take what today, and how long each pack lasts.

## Scope

**In Pillbox, the pack is the center, not the person.** A medication has one pack with stock per strength; people and times of day are attached to the packs. This gives you coverage ("lasts until ...") and shared packs for several people.

Pillbox is a **daily checklist with a stock counter**, not a scheduler. An intake like "Morning" means "sometime in the morning": Pillbox only asks whether it has been done today and how long the pack will last. There is no "due", no "missed" and no adherence statistics. Clock times only come into play if you use the optional reminder blueprints.

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

"Add medication" shows name, strengths and the first pack (stock, intakes, tag, dosage) on one page, so a medication with a single strength is done in one step. Each further strength gets its own page. Editing via the gear icon at the medication works the same way; a new strength adds a pack, a removed one deletes it. **This is also where you link people to medications**: in the "Intakes" field (for example "Morning · Anna").

| Field | Meaning | Default |
| --- | --- | --- |
| `name` | Display name, e.g. "Magnesium" | – |
| `strengths` | Strengths, e.g. "10 mg", "20 mg". Empty = a single pack without strength | – |

Per pack:

| Field | Meaning | Default |
| --- | --- | --- |
| `stock` | Stock in tablets, halves and quarters allowed (e.g. 24.5). Changing it overwrites the counted stock | – |
| `intakes` | Regular intakes, who takes it when: time of day with person, e.g. "Morning · Anna". Without people, only the time | first time of day (without people) |
| `as_needed` | Intakes taken only when needed, e.g. "Night · Anna" (see below). Selecting them here is enough; at least one intake is required in `intakes` or `as_needed` | none |
| `tag_id` | NFC tag on the pack; a scan records the next open intake of this pack. Dropdown with all HA tags | – |
| `tablets_per_intake` | Dose per intake in tablets, in steps of 0.25 (collapsed section "Dosage and warning") | 1 |
| `individual_doses` | "Different dose per intake" (same section): next, one page with a dose field per intake, prefilled with `tablets_per_intake`. Only doses that differ are stored (`doses`); unchecking it removes them again | off |
| `low_threshold` | Low stock warning threshold (same section) | 20 |

An NFC tag belongs to exactly one person or pack; the form rejects duplicate assignments.

**Split tablets and doses:** every intake takes its dose off the stock, e.g. 0.5 for half a tablet; the stock is then counted in halves or quarters as well (e.g. 19.5). With "Different dose per intake", people sharing a pack can take different amounts.

**As needed:** an intake marked "as needed" keeps its time of day and its switch and can be checked off as usual (stock goes down by its dose). It is never open or due, though: it does not count for "open intakes", "complete today" or the coverage, the person's tag and "Take now" skip it, and the pack's tag only records it if the pack has nothing but "as needed" intakes. A pack with only "as needed" intakes has no days left (`unknown`); the low stock warning still works.

### Example: siblings sharing a pack

- People "Anna" (tag on her cup) and "Ben".
- Medication "Magnesium" with the strengths 10 mg and 20 mg:
  - Pack 10 mg: Morning · Anna, Morning · Ben, Noon · Anna.
  - Pack 20 mg: Morning · Ben.

Anna scans in the morning → only "Morning · Anna" on 10 mg; at noon she scans again → "Noon · Anna". Ben scans in the morning → 10 mg and 20 mg at once. Both count down the same 10 mg stock.

### Example: half a tablet and as needed

- Medication "Vitamin D", one pack with 30 tablets: Morning · Anna, Morning · Ben, Evening · Ben.
- "As needed": Evening · Ben. "Different dose per intake": Morning · Anna 0.5, the others 1.

Daily consumption is 1.5 tablets (Anna ½, Ben 1), so the pack lasts 20 days. In the evening Ben's intake shows up as "as needed"; if he takes it, the stock drops by one more tablet and the coverage is recalculated.

## Entities

### Per pack

| Platform | Entity | Purpose |
| --- | --- | --- |
| `number` | `…_stock` | Stock in tablets (steps of 0.25), directly editable (new pack → type in the remaining amount) |
| `sensor` | `…_days_left` | Days the stock still lasts (unit `d`); `unknown` if the pack is only taken as needed |
| `sensor` | `…_runs_out_on` | Date (`device_class: date`) until which the stock lasts |
| `sensor` | `…_intakes_today` | Number of intakes done today (including "as needed"); attributes `taken`, `open`, `total` (regular intakes per day), `as_needed` |
| `binary_sensor` | `…_complete_today` | On when all regular intakes of the pack are done today |
| `binary_sensor` | `…_low_stock` | `problem` when the stock is below the threshold |
| `button` | `…_take` | Record the next open intake (like the tag on the pack) |
| `switch` | `…_<time>`, e.g. `…_morning` | One switch per intake **without a person** (see below) |

### Per person

| Platform | Entity | Purpose |
| --- | --- | --- |
| `switch` | `<person>_<pack>_<time>`, e.g. `switch.anna_magnesium_10_mg_morning` | One switch per intake of the person, across all packs. This way the person's device page shows what is still open today |
| `sensor` | `…_open_intakes` | Open intakes today across all packs ("as needed" ones never count); attributes `next_slot`, `next`, `open`, `taken`, `as_needed` |
| `button` | `…_take_now` | Like the person's tag: check off all intakes at the next open time of day |

**Intake switches:** on = taken (stock drops by the intake's dose), off = undone (stock goes back up). Attributes `medication`, `intake`, `slot`, `slot_id`, `person`, `ha_person`, `dose` (tablets), `as_needed`, `taken_amount` (tablets taken today, 0 = open).

Entity IDs follow the device, e.g. `number.magnesium_10_mg_stock`. Pillbox never changes existing entity IDs: renaming times of day or people, or merging older entries, only changes the display name.

### Day and storage

- Day change at 04:00: an intake between midnight and 04:00 still counts for the previous day. If Home Assistant was off at that time, the change is caught up on startup.
- Stock and status are stored per pack in `.storage/pillbox.state.<entry_id>`.

## Services

| Service | Fields | Effect |
| --- | --- | --- |
| `pillbox.take` | `device_id`: pack or person devices | Pack: records the next open intake. Person: checks off all of their open intakes at the next open time of day (like their tag) |
| `pillbox.take_intake` | target: intake switches; `amount` (optional) | Checks off the intake with `amount` tablets instead of its dose, e.g. 0.75 instead of 1. Only for today: the stock drops by the amount, undo (switch off) puts exactly it back, the coverage keeps using the dose. On an intake already taken, it corrects the amount |
| `pillbox.refill` | `device_id`: pack devices; `add` **or** `stock` | `add`: adds tablets (e.g. a new pack of 50); `stock`: sets the stock. Both in steps of 0.25 |

```yaml
action: pillbox.refill
data:
  device_id: <device id of "Magnesium 10 mg">
  add: 50
```

## Dashboard card

The integration ships two cards (this one and the [intake card](#intake-card)) and loads them automatically; no resource needs to be added. Add them via the card picker ("Pillbox", "Pillbox intake") and set the options in the card editor; no YAML needed.

- **People:** all intakes of the day as chips (done ✓ / open), the next time of day highlighted, and a "Take now" button. Tapping a chip checks the intake off or undoes it. A dose other than 1 is shown in the chip (e.g. "½×"); "as needed" intakes have a dashed border and are never highlighted as next.
- **Packs:** stock (with fractions, e.g. "19½"), days left and "lasts until"; packs with low stock are shown in red. Optionally with **−** / **+** buttons for the stock. Tapping a pack's name opens a dialog to type in its stock (e.g. after a new pack).

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
| `stock_step` | Tablets per press on **−** / **+**, in steps of 0.25 | `1` |

```yaml
type: custom:pillbox-card
title: Medication
hide_done_people: true
packs_sort: days_left
hide_columns: [stock]
```

The older keys `show_people` / `show_packs` still work. The card's texts follow the user's language (English or German).

## Intake card

A second card, "Pillbox intake" (`custom:pillbox-intake-card`), checks off an intake with the amount actually taken. One row per intake of today: medication, below it person, time of day and dose; with several people, one section per person, and one **dose button** per amount. A tap checks the intake off with that amount; on an intake already taken, another button corrects the amount (the current one is highlighted). Taken intakes show the amount (e.g. "✓ ¾ taken") and an "Undo" button. The card calls `pillbox.take_intake`.

| Option | Meaning | Default |
| --- | --- | --- |
| `title` | Card title | "Take intake" |
| `buttons` | Dose buttons in tablets, e.g. `[0.5, 0.75, 1]`. In the editor pick from ¼ to 2 or type in your own values | `[1]` |
| `people` | Only intakes of these people (device IDs) | all |
| `packs` | Only intakes of these packs (device IDs) | all |
| `hide_done` | Hide intakes already taken today | `false` |
| `hide_as_needed` | Hide "as needed" intakes | `false` |

```yaml
type: custom:pillbox-intake-card
buttons: [0.5, 0.75, 1]
people: [<device id of "Anna">]
hide_done: true
```

## Events

- `pillbox_low_stock` (`medication`, e.g. "Magnesium 10 mg"): when the stock drops below the warning threshold, whether by an intake or a manual change (stock entity, `pillbox.refill`, card buttons), for your own automations.
- Pillbox listens to `tag_scanned` and compares with the tags of people and packs.

## Reminders (blueprints)

Pillbox ships two blueprints and copies them to `/config/blueprints/automation/pillbox/` on every start of Home Assistant and whenever the times of day change (only if they are missing or have changed, so local edits to those files are overwritten by updates). The times of day are filled in as dropdown options, since a blueprint cannot read them itself.

Phones are picked from a dropdown of the Companion app devices; Pillbox sends to `notify.mobile_app_<device name>`, the notify action the app registered. If a phone was renamed in the app after setting it up, use the "other notify action" field instead. Nothing to import: Settings → Automations → Blueprints → pick one → "Create automation".

### Per intake: "Pillbox – intake reminder"

[`intake_reminder.yaml`](custom_components/pillbox/blueprints/intake_reminder.yaml), one automation per intake:

- Inputs: intake switch, phones (dropdown with the Companion apps, several possible), other notify action (optional, e.g. `notify.family`), time Mon–Fri and Sat–Sun, repeat interval in minutes (0 = once), last reminder (default 22:00), title, message, button texts, snooze time and alarm mode.
- Reminds from the given time while the switch is off and stops as soon as the intake is done. Not meant for "as needed" intakes.
- On phones: a "Taken" button in the notification checks off the intake directly; done reminders are removed from the phone.

Defaults: title = medication and strength, message "<intake>: not taken yet.", button "Taken". All three can be changed via the inputs, e.g. to another language; `{{ medication }}` and `{{ intake }}` can be used in title and message.

### Per person: "Pillbox – person reminder"

[`person_reminder.yaml`](custom_components/pillbox/blueprints/person_reminder.yaml), one automation per person and time of day. One notification with everything the person still has to take at that time of day, across all packs, one per line: "Still to take:", then "• Magnesium 10 mg", "• Vitamin D (½)".

- Inputs: person (device), time of day (dropdown with the times of day from the Pillbox options; empty = the person's next time of day with something open), intakes (optional, see below), phones, other notify action, time Mon–Fri and Sat–Sun, repeat interval, last reminder, title, message, button texts, snooze time and alarm mode.
- Without chosen intakes, it is about all of the person's intakes at that time of day, without "as needed" ones. With chosen intakes (dropdown with all intake switches, e.g. "Anna Vitamin D Morning"), it is about exactly those, "as needed" ones included.
- Each repeated reminder only lists what is still open; it stops when everything is done. If nothing is open, there is no reminder.
- On phones: the "Taken" button checks off all intakes listed; done reminders are removed from the phone.

Defaults: title "{{ person }}: {{ slot }}", message "Still to take:" plus `{{ medications }}` on the next line, button "Taken". The message field takes several lines. In title and message you can use `{{ person }}`, `{{ slot }}`, `{{ medications }}` (one per line, with "• ") and `{{ medications_inline }}` (comma-separated, e.g. "{{ person }}, du musst noch {{ medications_inline }} nehmen").

### Buttons: taken, skip, later

Phone notifications of both blueprints have up to three buttons, in this order ("Skip" in the middle, so it is not hit by mistake at the edge):

- **Taken** (`button_title`): checks off the intakes of the reminder; the notification is removed.
- **Skip** (`dismiss_title`): no more reminders today; the notification is removed from all phones, the intakes stay open. Empty text = no button.
- **Later** (`snooze_title`, `snooze_minutes`, default 15): the next reminder comes after the snooze time, also if repetition is off. 0 minutes = no button.

### Alarm mode

Both blueprints have an "Alarm mode" switch for phone notifications:

- **Android:** sent via the `alarm_stream` channel (alarm sound, also with Do Not Disturb), with `priority: high` and `ttl: 0`.
- **iOS:** sent as a critical alert with sound (also when muted or in a Focus). iOS asks once whether the Companion app may send critical alerts.

## Calculation

Per pack:

- Daily consumption = sum of the doses of all regular intakes ("as needed" ones are left out).
- Need today = sum of the doses of the regular intakes still open today.
- Last covered day = today + ⌊(stock − need today) / daily consumption⌋.
- Example: 53 tablets, 1 per day, still open today → lasts until today + 52 days; taken today (52 tablets) → same date.
- Example: 10 tablets, ½ per day, still open today → lasts until today + 19 days (20 days including today).
- Daily consumption 0 (only "as needed") → no days left and no date.

## Roadmap

1. **v0.1** Packs per strength, people with NFC tags, shared packs, times of day, day reset, `low_stock` event, services, dashboard card, translations (de/en), reminder blueprint, tests and CI.
2. **v0.2** Split tablets (doses in steps of 0.25), a dose per intake, intakes taken as needed, intake card with the amount actually taken, person reminder blueprint, alarm mode, blueprints installed automatically.
3. Next: prescription reminder (low stock → request a prescription), feedback from daily use.

## Development

```bash
uv venv .venv -p 3.13
uv pip install -p .venv -r requirements_test.txt
.venv/bin/python -m pytest -q      # core logic, integration, services, card and blueprint tests against HA
scripts/deploy_hass.sh -n          # dry run: copy to the HA instance (access in .env, template .env.example)
scripts/deploy_hass.sh -r          # copy and restart HA
```

Layout: `custom_components/pillbox/` (`logic.py` pure logic, `__init__.py` manager, setup and migration of older entries, `services.py`, `entity.py` common base, one file per platform, `config_flow.py`, `frontend/pillbox-card.js`, `blueprints/` reminder blueprint, `translations/` de/en, `brand/` icon), `assets/` (logo sources), `scripts/`, `tests/`.

GitHub Actions run the tests, Home Assistant's `hassfest` and the repository validation (`hacs/action`, also used by the Marketplace) on every push.

Notes for contributors (including AI agents) are in [AGENTS.md](AGENTS.md).

## License

Pillbox is licensed under the [GNU General Public License v3.0](LICENSE).
