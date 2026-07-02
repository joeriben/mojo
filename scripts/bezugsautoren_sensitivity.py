"""Sensitivitätstest: wie viele Werke pro Autor sind treffsicher?

Variiert N (neueste N + meistzitierte N) und misst den Abgleich gegen Benjamins
Korpus auf der 222-Bezug-Artikel-Menge. Zieht EINMAL 20+20 pro Autor und
subsamplet die kleineren N aus der API-Reihenfolge (konsistent, ein Fetch).

Frage (Benjamin): War 10 ein guter Guess? Reichen 5? Sollten es 2×20 sein?
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
from journal_bot.signals import _normalize_doi_local, _normalize_oa_id

ARTICLES_DB = ROOT / "articles.db"
OWN_REFS_DB = ROOT / "own_refs.db"
N_LEVELS = [2, 5, 10, 20]
FETCH_N = 20


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


def fetch_ordered(client, aid, sort):
    """Ordered list of (work_id, set(refs)) wie von der API sortiert."""
    try:
        r = client.get("https://api.openalex.org/works", params={
            "filter": f"author.id:{aid}", "sort": sort, "per-page": FETCH_N,
            "select": "id,referenced_works"})
        r.raise_for_status()
        res = r.json().get("results", [])
    except Exception:
        return []
    out = []
    for w in res:
        wid = bz._bare(w.get("id"))
        refs = {bz._bare(x) for x in (w.get("referenced_works") or []) if x}
        refs.discard("")
        out.append((wid, refs))
    return out


def author_refs_at_N(recent, cited, n):
    seen, refs = set(), set()
    for wid, rs in recent[:n] + cited[:n]:
        if wid in seen:
            continue
        seen.add(wid); refs |= rs
    return refs, len(seen)


def classify(claims, works_hit, n_shared, zkey2cid):
    c = Counter()
    for pid in claims:
        cid = zkey2cid.get(pid)
        if cid is None:
            c["bad"] += 1
        elif cid in works_hit:
            c["corroborated"] += 1
        elif n_shared > 0:
            c["weak"] += 1
        else:
            c["ungrounded"] += 1
    return c


def main() -> int:
    oa2works, zkey2cid = load_attribution()
    own_oa = set(oa2works)

    # claim-articles + Erstautor (aus author_seed)
    con_bz = sqlite3.connect(str(bz.DEFAULT_DB)); con_bz.row_factory = sqlite3.Row
    seed = {r["article_id"]: r["author_oa_id"]
            for r in con_bz.execute("SELECT article_id, author_oa_id FROM author_seed WHERE role='first_author'")}
    con_bz.close()

    con = sqlite3.connect(str(ARTICLES_DB)); con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT id, openalex_refs, agent_entry_json FROM articles "
        "WHERE agent_entry_json IS NOT NULL AND openalex_id IS NOT NULL AND openalex_id!=''"
    ).fetchall()
    con.close()
    targets = [r for r in rows if llm_claims(r["agent_entry_json"]) and r["id"] in seed]
    authors = sorted({seed[r["id"]] for r in targets})
    print(f"Ziel: {len(targets)} Bezug-Artikel, {len(authors)} eindeutige Erstautoren")
    print(f"Ziehe {FETCH_N}+{FETCH_N} Werke je Autor …")

    client = bz.make_client()
    fetched = {}
    t0 = time.time(); calls = 0
    for i, aid in enumerate(authors, 1):
        recent = fetch_ordered(client, aid, "publication_date:desc"); calls += 1
        time.sleep(bz.THROTTLE_SECONDS)
        cited = fetch_ordered(client, aid, "cited_by_count:desc"); calls += 1
        time.sleep(bz.THROTTLE_SECONDS)
        fetched[aid] = (recent, cited)
        if i % 50 == 0:
            print(f"  … {i}/{len(authors)}")
    client.close()
    print(f"  {calls} API-Calls in {time.time()-t0:.0f}s\n")

    # Artikel-Ebene-Baseline
    def art_refs(r):
        try:
            s = {_normalize_oa_id(x) for x in json.loads(r["openalex_refs"] or "[]") if x}
        except json.JSONDecodeError:
            s = set()
        s.discard(""); return s

    print(f"{'Basis':<22}{'corrob':>8}{'weak':>8}{'ungrnd':>8}{'rescued':>9}{'⌀Werke':>8}{'⌀Refs':>8}")
    print("-" * 70)

    # N=0: Artikel-Ebene
    aud = Counter()
    for r in targets:
        sh = art_refs(r) & own_oa
        wh = set().union(*[oa2works[h] for h in sh]) if sh else set()
        aud += classify(llm_claims(r["agent_entry_json"]), wh, len(sh), zkey2cid)
    tot = sum(aud[k] for k in ("corroborated", "weak", "ungrounded", "bad"))
    print(f"{'Artikel-Ebene':<22}{100*aud['corroborated']/tot:>7.1f}%{100*aud['weak']/tot:>7.1f}%"
          f"{100*aud['ungrounded']/tot:>7.1f}%{'—':>9}{'—':>8}{'—':>8}")

    for n in N_LEVELS:
        aud = Counter(); rescued = 0; sum_w = 0; sum_r = 0
        for r in targets:
            aid = seed[r["id"]]
            recent, cited = fetched.get(aid, ([], []))
            arefs, nw = author_refs_at_N(recent, cited, n)
            sum_w += nw; sum_r += len(arefs)
            sh = arefs & own_oa
            wh = set().union(*[oa2works[h] for h in sh]) if sh else set()
            aud += classify(llm_claims(r["agent_entry_json"]), wh, len(sh), zkey2cid)
            if len(art_refs(r) & own_oa) == 0 and len(sh) > 0:
                rescued += 1
        tot = sum(aud[k] for k in ("corroborated", "weak", "ungrounded", "bad"))
        print(f"{('Autor N='+str(n)+'+'+str(n)):<22}{100*aud['corroborated']/tot:>7.1f}%"
              f"{100*aud['weak']/tot:>7.1f}%{100*aud['ungrounded']/tot:>7.1f}%"
              f"{rescued:>9}{sum_w/len(targets):>8.1f}{sum_r/len(targets):>8.0f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
