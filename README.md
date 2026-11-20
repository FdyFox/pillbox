<p align="center"><img src="assets/pillbox-logo.png" alt="Pillbox" width="600"></p>

# Pillbox

Home-Assistant-Integration (HACS), die Einnahme und Vorrat von Medikamenten trackt.
Ein NFC-Tag-Scan genügt: Einnahme abhaken, Vorrat runterzählen, Reichweite berechnen. Erinnerungen kommen per Blueprint.

> Status: **v0.1.0-dev**. Config-Flow, Entitäten, Tag-Scan, Tagesreset und der Erinnerungs-Blueprint laufen in den Integrationstests (HA 2026.2), sind aber noch nicht lange auf einer echten Instanz im Einsatz. Services fehlen noch.

## Ziele

- Ein neues Medikament in der Oberfläche anlegen, ohne Helper, Templates oder Namenskonventionen.
- Mehrere Personen können sich eine Packung teilen (z. B. Geschwister mit demselben Medikament), jede mit eigenem NFC-Tag.
- Einnahme-Zeiten des Tages („Morgens“, „Mittags“, …) frei benennbar.
- Erinnerungen flexibel per Blueprint, je Einnahme eigene Uhrzeit und Empfänger.
- Echte Entitäten und Services, damit Dashboards und Automationen einfach darauf aufbauen.

## Abgrenzung

**Bei Pillbox steht die Packung im Mittelpunkt, nicht die Person.** Ein Medikament ist eine Packung mit Vorrat; Personen und Einnahme-Zeiten hängen daran. Daraus folgen Reichweite („reicht bis …“) und gemeinsame Packungen für mehrere Personen.

Pillbox ist eine **Tages-Checkliste mit Vorratszähler**, kein Terminplaner. Eine Einnahme wie „Morgens“ heißt „irgendwann morgens“: Pillbox fragt nur, ob sie heute erledigt ist und wie lange die Packung noch reicht. Es gibt kein „fällig“, kein „verpasst“ und keine Statistik zur Einnahmetreue. Uhrzeiten kommen nur ins Spiel, wenn man den optionalen Erinnerungs-Blueprint nutzt.

Das passt für Alltagsmedikamente, bei denen es ums Nicht-Vergessen und rechtzeitige Nachbestellen geht.

