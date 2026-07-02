"""Diagnose der Sample-Kontamination (Benjamins Einwand).

(1) Recency: MOJO ist Wochen-Scanner → alte Artikel sind kategorial ungeeignet.
(3) Eigener Fußabdruck: Selbst-/Ko-Autorschaft + eigene Projekte → 'muss ich kennen',
    kein Relevanzsignal. Diese Items blähen die Kopplungs-Korrelation künstlich auf.

Beziffert: Jahrgänge × Bucket, Selbst-Autorschaft, Ko-Autor-Overlap (aus Zotero-Bibliothek),
und wie viele Items je Bucket unter Recency-Cutoffs + Eigen-Umfeld-Ausschluss übrig bleiben.
"""

from __future__ import annotations

import json
import sqlite3
import sys
import unicodedata
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
ZOTERO_LIB = ROOT / "zotero_library.json"


def _norm_last(name: str) -> str:
    """Nachname → ascii-lower, letzter Token (vor Komma falls 'Last, First')."""
    name = (name or "").strip()
    if not name:
        return ""
    last = name.split(",")[0].strip() if "," in name else name.split()[-1]
    last = unicodedata.normalize("NFKD", last).encode("ascii", "ignore").decode().lower()
    return last


def benjamin_coauthors() -> set[str]:
    """Nachnamen aller Ko-Autor:innen aus Benjamins Zotero-Bibliothek (ohne ihn selbst)."""
    if not ZOTERO_LIB.exists():
        return set()
    try:
        data = json.loads(ZOTERO_LIB.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return set()
    items = data.values() if isinstance(data, dict) else data
    out: set[str] = set()
    for it in items:
        d = it.get("data", it) if isinstance(it, dict) else {}
        for cr in (d.get("creators") or []):
            last = _norm_last(cr.get("lastName") or cr.get("name") or "")
            if last and "orissen" not in last:
                out.add(last)
    return out


def llm_claims(entry_json):
    try:
        d = json.loads(entry_json or "{}")
        return [str(b["pub_id"]).strip() for b in (d.get("bezuege") or d.get("bezüge") or [])
                if isinstance(b, dict) and b.get("pub_id")]
    except json.JSONDecodeError:
        return []


def article_lastnames(authors_json):
    try:
        a = json.loads(authors_json or "[]")
    except json.JSONDecodeError:
        return []
    out = []
    for x in a:
        nm = x if isinstance(x, str) else (x.get("name") or x.get("display_name") or "" if isinstance(x, dict) else "")
        if nm:
            out.append(_norm_last(nm))
    return out


def main() -> int:
    own = load_own_refs_index(OWN_REFS_DB)
    own_oa = own.oa_ids
    cf = load_or_compute_corpus_freq(ARTICLES_DB, own)
    con_o = sqlite3.connect(str(OWN_REFS_DB)); con_o.row_factory = sqlite3.Row
    oa2works = defaultdict(set)
    for r in con_o.execute("SELECT canonical_id, ref_oa_id FROM pub_refs"):
        if r["ref_oa_id"]:
            oa2works[_normalize_oa_id(r["ref_oa_id"])].add(r["canonical_id"])
    oa2works.pop("", None)
    zkey2cid = {r["source_item_id"]: r["canonical_id"]
                for r in con_o.execute("SELECT canonical_id, source_item_id FROM source_refs")
                if r["source_item_id"]}
    con_o.close()

    coauthors = benjamin_coauthors()
    print(f"Benjamins Ko-Autor-Nachnamen aus Zotero: {len(coauthors)}")

    con_bz = sqlite3.connect(str(bz.DEFAULT_DB)); con_bz.row_factory = sqlite3.Row
    seed = {r["article_id"]: r["author_oa_id"]
            for r in con_bz.execute("SELECT article_id, author_oa_id FROM author_seed WHERE role='first_author'")}

    con = sqlite3.connect(str(ARTICLES_DB)); con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT id, year, authors_json, abstract, openalex_abstract, agent_entry_json FROM articles "
        "WHERE agent_entry_json IS NOT NULL AND openalex_id IS NOT NULL AND openalex_id!='' "
        "AND (user_verdict IS NULL OR user_verdict='')"
    ).fetchall()
    con.close()

    pool = []
    for r in rows:
        if not (llm_claims(r["agent_entry_json"]) and r["id"] in seed):
            continue
        ab = (r["abstract"] or "").strip()
        if not ab or ab.startswith("{"):
            ab = (r["openalex_abstract"] or "").strip()
        if not ab or ab.startswith("{"):
            continue
        aid = seed[r["id"]]
        shared = bz.author_ref_set(con_bz, aid) & own_oa
        wh = set().union(*[oa2works[h] for h in shared]) if shared else set()
        idf = bz.coupling_idf(shared, cf)
        claims = llm_claims(r["agent_entry_json"])
        if any(zkey2cid.get(p) in wh for p in claims):
            bucket = "corroborated"
        elif idf >= bz.AUTHOR_COUPLING_WEAK:
            bucket = "weak"
        else:
            bucket = "ungrounded"
        lasts = article_lastnames(r["authors_json"])
        try:
            yr = int(str(r["year"])[:4])
        except (ValueError, TypeError):
            yr = 0
        is_self = any("orissen" in ln for ln in lasts)
        is_coauthor = bool(set(lasts) & coauthors)
        pool.append({"year": yr, "bucket": bucket, "self": is_self, "coauthor": is_coauthor})
    con_bz.close()

    print(f"\nUngelabelte Bezug-Artikel mit Abstract: {len(pool)}\n")

    # Jahrgang × Bucket
    years = sorted({p["year"] for p in pool})
    print("Jahrgang × Bucket:")
    print(f"  {'Jahr':>6} | {'corrob':>7}{'weak':>6}{'ungrnd':>7} | {'Σ':>4}")
    for y in years:
        sub = [p for p in pool if p["year"] == y]
        c = Counter(p["bucket"] for p in sub)
        print(f"  {y:>6} | {c['corroborated']:>7}{c['weak']:>6}{c['ungrounded']:>7} | {len(sub):>4}")

    # Eigen-Fußabdruck
    n_self = sum(p["self"] for p in pool)
    n_co = sum(p["coauthor"] for p in pool)
    n_any = sum(p["self"] or p["coauthor"] for p in pool)
    print(f"\nEigener Fußabdruck im Pool:")
    print(f"  selbst (Jörissen) Autor:   {n_self}")
    print(f"  Ko-Autor:in (Zotero):      {n_co}")
    print(f"  selbst ODER Ko-Autor:      {n_any}  ({100*n_any/len(pool):.0f}%)")
    # Footprint nach Bucket
    print("  davon nach Bucket (selbst|ko):")
    for b in ("corroborated", "weak", "ungrounded"):
        sub = [p for p in pool if p["bucket"] == b]
        print(f"    {b:<13}: {sum(p['self'] or p['coauthor'] for p in sub)}/{len(sub)}")

    # Übrig je Cutoff nach Eigen-Umfeld-Ausschluss
    print("\nÜbrig je Recency-Cutoff NACH Ausschluss (selbst ∨ Ko-Autor):")
    print(f"  {'cutoff':>7} | {'corrob':>7}{'weak':>6}{'ungrnd':>7} | {'Σ':>4}")
    for cut in (2022, 2023, 2024, 2025):
        sub = [p for p in pool if p["year"] >= cut and not (p["self"] or p["coauthor"])]
        c = Counter(p["bucket"] for p in sub)
        print(f"  ≥{cut:>5} | {c['corroborated']:>7}{c['weak']:>6}{c['ungrounded']:>7} | {len(sub):>4}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
