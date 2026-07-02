"""Grounded Werk-Bezüge — algorithmische Alternative zur LLM-Kommentar-Prosa.

Motiv (Benjamin 2026-05-30): Die MOJO-1-Kommentare sind pseudo-hilfreich —
sie paraphrasieren/verschleiern das Abstract, ziehen weder Bibliografie noch
Volltext heran und konfabulieren Werk-Bezüge ("ERWEITERT Jörissen & X"), die
bibliografisch nicht gedeckt sind. Beispiel: "Data colonialism and indigenous
languages in AI" (AI&Society 2026) — von MOJO 1 als lesenswert mit zwei
konkreten Werk-Bezügen kommentiert, teilt aber NULL Referenzen mit Benjamins
Korpus und zitiert ihn nicht.

Dieses Skript baut den Teil "Bezüge zu Deinem Werk" rein algorithmisch aus
nachprüfbar geteilter Literatur:
  - Schnittmenge der Artikel-Referenzen (OpenAlex-IDs + DOIs) mit Benjamins
    pub_refs, attributiert auf das konkrete Werk (canonical_id → Titel/Jahr/Zotero).
  - Bei Null-Überschneidung: ehrliche Aussage statt erfundener Verbindung.

Kein LLM. Reine Daten-Assemblierung gegen own_refs.db + articles.db.

Usage:
  python scripts/grounded_bezug_demo.py [article_id ...]
  (ohne Argumente: Null-Fall + Top-Überschneidungs-Artikel automatisch)
"""

from __future__ import annotations

import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from journal_bot.signals import _normalize_doi_local, _normalize_oa_id
from journal_bot.own_refs.oa_titles import resolve_oa_titles

ARTICLES_DB = ROOT / "articles.db"
OWN_REFS_DB = ROOT / "own_refs.db"
INDIGENOUS_ID = "1be537b10af26c1485188e25a5e6f31b"  # MOJO-1-Negativbeispiel


def load_own_refs_attribution():
    """oa_id/doi → {canonical_id}, plus canonical_id → Werk-Metadaten."""
    con = sqlite3.connect(str(OWN_REFS_DB))
    con.row_factory = sqlite3.Row
    oa2works: dict[str, set[str]] = defaultdict(set)
    doi2works: dict[str, set[str]] = defaultdict(set)
    for r in con.execute("SELECT canonical_id, ref_doi, ref_oa_id FROM pub_refs"):
        if r["ref_oa_id"]:
            oa2works[_normalize_oa_id(r["ref_oa_id"])].add(r["canonical_id"])
        if r["ref_doi"]:
            doi2works[_normalize_doi_local(r["ref_doi"])].add(r["canonical_id"])
    oa2works.pop("", None)
    doi2works.pop("", None)

    meta: dict[str, dict] = {}
    for r in con.execute("SELECT canonical_id, title, year FROM publications"):
        meta[r["canonical_id"]] = {"title": r["title"] or "(ohne Titel)",
                                   "year": r["year"] or "", "zkey": ""}
    # Zotero-Key je Werk (source_item_id), bevorzugt zotero-Quelle
    for r in con.execute("SELECT canonical_id, source_item_id, source_type FROM source_refs"):
        if r["canonical_id"] in meta and r["source_item_id"] and not meta[r["canonical_id"]]["zkey"]:
            meta[r["canonical_id"]]["zkey"] = r["source_item_id"]
    con.close()
    return oa2works, doi2works, meta


def article_ref_sets(row) -> tuple[set[str], set[str], dict[str, str]]:
    """Normalisierte OA-IDs + DOIs des Artikels, plus DOI→Titel-Map (aus crossref)."""
    oa_ids: set[str] = set()
    if row["openalex_refs"]:
        try:
            for x in json.loads(row["openalex_refs"]):
                if x:
                    oa_ids.add(_normalize_oa_id(x))
        except json.JSONDecodeError:
            pass
    oa_ids.discard("")
    dois: set[str] = set()
    doi_title: dict[str, str] = {}
    if row["crossref_refs"]:
        try:
            for x in json.loads(row["crossref_refs"]):
                if not isinstance(x, dict):
                    continue
                d = _normalize_doi_local(x.get("doi"))
                if d.startswith("10."):
                    dois.add(d)
                    t = (x.get("article-title") or x.get("title")
                         or x.get("unstructured") or "")
                    if isinstance(t, list):
                        t = t[0] if t else ""
                    if t:
                        doi_title[d] = str(t)[:120]
        except json.JSONDecodeError:
            pass
    return oa_ids, dois, doi_title


def grounded_bezug(row, oa2works, doi2works, meta) -> dict:
    oa_ids, dois, doi_title = article_ref_sets(row)
    works_hit: dict[str, list[dict]] = defaultdict(list)
    shared_refs: set[str] = set()
    for oa in oa_ids & set(oa2works):
        wid = oa.rsplit("/", 1)[-1]
        shared_refs.add(f"oa:{wid}")
        for cid in oa2works[oa]:
            works_hit[cid].append({"oa": wid})
    for d in dois & set(doi2works):
        shared_refs.add(f"doi:{d}")
        for cid in doi2works[d]:
            works_hit[cid].append({"doi": d, "ctitle": doi_title.get(d)})
    return {
        "n_oa_refs": len(oa_ids), "n_doi_refs": len(dois),
        "works_hit": works_hit, "n_shared_refs": len(shared_refs),
    }


