"""Custom fetcher for Computational Culture journal.

Computational Culture (https://computationalculture.net/, ISSN 2047-2390) publishes
peer-reviewed articles on computational culture, software studies, and related topics.
The journal uses a primitive WordPress HTML structure without OAI-PMH or structured feeds.

HTML Structure:
- Issues page: http://computationalculture.net/issues/
  - Lists all issues with links to issue pages
  - Format: "Issue N: [metadata]" as <ol><li><a>

- Issue pages: http://computationalculture.net/issue-N/
  - Contains articles as simple <p> tags (no semantic <article> markup)
  - Format: "Author(s), <em><a>Title</a></em>"
  - Some older issues (pre-2015) have malformed href attributes with embedded quotes

- Article detail pages: http://computationalculture.net/article-slug/
  - Structured metadata in <div class="entry-details"><li> elements
  - Contains: Author(s), Affiliation(s), Publication Date, Issue number
  - Full article text in <div class="entry-content">

This fetcher:
1. Fetches all issue links from the main issues page
2. Parses articles from each issue page (extracting authors from text before <a>)
3. Fetches each article's detail page to extract publication date and abstract
4. Handles malformed URLs from older issues (strips embedded quotes)
5. Filters by year (since_year / end_year)

Coverage: ~163 articles across 10 issues (2011–2025)
"""

from __future__ import annotations

import re
from typing import Optional

import httpx
from selectolax.parser import HTMLParser

from journal_bot.fetchers.base import Article
from journal_bot.settings import JournalConfig


