"""Substitutiver Eintrags-Komponist — Digest-Eintrag aus Daten statt LLM-Prosa.

Motiv (Benjamin 2026-05-31, Korpus-Audit `scripts/grounded_vs_llm_corpus.py`):
Die LLM-Kommentare konfabulieren Werk-Bezüge — von 347 expliziten Behauptungen
waren nur 12,7 % corroborated, 55,9 % ungrounded. Festlegung: Der Eintrag wird
SUBSTITUTIV komponiert — Abstract verbatim + gerechnete Signale + geerdete
Bezüge + ehrliche Leerstelle. Das LLM verlässt die Erzähler-Rolle; seine
Analyse bleibt gespeichert (§4-Erhalt), wird in der Darstellung aber
nachgeordnet und als ungeerdert markiert.

Bausteine (alle [gerechnet], kein LLM):
  - grounded: Schnittmenge der Artikel-Referenzen (OpenAlex-IDs + DOIs) mit
    Benjamins pub_refs (own_refs.db), attributiert auf konkrete Eigenwerke
    (canonical_id → Titel/Jahr/Zotero-Key). Null-Überschneidung → explizite
    Leerstelle statt erfundener Verbindung.
  - umfeld: Autor-Ebenen-Annotation aus bezugsautoren.db — (a) koppelt das
    Œuvre des Erstautors dieses Artikels mit dem Eigenkorpus, (b) zitiert der
    Artikel Werke von Umfeld-Autoren (Erstautoren früherer MOJO-Sichtungen);
    der eigene Erstautor ist dabei ausgeschlossen (sonst zählten
    Selbstzitationen als Umfeld). WICHTIG (iter_44, blindes Sample): Kopplung
    trennt NICHT Relevanz — reine Annotation, nie Ranking oder Verdikt.

Der Komponist verändert keine Verdikte und keine agent_entry-Daten; er
schreibt ausschließlich `composed_entry_json` (additive MOJO-2-Schicht).
Beide Quell-DBs sind optional: fehlt eine, degradiert der Baustein sichtbar
(`available: false`) statt zu raten.
"""

from __future__ import annotations

import json
import re
import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from journal_bot.signals import _normalize_doi_local, _normalize_oa_id

if TYPE_CHECKING:  # pragma: no cover
    from journal_bot.store import Store, StoredArticle

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OWN_REFS_DB = PROJECT_ROOT / "own_refs.db"
BEZUGSAUTOREN_DB = PROJECT_ROOT / "bezugsautoren.db"

COMPOSER_VERSION = 1
# Kappungen halten composed_entry_json klein; die vollen Mengen sind aus den
# Quell-DBs jederzeit rekonstruierbar (Komposition, kein Index).
MAX_WORKS = 12          # meist-gekoppelte Eigenwerke je Eintrag
MAX_VIA_PER_WORK = 6    # geteilte Referenzen je Eigenwerk
MAX_UMFELD_CITED = 8    # zitierte Umfeld-Autoren-Werke


# ── Ressourcen (einmal laden, über Artikel wiederverwenden) ──────────────────

@dataclass
class ComposerResources:
    """own_refs-Attribution im Speicher; bezugsautoren.db wird pro Artikel
    per SQL abgefragt (kann nach Skalierung sechsstellige Zeilen haben)."""

    oa2works: dict[str, set[str]] = field(default_factory=dict)
    doi2works: dict[str, set[str]] = field(default_factory=dict)
    work_meta: dict[str, dict] = field(default_factory=dict)
    n_publications: int = 0
    own_refs_available: bool = False
    bezugsautoren_path: Path = BEZUGSAUTOREN_DB
    bezugsautoren_available: bool = False


def load_composer_resources(
    own_refs_db: Path = OWN_REFS_DB,
    bezugsautoren_db: Path = BEZUGSAUTOREN_DB,
) -> ComposerResources:
    res = ComposerResources(bezugsautoren_path=bezugsautoren_db)
    res.bezugsautoren_available = bezugsautoren_db.exists()
    if not own_refs_db.exists():
        return res

    con = sqlite3.connect(str(own_refs_db))
    con.row_factory = sqlite3.Row
    try:
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
            meta[r["canonical_id"]] = {
                "title": r["title"] or "(ohne Titel)",
                "year": r["year"] or "",
                "zotero_key": "",
            }
        for r in con.execute(
            "SELECT canonical_id, source_item_id FROM source_refs"
        ):
            m = meta.get(r["canonical_id"])
            if m is not None and r["source_item_id"] and not m["zotero_key"]:
                m["zotero_key"] = r["source_item_id"]
    finally:
        con.close()

    res.oa2works = dict(oa2works)
    res.doi2works = dict(doi2works)
    res.work_meta = meta
    res.n_publications = len(meta)
    res.own_refs_available = True
    return res


