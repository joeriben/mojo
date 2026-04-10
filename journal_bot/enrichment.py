"""Enrichment-Layer: Crossref + OpenAlex.

Beide Dienste sind frei, kein Auth nötig. Wir bleiben höflich
(User-Agent, Polite Pool, Timeouts) und cachen Antworten lokal.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from journal_bot.settings import PROJECT_ROOT


CACHE_DIR = PROJECT_ROOT / ".enrichment_cache"
CACHE_DIR.mkdir(exist_ok=True)

POLITE_MAILTO = "journal-bot@localhost"
USER_AGENT = f"journal-bot/0.1 (mailto:{POLITE_MAILTO})"


@dataclass
class Reference:
    """Ein einzelner Eintrag aus dem Literaturverzeichnis eines Papers."""
    raw: str = ""
    authors: list[str] = field(default_factory=list)
    year: str = ""
    title: str = ""
    doi: str = ""
    journal: str = ""


def _cache_path(kind: str, key: str) -> Path:
    safe = hashlib.sha256(key.encode()).hexdigest()[:24]
    return CACHE_DIR / f"{kind}_{safe}.json"


def _cached_get(kind: str, key: str, url: str, timeout: float = 30) -> dict | None:
    cp = _cache_path(kind, key)
    if cp.exists():
        try:
            return json.loads(cp.read_text(encoding="utf-8"))
        except Exception:
            cp.unlink(missing_ok=True)
    try:
        resp = httpx.get(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            timeout=timeout,
            follow_redirects=True,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        cp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return data
    except Exception:
        return None


def get_references_crossref(doi: str) -> list[Reference]:
    """Crossref-API: liefert `reference` Array, wenn der Verlag es deponiert hat.

    Viele deutsche Geisteswissenschafts-Journals (Beltz, Brill) depositen leider
    keine Refs. Dann ist das Ergebnis leer — kein Fehler.
    """
    if not doi:
        return []
    doi = doi.strip().rstrip(".")
    url = f"https://api.crossref.org/works/{doi}?mailto={POLITE_MAILTO}"
    data = _cached_get("crossref", doi, url)
    if not data:
        return []
    message = data.get("message", {})
    refs_raw = message.get("reference", []) or []
    out: list[Reference] = []
    for r in refs_raw:
        authors: list[str] = []
        if r.get("author"):
            authors = [r["author"]]
        out.append(
            Reference(
                raw=r.get("unstructured", "") or "",
                authors=authors,
                year=r.get("year", "") or "",
                title=r.get("article-title", "") or r.get("volume-title", "") or "",
                doi=r.get("DOI", "") or "",
                journal=r.get("journal-title", "") or "",
            )
        )
    return out


def get_work_openalex(doi: str) -> dict | None:
    """OpenAlex-Work-Objekt per DOI. Enthält u.a. concepts, topics, referenced_works."""
    if not doi:
        return None
    doi = doi.strip().rstrip(".")
    url = f"https://api.openalex.org/works/doi:{doi}?mailto={POLITE_MAILTO}"
    return _cached_get("openalex_work", doi, url)


def get_work_title_openalex(openalex_id: str) -> dict | None:
    """OpenAlex-Work per ID (z.B. für referenced_works-Auflösung)."""
    if not openalex_id:
        return None
    # IDs kommen oft als URL; wir akzeptieren beides
    wid = openalex_id.rsplit("/", 1)[-1]
    url = f"https://api.openalex.org/works/{wid}?mailto={POLITE_MAILTO}"
    return _cached_get("openalex_work", wid, url)


def enrich(doi: str) -> dict:
    """Convenience: holt beides für ein DOI.

    Rückgabe:
      {
        "doi": ...,
        "references_crossref": [Reference, ...],  # oft leer
        "openalex": {
            "title": ..., "abstract": ..., "concepts": [...], "topics": [...],
            "referenced_works": [oa_ids], "cited_by_count": ...
        } | None
      }
    """
    result: dict = {"doi": doi}
    result["references_crossref"] = [
        r.__dict__ for r in get_references_crossref(doi)
    ]
    oa = get_work_openalex(doi)
    if oa:
        work = oa if "id" in oa else oa.get("message") or oa
        # OpenAlex returns the work directly (no .message wrapper)
        abstract_inv = work.get("abstract_inverted_index") or {}
        abstract = _reconstruct_abstract(abstract_inv) if abstract_inv else ""
        result["openalex"] = {
            "id": work.get("id", ""),
            "title": work.get("title", ""),
            "abstract": abstract,
            "publication_year": work.get("publication_year"),
            "concepts": [
                {"name": c.get("display_name"), "score": c.get("score")}
                for c in (work.get("concepts") or [])[:10]
            ],
            "topics": [
                {"name": t.get("display_name"), "score": t.get("score")}
                for t in (work.get("topics") or [])[:5]
            ],
            "referenced_works": (work.get("referenced_works") or [])[:50],
            "cited_by_count": work.get("cited_by_count", 0),
        }
    else:
        result["openalex"] = None
    return result


def _reconstruct_abstract(inverted: dict) -> str:
    """OpenAlex speichert Abstracts als Wort→Positionen-Invertierung. Zurückbauen."""
    if not inverted:
        return ""
    positions: dict[int, str] = {}
    for word, idxs in inverted.items():
        for i in idxs:
            positions[i] = word
    if not positions:
        return ""
    return " ".join(positions[i] for i in sorted(positions.keys()))
