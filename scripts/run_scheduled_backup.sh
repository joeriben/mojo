#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

PYTHON_BIN="${MOJO_PYTHON:-$PROJECT_ROOT/.venv/bin/python}"
BACKUP_DIR="${MOJO_BACKUP_DIR:-$HOME/Documents/MOJO Backups}"
BACKUP_KEEP="${MOJO_BACKUP_KEEP:-10}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
OUTPUT_PATH="$BACKUP_DIR/mojo_user_backup_${TIMESTAMP}.zip"

mkdir -p "$BACKUP_DIR"
cd "$PROJECT_ROOT"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "[mojo] Python not executable: $PYTHON_BIN" >&2
  exit 1
fi

if ! [[ "$BACKUP_KEEP" =~ ^[0-9]+$ ]] || (( BACKUP_KEEP < 1 )); then
  echo "[mojo] MOJO_BACKUP_KEEP muss eine positive ganze Zahl sein: $BACKUP_KEEP" >&2
  exit 1
fi

"$PYTHON_BIN" -m journal_bot.cli backup --output "$OUTPUT_PATH"
echo "[mojo] Backup geschrieben: $OUTPUT_PATH"

setopt local_options null_glob
backup_files=("$BACKUP_DIR"/mojo_user_backup_*.zip)
delete_count=$((${#backup_files[@]} - BACKUP_KEEP))

if (( delete_count > 0 )); then
  for (( i = 1; i <= delete_count; i++ )); do
    old_file="${backup_files[$i]}"
    rm -f -- "$old_file"
    echo "[mojo] Altes Backup geloescht: $old_file"
  done
fi
