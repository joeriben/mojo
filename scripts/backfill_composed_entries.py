"""Backfill: substitutive Einträge (composed_entry_json) für den Bestand.

Komponiert für jeden Artikel den geerdeten Eintrag (journal_bot/entry_composer)
— geteilte Referenzen mit dem Eigenkorpus, Umfeld-Annotation, ehrliche
Leerstelle. Rein algorithmisch, $0; einzige Netzlast ist der gecachte
OpenAlex-Titel-Lookup für geteilte Referenzen (abschaltbar via --no-titles).

Idempotent: ohne --force werden nur Artikel ohne composed_entry_json
komponiert; ein abgebrochener Lauf setzt einfach fort. Verdikte und
agent_entry_json bleiben unberührt.

Usage:
  python scripts/backfill_composed_entries.py --limit 20   # Verifikation
  python scripts/backfill_composed_entries.py              # ganzer Bestand
  python scripts/backfill_composed_entries.py --force      # neu komponieren
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from journal_bot import entry_composer
from journal_bot.store import Store


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--force", action="store_true",
                    help="auch bereits komponierte Artikel neu komponieren")
    ap.add_argument("--no-titles", action="store_true",
                    help="OpenAlex-Titel-Lookup überspringen (offline)")
    args = ap.parse_args()

    store = Store()  # legt composed_entry_json per Migration an
    with store._conn() as c:
        sql = "SELECT id FROM articles"
        if not args.force:
            sql += " WHERE composed_entry_json IS NULL"
        sql += " ORDER BY fetched_at DESC"
        ids = [r["id"] for r in c.execute(sql)]
    if args.limit:
        ids = ids[: args.limit]

    res = entry_composer.get_resources()
    print(
        f"Backfill: {len(ids)} Artikel · "
        f"own_refs={'ja' if res.own_refs_available else 'NEIN'} "
        f"({res.n_publications} Werke) · "
        f"bezugsautoren={'ja' if res.bezugsautoren_available else 'NEIN'}"
    )

    dist: Counter = Counter()
    n = 0
    for aid in ids:
        sa = store.get(aid)
        if sa is None:
            continue
        composed = entry_composer.compose_and_store(
            store, sa, resources=res, resolve_titles=not args.no_titles
        )
        dist[composed["einordnung"]] += 1
        n += 1
        if n % 1000 == 0:
            print(f"  … {n}/{len(ids)}  (konkret {dist['konkret']} · "
                  f"umfeld {dist['umfeld']} · leer {dist['leer']})")

    print(f"\nFertig: {n} komponiert.")
    total = max(1, n)
    for k in ("konkret", "umfeld", "leer"):
        print(f"   {k:<8}: {dist[k]:>6}  ({100 * dist[k] / total:4.1f}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
