"""HTML-Scraper-Stub.

Für Journals ohne Feed (z.B. ZfPäd bei Beltz, VjwP bei Brill).
Die konkreten Selektoren müssen pro Seite gepflegt werden — siehe TODOs.
"""

from __future__ import annotations

import httpx
from selectolax.parser import HTMLParser

from journal_bot.settings import JournalConfig
from journal_bot.fetchers.base import Article


class HTMLFetcher:
    def __init__(self, jc: JournalConfig) -> None:
        self.jc = jc

    def fetch(self) -> list[Article]:
        if not self.jc.url:
            return []
        resp = httpx.get(
            self.jc.url,
            timeout=30,
            headers={"User-Agent": "mojo/0.1 (personal research assistant)"},
            follow_redirects=True,
        )
        resp.raise_for_status()
        tree = HTMLParser(resp.text)

        # TODO: journal-spezifische Selektoren einbauen.
        # Hier ein bewusst generisches Beispiel, das jede <article>-Section einsammelt.
        out: list[Article] = []
        for node in tree.css("article, .article, .toc-entry, .issue-article"):
            title_node = node.css_first("h2, h3, .title, a.title")
            if not title_node:
                continue
            title = title_node.text(strip=True)
            if not title:
                continue
            link_node = node.css_first("a")
            url = link_node.attributes.get("href", "") if link_node else ""
            if url and url.startswith("/"):
                # relative URL auflösen
                base = httpx.URL(self.jc.url)
                url = str(base.copy_with(path=url))
            abstract_node = node.css_first(".abstract, .summary, p")
            abstract = abstract_node.text(strip=True) if abstract_node else ""
            out.append(
                Article(
                    journal=self.jc.short,
                    journal_full=self.jc.name,
                    title=title,
                    abstract=abstract,
                    url=url,
                )
            )
        return out
