"""Portable raw article exchange without personal analysis data."""

from __future__ import annotations

import json
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from journal_bot.store import Store, StoredArticle


RAW_EXPORT_SCHEMA_VERSION = 1


RAW_FIELDS = [
    "id",
    "journal_short",
    "journal_full",
    "title",
    "authors",
    "abstract",
    "doi",
    "url",
    "year",
    "published",
    "fetched_at",
    "openalex_id",
    "openalex_abstract",
    "openalex_concepts",
    "openalex_topics",
    "openalex_refs",
    "crossref_refs",
    "enrichment_status",
]


@dataclass(frozen=True)
class RawExportResult:
    archive_path: Path
    article_count: int


@dataclass(frozen=True)
class RawImportResult:
    archive_path: Path
    imported: int
    created: int
    updated: int
    skipped: int
    warnings: list[str]


def default_raw_export_path(base_dir: Path) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return base_dir / f"mojo_article_rohdaten_{ts}.zip"


def export_raw_articles(
    store: Store,
    *,
    output_path: Path,
    journals: list[str] | None = None,
    since_year: int | None = None,
) -> RawExportResult:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    articles = store.find_in_window(
        start_year=since_year,
        journals=journals,
        only_processed=False,
    )

    tmp = tempfile.NamedTemporaryFile(
        prefix="mojo_raw_articles_",
        suffix=".jsonl",
        delete=False,
    )
    tmp_path = Path(tmp.name)
    count = 0
    try:
        with tmp:
            for article in articles:
                payload = _article_to_raw_payload(article)
                tmp.write((json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8"))
                count += 1

        with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            manifest = {
                "schema_version": RAW_EXPORT_SCHEMA_VERSION,
                "exported_at": datetime.now().isoformat(timespec="seconds"),
                "article_count": count,
                "notes": [
                    "Enthaelt nur Rohdaten und Enrichment fuer Artikel.",
                    "Bewusst ausgeschlossen: agent_verdict, agent_entry, user_verdict, user_memo, Kosten.",
                ],
            }
            zf.writestr(
                "manifest.json",
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            )
            zf.write(tmp_path, arcname="articles.jsonl")
    finally:
        if tmp_path.exists():
            tmp_path.unlink()

    return RawExportResult(archive_path=output_path, article_count=count)


def import_raw_articles(
    store: Store,
    archive_path: Path,
) -> RawImportResult:
    archive_path = Path(archive_path)
    imported = 0
    created = 0
    updated = 0
    skipped = 0
    warnings: list[str] = []

    with zipfile.ZipFile(archive_path, "r") as zf:
        names = set(zf.namelist())
        if "articles.jsonl" not in names:
            raise ValueError("Archiv enthaelt keine articles.jsonl.")
        if "manifest.json" not in names:
            warnings.append("manifest.json fehlt im Archiv.")

        with zf.open("articles.jsonl", "r") as fh:
            for raw_line in fh:
                line = raw_line.decode("utf-8").strip()
                if not line:
                    continue
                payload = json.loads(line)
                if not payload.get("id"):
                    skipped += 1
                    warnings.append("Ein Eintrag ohne id wurde uebersprungen.")
                    continue

                incoming = _raw_payload_to_article(payload)
                existing = store.get(incoming.id)
                merged = _merge_articles(existing, incoming)

                is_new = store.upsert_article(merged)
                imported += 1
                if is_new:
                    created += 1
                else:
                    updated += 1

    return RawImportResult(
        archive_path=archive_path,
        imported=imported,
        created=created,
        updated=updated,
        skipped=skipped,
        warnings=warnings,
    )


def _article_to_raw_payload(article: StoredArticle) -> dict:
    return {field: getattr(article, field) for field in RAW_FIELDS}


def _raw_payload_to_article(payload: dict) -> StoredArticle:
    return StoredArticle(
        id=str(payload.get("id", "") or ""),
        journal_short=str(payload.get("journal_short", "") or ""),
        journal_full=str(payload.get("journal_full", "") or ""),
        title=str(payload.get("title", "") or ""),
        authors=list(payload.get("authors") or []),
        abstract=str(payload.get("abstract", "") or ""),
        doi=str(payload.get("doi", "") or ""),
        url=str(payload.get("url", "") or ""),
        year=payload.get("year"),
        published=str(payload.get("published", "") or ""),
        fetched_at=str(payload.get("fetched_at", "") or ""),
        openalex_id=str(payload.get("openalex_id", "") or ""),
        openalex_abstract=str(payload.get("openalex_abstract", "") or ""),
        openalex_concepts=list(payload.get("openalex_concepts") or []),
        openalex_topics=list(payload.get("openalex_topics") or []),
        openalex_refs=list(payload.get("openalex_refs") or []),
        crossref_refs=list(payload.get("crossref_refs") or []),
        enrichment_status=str(payload.get("enrichment_status", "") or ""),
    )


def _merge_articles(existing: StoredArticle | None, incoming: StoredArticle) -> StoredArticle:
    if existing is None:
        return incoming

    return StoredArticle(
        id=incoming.id,
        journal_short=_prefer_text(incoming.journal_short, existing.journal_short),
        journal_full=_prefer_text(incoming.journal_full, existing.journal_full),
        title=_prefer_text(incoming.title, existing.title),
        authors=_prefer_list(incoming.authors, existing.authors),
        abstract=_prefer_text(incoming.abstract, existing.abstract),
        doi=_prefer_text(incoming.doi, existing.doi),
        url=_prefer_text(incoming.url, existing.url),
        year=incoming.year if incoming.year is not None else existing.year,
        published=_prefer_text(incoming.published, existing.published),
        fetched_at=_prefer_text(incoming.fetched_at, existing.fetched_at),
        openalex_id=_prefer_text(incoming.openalex_id, existing.openalex_id),
        openalex_abstract=_prefer_text(incoming.openalex_abstract, existing.openalex_abstract),
        openalex_concepts=_prefer_list(incoming.openalex_concepts, existing.openalex_concepts),
        openalex_topics=_prefer_list(incoming.openalex_topics, existing.openalex_topics),
        openalex_refs=_prefer_list(incoming.openalex_refs, existing.openalex_refs),
        crossref_refs=_prefer_list(incoming.crossref_refs, existing.crossref_refs),
        enrichment_status=_prefer_text(incoming.enrichment_status, existing.enrichment_status),
    )


def _prefer_text(primary: str, fallback: str) -> str:
    return primary if str(primary or "").strip() else fallback


def _prefer_list(primary: list, fallback: list) -> list:
    return list(primary) if primary else list(fallback)
