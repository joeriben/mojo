"""OpenRouter-Client mit interaktivem Key-Flow.

Liest den Key aus ~/.config/mojo/openrouter_key. Existiert die Datei nicht,
wird einmalig im Terminal gefragt (getpass), Key wird dann mit chmod 600 gespeichert.
"""

from __future__ import annotations

import getpass
import os
import sys

from openai import OpenAI

from journal_bot.settings import KEY_FILE, OPENROUTER_BASE_URL


def _load_or_prompt_key() -> str:
    # 1. Environment-Override (für Tests / CI)
    env_key = os.environ.get("OPENROUTER_API_KEY")
    if env_key:
        return env_key.strip()

    # 2. Gespeicherte Datei
    if KEY_FILE.exists():
        key = KEY_FILE.read_text().strip()
        if key:
            return key

    # 3. Interaktive Abfrage (nur wenn wir im Terminal sind)
    if not sys.stdin.isatty():
        raise RuntimeError(
            f"Kein OpenRouter-Key gefunden ({KEY_FILE}), und ich laufe nicht im Terminal. "
            f"Leg ihn an oder setze OPENROUTER_API_KEY."
        )

    print("Kein OpenRouter-Key gefunden.")
    print("Hol ihn unter https://openrouter.ai/keys (Create new).")
    key = getpass.getpass("Key hier einfügen (Eingabe wird nicht angezeigt): ").strip()
    if not key:
        raise RuntimeError("Kein Key eingegeben.")

    KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    KEY_FILE.write_text(key + "\n")
    KEY_FILE.chmod(0o600)
    print(f"Gespeichert in {KEY_FILE} (chmod 600).")
    return key


def build_client() -> OpenAI:
    # timeout/max_retries: Hard-Limits gegen hängende Verbindungen.
    #
    # Vorfall 2026-05-23: Trends-Call (MiMo) lief 33+ min mit 100% CPU,
    # während die TCP-Verbindung zu OpenRouter bereits in CLOSE_WAIT war.
    # Ohne explizites timeout fällt die OpenAI-SDK auf ihren Default zurück
    # (kann je nach Version >10 min oder gar None sein) und retried zudem
    # transparent — was bei einem hängenden Stream zu Endlos-Loops führt.
    #
    # 600s = 10 min Hard-Cap. Trends ist der teuerste Call und liegt
    # normalerweise bei 60–180s; assess/verify/screen/summarize deutlich
    # darunter. 10 min ist großzügiges Sicherheitsnetz, schneidet aber
    # 30-min-Hänger sofort ab.
    #
    # max_retries=1: ein einziger Retry bei transientem Netzwerk-Fehler,
    # kein stilles Mehrfach-Wiederholen langlaufender Calls.
    return OpenAI(
        base_url=OPENROUTER_BASE_URL,
        api_key=_load_or_prompt_key(),
        timeout=600.0,
        max_retries=1,
        default_headers={
            "HTTP-Referer": "https://localhost/mojo",
            "X-Title": "mojo",
        },
    )
