# AGENTS.md

Hinweise für KI-Agenten (und Menschen), die an Pillbox arbeiten.

## Projekt

Home-Assistant-Integration (HACS) für Medikamentenvorrat und Einnahmen. Fachliches Modell, Entitäten und Bedienung stehen in der [README](README.md).

- `custom_components/pillbox/logic.py`: reine Logik ohne HA-Abhängigkeit (Vorrat, Reichweite, Einnahmen).
- `custom_components/pillbox/__init__.py`: `PillboxManager` (Laden, Speichern, Tag-Scans, Tageswechsel) und `_async_migrate` (Übernahme älterer Einträge).
- `custom_components/pillbox/config_flow.py`: Pillbox-Eintrag mit Optionen (Einnahme-Zeiten) und Untereinheiten „Personen“ und „Medikament“ (mit Packungen).
- Plattformen: `number`, `sensor`, `binary_sensor`, `switch`, `button`; gemeinsame Basis in `entity.py`.
- `blueprints/automation/pillbox/intake_reminder.yaml`: Erinnerungs-Blueprint.
- `tests/`: Logik-, Integrations- und Blueprint-Tests gegen ein echtes HA.

## Regeln

1. **README aktuell halten.** Jede Änderung an Verhalten, Formularen, Entitäten, Events, Blueprint, Installation oder Entwicklung wird im selben Commit in der README nachgezogen. Der KI-Hinweis oben in der README bleibt stehen.
2. **Keine persönlichen Daten.** Das Repo ist öffentlich. Keine echten Namen von Personen, keine echten Medikamente, Geräte, Hostnamen, IP-Adressen oder E-Mail-Adressen, weder in Code, Kommentaren, Tests, Doku noch Commit-Messages. Beispiele nur neutral: Personen „Anna“ und „Ben“, Medikamente „Magnesium“ und „Vitamin D“, Benachrichtigung `notify.mobile_app_handy`, Host `homeassistant.local`. Vor jedem Commit prüfen, z. B. mit `git diff --cached`.
3. **Entitäts-IDs nie brechen.** `unique_id`s bleiben stabil: Packungen und Personen behalten ihre id, auch wenn Einträge zusammengeführt oder umbenannt werden. Beim Umbau von Untereinheiten Entitäten und Geräte umhängen (`_move_to_subentry`), nicht löschen und neu anlegen.
4. **Ältere Einträge übernehmen.** Ändert sich das Datenformat, eine Übernahme in `_async_migrate` ergänzen und mit einem Test absichern, der vom alten Format ausgeht.
5. **Tests.** Jede Änderung mit Tests absichern; vor dem Commit muss alles grün sein:
   ```bash
   .venv/bin/python -m pytest -q
   uvx ruff check --select F,E9 custom_components tests
   ```
   Einrichtung der Testumgebung: siehe README, Abschnitt „Entwicklung“.
6. **Übersetzungen.** Neue Texte in `strings.json`, `translations/en.json` und `translations/de.json` pflegen. Home Assistant lädt Übersetzungen nur beim Start; zum Prüfen HA Core neu starten.
7. **Sprache.** Code-Kommentare, Docstrings und Doku auf Deutsch; Bezeichner im Code auf Englisch.
8. **Commits.** Format `typ(): Beschreibung` auf Englisch (z. B. `feat(): …`, `fix(): …`, `docs(): …`, `test(): …`), keine `Co-Authored-By`-Zeilen oder sonstige KI-Attribution in Commits.

## Ausrollen

`scripts/deploy_hass.sh` kopiert die Integration per rsync auf eine HA-Instanz (Zugang in `.env`, Vorlage `.env.example`; `.env` nie committen). Ausrollen auf die produktive Instanz übernimmt der Maintainer.