_RESOURCES: ComposerResources | None = None


def get_resources(refresh: bool = False) -> ComposerResources:
    """Modulweiter Cache — der Wochenlauf lädt die Attribution genau einmal."""
    global _RESOURCES
    if _RESOURCES is None or refresh:
        _RESOURCES = load_composer_resources()
    return _RESOURCES


# ── Artikel-Referenzmengen ───────────────────────────────────────────────────

def _clean_title(t: str | None) -> str | None:
    """OpenAlex/Crossref-Titel tragen teils rohe HTML-Tags (<i>…</i>)."""
    if not t:
        return t
    return re.sub(r"<[^>]+>", "", str(t)).strip() or None


def article_ref_sets(
    openalex_refs: list[str] | None,
    crossref_refs: list[dict] | None,
) -> tuple[set[str], set[str], dict[str, str]]:
    """Normalisierte OA-IDs + DOIs des Artikels, plus DOI→Titel (aus Crossref)."""
    oa_ids = {_normalize_oa_id(x) for x in (openalex_refs or []) if x}
    oa_ids.discard("")
    dois: set[str] = set()
    doi_title: dict[str, str] = {}
    for x in crossref_refs or []:
        if not isinstance(x, dict):
            continue
        d = _normalize_doi_local(x.get("doi"))
        if not d.startswith("10."):
            continue
        dois.add(d)
        t = x.get("article-title") or x.get("title") or x.get("unstructured") or ""
        if isinstance(t, list):
            t = t[0] if t else ""
        t = _clean_title(str(t)) if t else None
        if t:
            doi_title[d] = t[:160]
    return oa_ids, dois, doi_title


# ── Baustein 1: grounded Werk-Bezüge ─────────────────────────────────────────

