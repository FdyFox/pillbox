#!/usr/bin/env bash
# Copies custom_components/pillbox to the Home Assistant instance via rsync (SSH add-on).
#
# Usage:  scripts/deploy_hass.sh [-n] [-r]
#   -n  dry run: only show what would be copied/deleted
#   -r  afterwards check the configuration and restart HA Core
#
# Configurable via environment variables or .env in the repo (template: .env.example):
#   HASS_HOST, HASS_USER, HASS_PORT, HASS_SSH_KEY (path to the private key),
#   optional HASS_PASSWORD (requires sshpass, only without a key)
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

# One SSH connection for all steps, so the password is only asked once.
control="$(mktemp -u "${TMPDIR:-/tmp}/deploy_hass.XXXXXX")"
ssh_opts=(-p "$HASS_PORT" -o ControlMaster=auto -o ControlPath="$control" -o ControlPersist=60)
if [[ -n "${HASS_SSH_KEY:-}" ]]; then
  HASS_SSH_KEY="${HASS_SSH_KEY/#\~/$HOME}"
  [[ -f "$HASS_SSH_KEY" ]] || { echo "Error: key $HASS_SSH_KEY not found." >&2; exit 1; }
  ssh_opts+=(-i "$HASS_SSH_KEY" -o IdentitiesOnly=yes)
fi
trap 'ssh "${ssh_opts[@]}" -O exit "$HASS_USER@$HASS_HOST" 2>/dev/null || true' EXIT
remote() { ssh "${ssh_opts[@]}" "$HASS_USER@$HASS_HOST" "$@"; }

# Open the connection; all following ssh/rsync calls reuse it.
if [[ -n "${HASS_PASSWORD:-}" ]]; then
  command -v sshpass >/dev/null || { echo "Error: HASS_PASSWORD is set, but sshpass is missing (sudo apt install sshpass)." >&2; exit 1; }
  SSHPASS="$HASS_PASSWORD" sshpass -e ssh "${ssh_opts[@]}" -MNf "$HASS_USER@$HASS_HOST"
else
  ssh "${ssh_opts[@]}" -MNf "$HASS_USER@$HASS_HOST"
fi

if ! remote 'command -v rsync >/dev/null'; then
  echo "Error: rsync is missing on $HASS_HOST. Add rsync under 'packages' in the SSH add-on." >&2
  exit 1
fi

# /config belongs to root -> write via sudo when logged in as a non-root user (e.g. hassio).
sudo=""
[[ "$HASS_USER" != root ]] && sudo="sudo -n"

# The ha CLI needs the supervisor token from the add-on environment.
ha_cmd() {
  remote "$sudo sh -c 'SUPERVISOR_TOKEN=\$(cat /run/s6/container_environment/SUPERVISOR_TOKEN) ha $*'"
}

rsync -avz --delete --no-owner --no-group $dry_run \
  --exclude '__pycache__/' --exclude '*.pyc' \
  --rsync-path="$sudo rsync" \
  -e "ssh ${ssh_opts[*]}" \
  "$SRC" "$HASS_USER@$HASS_HOST:$DEST"

if [[ -n "$dry_run" ]]; then
  echo "Dry run, nothing changed."
  exit 0
fi

if (( restart )); then
  echo "Checking configuration ..."
  ha_cmd core check
  echo "Restarting HA Core ..."
  ha_cmd core restart
else
  echo "Done. Restart HA for the changes to take effect (or run again with -r)."
fi