Wer feste Einnahmezeiten braucht (z. B. exakt alle 12 Stunden), mit Verschieben, Überspringen, Eskalation an Angehörige und Auswertung der Einnahmetreue, ist mit [pill-reminder](https://github.com/GuidoJeuken-6512/pill-reminder) besser bedient. Dort steht die Person im Mittelpunkt, mit ihrem Zeitplan; Vorrat und NFC-Tags deckt pill-reminder nicht ab.

## Aufbau

- Ein Config-Entry „Pillbox“ (Single Instance). Seine **Optionen** legen die Einnahme-Zeiten des Tages fest: bis zu 6, Standard „Morgens, Mittags, Abends, Nachts“. Umbenennen geht jederzeit; eine Zeit, die noch ein Medikament nutzt, lässt sich nicht löschen.
- Pro **Person** eine Untereinheit (Typ `person`) und ein Gerät. Optional.
- Pro **Medikament** eine Untereinheit (Typ `medication`), darunter **je Wirkstärke eine Packung** mit eigenem Gerät und Vorrat. In der Integrationsübersicht steht so „Magnesium“ einmal, darunter „Magnesium 10 mg“, „Magnesium 20 mg“ usw.

### Einstellungen pro Person

| Feld | Bedeutung |
| --- | --- |
| `name` | z. B. „Anna“ |
| `ha_person` | optional, Verknüpfung mit einer Person in HA |
| `tag_id` | NFC-Tag der Person. Ein Scan hakt alle ihre offenen Einnahmen zur frühesten offenen Einnahme-Zeit ab, über alle Medikamente |

### Einstellungen pro Medikament

„Medikament hinzufügen“ fragt zuerst Name und Wirkstärken ab, danach folgt je Wirkstärke eine Seite für die Packung. „Bearbeiten“ läuft genauso; eine neue Wirkstärke fügt eine Packung hinzu, eine entfernte löscht sie.

| Feld | Bedeutung | Standard |
| --- | --- | --- |
| `name` | Anzeigename, z. B. „Magnesium“ | – |
| `strengths` | Wirkstärken, z. B. „10 mg“, „20 mg“. Leer = eine Packung ohne Wirkstärke | – |

### Einstellungen pro Packung

| Feld | Bedeutung | Standard |
| --- | --- | --- |
| `stock` | Startvorrat in Stück | – |
| `intakes` | Wer nimmt wann: Einnahme-Zeit mit Person, z. B. „Morgens · Anna“, „Morgens · Ben“. Ohne angelegte Personen nur die Zeit | erste Einnahme-Zeit |
| `tag_id` | NFC-Tag an der Packung; ein Scan erfasst die nächste offene Einnahme. Dropdown mit allen HA-Tags | – |
| `tablets_per_intake` | Tabletten pro Einnahme (eingeklappter Abschnitt „Dosierung und Warnung“) | 1 |
| `low_threshold` | Warnschwelle für niedrigen Vorrat (ebenda) | 20 |

Ein NFC-Tag gehört genau einer Person oder einem Medikament; doppelte Zuordnungen lehnt das Formular ab.

### Beispiel: Geschwister mit gemeinsamer Packung

- Personen „Anna“ (Tag am Becher von Anna) und „Ben“.
- Medikament „Magnesium“ mit den Wirkstärken 10 mg und 20 mg:
  - Packung 10 mg: Morgens · Anna, Morgens · Ben, Mittags · Anna.
  - Packung 20 mg: Morgens · Ben.

Anna scannt morgens → nur „Morgens · Anna“ an 10 mg; mittags scannt sie erneut → „Mittags · Anna“. Ben scannt morgens → 10 mg und 20 mg auf einmal. Beide zählen vom selben 10-mg-Vorrat herunter.

## Entitätsmodell (pro Packung)

| Plattform | Entität | Zweck |
| --- | --- | --- |
| `number` | `…_stock` | Vorrat in Stk, direkt editierbar (neue Packung → Restmenge eintippen) |
| `switch` | `…_<person>_<zeit>`, z. B. `…_anna_morgens` | Ein Schalter je Einnahme. An = genommen (Vorrat sinkt), Aus = zurückgenommen (Vorrat steigt wieder). Attribute `slot`, `person`, `ha_person` |
| `sensor` | `…_intakes_today` | Anzahl erledigter Einnahmen heute; Attribute `taken`, `open`, `total` |
| `binary_sensor` | `…_complete_today` | An, wenn alle Einnahmen des Tages erledigt sind |
| `sensor` | `…_days_left` | Tage, die der Vorrat noch trägt (Einheit `d`) |
| `sensor` | `…_runs_out_on` | Datum (`device_class: date`), bis wann der Vorrat reicht |
| `binary_sensor` | `…_low_stock` | `problem`, wenn Vorrat unter Schwelle |
| `button` | `…_take` | Nächste offene Einnahme erfassen (wie ein Tag-Scan) |

Entitäts-IDs folgen Name und Wirkstärke, z. B. `switch.magnesium_10_mg_anna_morgens`. Wird eine Einnahme-Zeit oder Person umbenannt, bleibt die Entität erhalten (nur der Anzeigename ändert sich); fällt eine Einnahme weg oder wird die Person gelöscht, verschwindet der Schalter.

### Pro Person

| Plattform | Entität | Zweck |
| --- | --- | --- |
| `sensor` | `…_open_intakes` | Offene Einnahmen heute über alle Medikamente; Attribute `next_slot`, `next`, `open`, `taken` |
| `button` | `…_take_now` | Wie der Tag der Person: alle Einnahmen zur nächsten offenen Zeit abhaken |

Persistenz: `Store` (`.storage/pillbox.state.<entry_id>`) mit dem aktuellen Tag und `stock`/`taken` (Status je Einnahme) je Untereinheit. Tagesreset um 04:00; war HA zu dem Zeitpunkt aus, wird der Reset beim Start nachgeholt. Eine Einnahme zwischen Mitternacht und 04:00 zählt noch zum Vortag.

Wird der Vorrat über „Medikament bearbeiten“ geändert, überschreibt der neue Wert den gespeicherten Stand. Ohne Änderung bleibt der gezählte Vorrat erhalten.

## Services und Events

- `pillbox.take` (`entity_id` oder `medication`): Einnahme erfassen.
- `pillbox.refill` (`entity_id`, `stock`): Restmenge nach neuer Packung setzen.
- Event `pillbox_low_stock` (`medication`): beim Unterschreiten der Schwelle, für eigene Automationen.
- Hört auf das HA-Event `tag_scanned` und vergleicht mit den Tags der Personen und Medikamente.

## Erinnerung (Blueprint)

[`blueprints/automation/pillbox/intake_reminder.yaml`](blueprints/automation/pillbox/intake_reminder.yaml), eine Automation pro Einnahme:

- Eingaben: Einnahme-Schalter, Uhrzeit Mo–Fr und Sa–So, Benachrichtigungs-Action (z. B. `notify.mobile_app_handy`), Wiederholung in Minuten (0 = einmal), letzte Erinnerung (Standard 22:00), Titel und Text.
- Erinnert ab der Uhrzeit, solange der Schalter aus ist, und hört auf, sobald die Einnahme erledigt ist.
- Bei `notify.mobile_app_*`: Knopf „Genommen“ in der Benachrichtigung hakt die Einnahme direkt ab; erledigte Erinnerungen werden vom Handy entfernt.

Import: Einstellungen → Automationen → Blueprints → „Blueprint importieren“ mit der GitHub-URL der Datei, oder die Datei nach `/config/blueprints/automation/pillbox/` kopieren.

## Berechnung

- Tagesverbrauch = Anzahl Einnahmen × `tablets_per_intake`.
- Heutiger Bedarf = offene Einnahmen × `tablets_per_intake`.
- Letzter gedeckter Tag = heute + (Vorrat − Bedarf heute) // Tagesverbrauch; ist heute schon alles genommen, ist der Bedarf heute 0.
- Beispiel: 53 Stk, 1 pro Tag, heute noch offen → reicht bis heute + 52 Tage; heute genommen (52 Stk) → gleiches Datum.

## Roadmap

1. **v0.1** Config-Flow, Store, Tag-Scan, Entitäten, benannte Einnahmen, Tagesreset, `low_stock`-Event, Übersetzungen (de/en), Erinnerungs-Blueprint, Tests.
2. **v0.2** Services `pillbox.take` / `pillbox.refill`.
3. **v0.3** Mitgelieferte Lovelace-Karte.
4. Später: mehrere Personen/Gruppen, Rezept-Erinnerung (Vorrat niedrig → Rezept anfordern).

## Entwicklung

```bash
uv venv .venv -p 3.13
uv pip install -p .venv pytest-homeassistant-custom-component
.venv/bin/python -m pytest -q      # Kernlogik, Integrationstests und Blueprint gegen HA
scripts/deploy_hass.sh -n          # Probelauf: auf die HA-Instanz kopieren (Zugang in .env, Vorlage .env.example)
scripts/deploy_hass.sh -r          # kopieren und HA neu starten
```

Struktur: `custom_components/pillbox/` (`logic.py` rein, `__init__.py` Manager und Setup, `entity.py` gemeinsame Basis, je Plattform eine Datei, `config_flow.py`, `translations/` de/en, `brand/` Icon ab HA 2026.3), `blueprints/`, `assets/` (Logo-Quellen), `tests/`.
