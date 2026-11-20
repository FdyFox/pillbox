<p align="center"><img src="assets/pillbox-logo.png" alt="Pillbox" width="600"></p>

# Pillbox

> [!NOTE]
> Diese Integration wurde mit Hilfe von KI (Claude von Anthropic) entwickelt: Code, Tests und Dokumentation sind KI-unterstützt entstanden und werden von mir geprüft und im eigenen Home Assistant genutzt. Pillbox ist eine Merkhilfe, kein Medizinprodukt.

Home-Assistant-Integration (HACS), die Einnahme und Vorrat von Medikamenten trackt.
Ein NFC-Tag-Scan genügt: Einnahme abhaken, Vorrat runterzählen, Reichweite berechnen. Erinnerungen kommen per Blueprint.

> Status: **v0.1.0-dev**. Läuft im eigenen Home Assistant und in den Integrationstests (HA 2026.2). Services fehlen noch.

## Ziele

- Medikamente in der Oberfläche anlegen, ohne Helper, Templates oder Namenskonventionen.
- Eine Packung je Wirkstärke, jede mit eigenem Vorrat und eigener Reichweite.
- Mehrere Personen können sich eine Packung teilen (z. B. Geschwister mit demselben Medikament), jede mit eigenem NFC-Tag.
- Einnahme-Zeiten des Tages („Morgens“, „Mittags“, …) frei benennbar.
- Erinnerungen flexibel per Blueprint, je Einnahme eigene Uhrzeit und Empfänger.
- Echte Entitäten, damit Dashboards und Automationen einfach darauf aufbauen.

## Abgrenzung

**Bei Pillbox steht die Packung im Mittelpunkt, nicht die Person.** Ein Medikament hat je Wirkstärke eine Packung mit Vorrat; Personen und Einnahme-Zeiten hängen an den Packungen. Daraus folgen Reichweite („reicht bis …“) und gemeinsame Packungen für mehrere Personen.

Pillbox ist eine **Tages-Checkliste mit Vorratszähler**, kein Terminplaner. Eine Einnahme wie „Morgens“ heißt „irgendwann morgens“: Pillbox fragt nur, ob sie heute erledigt ist und wie lange die Packung noch reicht. Es gibt kein „fällig“, kein „verpasst“ und keine Statistik zur Einnahmetreue. Uhrzeiten kommen nur ins Spiel, wenn man den optionalen Erinnerungs-Blueprint nutzt.

Das passt für Alltagsmedikamente, bei denen es ums Nicht-Vergessen und rechtzeitige Nachbestellen geht.

