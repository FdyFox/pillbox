#!/usr/bin/env bash
# Kopiert custom_components/pillbox per rsync auf die Home-Assistant-Instanz (SSH-Add-on).
#
# Aufruf:  scripts/deploy_hass.sh [-n] [-r]
#   -n  Probelauf: nur anzeigen, was kopiert/gelöscht würde
#   -r  danach Konfiguration prüfen und HA Core neu starten
#
# Anpassbar per Umgebungsvariable oder .env im Repo (Vorlage: .env.example):
#   HASS_HOST, HASS_USER, HASS_PORT, HASS_SSH_KEY (Pfad zum privaten Schlüssel),
#   optional HASS_PASSWORD (braucht sshpass, nur ohne Schlüssel)
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -f "$REPO_DIR/.env" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "$REPO_DIR/.env"
  set +a
fi

HASS_HOST="${HASS_HOST:-homeassistant.local}"
HASS_USER="${HASS_USER:-hassio}"
HASS_PORT="${HASS_PORT:-22}"

SRC="$REPO_DIR/custom_components/pillbox/"
DEST="/config/custom_components/pillbox/"

dry_run=""
restart=0
while getopts "nrh" opt; do
  case "$opt" in
    n) dry_run="--dry-run" ;;
    r) restart=1 ;;
    *) sed -n '2,10p' "$0"; exit 0 ;;
  esac
done

# Eine SSH-Verbindung für alle Schritte, damit das Passwort nur einmal abgefragt wird.
control="$(mktemp -u "${TMPDIR:-/tmp}/deploy_hass.XXXXXX")"
ssh_opts=(-p "$HASS_PORT" -o ControlMaster=auto -o ControlPath="$control" -o ControlPersist=60)
if [[ -n "${HASS_SSH_KEY:-}" ]]; then
  HASS_SSH_KEY="${HASS_SSH_KEY/#\~/$HOME}"
  [[ -f "$HASS_SSH_KEY" ]] || { echo "Fehler: Schlüssel $HASS_SSH_KEY nicht gefunden." >&2; exit 1; }
  ssh_opts+=(-i "$HASS_SSH_KEY" -o IdentitiesOnly=yes)
fi
trap 'ssh "${ssh_opts[@]}" -O exit "$HASS_USER@$HASS_HOST" 2>/dev/null || true' EXIT
remote() { ssh "${ssh_opts[@]}" "$HASS_USER@$HASS_HOST" "$@"; }

# Verbindung aufbauen; alle folgenden ssh/rsync-Aufrufe nutzen sie mit.
if [[ -n "${HASS_PASSWORD:-}" ]]; then
  command -v sshpass >/dev/null || { echo "Fehler: HASS_PASSWORD gesetzt, aber sshpass fehlt (sudo apt install sshpass)." >&2; exit 1; }
  SSHPASS="$HASS_PASSWORD" sshpass -e ssh "${ssh_opts[@]}" -MNf "$HASS_USER@$HASS_HOST"
else
  ssh "${ssh_opts[@]}" -MNf "$HASS_USER@$HASS_HOST"
fi

if ! remote 'command -v rsync >/dev/null'; then
  echo "Fehler: rsync fehlt auf $HASS_HOST. Im SSH-Add-on unter 'packages' rsync eintragen." >&2
  exit 1
fi

# /config gehört root -> als Nicht-root-User (z. B. hassio) per sudo schreiben.
sudo=""
[[ "$HASS_USER" != root ]] && sudo="sudo -n"

# ha-CLI braucht das Supervisor-Token aus der Umgebung des Add-ons.
ha_cmd() {
  remote "$sudo sh -c 'SUPERVISOR_TOKEN=\$(cat /run/s6/container_environment/SUPERVISOR_TOKEN) ha $*'"
}

rsync -avz --delete --no-owner --no-group $dry_run \
  --exclude '__pycache__/' --exclude '*.pyc' \
  --rsync-path="$sudo rsync" \
  -e "ssh ${ssh_opts[*]}" \
  "$SRC" "$HASS_USER@$HASS_HOST:$DEST"

if [[ -n "$dry_run" ]]; then
  echo "Probelauf, nichts geändert."
  exit 0
fi

if (( restart )); then
  echo "Prüfe Konfiguration ..."
  ha_cmd core check
  echo "Starte HA Core neu ..."
  ha_cmd core restart
else
  echo "Fertig. Für die Änderungen HA neu starten (oder erneut mit -r aufrufen)."
fi
