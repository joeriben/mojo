"""Enrichment-Layer: Crossref + OpenAlex.

Beide Dienste sind frei, kein Auth nötig. Wir bleiben höflich
(User-Agent, Polite Pool, Timeouts) und cachen Antworten lokal.
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from journal_bot.settings import PROJECT_ROOT


CACHE_DIR = PROJECT_ROOT / ".enrichment_cache"
CACHE_DIR.mkdir(exist_ok=True)

POLITE_MAILTO = "mojo@localhost"
USER_AGENT = f"mojo/0.1 (mailto:{POLITE_MAILTO})"

# OpenAlex trägt Abstracts oft Wochen nach Titel/DOI nach. Ein Work-Cache OHNE
# Verfallsdatum friert genau die frühe, abstract-lose Fassung ein (belegt: 68 %
# der abstract-losen 2024+-Artikel haben bei OpenAlex HEUTE einen Abstract, den
# wir nur wegen des Dauer-Caches nie nachziehen). Deshalb ein TTL auf den
# Work-per-DOI-Abruf. Referenz-Auflösung (per ID) bleibt dauerhaft.
OPENALEX_WORK_TTL_DAYS = 21


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


def _cache_age_days(cp: Path) -> float:
    try:
        return (time.time() - cp.stat().st_mtime) / 86400.0
    except OSError:
        return float("inf")


def _cached_get(
    kind: str,
    key: str,
    url: str,
    timeout: float = 30,
    max_age_days: float | None = None,
    force: bool = False,
) -> dict | None:
    """Gecachter GET. `max_age_days`/`force` erlauben gezieltes Nachfassen.

    Ein zu altes (oder per `force` übergangenes) Cache-Objekt wird neu geholt;
    schlägt der Neuabruf fehl, bleibt der alte Stand erhalten (besser als nichts).
    """
    cp = _cache_path(kind, key)
    cached: dict | None = None
    if cp.exists():
        try:
            cached = json.loads(cp.read_text(encoding="utf-8"))
        except Exception:
            cp.unlink(missing_ok=True)
    frisch = max_age_days is None or _cache_age_days(cp) <= max_age_days
    if cached is not None and frisch and not force:
        return cached
    try:
        resp = httpx.get(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            timeout=timeout,
            follow_redirects=True,
        )
        if resp.status_code != 200:
            return cached
        data = resp.json()
        cp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return data
    except Exception:
        return cached


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


def get_work_openalex(doi: str, force: bool = False) -> dict | None:
    """OpenAlex-Work-Objekt per DOI. Enthält u.a. concepts, topics, referenced_works.

    Der Work-Cache verfällt nach `OPENALEX_WORK_TTL_DAYS`, damit später
    nachgetragene Abstracts ankommen; `force` erzwingt sofortiges Nachfassen
    (für den gezielten Abstract-Nachzug).
    """
    if not doi:
        return None
    doi = doi.strip().rstrip(".")
    url = f"https://api.openalex.org/works/doi:{doi}?mailto={POLITE_MAILTO}"
    return _cached_get("openalex_work", doi, url,
                       max_age_days=OPENALEX_WORK_TTL_DAYS, force=force)


def _norm_title(s: str) -> str:
    return "".join(ch for ch in (s or "").lower() if ch.isalnum())


def _title_words(s: str) -> list[str]:
    import re
    return [w for w in re.findall(r"[a-z0-9]+", (s or "").lower()) if len(w) >= 3]


def _titles_match(a: str, b: str) -> bool:
    """Gleicher Artikel trotz abweichendem Untertitel? Sicher, aber nicht naiv.

    DOAJ-Titel weichen oft im Untertitel ab (belegt: »… ENTANGLEMENT« vs »…
    entangled ecological imagination«), ein Exakt-Match verfehlt sie. Akzeptiert
    wird, wenn die ersten Wörter übereinstimmen ODER die Wortmengen stark
    überlappen — genug gegen Zufallstreffer, durchlässig für Untertitel-Varianten.
    """
    wa, wb = _title_words(a), _title_words(b)
    if len(wa) < 3 or len(wb) < 3:
        return _norm_title(a) == _norm_title(b)     # kurze Titel: exakt
    k = min(5, len(wa), len(wb))
    if wa[:k] == wb[:k]:
        return True
    shared = set(wa) & set(wb)
    return len(shared) >= 4 and len(shared) / min(len(wa), len(wb)) >= 0.7


def _doaj_results(query: str) -> list[dict]:
    q = urllib.parse.quote(query, safe="")
    url = f"https://doaj.org/api/v2/search/articles/{q}?pageSize=5"
    data = _cached_get("doaj", query, url, max_age_days=OPENALEX_WORK_TTL_DAYS)
    return (data or {}).get("results", []) or []


def get_abstract_doaj(doi: str = "", title: str = "", journal: str = "") -> str:
    """Abstract aus DOAJ (Directory of Open Access Journals).

    DOAJ deckt Open-Access-Journals ab, die OpenAlex teils gar nicht oder ohne
    Abstract führt (belegt: Digital Culture & Education, MedienPädagogik u. a.).
    Erst per DOI (eindeutig), dann per Titel mit `_titles_match` und, wenn ein
    Journal gegeben ist, auf dieses eingegrenzt — lieber eine Lücke als ein
    falscher Abstract.
    """
    def _abstract(r: dict) -> str:
        ab = ((r.get("bibjson", {}) or {}).get("abstract") or "").strip()
        return ab if len(ab) > 80 else ""

    doi = (doi or "").strip().rstrip(".")
    if doi:
        for r in _doaj_results(f'doi:"{doi}"'):
            if _abstract(r):
                return _abstract(r)
    if title:
        # Mit den FÜHRENDEN Titelwörtern suchen (in beiden Fassungen stabil) —
        # die volle Titel-Phrase verfehlt DOAJ, sobald der Untertitel abweicht.
        lead = " ".join(_title_words(title)[:6])
        if lead:
            for r in _doaj_results(f'bibjson.title:"{lead}"'):
                b = r.get("bibjson", {}) or {}
                if _titles_match(title, b.get("title", "")) and _abstract(r):
                    return _abstract(r)
    return ""


def get_work_title_openalex(openalex_id: str) -> dict | None:
    """OpenAlex-Work per ID (z.B. für referenced_works-Auflösung)."""
    if not openalex_id:
        return None
    # IDs kommen oft als URL; wir akzeptieren beides
    wid = openalex_id.rsplit("/", 1)[-1]
    url = f"https://api.openalex.org/works/{wid}?mailto={POLITE_MAILTO}"
    return _cached_get("openalex_work", wid, url)


def enrich(doi: str, refresh: bool = False, title: str = "", journal: str = "") -> dict:
    """Convenience: holt Refs + OpenAlex, und wenn nötig einen DOAJ-Abstract.

    `refresh` erzwingt einen frischen OpenAlex-Abruf (übergeht den Work-Cache),
    für den gezielten Nachzug später eingetragener Abstracts. `title`/`journal`
    erlauben den DOAJ-Titel-Treffer, wenn OpenAlex keinen Abstract liefert.

    Rückgabe:
      {
        "doi": ...,
        "references_crossref": [Reference, ...],  # oft leer
        "openalex": {... "abstract" ...} | None,
        "doaj_abstract": str,   # nur gefüllt, wenn OpenAlex keinen Abstract hatte
      }
    """
    result: dict = {"doi": doi}
    result["references_crossref"] = [
        r.__dict__ for r in get_references_crossref(doi)
    ]
    oa = get_work_openalex(doi, force=refresh)
    oa_abstract = ""
    if oa:
        work = oa if "id" in oa else oa.get("message") or oa
        # OpenAlex returns the work directly (no .message wrapper)
        abstract_inv = work.get("abstract_inverted_index") or {}
        oa_abstract = _reconstruct_abstract(abstract_inv) if abstract_inv else ""
        result["openalex"] = {
            "id": work.get("id", ""),
            "title": work.get("title", ""),
            "abstract": oa_abstract,
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
    # DOAJ nur befragen, wenn OpenAlex keinen Abstract lieferte — spart Anfragen.
    result["doaj_abstract"] = ""
    if not oa_abstract and (doi or title):
        result["doaj_abstract"] = get_abstract_doaj(doi=doi, title=title, journal=journal)
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
