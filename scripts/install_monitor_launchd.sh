#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TEMPLATE_PATH="$PROJECT_ROOT/launchd/mojo.plist.template"

PYTHON_BIN="${MOJO_PYTHON:-$PROJECT_ROOT/.venv/bin/python}"
LABEL="${MOJO_MONITOR_LABEL:-de.mojo.monitor}"
WEEKDAY="${MOJO_MONITOR_WEEKDAY:-1}"
HOUR="${MOJO_MONITOR_HOUR:-7}"
MINUTE="${MOJO_MONITOR_MINUTE:-0}"
DIGEST_NEXT="${MOJO_DIGEST_NEXT:-50}"
SINCE_YEAR="${MOJO_SINCE_YEAR:-$(( $(date +%Y) - 1 ))}"
(( SINCE_YEAR > 1900 )) || SINCE_YEAR=2025

LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
TARGET_PLIST="$LAUNCH_AGENTS_DIR/$LABEL.plist"

mkdir -p "$LAUNCH_AGENTS_DIR" "$PROJECT_ROOT/launchd"

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
template_content="${template_content//__DIGEST_NEXT__/$DIGEST_NEXT}"
template_content="${template_content//__SINCE_YEAR__/$SINCE_YEAR}"
template_content="${template_content//__WEEKDAY__/$WEEKDAY}"
template_content="${template_content//__HOUR__/$HOUR}"
template_content="${template_content//__MINUTE__/$MINUTE}"

printf '%s\n' "$template_content" > "$TARGET_PLIST"

launchctl bootout "gui/$(id -u)/$LABEL" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$TARGET_PLIST"

echo "[mojo] Monitoring installiert: $TARGET_PLIST"
echo "[mojo] Zeitplan: weekday=$WEEKDAY hour=$HOUR minute=$MINUTE"
echo "[mojo] Batchgröße: $DIGEST_NEXT"
echo "[mojo] Since-Year: $SINCE_YEAR"
