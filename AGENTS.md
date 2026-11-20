# AGENTS.md

Notes for AI agents (and humans) working on Pillbox.

## Project

Home Assistant integration (HACS) for medication stock and intakes. The domain model, entities and usage are described in the [README](README.md).

- `custom_components/pillbox/logic.py`: pure logic without HA dependencies (stock, coverage, intakes).
- `custom_components/pillbox/__init__.py`: `PillboxManager` (load, save, tag scans, day change) and `_async_migrate` (migration of older entries).
- `custom_components/pillbox/config_flow.py`: Pillbox entry with options (times of day) and the subentries "People" and "Medication" (with packs).
- Platforms: `number`, `sensor`, `binary_sensor`, `switch`, `button`; common base in `entity.py`.
- `custom_components/pillbox/services.py`: services `pillbox.take` and `pillbox.refill` (`services.yaml`, icons in `icons.json`).
- `custom_components/pillbox/frontend/pillbox-card.js`: dashboard card, plain JavaScript without a build step, served and registered by `__init__.py`. Bump `version` in `manifest.json` when it changes, so browsers load the new file.
- `blueprints/automation/pillbox/intake_reminder.yaml`: reminder blueprint.
- `tests/`: logic, integration, service, card (rendered with QuickJS) and blueprint tests against a real HA.
- `.github/workflows/validate.yml`: tests, `hassfest` and HACS validation on every push.

## Rules

1. **Keep the README up to date.** Every change to behavior, forms, entities, events, blueprint, installation or development is reflected in the README in the same commit. The AI notice at the top of the README stays.
2. **No personal data.** The repository is public. No real names of people, no real medications, devices, host names, IP addresses or e-mail addresses, neither in code, comments, tests, docs nor commit messages. Use neutral examples only: people "Anna" and "Ben", medications "Magnesium" and "Vitamin D", notify action `notify.mobile_app_phone`, host `homeassistant.local`. Check before every commit, e.g. with `git diff --cached`.
3. **Never break entity IDs.** `unique_id`s stay stable: packs and people keep their id, even when entries are merged or renamed. When restructuring subentries, move entities and devices (`_move_to_subentry`) instead of deleting and recreating them.
4. **Migrate older entries.** When the data format changes, add a migration to `_async_migrate` and cover it with a test that starts from the old format.
5. **Tests.** Cover every change with tests; everything must pass before committing:

   ```bash
   .venv/bin/python -m pytest -q
   uvx ruff check --select F,E9 custom_components tests
   ```

   Setting up the test environment: see the README, section "Development". Test dependencies are pinned in `requirements_test.txt`. The minimum HA version (`hacs.json`) is the oldest version the full test suite passes on.
6. **Translations.** Maintain new UI texts (including services and exceptions) in `strings.json`, `translations/en.json` and `translations/de.json`; the card has its own `STRINGS`. Home Assistant only loads translations on startup; restart HA Core to check them.
7. **Language.** Code, comments, docstrings, README and other docs in English. The UI is translated into English and German via the translation files.
8. **Commits.** Format `type(): description` in English (e.g. `feat(): …`, `fix(): …`, `docs(): …`, `test(): …`), no `Co-Authored-By` lines or other AI attribution in commits.

## Deployment

`scripts/deploy_hass.sh` copies the integration to an HA instance via rsync (access in `.env`, template `.env.example`; never commit `.env`). Deploying to the production instance is done by the maintainer.
