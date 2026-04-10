"""OpenRouter-Client mit interaktivem Key-Flow.

Liest den Key aus ~/.config/journal-bot/openrouter_key. Existiert die Datei nicht,
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
    return OpenAI(
        base_url=OPENROUTER_BASE_URL,
        api_key=_load_or_prompt_key(),
        default_headers={
            "HTTP-Referer": "https://localhost/journal-bot",
            "X-Title": "journal-bot",
        },
    )