def _grounded_block(
    oa_ids: set[str],
    dois: set[str],
    doi_title: dict[str, str],
    res: ComposerResources,
    oa_titles: dict[str, dict] | None,
) -> dict:
    works_hit: dict[str, list[dict]] = defaultdict(list)
    shared_refs: set[str] = set()
    for oa in oa_ids & set(res.oa2works):
        shared_refs.add(f"oa:{oa}")
        for cid in res.oa2works[oa]:
            info = (oa_titles or {}).get(oa) or {}
            works_hit[cid].append({
                "kind": "oa", "id": oa,
                "title": _clean_title(info.get("title")), "year": info.get("year"),
            })
    for d in dois & set(res.doi2works):
        shared_refs.add(f"doi:{d}")
        for cid in res.doi2works[d]:
            works_hit[cid].append({
                "kind": "doi", "id": d,
                "title": doi_title.get(d), "year": None,
            })

    ranked = sorted(works_hit.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    works = []
    for cid, refs in ranked[:MAX_WORKS]:
        m = res.work_meta.get(
            cid, {"title": cid, "year": "", "zotero_key": ""}
        )
        works.append({
            "pub_id": cid,
            "title": m["title"],
            "year": m["year"],
            "zotero_key": m["zotero_key"],
            "n_shared": len(refs),
            "via": refs[:MAX_VIA_PER_WORK],
            "n_via_more": max(0, len(refs) - MAX_VIA_PER_WORK),
        })
    return {
        "available": res.own_refs_available,
        "n_oa_refs": len(oa_ids),
        "n_doi_refs": len(dois),
        "n_shared_refs": len(shared_refs),
        "n_works_hit": len(works_hit),
        "n_corpus_works": res.n_publications,
        "works": works,
    }


# ── Baustein 2: Umfeld-Annotation (Autor-Ebene) ──────────────────────────────

def _umfeld_block(
    article_id: str,
    oa_ids: set[str],
    res: ComposerResources,
) -> dict:
    out: dict = {
        "available": False,
        "first_author": None,
        "cited_works": [],
        "n_cited_works": 0,
    }
    if not res.bezugsautoren_available or not res.bezugsautoren_path.exists():
        return out

    con = sqlite3.connect(str(res.bezugsautoren_path))
    con.row_factory = sqlite3.Row
    try:
        out["available"] = True
        # (a) Erstautor dieses Artikels: koppelt sein Œuvre mit dem Eigenkorpus?
        seeded = [
            r["author_oa_id"]
            for r in con.execute(
                "SELECT author_oa_id FROM author_seed WHERE article_id=?",
                (article_id,),
            )
        ]
        own_oa = set(res.oa2works)
        if seeded:
            aid = seeded[0]
            arow = con.execute(
                "SELECT display_name, n_works_fetched FROM authors "
                "WHERE author_oa_id=?",
                (aid,),
            ).fetchone()
            refs: set[str] = set()
            for (rj,) in con.execute(
                "SELECT referenced_works_json FROM author_works "
                "WHERE author_oa_id=?",
                (aid,),
            ):
                if rj:
                    try:
                        refs.update(json.loads(rj))
                    except json.JSONDecodeError:
                        pass
            refs.discard("")
            shared = refs & own_oa
            hit_works: set[str] = set()
            for h in shared:
                hit_works |= res.oa2works.get(h, set())
            out["first_author"] = {
                "oa_id": aid,
                "name": (arow["display_name"] if arow else "") or "",
                "n_works_sampled": (arow["n_works_fetched"] if arow else 0) or 0,
                "n_shared_refs": len(shared),
                "n_own_works": len(hit_works),
            }

        # (b) Artikel zitiert Werke von Umfeld-Autoren (eigener Erstautor raus)
        if oa_ids:
            ph = ",".join("?" * len(oa_ids))
            rows = con.execute(
                f"""
                SELECT aw.work_oa_id, aw.title, aw.publication_year,
                       au.display_name
                FROM author_works aw
                JOIN authors au ON au.author_oa_id = aw.author_oa_id
                WHERE aw.work_oa_id IN ({ph})
                  AND aw.author_oa_id NOT IN (
                      SELECT author_oa_id FROM author_seed WHERE article_id=?
                  )
                ORDER BY aw.cited_by_count DESC
                """,
                (*sorted(oa_ids), article_id),
            ).fetchall()
            by_work: dict[str, dict] = {}
            for r in rows:
                w = by_work.setdefault(r["work_oa_id"], {
                    "oa_id": r["work_oa_id"],
                    "title": _clean_title(r["title"]) or "(ohne Titel)",
                    "year": r["publication_year"],
                    "authors": [],
                })
                if r["display_name"] and r["display_name"] not in w["authors"]:
                    w["authors"].append(r["display_name"])
            cited = list(by_work.values())
            out["n_cited_works"] = len(cited)
            out["cited_works"] = cited[:MAX_UMFELD_CITED]
    finally:
        con.close()
    return out


# ── Komposition ──────────────────────────────────────────────────────────────

def compose_entry(
    sa: "StoredArticle",
    resources: ComposerResources | None = None,
    *,
    citation_hits: list[dict] | None = None,
    resolve_titles: bool = True,
) -> dict:
    """Komponiert den substitutiven Eintrag für einen Artikel.

    `citation_hits`: frische Hits aus dem Agent-Result (falls der Store-Stand
    noch alt ist); default = der gespeicherte Stand. `resolve_titles=False`
    unterdrückt den (gecachten) OpenAlex-Titel-Lookup — für Tests/Offline.
    """
    res = resources or get_resources()
    oa_ids, dois, doi_title = article_ref_sets(sa.openalex_refs, sa.crossref_refs)

    oa_titles: dict[str, dict] = {}
    shared_oa = oa_ids & set(res.oa2works)
    if resolve_titles and shared_oa:
        from journal_bot.own_refs.oa_titles import resolve_oa_titles
        try:
            oa_titles = resolve_oa_titles(shared_oa)
        except Exception:
            oa_titles = {}

    grounded = _grounded_block(oa_ids, dois, doi_title, res, oa_titles)
    umfeld = _umfeld_block(sa.id, oa_ids, res)

    hits = citation_hits if citation_hits is not None else (sa.citation_hits or [])
    fa = umfeld.get("first_author") or {}
    if grounded["works"] or umfeld["cited_works"] or hits:
        einordnung = "konkret"      # artikel-eigener, verifizierbarer Anker
    elif fa.get("n_shared_refs", 0) > 0:
        einordnung = "umfeld"       # nur Autor-Ebene koppelt, Artikel nicht
    else:
        einordnung = "leer"         # ehrliche Leerstelle

    return {
        "composer_version": COMPOSER_VERSION,
        "composed_at": datetime.now(timezone.utc).isoformat(),
        "einordnung": einordnung,
        "n_citation_hits": len(hits),
        "grounded": grounded,
        "umfeld": umfeld,
    }


def compose_and_store(
    store: "Store",
    sa: "StoredArticle",
    resources: ComposerResources | None = None,
    *,
    citation_hits: list[dict] | None = None,
    resolve_titles: bool = True,
) -> dict:
    composed = compose_entry(
        sa, resources, citation_hits=citation_hits, resolve_titles=resolve_titles
    )
    store.update_composed_entry(sa.id, composed)
    return composed
