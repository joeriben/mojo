"""Verifikation des H7-Fallgestalt-Ports (journal_bot/fallgestalt.py) gegen
JK26 — dasselbe Dokument, mit dem SARAHs H7-Pass bereits geprüft wurde
(canonical_id hash:6839b2118380813f = "Cultural Resilience" and the
Cultivation of a Postdigital Planetary Dissensus, Jörissen/Klepacki, eigenes
Werk). Erlaubt einen echten Cross-Implementation-Vergleich: gleicher Text,
gleiches Modell (MiMo), zwei unabhängige Implementierungen des Verfahrens.

Aufruf: python scripts/h7_fallgestalt_verify.py
"""

from __future__ import annotations

import json
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from journal_bot.fallgestalt import assemble_fallgestalt, run_document_profile_h7

CANONICAL_ID = "hash:6839b2118380813f"
DB_PATH = Path(__file__).parent.parent / "own_refs.db"

STANCE = {"affirms", "extends", "contrasts", "reserves", "rejects"}


def load_publication(canonical_id: str) -> dict:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT title, year, venue, authors_json, fulltext_path FROM publications WHERE canonical_id = ?",
        (canonical_id,),
    ).fetchone()
    conn.close()
    if row is None:
        raise SystemExit(f"Publikation {canonical_id} nicht in own_refs.db gefunden")
    return dict(row)


def main() -> None:
    pub = load_publication(CANONICAL_ID)
    fulltext = Path(pub["fulltext_path"]).read_text(encoding="utf-8")
    authors = json.loads(pub["authors_json"])

    print(f"\n══ H7-PORT VERIFIKATION · {pub['title'][:60]}… ══")
    print(f"  {len(fulltext)} Zeichen Volltext · {len(authors)} Autoren · {pub['year']}\n")

    t0 = time.time()
    read = run_document_profile_h7(fulltext, route_key="mimo")
    secs = time.time() - t0

    # Kalibrierungs-Check: SARAHs bekannte dens-Werte für dieses Dokument
    # (aus der geparsten Bibliographie, topology.ts) — Jörissen=7, Barad=6,
    # Brown=5, Klepacki=4, Haraway=3. Regex-Topologie sollte nahe rankommen.
    known = {"Jörissen": 7, "Barad": 6, "Brown": 5, "Klepacki": 4, "Haraway": 3}
    print("── Kalibrierung: Regex-dens vs. SARAHs Bibliographie-dens ──")
    for author, sarah_dens in known.items():
        hit = read["topology"].get(author)
        got = hit["dens"] if hit else 0
        print(f"  {author:12s} SARAH={sarah_dens}  Regex={got}")
    print()

    src = [n for n in read["nodes"] if n["nodeType"] == "source" and not n["properties"].get("ownWork")]
    own = [n for n in read["nodes"] if n["nodeType"] == "source" and n["properties"].get("ownWork")]
    terms = [n for n in read["nodes"] if n["nodeType"] == "term"]
    stance_edges = [e for e in read["edges"] if e["edgeKind"] in STANCE]
    rel: dict[str, int] = {}
    for e in stance_edges:
        rel[e["edgeKind"]] = rel.get(e["edgeKind"], 0) + 1

    print(
        f"  ✓ N={len(read['nodes'])}/E={len(read['edges'])}  extern={len(src)}  "
        f"O2={len(terms)}  O6={len(own)}  "
        f"σ +{sum(1 for e in stance_edges if e['sigma']=='+')}/"
        f"-{sum(1 for e in stance_edges if e['sigma']=='-')}  "
        f"rel={json.dumps(rel, ensure_ascii=False)}  "
        f"· {read['tokens']['input']}→{read['tokens']['output']} tok · {secs:.1f}s  "
        f"unparsed={len(read['unparsed'])}"
    )
    if read["unparsed"]:
        print(f"  Unparsed-Zeilen: {read['unparsed']}")

    meta = {
        "document_id": CANONICAL_ID,
        "title": pub["title"],
        "authors": authors,
        "year": str(pub["year"]) if pub["year"] else None,
        "venue": pub["venue"],
        "disc": None,
    }
    fg = assemble_fallgestalt(meta, read["nodes"], read["edges"])
    out_dir = Path("/private/tmp/claude-502/-Users-joerissen-ai-sarah/31147938-99b3-40e2-8bde-dbe26911735c/scratchpad")
    out_file = out_dir / "fallgestalt_mojo_port_jk26.json"
    out_file.write_text(json.dumps(fg, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  Dump: {out_file}")


if __name__ == "__main__":
    main()