def _ref_label(desc: dict, oa_titles: dict) -> str:
    if "oa" in desc:
        info = oa_titles.get(desc["oa"], {})
        t = info.get("title")
        if t:
            yr = info.get("year")
            return f"»{t[:84]}«{f' ({yr})' if yr else ''}"
        return f"OpenAlex {desc['oa']} (Titel nicht auflösbar)"
    t = desc.get("ctitle")
    if t:
        return f"»{t[:84]}« [doi:{desc['doi']}]"
    return f"doi:{desc['doi']}"


def render(row, gb, meta, oa_titles) -> str:
    lines = []
    cites_benjamin = bool(json.loads(row["citation_hits_json"] or "[]"))
    if not gb["works_hit"]:
        lines.append("Bezüge zu Deinem Werk: KEINE nachweisbare bibliografische Anbindung.")
        lines.append(f"  · Artikel zitiert dich: {'ja' if cites_benjamin else 'nein'}.")
        lines.append(f"  · Geteilte Referenzen mit deinem Korpus (161 Werke): 0 "
                     f"(von {gb['n_oa_refs']} OA- + {gb['n_doi_refs']} DOI-Refs des Artikels).")
        lines.append("  · → thematisch benachbart möglich, aber keine belegbare Werk-Verbindung. "
                     "Keine Bezugs-Behauptung.")
        return "\n".join(lines)
    lines.append(f"Bezüge zu Deinem Werk: {gb['n_shared_refs']} geteilte Referenz(en), "
                 f"belegt über {len(gb['works_hit'])} deiner Werke "
                 f"(Artikel zitiert dich: {'ja' if cites_benjamin else 'nein'}).")
    ranked = sorted(gb["works_hit"].items(), key=lambda kv: len(kv[1]), reverse=True)
    for cid, refs in ranked[:6]:
        m = meta.get(cid, {"title": cid, "year": "", "zkey": ""})
        zk = f" [Zotero {m['zkey']}]" if m["zkey"] else ""
        lines.append(f"  · »{m['title'][:80]}« ({m['year']}){zk}")
        for ref in refs[:4]:
            lines.append(f"        ↳ via {_ref_label(ref, oa_titles)}")
        if len(refs) > 4:
            lines.append(f"        ↳ … +{len(refs) - 4} weitere")
    return "\n".join(lines)


def mojo1_comment(row) -> str:
    try:
        e = json.loads(row["agent_entry_json"] or "{}")
    except json.JSONDecodeError:
        return "(kein Agent-Eintrag)"
    parts = []
    if e.get("kernthese"):
        parts.append("Kernthese: " + str(e["kernthese"])[:300])
    bez = e.get("bezuege") or e.get("bezüge") or []
    if isinstance(bez, list) and bez:
        for b in bez[:3]:
            if isinstance(b, dict):
                parts.append("  Bezug: " + str(b.get("text") or b.get("beschreibung") or b)[:220])
            else:
                parts.append("  Bezug: " + str(b)[:220])
    return "\n".join(parts) if parts else "(leer)"


def main() -> int:
    oa2works, doi2works, meta = load_own_refs_attribution()
    con = sqlite3.connect(str(ARTICLES_DB))
    con.row_factory = sqlite3.Row

    ids = sys.argv[1:]
    if not ids:
        # Auto: Null-Fall + Top-Überschneidungs-Artikel unter user=lesenswert
        cand = con.execute(
            "SELECT id, openalex_refs, crossref_refs, citation_hits_json "
            "FROM articles WHERE user_verdict='lesenswert' AND agent_entry_json IS NOT NULL"
        ).fetchall()
        scored = []
        for r in cand:
            gb = grounded_bezug(r, oa2works, doi2works, meta)
            if gb["n_shared_refs"] > 0:
                scored.append((gb["n_shared_refs"], r["id"]))
        scored.sort(reverse=True)
        ids = [INDIGENOUS_ID] + [i for _, i in scored[:2]]

    # Pass 1: rows + grounded_bezug; OA-IDs für Titel-Auflösung sammeln
    prepared = []
    all_oa: set[str] = set()
    for art_id in ids:
        row = con.execute("SELECT * FROM articles WHERE id=?", (art_id,)).fetchone()
        if not row:
            print(f"[nicht gefunden] {art_id}\n")
            continue
        gb = grounded_bezug(row, oa2works, doi2works, meta)
        for refs in gb["works_hit"].values():
            for d in refs:
                if "oa" in d:
                    all_oa.add(d["oa"])
        prepared.append((art_id, row, gb))

    oa_titles = resolve_oa_titles(all_oa) if all_oa else {}

    # Pass 2: rendern
    for art_id, row, gb in prepared:
        print("=" * 92)
        print(f"{row['journal_short']} {row['year']}  | user={row['user_verdict']} "
              f"agent={row['agent_verdict']}  | id={art_id[:16]}")
        print(f"TITEL: {row['title']}")
        print("-" * 92)
        ab = (row["abstract"] or row["openalex_abstract"] or "").strip()
        print("ABSTRACT (Original, präzise):")
        print("  " + (ab[:600] + (" …" if len(ab) > 600 else "") if ab else "(kein Abstract)"))
        print("-" * 92)
        print("MOJO-1-KOMMENTAR (LLM, abstract-basiert):")
        print("  " + mojo1_comment(row).replace("\n", "\n  "))
        print("-" * 92)
        print("GROUNDED (algorithmisch, aus geteilter Literatur):")
        print("  " + render(row, gb, meta, oa_titles).replace("\n", "\n  "))
        print()
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
