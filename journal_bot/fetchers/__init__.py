"""Fetcher-Registry — wählt den passenden Fetcher je nach type."""

from __future__ import annotations

from journal_bot.settings import JournalConfig
from journal_bot.fetchers.base import Article, Fetcher
from journal_bot.fetchers.rss_fetcher import RSSFetcher
from journal_bot.fetchers.ojs_fetcher import OJSFetcher
from journal_bot.fetchers.html_fetcher import HTMLFetcher
from journal_bot.fetchers.openalex_fetcher import OpenAlexFetcher
from journal_bot.fetchers.dce_fetcher import DCEFetcher


def build_fetcher(jc: JournalConfig, since_year: int | None = None) -> Fetcher:
    if jc.type == "rss":
        return RSSFetcher(jc)
    if jc.type == "ojs":
        return OJSFetcher(jc)
    if jc.type == "html":
        return HTMLFetcher(jc)
    if jc.type == "openalex":
        return OpenAlexFetcher(jc, since_year=since_year)
    if jc.type == "dce":
        return DCEFetcher(jc, since_year=since_year)
    raise ValueError(f"Unbekannter Fetcher-Typ: {jc.type}")


__all__ = ["Article", "Fetcher", "build_fetcher"]
