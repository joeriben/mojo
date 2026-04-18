"""digest: Agent-Lauf über Store-Einträge, Rückschreiben in Store,
Markdown-Export nach Obsidian.
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

from journal_bot import agent as agent_mod
from journal_bot.signals import derive_attention_profile, load_signal_resources
from journal_bot.settings import DIGEST_DIR
from journal_bot.store import Store, StoredArticle, make_article_id


def _slug(s: str, n: int = 60) -> str:
    s = re.sub(r"[^\w\s-]", "", s or "", flags=re.UNICODE)
    s = re.sub(r"\s+", "-", s.strip())
    return (s[:n].strip("-").lower()) or "eintrag"


def _article_dict_from_stored(sa: StoredArticle) -> dict:
    """Übersetzt StoredArticle in das dict, das run_agent erwartet.

    Enrichment-Daten werden durchgereicht, damit run_agent sie nicht
    nochmal von Crossref/OpenAlex holen muss.
    """
    return {
        "title": sa.title,
        "authors": sa.authors,
        "abstract": sa.abstract,
        "doi": sa.doi,
        "url": sa.url,
        "journal": sa.journal_full or sa.journal_short,
        # Pre-computed enrichment from store (avoids duplicate API calls)
        "enrichment": {
            "openalex": {
                "abstract": sa.openalex_abstract,
                "concepts": sa.openalex_concepts,
                "topics": sa.openalex_topics,
            } if sa.openalex_abstract or sa.openalex_concepts else None,
            "references_crossref": sa.crossref_refs,
        } if sa.enrichment_status == "ok" else None,
    }


def _merge_attention_metadata(entry: dict, profile: dict) -> dict:
    """Keep attention metadata alongside the semantic digest entry."""
    merged = dict(entry)
    merged.setdefault("selection_mode", profile["selection_mode"])
    merged.setdefault("discourse_indicator", profile["discourse_indicator"])
    merged.setdefault("signal_group", profile["signal_group"])
    if profile.get("project_hits") and "project_hits" not in merged:
        merged["project_hits"] = profile["project_hits"]
    return merged


def process_article(
    sa: StoredArticle,
    store: Store,
    verbose: bool = True,
    out_dir: Path = DIGEST_DIR,
    model: str | None = None,
    max_iterations: int | None = None,
    allow_read: bool = True,
    mode: str = "agent",
) -> dict:
    """Lässt den Agent über einen Store-Eintrag laufen, schreibt zurück, rendert Markdown.

    mode="agent": classic single-phase run_agent (allow_read controls tools).
    mode="assess_verify": two-phase assessment → verification pipeline.
    """
    article = _article_dict_from_stored(sa)
    signal_resources = load_signal_resources()

    if mode == "assess_verify":
        kwargs = {"verbose": verbose}
        if model:
            kwargs["model"] = model
        result = agent_mod.assess_then_verify(article, **kwargs)
    else:
        kwargs = {"verbose": verbose, "allow_read": allow_read}
        if model:
            kwargs["model"] = model
        if max_iterations is not None:
            kwargs["max_iterations"] = max_iterations
        result = agent_mod.run_agent(article, **kwargs)

    entry = result.get("entry")
    if entry:
        attention = derive_attention_profile(
            article_id=sa.id,
            title=sa.title,
            authors=sa.authors,
            abstract=sa.abstract,
            openalex_abstract=sa.openalex_abstract,
            crossref_refs=sa.crossref_refs,
            entry=entry,
            signal_resources=signal_resources,
        )
        entry = _merge_attention_metadata(entry, attention.to_dict())
        result["entry"] = entry
        store.update_agent_result(
            sa.id,
            verdict=entry.get("verdict", ""),
            entry=entry,
            citation_hits=result.get("citation_hits", []),
            tokens_in=result.get("tokens_in", 0),
            tokens_out=result.get("tokens_out", 0),
            tokens_cached_read=result.get("tokens_cached_read", 0),
            tokens_cache_write=result.get("tokens_cache_write", 0),
            cost_usd=result.get("est_cost_usd", 0.0),
            iterations=result.get("iterations", 0),
            selection_mode=attention.selection_mode,
            discourse_indicator=attention.discourse_indicator,
            signal_group=attention.signal_group,
        )

    md = agent_mod.render_markdown(result)
    out_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{date.today().isoformat()}_{_slug(article['title'])}.md"
    out_path = out_dir / filename
    out_path.write_text(md, encoding="utf-8")

    return {
        "stored_article": sa,
        "agent_result": result,
        "markdown_path": out_path,
    }


def process_by_doi(doi: str, store: Store, journal: str = "", verbose: bool = True) -> dict:
    """Fall: DOI wird direkt angegeben, Artikel ggf. erst in den Store ziehen."""
    # Versuche aus Store zu laden
    aid = make_article_id(doi, None, "")
    sa = store.get(aid)
    if sa is None:
        # Artikel ad-hoc via OpenAlex holen und in Store legen
        from journal_bot.enrichment import get_work_openalex, _reconstruct_abstract
        from journal_bot.store import StoredArticle

        data = get_work_openalex(doi)
        if not data:
            raise SystemExit(f"OpenAlex kennt DOI {doi!r} nicht.")

        abstract_inv = data.get("abstract_inverted_index") or {}
        abstract = _reconstruct_abstract(abstract_inv) if abstract_inv else ""
        authors = [
            (a.get("author") or {}).get("display_name", "")
            for a in (data.get("authorships") or [])
        ]
        authors = [a for a in authors if a]
        venue = (
            ((data.get("primary_location") or {}).get("source") or {}).get("display_name", "")
        )
        url = (data.get("primary_location") or {}).get("landing_page_url", "")

        sa = StoredArticle(
            id=aid,
            journal_short=journal or venue[:20] or "ad-hoc",
            journal_full=journal or venue,
            title=data.get("title", ""),
            authors=authors,
            abstract=abstract,
            doi=doi,
            url=url,
            year=data.get("publication_year"),
        )
        # Noch Enrichment hinzufügen (refs etc.) via full enrich()
        from journal_bot.enrichment import enrich
        from journal_bot.fetch import _article_to_stored
        from journal_bot.fetchers.base import Article as FetchArticle

        enrichment = enrich(doi)
        enrichment["status"] = "ok"
        art_for_enrich = FetchArticle(
            journal=sa.journal_short,
            journal_full=sa.journal_full,
            title=sa.title,
            authors=sa.authors,
            abstract=sa.abstract,
            url=sa.url,
            doi=sa.doi,
            published=str(sa.year or ""),
        )
        sa = _article_to_stored(art_for_enrich, enrichment)
        store.upsert_article(sa)

    return process_article(sa, store, verbose=verbose)
