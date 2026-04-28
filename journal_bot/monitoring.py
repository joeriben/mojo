"""Weekly monitoring schedule helpers for the local macOS app."""

from __future__ import annotations

import os
import plistlib
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from journal_bot.settings import PROJECT_ROOT

MONITOR_LABEL = "de.mojo.monitor"
LAUNCH_AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"
MONITOR_PLIST = LAUNCH_AGENTS_DIR / f"{MONITOR_LABEL}.plist"
MONITOR_TEMPLATE = PROJECT_ROOT / "launchd" / "mojo.plist.template"
MONITOR_SCRIPT = PROJECT_ROOT / "scripts" / "run_weekly_digest.sh"
MONITOR_STDOUT = PROJECT_ROOT / "launchd" / "stdout.log"
MONITOR_STDERR = PROJECT_ROOT / "launchd" / "stderr.log"

DEFAULT_WEEKDAY = 1
DEFAULT_HOUR = 7
DEFAULT_MINUTE = 0
DEFAULT_DIGEST_NEXT = 50
DEFAULT_SINCE_YEAR = max(datetime.now().year - 1, 2025)

WEEKDAY_LABELS = {
    1: "Montag",
    2: "Dienstag",
    3: "Mittwoch",
    4: "Donnerstag",
    5: "Freitag",
    6: "Samstag",
    7: "Sonntag",
}


def _default_python() -> Path:
    return PROJECT_ROOT / ".venv" / "bin" / "python"


def _fmt_ts(path: Path) -> str:
    if not path.exists():
        return ""
    return datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")


def _tail_text(path: Path, lines: int = 40) -> str:
    if not path.exists():
        return ""
    try:
        content = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return ""
    return "\n".join(content[-lines:])


