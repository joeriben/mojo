#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TEMPLATE_PATH="$PROJECT_ROOT/launchd/mojo-backup.plist.template"

PYTHON_BIN="${MOJO_PYTHON:-$PROJECT_ROOT/.venv/bin/python}"
BACKUP_DIR="${MOJO_BACKUP_DIR:-$HOME/Documents/MOJO Backups}"
BACKUP_KEEP="${MOJO_BACKUP_KEEP:-10}"
LABEL="${MOJO_BACKUP_LABEL:-de.mojo.backup}"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
TARGET_PLIST="$LAUNCH_AGENTS_DIR/$LABEL.plist"

mkdir -p "$LAUNCH_AGENTS_DIR" "$BACKUP_DIR" "$PROJECT_ROOT/launchd"

if [[ ! -f "$TEMPLATE_PATH" ]]; then
  echo "[mojo] Template nicht gefunden: $TEMPLATE_PATH" >&2
  exit 1
fi

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "[mojo] Python not executable: $PYTHON_BIN" >&2
  exit 1
fi

template_content="$(<"$TEMPLATE_PATH")"
template_content="${template_content//__LABEL__/$LABEL}"
template_content="${template_content//__PROJECT_ROOT__/$PROJECT_ROOT}"
template_content="${template_content//__PYTHON__/$PYTHON_BIN}"
template_content="${template_content//__BACKUP_DIR__/$BACKUP_DIR}"
template_content="${template_content//__BACKUP_KEEP__/$BACKUP_KEEP}"

printf '%s\n' "$template_content" > "$TARGET_PLIST"

launchctl bootout "gui/$(id -u)/$LABEL" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$TARGET_PLIST"

echo "[mojo] LaunchAgent installiert: $TARGET_PLIST"
echo "[mojo] Taegliches Backup-Ziel: $BACKUP_DIR"
echo "[mojo] Aufbewahrung: $BACKUP_KEEP Backups"
