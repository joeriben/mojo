#!/usr/bin/env python3
"""Baut den Beispiel-Index für `journal_bot/beispiele.py`.

Über alle schon beurteilten Artikel: MiniLM-Embedding von Titel + Abstract,
dazu Titel, Verdikt und Memo im Wortlaut des Nutzers. Der Index ist die
Nachbarschafts-Wolke, aus der das Screening zu jedem neuen Artikel die nächsten
echten Urteile zieht.

Additiv-idempotent: wächst mit jedem neuen Urteil, einfach neu bauen.

    scripts/beispiel_index_build.py
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from journal_bot import textembed  # noqa: E402
from journal_bot.beispiele import INDEX_NPZ  # noqa: E402


def main() -> int:
    con = sqlite3.connect(f"file:{ROOT / 'articles.db'}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT id, title, abstract, openalex_abstract, user_verdict, user_memo"
        " FROM articles WHERE user_verdict IS NOT NULL ORDER BY id"
    ).fetchall()
    con.close()
    if not rows:
        print("Keine Urteile — nichts zu bauen.")
        return 1

    texte = [f"{r['title'] or ''}. "
             f"{(r['abstract'] or r['openalex_abstract'] or '')}".strip()
             for r in rows]
    print(f"Bette {len(rows)} beurteilte Artikel ein …")
    emb = textembed.encode(texte)

    np.savez(
        INDEX_NPZ,
        ids=np.array([r["id"] for r in rows]),
        emb=emb.astype("float32"),
        titles=np.array([r["title"] or "" for r in rows], dtype=object),
        verdicts=np.array([r["user_verdict"] for r in rows], dtype=object),
        memos=np.array([(r["user_memo"] or "") for r in rows], dtype=object),
    )
    from collections import Counter
    vc = Counter(r["user_verdict"] for r in rows)
    print(f"→ {INDEX_NPZ.name}  ({len(rows)} Artikel, {emb.shape[1]}-dim)")
    print("  Verdikte: " + ", ".join(f"{k} {n}" for k, n in vc.most_common()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
