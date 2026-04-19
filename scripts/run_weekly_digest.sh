#!/bin/zsh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

PYTHON_BIN="${MOJO_PYTHON:-$PROJECT_ROOT/.venv/bin/python}"
DIGEST_NEXT="${MOJO_DIGEST_NEXT:-50}"
SINCE_YEAR="${MOJO_SINCE_YEAR:-2025}"

cd "$PROJECT_ROOT"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "[mojo] Python not executable: $PYTHON_BIN" >&2
  exit 1
fi

"$PYTHON_BIN" -m journal_bot.cli fetch
"$PYTHON_BIN" -m journal_bot.cli digest --next "$DIGEST_NEXT" --since "$SINCE_YEAR"
