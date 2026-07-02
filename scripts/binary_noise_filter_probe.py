"""Re-Cut auf der RICHTIGEN Achse (Benjamin): {lesenswert+scannen} BEHALTEN vs {ignorieren}.

Nicht mehr 3-Klassen-Macro-F1, nicht mehr %lesenswert. Frage: kann der Algorithmus
das I-Rauschen abgreifen, OHNE L/S zu verlieren? Zielgröße = Recall auf BEHALTEN
(L/S nicht verlieren) + wie viel I-Rauschen sich bei hohem Behalten-Recall wegwerfen lässt.

(1) Sauberes Blind-Sample (31) binär nach Kopplungs-Bucket — taugt Kopplung als Filter?
(2) Voller Label-Satz binär: Balance + welche algorithmischen Felder I isolieren.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARTICLES_DB = ROOT / "articles.db"
KEY = ROOT / "bezugsautoren_sample_key.json"

KEEP = {"lesenswert", "scannen", "pflichtlektuere"}  # behalten
DISCARD = {"ignorieren"}                              # Rauschen


def binary(v):
    if v in KEEP:
        return "BEHALTEN"
    if v in DISCARD:
        return "wegwerfen"
    return None


def main() -> int:
    con = sqlite3.connect(str(ARTICLES_DB)); con.row_factory = sqlite3.Row

    # (1) Sauberes Sample binär nach Bucket
    key = json.loads(KEY.read_text(encoding="utf-8"))
    print("(1) Sauberes Blind-Sample (31) — Kopplungs-Bucket × binär:")
    print(f"    {'Bucket':<13} {'behalten':>9} {'wegwerfen':>10} {'Σ':>4} {'%behalten':>10}")
    for b in ("corroborated", "weak", "ungrounded"):
        ks = [k for k in key if k["bucket"] == b]
        c = Counter()
        for k in ks:
            row = con.execute("SELECT user_verdict FROM articles WHERE id=?", (k["id"],)).fetchone()
            bb = binary(row["user_verdict"] if row else None)
            if bb:
                c[bb] += 1
        tot = sum(c.values())
        rate = f"{100*c['BEHALTEN']/tot:.0f}%" if tot else "—"
        print(f"    {b:<13} {c['BEHALTEN']:>9} {c['wegwerfen']:>10} {tot:>4} {rate:>10}")
    base = sum(binary(con.execute('SELECT user_verdict FROM articles WHERE id=?', (k['id'],)).fetchone()['user_verdict']) == 'BEHALTEN' for k in key)
    print(f"    → Basisrate behalten: {base}/{len(key)} = {100*base/len(key):.0f}%  "
          f"(Kopplung trennt das kaum → falsches Filterinstrument)\n")

    # (2) Voller Label-Satz binär
    rows = con.execute(
        "SELECT user_verdict, agent_verdict, selection_mode, discourse_indicator, signal_group "
        "FROM articles WHERE user_verdict IS NOT NULL AND user_verdict!=''"
    ).fetchall()
    lab = [(r, binary(r["user_verdict"])) for r in rows]
    lab = [(r, b) for r, b in lab if b]
    n = len(lab)
    keep_n = sum(1 for _, b in lab if b == "BEHALTEN")
    disc_n = n - keep_n
    print(f"(2) Voller Label-Satz: n={n} — behalten {keep_n} ({100*keep_n/n:.0f}%) · "
          f"wegwerfen {disc_n} ({100*disc_n/n:.0f}%)")
    print(f"    Trivial: 'alles behalten' filtert 0 Rauschen; 'alles wegwerfen' verliert alles.")
    print(f"    ACHTUNG Selektionsbias: dieser Satz ist intentional-positiv; im echten Scan-")
    print(f"    Strom ist der I-Anteil VIEL höher → Filter-Nutzen real noch größer.\n")

    # Welche algorithmischen Felder isolieren I? (Reinheit + Deckung)
    for field in ("agent_verdict", "selection_mode", "discourse_indicator", "signal_group"):
        ct = defaultdict(Counter)
        for r, b in lab:
            ct[r[field] if r[field] not in (None, "") else "—"][b] += 1
        print(f"    {field}:")
        # nach I-Reinheit sortiert, nur Werte mit n>=10
        rowsf = []
        for val, c in ct.items():
            tot = c["BEHALTEN"] + c["wegwerfen"]
            if tot >= 10:
                rowsf.append((c["wegwerfen"] / tot, tot, val, c))
        for purity, tot, val, c in sorted(rowsf, reverse=True):
            flag = "  ← I-rein (Wegwerf-Kandidat)" if purity >= 0.80 else ""
            print(f"       {str(val)[:22]:<22} n={tot:>4}  I-Anteil={100*purity:>3.0f}%  "
                  f"(behalten {c['BEHALTEN']}, wegwerfen {c['wegwerfen']}){flag}")
        print()

    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
