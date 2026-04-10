"""fetch-Pipeline: Feeds → Enrichment → Store. Kein LLM-Call.

Iteriert alle enabled Fetcher, holt Artikel, enriched via OpenAlex/Crossref
und schreibt in articles.db. Idempotent — Artikel, die bereits im Store sind,
werden übersprungen (bzw. ihre Metadaten aktualisiert).
"""

from __future__ import annotations

from dataclasses import dataclass

from journal_bot.enrichment import enrich, _reconstruct_abstract
from journal_bot.fetchers import build_fetcher
from journal_bot.fetchers.base import Article
from journal_bot.settings import JOURNALS
from journal_bot.store import Store, StoredArticle, make_article_id


@dataclass
class FetchStats:
    total_fetched: int = 0
    new_in_store: int = 0
    enriched_ok: int = 0
    enrichment_skipped: int = 0
    enrichment_failed: int = 0
    errors: list[str] = None  # type: ignore

    def __post_init__(self) -> None:
        if self.errors is None:
            self.errors = []


def _year_from_published(published: str) -> int | None:
    import re
    m = re.search(r"(19|20)\d{2}", published or "")
    return int(m.group(0)) if m else None


def _enrich_article(article: Article) -> dict:
    """Wrapped enrichment — gibt immer ein dict zurück, auch im Fehlerfall."""
    if not article.doi:
        return {"status": "no_doi"}
    try:
        data = enrich(article.doi)
        data["status"] = "ok"
        return data
    except Exception as e:
        return {"status": f"failed:{e}", "openalex": None, "references_crossref": []}


def _article_to_stored(art: Article, enrichment: dict) -> StoredArticle:
    oa = enrichment.get("openalex") or {}
    refs = enrichment.get("references_crossref") or []
    year = _year_from_published(art.published)
    if oa and oa.get("publication_year"):
        year = oa["publication_year"]

    return StoredArticle(
        id=make_article_id(art.doi, art.url, art.title),
        journal_short=art.journal,
        journal_full=art.journal_full,
        title=art.title,
        authors=art.authors,
        abstract=art.abstract,
        doi=art.doi,
        url=art.url,
        year=year,
        published=art.published,
        openalex_id=oa.get("id", "") if oa else "",
        openalex_abstract=oa.get("abstract", "") if oa else "",
        openalex_concepts=(oa.get("concepts") or []) if oa else [],
        openalex_topics=(oa.get("topics") or []) if oa else [],
        openalex_refs=(oa.get("referenced_works") or []) if oa else [],
        crossref_refs=refs,
        enrichment_status=enrichment.get("status", ""),
    )


def run(
    store: Store | None = None,
    verbose: bool = True,
    since_year: int | None = None,
) -> FetchStats:
    store = store or Store()
    stats = FetchStats()

    enabled = [j for j in JOURNALS if j.enabled]
    if verbose:
        label = f" (seit {since_year})" if since_year else ""
        print(f"[fetch] {len(enabled)} aktive Feeds{label}")

    for jc in enabled:
        # For backfill: use OpenAlex for RSS/OJS journals that have an ISSN
        use_openalex_backfill = (
            since_year
            and jc.type in ("rss", "ojs", "html")
            and jc.issn
        )
        if use_openalex_backfill:
            from journal_bot.fetchers.openalex_fetcher import OpenAlexFetcher
            from journal_bot.settings import JournalConfig
            backfill_jc = JournalConfig(
                name=jc.name, short=jc.short, type="openalex",
                url=f"issn:{jc.issn}", enabled=True, issn=jc.issn,
            )
            if verbose:
                print(f"\n[fetch] → {jc.short} (openalex-backfill, ISSN {jc.issn})")
            fetcher = OpenAlexFetcher(backfill_jc, since_year=since_year)
        else:
            if verbose:
                print(f"\n[fetch] → {jc.short} ({jc.type})")
            fetcher = build_fetcher(jc, since_year=since_year)

        try:
            articles = fetcher.fetch()
        except Exception as e:
            msg = f"{jc.short}: fetch failed — {e}"
            stats.errors.append(msg)
            if verbose:
                print(f"[fetch]   FEHLER: {msg}")
            continue

        if verbose:
            print(f"[fetch]   {len(articles)} Einträge aus dem Feed")

        for art in articles:
            stats.total_fetched += 1
            aid = make_article_id(art.doi, art.url, art.title)

            # Skip wenn schon enriched im Store (aber nicht-enriched updaten)
            existing = store.get(aid)
            if existing and existing.enrichment_status == "ok":
                continue

            enrichment = _enrich_article(art)
            status = enrichment.get("status", "")
            if status == "ok":
                stats.enriched_ok += 1
            elif status == "no_doi":
                stats.enrichment_skipped += 1
            else:
                stats.enrichment_failed += 1

            stored = _article_to_stored(art, enrichment)
            is_new = store.upsert_article(stored)
            if is_new:
                stats.new_in_store += 1

            if verbose:
                flag = "NEW" if is_new else "upd"
                enr = {"ok": "✓", "no_doi": "—", }.get(status, "✗")
                print(f"[fetch]   {flag} {enr}  {art.title[:80]}")

    if verbose:
        print()
        print("=== fetch fertig ===")
        print(f"Im Feed gesehen:         {stats.total_fetched}")
        print(f"Neu im Store:            {stats.new_in_store}")
        print(f"Enrichment OK:           {stats.enriched_ok}")
        print(f"Enrichment kein DOI:     {stats.enrichment_skipped}")
        print(f"Enrichment fehlgeschl.:  {stats.enrichment_failed}")
        if stats.errors:
            print(f"Feed-Fehler:             {len(stats.errors)}")
            for e in stats.errors:
                print(f"  · {e}")

    return stats
