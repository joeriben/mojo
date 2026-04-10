"""Generischer RSS/Atom-Fetcher für Springer etc."""

from __future__ import annotations

import re

import feedparser

from journal_bot.settings import JournalConfig
from journal_bot.fetchers.base import Article


DOI_RE = re.compile(r"10\.\d{4,9}/[^\s\"']+")


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


def _extract_doi(entry: dict) -> str:
    # Springer Feeds haben oft <dc:identifier>doi:...</dc:identifier>
    for key in ("dc_identifier", "prism_doi", "id"):
        val = entry.get(key, "")
        if isinstance(val, str):
            m = DOI_RE.search(val)
            if m:
                return m.group(0)
    # Fallback: im summary suchen
    m = DOI_RE.search(entry.get("summary", "") or "")
    return m.group(0) if m else ""


class RSSFetcher:
    def __init__(self, jc: JournalConfig) -> None:
        self.jc = jc

    def fetch(self) -> list[Article]:
        feed = feedparser.parse(self.jc.url)
        if feed.bozo and not feed.entries:
            raise RuntimeError(
                f"RSS-Feed {self.jc.url} konnte nicht geparst werden: {feed.bozo_exception}"
            )

        out: list[Article] = []
        for entry in feed.entries:
            title = _strip_html(entry.get("title", "")).strip()
            if not title:
                continue
            authors = [a.get("name", "") for a in entry.get("authors", []) if a.get("name")]
            if not authors and entry.get("author"):
                authors = [entry["author"]]
            out.append(
                Article(
                    journal=self.jc.short,
                    journal_full=self.jc.name,
                    title=title,
                    authors=authors,
                    abstract=_strip_html(entry.get("summary", "")),
                    url=entry.get("link", ""),
                    doi=_extract_doi(entry),
                    published=entry.get("published", "") or entry.get("updated", ""),
                )
            )
        return out
