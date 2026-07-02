"""Scoring: Autor-Kopplungs-Bucket × Benjamins echte Blind-Urteile (sauberes Sample).

Liest den versteckten Schlüssel (bezugsautoren_sample_key.json, Bucket je Artikel
schon berechnet), Benjamins user_verdict aus articles.db und die manuellen
Ausschlüsse (label_exclusions.json). Kreuzt Bucket × Urteil — beantwortet:
verteilen sich 'ungrounded' ähnlich über die Urteile wie 'corroborated', dann ist
Kopplungs-ABWESENHEIT blind für Relevanz, die Benjamin sieht.

Zusätzlich: in welchen Buckets häufen sich die 'kenne ich'-Ausschlüsse? (Konzentration
in corroborated/weak = empirischer Beleg, dass Kopplung das eigene Umfeld wiederfindet.)
"""

from __future__ import annotations

import json
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KEY = ROOT / "bezugsautoren_sample_key.json"
EXCL = ROOT / "label_exclusions.json"
ARTICLES_DB = ROOT / "articles.db"

BUCKETS = ("corroborated", "weak", "ungrounded")
POS = ("lesenswert", "pflichtlektuere")


def main() -> int:
    key = json.loads(KEY.read_text(encoding="utf-8"))
    excl = {}
    if EXCL.exists():
        try:
            excl = json.loads(EXCL.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass

    con = sqlite3.connect(str(ARTICLES_DB)); con.row_factory = sqlite3.Row
    verdict = {}
    for k in key:
        row = con.execute("SELECT user_verdict FROM articles WHERE id=?", (k["id"],)).fetchone()
        verdict[k["id"]] = (row["user_verdict"] if row else None) or None
    con.close()

    n = len(key)
    excluded = [k for k in key if k["id"] in excl]
    labeled = [k for k in key if k["id"] not in excl and verdict[k["id"]]]
    untouched = [k for k in key if k["id"] not in excl and not verdict[k["id"]]]

    print(f"Sample: {n}  →  bewertet {len(labeled)} · ausgeschlossen {len(excluded)} · "
          f"unberührt {len(untouched)}\n")

    # Ausschlüsse nach Bucket (Footprint-Beleg)
    if excluded:
        ec = Counter(k["bucket"] for k in excluded)
        print("‚kenne ich'-Ausschlüsse nach Bucket (Erwartung: häuft sich bei corroborated/weak):")
        for b in BUCKETS:
            print(f"   {b:<13}: {ec.get(b, 0)}")
        print()

    if not labeled:
        print("Noch keine bewerteten Artikel — nichts zu kreuzen.")
        return 0

    # Kreuztabelle Bucket × Urteil
    ct = defaultdict(Counter)
    for k in labeled:
        ct[k["bucket"]][verdict[k["id"]]] += 1

    verdicts = ["lesenswert", "scannen", "ignorieren", "pflichtlektuere"]
    print(f"{'Bucket':<14} | " + " ".join(f"{v[:9]:>10}" for v in verdicts) + f" {'Σ':>4} {'%LES':>6}")
    print("-" * 78)
    for b in BUCKETS:
        row = ct[b]; tot = sum(row.values())
        pos = sum(row.get(v, 0) for v in POS)
        pct = f"{100*pos/tot:.0f}%" if tot else "—"
        print(f"{b:<14} | " + " ".join(f"{row.get(v,0):>10}" for v in verdicts) + f" {tot:>4} {pct:>6}")
    print()

    # Headline
    def rate(b):
        row = ct[b]; tot = sum(row.values())
        return (sum(row.get(v, 0) for v in POS) / tot if tot else None), tot
    cr, cn = rate("corroborated")
    ur, un = rate("ungrounded")
    print("Kernfrage — %lesenswert:")
    print(f"   corroborated: {f'{100*cr:.0f}%' if cr is not None else '—'} (n={cn})")
    print(f"   ungrounded:   {f'{100*ur:.0f}%' if ur is not None else '—'} (n={un})")
    if cr is not None and ur is not None:
        gap = 100 * (cr - ur)
        print(f"\n   Gap corroborated − ungrounded: {gap:+.0f} pp")
        print("   → klein  ⇒ Kopplungs-Abwesenheit blind für deine Relevanz (Bezug nur sprechen, nicht abwerten)")
        print("   → groß   ⇒ Kopplung trägt doch ein Relevanzsignal")
    return 0


if __name__ == "__main__":
    sys.exit(main())