Wer feste Einnahmezeiten braucht (z. B. exakt alle 12 Stunden), mit Verschieben, Überspringen, Eskalation an Angehörige und Auswertung der Einnahmetreue, ist mit [pill-reminder](https://github.com/GuidoJeuken-6512/pill-reminder) besser bedient. Dort steht die Person im Mittelpunkt, mit ihrem Zeitplan; Vorrat und NFC-Tags deckt pill-reminder nicht ab.

## Installation

- **HACS:** HACS → Benutzerdefinierte Repositories → `https://github.com/FdyFox/pillbox`, Typ „Integration“. Danach „Pillbox“ installieren und Home Assistant neu starten.
- **Manuell:** `custom_components/pillbox/` nach `/config/custom_components/pillbox/` kopieren und Home Assistant neu starten.

Dann: Einstellungen → Geräte & Dienste → Integration hinzufügen → „Pillbox“.

Entwickelt und getestet mit Home Assistant 2026.2. Das eigene Icon in der Oberfläche zeigt Home Assistant ab 2026.3.

## Aufbau

In der Integrationsübersicht sieht das so aus:

```text
Pillbox                      ⚙ Einnahme-Zeiten
├ Personen                   ⚙ Personen bearbeiten
│  ├ Anna                    Gerät
│  └ Ben                     Gerät
└ Magnesium                  ⚙ Medikament bearbeiten
   ├ Magnesium 10 mg         Gerät (Packung)
   └ Magnesium 20 mg         Gerät (Packung)
```

- **Pillbox** (ein Eintrag). Das Zahnrad legt die **Einnahme-Zeiten** des Tages fest: bis zu 6, Standard „Morgens, Mittags, Abends, Nachts“. Umbenennen geht jederzeit; eine Zeit, die noch eine Packung nutzt, lässt sich nicht löschen.
- **Personen** (optional, eine Untereinheit für alle). Jede Person ist ein Gerät.
- **Medikament** (je Medikament eine Untereinheit). Jede Wirkstärke ist eine **Packung** und ein eigenes Gerät.

### Personen

„Personen hinzufügen“ fragt zuerst die Namen ab, danach folgt je Person eine Seite. Später bearbeitest du alle über das Zahnrad bei „Personen“: Namen hinzufügen oder entfernen, je Person Name, HA-Person und Tag ändern. Umbenennen behält die Einnahmen; wird eine Person entfernt, verschwinden ihre Einnahmen aus den Packungen.

| Feld | Bedeutung |
| --- | --- |
| `name` | z. B. „Anna“ |
| `ha_person` | optional, Verknüpfung mit einer Person in HA |
| `tag_id` | NFC-Tag der Person. Ein Scan hakt alle ihre offenen Einnahmen zur frühesten offenen Einnahme-Zeit ab, über alle Packungen |

### Medikament und Packungen

„Medikament hinzufügen“ fragt zuerst Name und Wirkstärken ab, danach folgt je Wirkstärke eine Seite für die Packung. Über das Zahnrad am Medikament läuft das Bearbeiten genauso; eine neue Wirkstärke fügt eine Packung hinzu, eine entfernte löscht sie. **Hier verknüpfst du auch Personen mit Medikamenten**: auf der Seite der Packung im Feld „Einnahmen“.

| Feld | Bedeutung | Standard |
| --- | --- | --- |
| `name` | Anzeigename, z. B. „Magnesium“ | – |
| `strengths` | Wirkstärken, z. B. „10 mg“, „20 mg“. Leer = eine Packung ohne Wirkstärke | – |

Je Packung:

| Feld | Bedeutung | Standard |
| --- | --- | --- |
| `stock` | Vorrat in Stück. Eine Änderung überschreibt den gezählten Vorrat | – |
| `intakes` | Wer nimmt wann: Einnahme-Zeit mit Person, z. B. „Morgens · Anna“. Ohne angelegte Personen nur die Zeit | erste Einnahme-Zeit (ohne Personen) |
| `tag_id` | NFC-Tag an der Packung; ein Scan erfasst die nächste offene Einnahme dieser Packung. Dropdown mit allen HA-Tags | – |
| `tablets_per_intake` | Tabletten pro Einnahme (eingeklappter Abschnitt „Dosierung und Warnung“) | 1 |
| `low_threshold` | Warnschwelle für niedrigen Vorrat (ebenda) | 20 |

Ein NFC-Tag gehört genau einer Person oder einer Packung; doppelte Zuordnungen lehnt das Formular ab.

### Beispiel: Geschwister mit gemeinsamer Packung

- Personen „Anna“ (Tag an ihrem Becher) und „Ben“.
- Medikament „Magnesium“ mit den Wirkstärken 10 mg und 20 mg:
  - Packung 10 mg: Morgens · Anna, Morgens · Ben, Mittags · Anna.
  - Packung 20 mg: Morgens · Ben.

Anna scannt morgens → nur „Morgens · Anna“ an 10 mg; mittags scannt sie erneut → „Mittags · Anna“. Ben scannt morgens → 10 mg und 20 mg auf einmal. Beide zählen vom selben 10-mg-Vorrat herunter.

## Entitäten

### Pro Packung

| Plattform | Entität | Zweck |
| --- | --- | --- |
| `number` | `…_stock` | Vorrat in Stk, direkt editierbar (neue Packung → Restmenge eintippen) |
| `sensor` | `…_days_left` | Tage, die der Vorrat noch trägt (Einheit `d`) |
| `sensor` | `…_runs_out_on` | Datum (`device_class: date`), bis wann der Vorrat reicht |
| `sensor` | `…_intakes_today` | Anzahl erledigter Einnahmen heute; Attribute `taken`, `open`, `total` |
| `binary_sensor` | `…_complete_today` | An, wenn alle Einnahmen der Packung heute erledigt sind |
| `binary_sensor` | `…_low_stock` | `problem`, wenn der Vorrat unter der Schwelle liegt |
| `button` | `…_take` | Nächste offene Einnahme erfassen (wie der Tag an der Packung) |
| `switch` | `…_<zeit>`, z. B. `…_morgens` | Ein Schalter je Einnahme **ohne Person** (siehe unten) |

### Pro Person

| Plattform | Entität | Zweck |
| --- | --- | --- |
| `switch` | `<person>_<packung>_<zeit>`, z. B. `switch.anna_magnesium_10_mg_morgens` | Ein Schalter je Einnahme der Person, über alle Packungen. So zeigt die Geräteseite der Person, was heute noch offen ist |
| `sensor` | `…_open_intakes` | Offene Einnahmen heute über alle Packungen; Attribute `next_slot`, `next`, `open`, `taken` |
| `button` | `…_take_now` | Wie der Tag der Person: alle Einnahmen zur nächsten offenen Zeit abhaken |

**Einnahme-Schalter:** An = genommen (Vorrat sinkt um „Tabletten pro Einnahme“), Aus = zurückgenommen (Vorrat steigt wieder). Attribute `medication`, `intake`, `slot`, `slot_id`, `person`, `ha_person`.

Entitäts-IDs folgen dem Gerät, z. B. `number.magnesium_10_mg_stock`. Bestehende Entitäts-IDs ändert Pillbox nie: Beim Umbenennen von Einnahme-Zeiten, Personen oder beim Zusammenführen älterer Einträge ändert sich nur der Anzeigename.

### Tag und Speicher

- Tageswechsel um 04:00: Eine Einnahme zwischen Mitternacht und 04:00 zählt noch zum Vortag. War Home Assistant zu dem Zeitpunkt aus, wird der Wechsel beim Start nachgeholt.
- Vorrat und Status liegen in `.storage/pillbox.state.<entry_id>`, je Packung.

## Events

- `pillbox_low_stock` (`medication`, z. B. „Magnesium 10 mg“): beim Unterschreiten der Warnschwelle, für eigene Automationen.
- Pillbox hört auf `tag_scanned` und vergleicht mit den Tags der Personen und Packungen.

## Erinnerung (Blueprint)

[`blueprints/automation/pillbox/intake_reminder.yaml`](blueprints/automation/pillbox/intake_reminder.yaml), eine Automation pro Einnahme:

- Eingaben: Einnahme-Schalter, Uhrzeit Mo–Fr und Sa–So, Benachrichtigungs-Action (z. B. `notify.mobile_app_handy`), Wiederholung in Minuten (0 = einmal), letzte Erinnerung (Standard 22:00), Titel und Text.
- Erinnert ab der Uhrzeit, solange der Schalter aus ist, und hört auf, sobald die Einnahme erledigt ist.
- Bei `notify.mobile_app_*`: Knopf „Genommen“ in der Benachrichtigung hakt die Einnahme direkt ab; erledigte Erinnerungen werden vom Handy entfernt.

Import: Einstellungen → Automationen → Blueprints → „Blueprint importieren“ mit der GitHub-URL der Datei, oder die Datei nach `/config/blueprints/automation/pillbox/` kopieren.

## Berechnung

Je Packung:

- Tagesverbrauch = Anzahl Einnahmen × `tablets_per_intake`.
- Heutiger Bedarf = offene Einnahmen × `tablets_per_intake`.
- Letzter gedeckter Tag = heute + (Vorrat − Bedarf heute) // Tagesverbrauch.
- Beispiel: 53 Stk, 1 pro Tag, heute noch offen → reicht bis heute + 52 Tage; heute genommen (52 Stk) → gleiches Datum.

## Roadmap

1. **v0.1** Packungen je Wirkstärke, Personen mit NFC-Tag, gemeinsame Packungen, Einnahme-Zeiten, Tagesreset, `low_stock`-Event, Übersetzungen (de/en), Erinnerungs-Blueprint, Tests.
2. **v0.2** Services `pillbox.take` / `pillbox.refill`.
3. **v0.3** Mitgelieferte Lovelace-Karte bzw. Übersichtsseite (pro Person: was ist offen; pro Packung: Vorrat und Reichweite).
4. Später: Rezept-Erinnerung (Vorrat niedrig → Rezept anfordern).

## Entwicklung

```bash
uv venv .venv -p 3.13
uv pip install -p .venv pytest-homeassistant-custom-component
.venv/bin/python -m pytest -q      # Kernlogik, Integrationstests und Blueprint gegen HA
scripts/deploy_hass.sh -n          # Probelauf: auf die HA-Instanz kopieren (Zugang in .env, Vorlage .env.example)
scripts/deploy_hass.sh -r          # kopieren und HA neu starten
```

Struktur: `custom_components/pillbox/` (`logic.py` reine Logik, `__init__.py` Manager, Setup und Übernahme alter Einträge, `entity.py` gemeinsame Basis, je Plattform eine Datei, `config_flow.py`, `translations/` de/en, `brand/` Icon), `blueprints/`, `assets/` (Logo-Quellen), `scripts/`, `tests/`.

Hinweise für Beiträge (auch durch KI-Agenten) stehen in [AGENTS.md](AGENTS.md).
