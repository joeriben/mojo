"""OpenAlex-Fetcher: holt neue Artikel einer Zeitschrift über die OpenAlex-API.

Vorteil gegenüber publisher-spezifischen Scrapern:
  - eine API statt 15 Verlags-HTML-Layouts
  - Metadaten + Abstract + Concepts/Topics bereits enthalten (kein separates Enrichment
    für OpenAlex nötig, nur Crossref-Refs für Citation-Tracking müssen ggf. nachgeholt
    werden)
  - kostenlos, polite pool via mailto
  - Latenz 1–4 Wochen (OpenAlex-Indexierung) — für wöchentliche Sichtung ok

Config-Format (im JournalConfig.url-Feld):
  - "issn:XXXX-XXXX"              — ISSN-basierte Abfrage (bevorzugt)
  - "openalex:S123456789"         — Source-ID-Abfrage
  - "https://..."                 — Fallback, Parser versucht URL-Komponenten zu erkennen

Konventionen im JournalConfig:
  type = "openalex"
  url  = "issn:1741-5446"         (Beispiel Journal of Philosophy of Education)
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta

import httpx

from journal_bot.fetchers.base import Article
from journal_bot.settings import JournalConfig


OPENALEX_BASE = "https://api.openalex.org/works"
POLITE_MAILTO = "journal-bot@localhost"
USER_AGENT = f"journal-bot/0.1 (mailto:{POLITE_MAILTO})"

# Default-Fenster: 180 Tage. Hoch genug um langsamer publizierende Journals
# (JAE, DIME, Resilience) zu erfassen, schnellere Journals sind via MAX_RESULTS
# gedeckelt.
DEFAULT_WINDOW_DAYS = 180

# Max Anzahl Artikel pro Zeitschrift pro Lauf (Schutz vor exzessiven Journals)
MAX_RESULTS = 50


def _parse_filter(url: str) -> str:
    """Übersetzt den url-Eintrag aus JournalConfig in einen OpenAlex-Filter."""
    url = url.strip()
    if url.startswith("issn:"):
        issn = url[5:].strip()
        return f"primary_location.source.issn:{issn}"
    if url.startswith("openalex:"):
        source_id = url[len("openalex:"):].strip()
        return f"primary_location.source.id:{source_id}"
    # Fallback: versuche ISSN oder S-ID im String zu finden
    m = re.search(r"(\d{4}-\d{3}[\dXx])", url)
    if m:
        return f"primary_location.source.issn:{m.group(1)}"
    m = re.search(r"(S\d{6,})", url)
    if m:
        return f"primary_location.source.id:{m.group(1)}"
    raise ValueError(
        f"OpenAlex-Fetcher: url {url!r} enthält weder ISSN ('issn:XXXX-XXXX') "
        f"noch Source-ID ('openalex:SXXXXXXXXX')."
    )


def _reconstruct_abstract(inverted: dict | None) -> str:
    if not inverted:
        return ""
    positions: dict[int, str] = {}
    for word, idxs in inverted.items():
        for i in idxs:
            positions[i] = word
    if not positions:
        return ""
    return " ".join(positions[i] for i in sorted(positions.keys()))


def _work_to_article(work: dict, jc: JournalConfig) -> Article | None:
    title = (work.get("title") or "").strip()
    if not title:
        return None

    authors: list[str] = []
    for a in work.get("authorships") or []:
        name = (a.get("author") or {}).get("display_name", "")
        if name:
            authors.append(name)

    doi = (work.get("doi") or "").strip()
    if doi.startswith("https://doi.org/"):
        doi = doi[len("https://doi.org/"):]
    elif doi.startswith("http://doi.org/"):
        doi = doi[len("http://doi.org/"):]

    abstract = _reconstruct_abstract(work.get("abstract_inverted_index"))

    primary_loc = work.get("primary_location") or {}
    url = primary_loc.get("landing_page_url", "") or ""

    return Article(
        journal=jc.short,
        journal_full=jc.name,
        title=title,
        authors=authors,
        abstract=abstract,
        url=url,
        doi=doi,
        published=work.get("publication_date", "") or str(work.get("publication_year", "")),
    )


class OpenAlexFetcher:
    def __init__(
        self,
        jc: JournalConfig,
        window_days: int = DEFAULT_WINDOW_DAYS,
        max_results: int = MAX_RESULTS,
    ) -> None:
        self.jc = jc
        self.window_days = window_days
        self.max_results = max_results

    def fetch(self) -> list[Article]:
        from_date = (datetime.utcnow() - timedelta(days=self.window_days)).date().isoformat()
        source_filter = _parse_filter(self.jc.url)
        full_filter = f"{source_filter},from_publication_date:{from_date},type:article"

        params = {
            "filter": full_filter,
            "sort": "publication_date:desc",
            "per-page": min(200, self.max_results),
            "mailto": POLITE_MAILTO,
            "select": (
                "id,doi,title,authorships,publication_date,publication_year,"
                "abstract_inverted_index,primary_location,type"
            ),
        }

        try:
            resp = httpx.get(
                OPENALEX_BASE,
                params=params,
                timeout=30,
                headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            )
        except Exception as e:
            raise RuntimeError(f"OpenAlex-Request fehlgeschlagen: {e}") from e

        if resp.status_code != 200:
            raise RuntimeError(
                f"OpenAlex {resp.status_code}: {resp.text[:300]}"
            )

        data = resp.json()
        works = data.get("results") or []

        articles: list[Article] = []
        for w in works[: self.max_results]:
            art = _work_to_article(w, self.jc)
            if art is not None:
                articles.append(art)
        return articles