class ComputationalCultureFetcher:
    """Fetch articles from Computational Culture journal."""

    BASE_URL = "http://computationalculture.net"
    ISSUES_URL = "http://computationalculture.net/issues/"

    def __init__(
        self,
        jc: JournalConfig,
        since_year: int | None = None,
        end_year: int | None = None,
    ) -> None:
        self.jc = jc
        self.since_year = since_year or 2010
        self.end_year = end_year
        self.client = httpx.Client(
            timeout=30,
            headers={"User-Agent": "mojo/1.0 (personal research assistant)"},
            follow_redirects=True,
        )

    def fetch(self) -> list[Article]:
        """Fetch all articles from all issues."""
        # Get issue links from main issues page
        issue_links = self._fetch_issue_links()

        all_articles: list[Article] = []
        for issue_url, issue_label in issue_links:
            articles = self._fetch_issue(issue_url, issue_label)
            if articles:
                print(f"  [{self.jc.short}] {issue_label}: {len(articles)} Artikel")
                all_articles.extend(articles)

        return all_articles

    def _fetch_issue_links(self) -> list[tuple[str, str]]:
        """Extract issue links from the issues page."""
        resp = self.client.get(self.ISSUES_URL)
        resp.raise_for_status()
        tree = HTMLParser(resp.text)

        issue_links: list[tuple[str, str]] = []

        # Find the issue list in entry-content
        for link in tree.css('div.entry-content ol li a'):
            href = link.attributes.get('href', '')
            text = link.text(strip=True)
            if not href or not text:
                continue

            # Extract year from text (e.g., "Issue One (Publication Date: November 2011)")
            year_match = re.search(r'(\d{4})', text)
            if year_match:
                year = int(year_match.group(1))
                if year < self.since_year:
                    continue
                if self.end_year is not None and year > self.end_year:
                    continue

            # Resolve relative URL
            if not href.startswith(('http://', 'https://')):
                href = self.BASE_URL + href

            issue_links.append((href, text))

        return issue_links

    def _fetch_issue(self, issue_url: str, issue_label: str) -> list[Article]:
        """Extract articles from a single issue page."""
        resp = self.client.get(issue_url)
        resp.raise_for_status()
        tree = HTMLParser(resp.text)

        articles: list[Article] = []

        # Find the entry-content div
        content_div = tree.css_first('div.entry-content')
        if not content_div:
            return articles

        # Iterate through paragraphs
        for p in content_div.css('p'):
            # Skip paragraphs with only <strong> headers (like "Special Issue Articles")
            text = p.text(strip=True)
            if not text or text.startswith('Special Issue') or text.startswith('Issue Archive'):
                continue

            # Find the link in this paragraph
            link = p.css_first('a')
            if not link:
                continue

            # Raw inner HTML for fallback URL extraction
            p_inner = re.search(r'<p>(.*?)</p>', p.html, re.DOTALL)
            p_inner_html = p_inner.group(1) if p_inner else p.html

            # Get article URL. Old issues have href="“http://...”" (curly quotes)
            # or href=""http://..."" — strip any leading/trailing quote characters.
            _QUOTE_CHARS = '"\'"“”‘’'
            article_url = link.attributes.get('href', '').strip(_QUOTE_CHARS).strip()
            # Strip residual HTML entities (&quot;) and any remaining quotes
            article_url = article_url.replace('&quot;', '').strip(_QUOTE_CHARS).strip()

            if not article_url or not article_url.startswith(('http://', 'https://', '/')):
                continue

            # Resolve relative URL
            if not article_url.startswith(('http://', 'https://')):
                article_url = self.BASE_URL + article_url

            # Get title from link text (may be wrapped in <em>)
            title = link.text(strip=True)
            if not title:
                continue

            # Get authors from text before first <a> or <em>
            # Formats: "Author(s), <em><a>Title</a></em>" or "Author(s), <a>Title</a>"
            # Some paragraphs start with a <strong>Section header</strong><br>Author(s), ...
            author_match = re.search(r'(?:^|>)([^<]+?),\s*(?:<em>)?<a', p_inner_html)
            if author_match:
                author_text = author_match.group(1).strip()
                authors = [
                    a.strip()
                    for a in re.split(r'\s*,\s*|\s+and\s+|\s+und\s+|\s*&\s*', author_text)
                    if a.strip() and len(a.strip()) > 2
                ]
            else:
                authors = []

            # Create article (metadata will be fetched from detail page)
            article = Article(
                journal=self.jc.short,
                journal_full=self.jc.name,
                title=title,
                authors=authors,
                abstract="",  # Will be filled from detail page
                url=article_url,
                doi="",
                published="",  # Will be filled from detail page
                issue=issue_label,
            )

            # Fetch detail page to get metadata
            self._enrich_from_detail(article)
            articles.append(article)

        return articles

    def _enrich_from_detail(self, article: Article) -> None:
        """Fetch article detail page to get publication date and abstract."""
        try:
            resp = self.client.get(article.url, timeout=10)
            resp.raise_for_status()
            tree = HTMLParser(resp.text)

            # Extract metadata from <li> elements in entry-details
            for li in tree.css('div.entry-details li'):
                text = li.text(strip=True)

                if text.startswith('Publication Date:'):
                    date_str = text.replace('Publication Date:', '').strip()
                    article.published = date_str

                # Get abstract from first paragraph of entry-content
                # if it's not in the metadata section

            # Get abstract from entry-content (skip metadata section)
            content_div = tree.css_first('div.entry-content')
            if content_div:
                # Skip the entry-details section
                first_p = None
                for p in content_div.css('p'):
                    p_text = p.text(strip=True)
                    # Skip empty paragraphs and metadata-like paragraphs
                    if p_text and len(p_text) > 50 and not p_text.startswith('Article Information'):
                        first_p = p
                        break

                if first_p:
                    article.abstract = first_p.text(strip=True)[:2000]

        except Exception:
            # Silent fail — use what we have from the index page
            pass


def fetch_articles(
    jc: JournalConfig,
    since_year: int | None = None,
    end_year: int | None = None,
) -> list[Article]:
    """Convenience function matching the standard fetcher interface."""
    fetcher = ComputationalCultureFetcher(jc, since_year, end_year)
    return fetcher.fetch()
