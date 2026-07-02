"""Höhere-N-Sensitivität + Null-Kontrolle.

Benjamin: corroborated steigt bei N=20 noch — höher testen (30/40/50/100/200).
Kritische Gegenprobe: Sinkt `ungrounded` durch ECHTE Nähe, oder teilt mit genug
Werken fast jeder Autor zufällig eine Ref aus Benjamins 537-Ref-Wolke?

→ Null-Kontrolle: zufällige Erstautoren aus IGNORIERTEN Artikeln OHNE Werk-Bezug.
  Ihre Kopplungsrate je N = Zufalls-Boden. Signal = Bezug-Autoren MINUS Kontrolle.

OpenAlex per-page max = 200 → ein Fetch je Sortierung deckt N≤200 ab (2 Calls/Autor).
"""

from __future__ import annotations

import json
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from journal_bot import bezugsautoren as bz
from journal_bot.signals import _normalize_oa_id

ARTICLES_DB = ROOT / "articles.db"
OWN_REFS_DB = ROOT / "own_refs.db"
N_LEVELS = [10, 20, 30, 40, 50, 100, 200]
FETCH_N = 200
N_CONTROL = 150


def load_attribution():
    con = sqlite3.connect(str(OWN_REFS_DB)); con.row_factory = sqlite3.Row
    oa2works = defaultdict(set)
    for r in con.execute("SELECT canonical_id, ref_oa_id FROM pub_refs"):
        if r["ref_oa_id"]:
            oa2works[_normalize_oa_id(r["ref_oa_id"])].add(r["canonical_id"])
    oa2works.pop("", None)
    zkey2cid = {r["source_item_id"]: r["canonical_id"]
                for r in con.execute("SELECT canonical_id, source_item_id FROM source_refs")
                if r["source_item_id"]}
    con.close()
    return dict(oa2works), zkey2cid


def llm_claims(entry_json):
    try:
        d = json.loads(entry_json or "{}")
        bezs = d.get("bezuege") or d.get("bezüge") or []
    except json.JSONDecodeError:
        return []
    return [str(b["pub_id"]).strip() for b in bezs if isinstance(b, dict) and b.get("pub_id")]


def fetch_ordered(client, aid, sort, n=FETCH_N):
    try:
        r = client.get("https://api.openalex.org/works", params={
            "filter": f"author.id:{aid}", "sort": sort, "per-page": n,
            "select": "id,referenced_works"})
        r.raise_for_status()
        res = r.json().get("results", [])
    except Exception:
        return []
    out = []
    for w in res:
        refs = {bz._bare(x) for x in (w.get("referenced_works") or []) if x}
        refs.discard("")
        out.append((bz._bare(w.get("id")), refs))
    return out


def refs_at_N(recent, cited, n):
    seen, refs = set(), set()
    for wid, rs in recent[:n] + cited[:n]:
        if wid in seen:
            continue
        seen.add(wid); refs |= rs
    return refs, len(seen)


