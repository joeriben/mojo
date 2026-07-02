#!/usr/bin/env python3
"""Backfill display-kritischer Felder in bestehenden agent_entry_json-Einträgen.

Hintergrund: Der Agent (v.a. Gemini 3.5 Flash) lässt `kernthese` im
submit_digest_entry-Tool-Call gelegentlich weg. Im Lauf vom 2026-05-30 fehlte
das Feld bei 26 Einträgen und hat die Web-Digest-View mit einem 500
lahmgelegt. Die Schreibseite (store.update_agent_result) normalisiert seit
b6e3c3a+ jeden neuen Eintrag; dieses Skript bringt die bereits gespeicherten
Einträge auf denselben Stand.

Die Normalisierung ist rein lokal (kein LLM-Call, keine API-Kosten): eine
fehlende `kernthese` wird aus `theoretisch_methodisch` / `bemerkenswert[0]` /
`verdict_begruendung` rekonstruiert (siehe store.normalize_digest_entry).

Default: Dry-Run (zeigt nur, was sich ändern würde). Mit --apply schreiben.
Idempotent — ein zweiter Lauf findet nichts mehr.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from journal_bot.store import Store, normalize_digest_entry


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill display-kritischer Felder in articles.db (agent_entry_json)",
    )
    parser.add_argument(
        "--db",
        default="articles.db",
        help="Pfad zur SQLite-DB (Default: articles.db)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Änderungen tatsächlich schreiben (ohne dieses Flag nur Dry-Run)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    store = Store(Path(args.db))

    with store._conn() as c:
        rows = c.execute(
            "SELECT id, agent_verdict, agent_entry_json FROM articles "
            "WHERE agent_entry_json IS NOT NULL AND agent_entry_json != ''"
        ).fetchall()

    scanned = 0
    unparsable = 0
    changes: list[tuple[str, str, str, dict]] = []  # (id, verdict, derived_kernthese, normalized)

    for row in rows:
        article_id, verdict, raw = row[0], row[1], row[2]
        scanned += 1
        try:
            original = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            unparsable += 1
            continue
        if not isinstance(original, dict):
            unparsable += 1
            continue

        # Tiefe Kopie für den Vorher-Vergleich, dann normalisieren.
        before = json.loads(json.dumps(original, ensure_ascii=False))
        normalized = normalize_digest_entry(json.loads(json.dumps(original, ensure_ascii=False)))
        if normalized != before:
            changes.append((article_id, verdict or "?", normalized.get("kernthese", ""), normalized))

    print(f"Geprüft: {scanned} Einträge mit agent_entry_json")
    if unparsable:
        print(f"  ⚠ {unparsable} nicht parsebar/kein Dict — übersprungen")
    print(f"Ergänzungsbedarf: {len(changes)} Einträge\n")

    for article_id, verdict, kernthese, _ in changes:
        preview = (kernthese or "(leer)").replace("\n", " ")[:100]
        print(f"  [{article_id[:8]}] {verdict:13s} kernthese ← {preview}")

    if not changes:
        print("\nNichts zu tun — alle Einträge sind vollständig.")
        return 0

    if not args.apply:
        print(f"\nDry-Run: {len(changes)} Einträge würden aktualisiert. "
              f"Mit --apply schreiben.")
        return 0

    with store._conn() as c:
        for article_id, _, _, normalized in changes:
            c.execute(
                "UPDATE articles SET agent_entry_json = ? WHERE id = ?",
                (json.dumps(normalized, ensure_ascii=False), article_id),
            )
    print(f"\n✓ {len(changes)} Einträge aktualisiert.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
