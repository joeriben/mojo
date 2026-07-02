"""IDF-gewichtete Autor-Kopplung: Kalibrierung gegen Null-Kontrolle.

Setzt um (Benjamin „mach das so"): N=30 (Modul-Default) + IDF-Gewichtung auf die
Autor-Kopplung. Zieht die 222 Bezug-Autoren auf N=30 in bezugsautoren.db nach,
zieht eine Null-Kontrolle (ignorierte Artikel ohne Bezug) frisch, und sweept die
IDF-Schwelle: gesucht ist der Wert, bei dem die Kontroll-Kopplung (~40 % binär)
einbricht, die Bezug-Kopplung aber hoch bleibt.

corpus_freq.idf_weight_oa: häufige Refs ~0, seltene bis 1,44.
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
from journal_bot.own_refs.corpus_freq import load_or_compute_corpus_freq
from journal_bot.own_refs.index import load_own_refs_index
from journal_bot.signals import _normalize_oa_id

ARTICLES_DB = ROOT / "articles.db"
OWN_REFS_DB = ROOT / "own_refs.db"
N_CONTROL = 150
THRESHOLDS = [0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0]


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


def fetch_author_refs(client, aid):
    refs = set()
    for sort in ("publication_date:desc", "cited_by_count:desc"):
        try:
            r = client.get("https://api.openalex.org/works", params={
                "filter": f"author.id:{aid}", "sort": sort,
                "per-page": bz.RECENT_N, "select": "id,referenced_works"})
            r.raise_for_status()
            for w in r.json().get("results", []):
                refs |= {bz._bare(x) for x in (w.get("referenced_works") or []) if x}
        except Exception:
            pass
        time.sleep(bz.THROTTLE_SECONDS)
    refs.discard("")
    return refs


def main() -> int:
    own = load_own_refs_index(OWN_REFS_DB)
    own_oa = own.oa_ids
    cf = load_or_compute_corpus_freq(ARTICLES_DB, own)
    oa2works, zkey2cid = load_attribution()

    con_bz = sqlite3.connect(str(bz.DEFAULT_DB)); con_bz.row_factory = sqlite3.Row
    bz.init_db(con_bz)
    seed = {r["article_id"]: r["author_oa_id"]
            for r in con_bz.execute("SELECT article_id, author_oa_id FROM author_seed WHERE role='first_author'")}

    con = sqlite3.connect(str(ARTICLES_DB)); con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT id, openalex_id, agent_verdict, agent_entry_json FROM articles "
        "WHERE agent_entry_json IS NOT NULL AND openalex_id IS NOT NULL AND openalex_id!=''"
    ).fetchall()
    con.close()
    claim_rows = [r for r in rows if llm_claims(r["agent_entry_json"]) and r["id"] in seed]
    bezug_authors = sorted({seed[r["id"]] for r in claim_rows})

    client = bz.make_client()
    print(f"1) Bezug-Autoren auf N={bz.RECENT_N} nachziehen ({len(bezug_authors)}) …")
    for i, aid in enumerate(bezug_authors, 1):
        bz.refresh_author(con_bz, client, aid, force=True)
        if i % 50 == 0:
            print(f"   … {i}/{len(bezug_authors)}")

    # IDF-Profil je Bezug-Autor
    bez_prof = {}
    for aid in bezug_authors:
        shared = bz.author_ref_set(con_bz, aid) & own_oa
        wh = set().union(*[oa2works[h] for h in shared]) if shared else set()
        bez_prof[aid] = (shared, bz.coupling_idf(shared, cf), wh)

    print(f"2) Null-Kontrolle ziehen (ignoriert, kein Bezug; bis {N_CONTROL}) …")
    ign = [r for r in rows if r["agent_verdict"] == "ignorieren" and not llm_claims(r["agent_entry_json"])]
    step = max(1, len(ign) // N_CONTROL)
    ctrl_scores = []
    seen = set()
    for i, r in enumerate(ign[::step][:N_CONTROL], 1):
        fa = bz.fetch_first_author(client, r["openalex_id"]); time.sleep(bz.THROTTLE_SECONDS)
        if not fa or fa[0] in seen:
            continue
        seen.add(fa[0])
        shared = fetch_author_refs(client, fa[0]) & own_oa
        ctrl_scores.append(bz.coupling_idf(shared, cf))
        if i % 50 == 0:
            print(f"   … {i}")
    client.close(); con_bz.close()
    print(f"   Kontroll-Autoren: {len(ctrl_scores)}\n")

    print(f"{'IDF-thr':>8} | {'Bezug-Kopp%':>11} | {'Kontr-Kopp%':>11} | {'Δ':>6} | "
          f"{'corrob':>7}{'weak':>6}{'ungrnd':>7}")
    print("-" * 72)
    for thr in THRESHOLDS:
        bez_coupled = sum(1 for (_, idf, _) in bez_prof.values() if idf >= thr) if thr > 0 \
            else sum(1 for (sh, _, _) in bez_prof.values() if sh)
        ctrl_coupled = sum(1 for s in ctrl_scores if (s >= thr if thr > 0 else s > 0))
        bez_rate = 100 * bez_coupled / len(bez_prof)
        ctrl_rate = 100 * ctrl_coupled / max(1, len(ctrl_scores))
        # Abgleich über Claims
        aud = Counter()
        for r in claim_rows:
            sh, idf, wh = bez_prof[seed[r["id"]]]
            coupled = (idf >= thr) if thr > 0 else bool(sh)
            for pid in llm_claims(r["agent_entry_json"]):
                cid = zkey2cid.get(pid)
                if cid is None:
                    aud["bad"] += 1
                elif cid in wh:
                    aud["corroborated"] += 1
                elif coupled:
                    aud["weak"] += 1
                else:
                    aud["ungrounded"] += 1
        tot = sum(aud[k] for k in ("corroborated", "weak", "ungrounded", "bad")) or 1
        print(f"{thr:>8.1f} | {bez_rate:>10.1f}% | {ctrl_rate:>10.1f}% | {bez_rate-ctrl_rate:>6.1f} | "
              f"{100*aud['corroborated']/tot:>6.1f}%{100*aud['weak']/tot:>5.1f}%{100*aud['ungrounded']/tot:>6.1f}%")
    print("\nthr=0.0 = binär (≥1 Ref, alter Stand). Gesucht: Δ groß, Kontrolle niedrig.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