def main() -> int:
    oa2works, zkey2cid = load_attribution()
    own_oa = set(oa2works)

    con_bz = sqlite3.connect(str(bz.DEFAULT_DB)); con_bz.row_factory = sqlite3.Row
    seed = {r["article_id"]: r["author_oa_id"]
            for r in con_bz.execute("SELECT article_id, author_oa_id FROM author_seed WHERE role='first_author'")}
    con_bz.close()

    con = sqlite3.connect(str(ARTICLES_DB)); con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT id, openalex_id, agent_verdict, agent_entry_json FROM articles "
        "WHERE agent_entry_json IS NOT NULL AND openalex_id IS NOT NULL AND openalex_id!=''"
    ).fetchall()
    con.close()

    claim_rows = [r for r in rows if llm_claims(r["agent_entry_json"]) and r["id"] in seed]
    claim_authors = sorted({seed[r["id"]] for r in claim_rows})

    # Kontrolle: zufallsnah – ignorierte Artikel ohne Bezug, deterministisch jeder k-te
    ign = [r for r in rows if r["agent_verdict"] == "ignorieren" and not llm_claims(r["agent_entry_json"])]
    step = max(1, len(ign) // N_CONTROL)
    control_rows = ign[::step][:N_CONTROL]

    client = bz.make_client()

    # 1) Bezug-Autoren: 200+200
    print(f"Bezug-Autoren: {len(claim_authors)} — ziehe {FETCH_N}+{FETCH_N} …")
    claim_fetch = {}
    for i, aid in enumerate(claim_authors, 1):
        rec = fetch_ordered(client, aid, "publication_date:desc"); time.sleep(bz.THROTTLE_SECONDS)
        cit = fetch_ordered(client, aid, "cited_by_count:desc"); time.sleep(bz.THROTTLE_SECONDS)
        claim_fetch[aid] = (rec, cit)
        if i % 50 == 0:
            print(f"  … {i}/{len(claim_authors)}")

    # 2) Kontroll-Autoren: Erstautor auflösen + 200+200
    print(f"Kontroll-Autoren (ignoriert, kein Bezug): bis {len(control_rows)} …")
    control_fetch = {}
    for i, r in enumerate(control_rows, 1):
        fa = bz.fetch_first_author(client, r["openalex_id"]); time.sleep(bz.THROTTLE_SECONDS)
        if not fa or fa[0] in control_fetch:
            continue
        aid = fa[0]
        rec = fetch_ordered(client, aid, "publication_date:desc"); time.sleep(bz.THROTTLE_SECONDS)
        cit = fetch_ordered(client, aid, "cited_by_count:desc"); time.sleep(bz.THROTTLE_SECONDS)
        control_fetch[aid] = (rec, cit)
        if i % 50 == 0:
            print(f"  … {i}/{len(control_rows)}")
    client.close()
    print(f"  Kontroll-Autoren effektiv: {len(control_fetch)}\n")

    # Auswertung
    hdr = (f"{'N':>5} | {'corrob':>7}{'weak':>7}{'ungrnd':>7} | "
           f"{'Bezug-Kopp%':>11}{'⌀Refs':>7} | {'Kontr-Kopp%':>12}{'⌀Refs':>7} | {'Δ-Kopp':>7}")
    print(hdr); print("-" * len(hdr))
    for n in N_LEVELS:
        aud = Counter()
        claim_coupled = 0; claim_refsum = 0
        for r in claim_rows:
            rec, cit = claim_fetch.get(seed[r["id"]], ([], []))
            refs, _ = refs_at_N(rec, cit, n)
            sh = refs & own_oa
            wh = set().union(*[oa2works[h] for h in sh]) if sh else set()
            if sh:
                claim_coupled += 1
            claim_refsum += len(sh)
            for pid in llm_claims(r["agent_entry_json"]):
                cid = zkey2cid.get(pid)
                if cid is None:
                    aud["bad"] += 1
                elif cid in wh:
                    aud["corroborated"] += 1
                elif sh:
                    aud["weak"] += 1
                else:
                    aud["ungrounded"] += 1
        tot = sum(aud[k] for k in ("corroborated", "weak", "ungrounded", "bad")) or 1
        # Kontrolle (per Autor)
        ctrl_coupled = 0; ctrl_refsum = 0
        for rec, cit in control_fetch.values():
            refs, _ = refs_at_N(rec, cit, n)
            sh = refs & own_oa
            if sh:
                ctrl_coupled += 1
            ctrl_refsum += len(sh)
        claim_rate = 100 * claim_coupled / len(claim_rows)
        ctrl_rate = 100 * ctrl_coupled / max(1, len(control_fetch))
        print(f"{n:>5} | {100*aud['corroborated']/tot:>6.1f}%{100*aud['weak']/tot:>6.1f}%"
              f"{100*aud['ungrounded']/tot:>6.1f}% | {claim_rate:>10.1f}%{claim_refsum/len(claim_rows):>7.1f}"
              f" | {ctrl_rate:>11.1f}%{ctrl_refsum/max(1,len(control_fetch)):>7.1f} | {claim_rate-ctrl_rate:>6.1f}")
    print("\nΔ-Kopp = Kopplungsrate Bezug-Autoren minus Kontrolle (= Signal über Zufall).")
    print("Wenn Kontrolle bei hohem N mithochläuft, ist der ungrounded-Rückgang teils Zufall.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
