"""Fetcher for Digital Culture & Education (digitalcultureandeducation.com).

DCE is a Squarespace-hosted journal not properly indexed in OpenAlex.
Structure: /browse-journal lists volume links, each volume page has
article entries with title, authors, abstract, date, and PDF link.
"""

from __future__ import annotations

import re

import httpx
from selectolax.parser import HTMLParser

from journal_bot.settings import JournalConfig
from journal_bot.fetchers.base import Article

BASE_URL = "https://www.digitalcultureandeducation.com"
BROWSE_URL = f"{BASE_URL}/browse-journal"


def _parse_date(text: str) -> str:
    """Extract ISO-ish date from 'Mar 17, 2026' or similar."""
    months = {
        "jan": "01", "feb": "02", "mar": "03", "apr": "04",
        "may": "05", "jun": "06", "jul": "07", "aug": "08",
        "sep": "09", "oct": "10", "nov": "11", "dec": "12",
    }
    m = re.match(r"(\w+)\s+(\d+),?\s+(\d{4})", text.strip())
    if m:
        mon = months.get(m.group(1).lower()[:3], "01")
        return f"{m.group(3)}-{mon}-{int(m.group(2)):02d}"
    # Fallback: just extract year
    ym = re.search(r"(20\d{2})", text)
    return ym.group(1) if ym else ""


def _parse_authors(text: str) -> list[str]:
    """Extract author names from 'Written by: Name1, Name2 & Name3'."""
    import html as html_mod
    # Decode HTML entities
    text = html_mod.unescape(text)
    # Remove "Written by:" prefix
    text = re.sub(r"(?i)written\s*(by\s*)?:?\s*", "", text).strip()
    # Remove any HTML tag remnants
    text = re.sub(r"<[^>]+>", " ", text)
    # Clean up whitespace
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return []
    # Split on comma, &, "and", and "amp;"
    parts = re.split(r"\s*[,&]\s*|\s+and\s+|\s*amp;\s*", text)
    return [p.strip() for p in parts if p.strip() and len(p.strip()) > 2]


def _extract_year(volume_label: str) -> int | None:
    """Extract year from volume label like 'Volume 16.1 (2025-26)'."""
    m = re.search(r"\((\d{4})", volume_label)
    if m:
        return int(m.group(1))
    # Try 4-digit year anywhere
    m = re.search(r"(20\d{2})", volume_label)
    return int(m.group(1)) if m else None


class DCEFetcher:
    """Scraper for Digital Culture & Education."""

    def __init__(
        self,
        jc: JournalConfig,
        since_year: int | None = None,
        end_year: int | None = None,
    ) -> None:
        self.jc = jc
        self.since_year = since_year or 2018
        self.end_year = end_year
        self.client = httpx.Client(
            timeout=30,
            headers={"User-Agent": "mojo/1.0 (personal research assistant)"},
            follow_redirects=True,
        )

    def _get_volume_urls(self) -> list[tuple[str, str]]:
        """Get all volume URLs and labels from the browse page."""
        resp = self.client.get(BROWSE_URL)
        resp.raise_for_status()
        tree = HTMLParser(resp.text)

        volumes = []
        for a in tree.css("a"):
            href = a.attributes.get("href", "")
            text = a.text(strip=True)
            if re.match(r"/volume-\d", href):
                full_url = BASE_URL + href
                volumes.append((full_url, text))
        return volumes

    def _scrape_volume(self, url: str, volume_label: str) -> list[Article]:
        """Scrape articles from a single volume page."""
        resp = self.client.get(url)
        resp.raise_for_status()
        tree = HTMLParser(resp.text)

        volume_year = _extract_year(volume_label)
        articles = []

        # Find all links to PDFs (articles in /s/ paths)
        # We need to find the container blocks around each PDF link
        # DCE uses Squarespace blocks — each article is in a content block
        # with date, title link, "Written by:", and "Abstract:"

        # Strategy: get the full page text split by blocks,
        # then parse each block for article data
        body = tree.css_first("main, .main-content, #page, body")
        if not body:
            return []

        # Get all text content as one string, use HTML structure
        html_str = body.html or ""

        # Split on PDF links — each article has a link to /s/
        # Find all <a> with /s/ href
        pdf_links = []
        for a in tree.css("a"):
            href = a.attributes.get("href", "")
            text = a.text(strip=True)
            if "/s/" in href and text and len(text) > 15:
                pdf_links.append((href, text))

        if not pdf_links:
            return []

        # For each PDF link, try to find surrounding context
        # We re-parse using regex on the raw HTML
        for pdf_url, title in pdf_links:
            # Find the block containing this article
            # Look for date, authors, abstract near the title
            escaped_title = re.escape(title[:40])
            # Search in a window around the title
            match = re.search(escaped_title, html_str)
            if not match:
                continue

            # Get a window around the match (2000 chars before, 3000 after)
            start = max(0, match.start() - 2000)
            end = min(len(html_str), match.end() + 3000)
            block = html_str[start:end]

            # Strip HTML tags for text analysis
            block_text = re.sub(r"<[^>]+>", " ", block)
            block_text = re.sub(r"\s+", " ", block_text)

            # Extract date
            date_match = re.search(
                r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d+,?\s+\d{4})",
                block_text,
            )
            published = _parse_date(date_match.group(1)) if date_match else ""
            year = int(published[:4]) if published and len(published) >= 4 else volume_year

            # Extract authors (between "Written by" and "Abstract")
            author_match = re.search(
                r"[Ww]ritten\s*(?:[Bb]y\s*)?:?\s*(.+?)(?:Abstract|Keywords|$)",
                block_text,
            )
            authors = _parse_authors(author_match.group(1)) if author_match else []
            # Filter out anything that looks like HTML or is too long for a name
            authors = [a for a in authors if len(a) < 60 and "<" not in a]

            # Extract abstract
            abstract = ""
            abs_match = re.search(
                r"Abstract\s*:?\s*(.+?)(?:Keywords|References|Read More|$)",
                block_text,
                re.IGNORECASE,
            )
            if abs_match:
                raw = abs_match.group(1).strip()
                # Clean HTML remnants
                raw = re.sub(r"<[^>]+>", " ", raw)
                raw = re.sub(r"\s+", " ", raw).strip()
                abstract = raw[:2000]

            articles.append(Article(
                journal=self.jc.short,
                journal_full=self.jc.name,
                title=title,
                authors=authors,
                abstract=abstract,
                url=pdf_url,
                published=published,
                issue=volume_label,
            ))

        return articles

    def fetch(self) -> list[Article]:
        """Fetch all articles from DCE since since_year."""
        volumes = self._get_volume_urls()
        print(f"  [DCE] {len(volumes)} Volumes gefunden")

        all_articles = []
        for url, label in volumes:
            year = _extract_year(label)
            if year and year < self.since_year:
                continue
            if year and self.end_year is not None and year > self.end_year:
                continue

            articles = self._scrape_volume(url, label)
            if articles:
                print(f"  [DCE] {label}: {len(articles)} Artikel")
                all_articles.extend(articles)

        self.client.close()
        return all_articles
