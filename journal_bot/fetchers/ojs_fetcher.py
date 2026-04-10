"""OJS-Fetcher — Open Journal Systems liefert einen sauberen RSS2-Feed
mit ganzen Heften. Wir parsen Titel/Abstract/DOI je Eintrag."""

from __future__ import annotations

import re

import feedparser

from journal_bot.settings import JournalConfig
from journal_bot.fetchers.base import Article


DOI_RE = re.compile(r"10\.\d{4,9}/[^\s\"']+")


def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text or "").strip()


class OJSFetcher:
    def __init__(self, jc: JournalConfig) -> None:
        self.jc = jc

    def fetch(self) -> list[Article]:
        feed = feedparser.parse(self.jc.url)
        if feed.bozo and not feed.entries:
            raise RuntimeError(
                f"OJS-Feed {self.jc.url} konnte nicht geparst werden: {feed.bozo_exception}"
            )

        out: list[Article] = []
        for entry in feed.entries:
            title = _strip_html(entry.get("title", "")).strip()
            if not title:
                continue
            summary = _strip_html(entry.get("summary", ""))
            doi = ""
            m = DOI_RE.search(summary + " " + entry.get("id", ""))
            if m:
                doi = m.group(0)
            authors = [a.get("name", "") for a in entry.get("authors", []) if a.get("name")]
            if not authors and entry.get("author"):
                authors = [entry["author"]]
            out.append(
                Article(
                    journal=self.jc.short,
                    journal_full=self.jc.name,
                    title=title,
                    authors=authors,
                    abstract=summary,
                    url=entry.get("link", ""),
                    doi=doi,
                    published=entry.get("published", "") or entry.get("updated", ""),
                )
            )
        return out