def _launchctl_print() -> tuple[bool, str]:
    target = f"gui/{os.getuid()}/{MONITOR_LABEL}"
    try:
        proc = subprocess.run(
            ["launchctl", "print", target],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return False, "launchctl nicht verfügbar."
    message = (proc.stdout or proc.stderr or "").strip()
    if len(message) > 4000:
        message = message[-4000:]
    if proc.returncode == 0:
        return True, message
    return False, message


def _validate_schedule(
    *,
    weekday: int,
    hour: int,
    minute: int,
    digest_next: int,
    since_year: int,
) -> None:
    if weekday not in WEEKDAY_LABELS:
        raise ValueError("Wochentag muss zwischen 1 und 7 liegen.")
    if hour < 0 or hour > 23:
        raise ValueError("Stunde muss zwischen 0 und 23 liegen.")
    if minute < 0 or minute > 59:
        raise ValueError("Minute muss zwischen 0 und 59 liegen.")
    if digest_next < 1:
        raise ValueError("Batch-Größe muss mindestens 1 sein.")
    if since_year < 1900 or since_year > 2100:
        raise ValueError("Seit-Jahr ist ungültig.")


def _render_plist(
    *,
    python_bin: Path,
    weekday: int,
    hour: int,
    minute: int,
    digest_next: int,
    since_year: int,
) -> str:
    template = MONITOR_TEMPLATE.read_text(encoding="utf-8")
    replacements = {
        "__LABEL__": MONITOR_LABEL,
        "__PROJECT_ROOT__": str(PROJECT_ROOT),
        "__PYTHON__": str(python_bin),
        "__DIGEST_NEXT__": str(digest_next),
        "__SINCE_YEAR__": str(since_year),
        "__WEEKDAY__": str(weekday),
        "__HOUR__": str(hour),
        "__MINUTE__": str(minute),
    }
    for placeholder, value in replacements.items():
        template = template.replace(placeholder, value)
    return template


def monitoring_status() -> dict[str, Any]:
    status = {
        "installed": MONITOR_PLIST.exists(),
        "loaded": False,
        "label": MONITOR_LABEL,
        "plist_path": str(MONITOR_PLIST),
        "template_path": str(MONITOR_TEMPLATE),
        "script_path": str(MONITOR_SCRIPT),
        "python_bin": str(_default_python()),
        "weekday": DEFAULT_WEEKDAY,
        "weekday_label": WEEKDAY_LABELS[DEFAULT_WEEKDAY],
        "hour": DEFAULT_HOUR,
        "minute": DEFAULT_MINUTE,
        "digest_next": DEFAULT_DIGEST_NEXT,
        "since_year": DEFAULT_SINCE_YEAR,
        "stdout_path": str(MONITOR_STDOUT),
        "stderr_path": str(MONITOR_STDERR),
        "stdout_exists": MONITOR_STDOUT.exists(),
        "stderr_exists": MONITOR_STDERR.exists(),
        "stdout_modified": _fmt_ts(MONITOR_STDOUT),
        "stderr_modified": _fmt_ts(MONITOR_STDERR),
        "stdout_tail": _tail_text(MONITOR_STDOUT),
        "stderr_tail": _tail_text(MONITOR_STDERR),
        "launchctl_message": "",
        "error": "",
    }

    if MONITOR_PLIST.exists():
        try:
            with MONITOR_PLIST.open("rb") as fh:
                payload = plistlib.load(fh)
            env = payload.get("EnvironmentVariables", {})
            sci = payload.get("StartCalendarInterval", {})
            status.update(
                {
                    "python_bin": env.get("MOJO_PYTHON", status["python_bin"]),
                    "weekday": int(sci.get("Weekday", status["weekday"])),
                    "hour": int(sci.get("Hour", status["hour"])),
                    "minute": int(sci.get("Minute", status["minute"])),
                    "digest_next": int(env.get("MOJO_DIGEST_NEXT", status["digest_next"])),
                    "since_year": int(env.get("MOJO_SINCE_YEAR", status["since_year"])),
                }
            )
        except Exception as exc:
            status["error"] = str(exc)

    loaded, message = _launchctl_print()
    status["loaded"] = loaded
    status["launchctl_message"] = message
    status["weekday_label"] = WEEKDAY_LABELS.get(status["weekday"], str(status["weekday"]))
    return status


def install_monitoring_schedule(
    *,
    weekday: int,
    hour: int,
    minute: int,
    digest_next: int,
    since_year: int,
    python_bin: str | None = None,
) -> dict[str, Any]:
    _validate_schedule(
        weekday=weekday,
        hour=hour,
        minute=minute,
        digest_next=digest_next,
        since_year=since_year,
    )

    py_path = Path(python_bin).expanduser() if python_bin else _default_python()
    if not py_path.exists():
        raise ValueError(f"Python nicht gefunden: {py_path}")
    if not MONITOR_TEMPLATE.exists():
        raise ValueError(f"Launchd-Template fehlt: {MONITOR_TEMPLATE}")

    LAUNCH_AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    (PROJECT_ROOT / "launchd").mkdir(parents=True, exist_ok=True)

    content = _render_plist(
        python_bin=py_path,
        weekday=weekday,
        hour=hour,
        minute=minute,
        digest_next=digest_next,
        since_year=since_year,
    )
    MONITOR_PLIST.write_text(content, encoding="utf-8")

    target = f"gui/{os.getuid()}/{MONITOR_LABEL}"
    subprocess.run(
        ["launchctl", "bootout", target],
        capture_output=True,
        text=True,
        check=False,
    )
    proc = subprocess.run(
        ["launchctl", "bootstrap", f"gui/{os.getuid()}", str(MONITOR_PLIST)],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "launchctl bootstrap failed").strip())

    return monitoring_status()


def disable_monitoring_schedule() -> dict[str, Any]:
    target = f"gui/{os.getuid()}/{MONITOR_LABEL}"
    subprocess.run(
        ["launchctl", "bootout", target],
        capture_output=True,
        text=True,
        check=False,
    )
    if MONITOR_PLIST.exists():
        MONITOR_PLIST.unlink()
    return monitoring_status()


def run_monitoring_now(
    *,
    digest_next: int,
    since_year: int,
    python_bin: str | None = None,
) -> dict[str, Any]:
    if digest_next < 1:
        raise ValueError("Batch-Größe muss mindestens 1 sein.")
    if since_year < 1900 or since_year > 2100:
        raise ValueError("Seit-Jahr ist ungültig.")

    py_path = Path(python_bin).expanduser() if python_bin else _default_python()
    if not py_path.exists():
        raise ValueError(f"Python nicht gefunden: {py_path}")
    if not MONITOR_SCRIPT.exists():
        raise ValueError(f"Monitoring-Script fehlt: {MONITOR_SCRIPT}")

    env = os.environ.copy()
    env.update(
        {
            "MOJO_PYTHON": str(py_path),
            "MOJO_DIGEST_NEXT": str(digest_next),
            "MOJO_SINCE_YEAR": str(since_year),
        }
    )
    proc = subprocess.run(
        ["/bin/zsh", str(MONITOR_SCRIPT)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "stdout": proc.stdout or "",
        "stderr": proc.stderr or "",
    }
