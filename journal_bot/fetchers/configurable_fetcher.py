"""Declarative fetcher driven by JSON config files.

Custom fetcher configs live in fetchers/custom/{short}.json.
The schema is fixed — no executable code, only CSS selectors and URL patterns.

Supported strategies:
  - single_page:  One URL with a list of articles.
  - paginated:    Like single_page but with page navigation.
  - issue_list:   Index page linking to per-issue pages, each containing articles.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import httpx
from selectolax.parser import HTMLParser, Node

from journal_bot.fetchers.base import Article
from journal_bot.settings import JournalConfig

# Fixed directory — not configurable by the agent or user at runtime.
CUSTOM_CONFIG_DIR = Path(__file__).parent / "custom"

# Allowed strategies (whitelist).
ALLOWED_STRATEGIES = {"single_page", "paginated", "issue_list"}

# Schema keys we accept (anything else is silently ignored).
_ARTICLE_FIELDS = {"container", "title", "url", "authors", "date", "abstract", "doi"}
_TOP_KEYS = {
    "$schema", "base_url", "strategy",
    "index", "issues", "article", "detail", "url_fixup",
}


# ---------------------------------------------------------------------------
# Config validation
# ---------------------------------------------------------------------------

def validate_config(cfg: dict) -> list[str]:
    """Return a list of error strings.  Empty list = valid."""
    errors: list[str] = []

    if not cfg.get("base_url"):
        errors.append("base_url ist Pflichtfeld.")
    if cfg.get("strategy") not in ALLOWED_STRATEGIES:
        errors.append(f"strategy muss einer von {sorted(ALLOWED_STRATEGIES)} sein.")

    strategy = cfg.get("strategy", "")

    # Index block required for single_page / paginated
    if strategy in ("single_page", "paginated"):
        idx = cfg.get("index", {})
        if not idx.get("url"):
            errors.append("index.url ist Pflichtfeld für single_page/paginated.")

    # Issues block required for issue_list
    if strategy == "issue_list":
        iss = cfg.get("issues", {})
        if not iss.get("url"):
            errors.append("issues.url ist Pflichtfeld für issue_list.")
        if not iss.get("link_selector"):
            errors.append("issues.link_selector ist Pflichtfeld für issue_list.")

    # Article block always required
    art = cfg.get("article", {})
    if not art.get("container"):
        errors.append("article.container ist Pflichtfeld.")
    if not art.get("title"):
        errors.append("article.title ist Pflichtfeld.")

    return errors


def load_config(short: str) -> dict:
    """Load and validate a custom config.  Raises ValueError on problems."""
    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "", short)
    path = CUSTOM_CONFIG_DIR / f"{safe_name}.json"
    if not path.exists():
        raise FileNotFoundError(
            f"Custom-Config nicht gefunden: {path.name}"
        )
    cfg = json.loads(path.read_text(encoding="utf-8"))
    errors = validate_config(cfg)
    if errors:
        raise ValueError(
            f"Ungültige Custom-Config {path.name}: " + "; ".join(errors)
        )
    return cfg


def save_config(short: str, cfg: dict) -> Path:
    """Validate and write a custom config.  Returns the file path."""
    errors = validate_config(cfg)
    if errors:
        raise ValueError("; ".join(errors))

    safe_name = re.sub(r"[^a-zA-Z0-9_-]", "", short)
    if not safe_name:
        raise ValueError("Ungültiger Kurzname.")

    path = CUSTOM_CONFIG_DIR / f"{safe_name}.json"
    path.write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


# ---------------------------------------------------------------------------
# Selector engine (CSS + optional @attr extraction)
# ---------------------------------------------------------------------------

def _extract(node: Node, selector: str) -> str:
    """Apply a CSS selector with optional @attr suffix.

    Examples:
        "h2 a"           → text content of first match
        "h2 a@href"      → href attribute of first match
        "time@datetime"  → datetime attribute of first match
    """
    # Split off @attr if present
    parts = selector.rsplit("@", 1)
    css = parts[0].strip()
    attr = parts[1].strip() if len(parts) == 2 else None

    el = node.css_first(css)
    if el is None:
        return ""

    if attr:
        return (el.attributes.get(attr, "") or "").strip()
    return el.text(strip=True)


def _extract_all(node: Node, selector: str) -> list[str]:
    """Like _extract but returns all matches."""
    parts = selector.rsplit("@", 1)
    css = parts[0].strip()
    attr = parts[1].strip() if len(parts) == 2 else None

    results = []
    for el in node.css(css):
        if attr:
            val = (el.attributes.get(attr, "") or "").strip()
        else:
            val = el.text(strip=True)
        if val:
            results.append(val)
    return results


def _try_selectors(node: Node, selector_str: str) -> str:
    """Try comma-separated selectors, return first non-empty result."""
    for sel in selector_str.split(","):
        sel = sel.strip()
        if not sel:
            continue
        result = _extract(node, sel)
        if result:
            return result
    return ""


def _resolve_url(url: str, base_url: str) -> str:
    """Resolve relative URLs against base_url."""
    if not url:
        return ""
    if url.startswith(("http://", "https://")):
        return url
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("/"):
        # Absolute path — combine with base origin
        parsed = httpx.URL(base_url)
        return str(parsed.copy_with(raw_path=url.encode("ascii", errors="ignore")))
    # Relative path
    return base_url.rstrip("/") + "/" + url


# ---------------------------------------------------------------------------
# Article extraction from a parsed HTML page
# ---------------------------------------------------------------------------

def _extract_articles(
    tree: HTMLParser,
    jc: JournalConfig,
    cfg: dict,
    page_url: str,
    issue_label: str = "",
) -> list[Article]:
    """Extract articles from a parsed page using config selectors."""
    art_cfg = cfg.get("article", {})
    base_url = cfg.get("base_url", "")
    fixup = cfg.get("url_fixup", {})

    container_sel = art_cfg["container"]
    articles: list[Article] = []

    for node in tree.css(container_sel):
        title = _try_selectors(node, art_cfg.get("title", ""))
        if not title:
            continue

        url = _try_selectors(node, art_cfg.get("url", ""))
        if fixup.get("relative_to_base", True):
            url = _resolve_url(url, base_url)

        # Authors: either a single selector returning comma/&-separated text,
        # or multiple elements.
        authors_raw = _try_selectors(node, art_cfg.get("authors", ""))
        if authors_raw:
            authors = [
                a.strip()
                for a in re.split(r"\s*[,;&]\s*|\s+and\s+|\s+und\s+", authors_raw)
                if a.strip() and len(a.strip()) > 2
            ]
        else:
            authors = _extract_all(
                node,
                art_cfg.get("authors", "").split(",")[0].strip(),
            ) if art_cfg.get("authors") else []

        date = _try_selectors(node, art_cfg.get("date", ""))
        abstract = _try_selectors(node, art_cfg.get("abstract", ""))
        doi = _try_selectors(node, art_cfg.get("doi", ""))

        if fixup.get("doi_prefix_strip") and doi:
            # Strip https://doi.org/ prefix to get bare DOI
            doi = re.sub(r"^https?://doi\.org/", "", doi)

        articles.append(Article(
            journal=jc.short,
            journal_full=jc.name,
            title=title,
            authors=authors,
            abstract=abstract[:2000],
            url=url,
            doi=doi,
            published=date,
            issue=issue_label,
        ))

    return articles


# ---------------------------------------------------------------------------
# Detail page enrichment (optional second fetch per article)
# ---------------------------------------------------------------------------

def _enrich_from_detail(
    articles: list[Article],
    cfg: dict,
    client: httpx.Client,
) -> None:
    """Fetch individual article pages to fill in missing abstracts."""
    detail_cfg = cfg.get("detail", {})
    if not detail_cfg.get("enabled", False):
        return

    abstract_sel = detail_cfg.get("abstract", "")
    if not abstract_sel:
        return

    for art in articles:
        if art.abstract or not art.url:
            continue
        try:
            resp = client.get(art.url)
            resp.raise_for_status()
            tree = HTMLParser(resp.text)
            art.abstract = _try_selectors(tree, abstract_sel)[:2000]
        except Exception:
            continue


# ---------------------------------------------------------------------------
# Main fetcher class
# ---------------------------------------------------------------------------

class ConfigurableFetcher:
    """Declarative fetcher that interprets a JSON config.

    No code execution — only CSS selectors and URL patterns.
    """

    def __init__(
        self,
        jc: JournalConfig,
        since_year: int | None = None,
    ) -> None:
        self.jc = jc
        self.since_year = since_year or 2018
        self.cfg = load_config(jc.short)
        self.client = httpx.Client(
            timeout=30,
            headers={"User-Agent": "mojo/1.0 (personal research assistant)"},
            follow_redirects=True,
        )

    def _fetch_page(self, url: str, issue_label: str = "") -> list[Article]:
        """Fetch and parse a single page."""
        resp = self.client.get(url)
        resp.raise_for_status()
        tree = HTMLParser(resp.text)
        return _extract_articles(tree, self.jc, self.cfg, url, issue_label)

    def _fetch_single_page(self) -> list[Article]:
        idx = self.cfg.get("index", {})
        url = idx.get("url", self.jc.url)
        return self._fetch_page(url)

    def _fetch_paginated(self) -> list[Article]:
        idx = self.cfg.get("index", {})
        pag = idx.get("pagination", {})
        base_url = idx.get("url", self.jc.url)
        max_pages = min(pag.get("max_pages", 5), 20)  # Hard cap at 20

        all_articles: list[Article] = []

        pag_type = pag.get("type", "query_param")

        for page_num in range(1, max_pages + 1):
            if pag_type == "url_suffix":
                pattern = pag.get("pattern", "/page/{n}")
                suffix = pattern.replace("{n}", str(page_num))
                url = base_url.rstrip("/") + suffix if page_num > 1 else base_url
            elif pag_type == "query_param":
                param = pag.get("param", "page")
                sep = "&" if "?" in base_url else "?"
                url = f"{base_url}{sep}{param}={page_num}" if page_num > 1 else base_url
            else:
                url = base_url

            articles = self._fetch_page(url)
            if not articles:
                break  # No more pages
            all_articles.extend(articles)

        return all_articles

    def _fetch_issue_list(self) -> list[Article]:
        iss_cfg = self.cfg.get("issues", {})
        index_url = iss_cfg.get("url", "")
        link_sel = iss_cfg.get("link_selector", "a")
        year_regex = iss_cfg.get("year_regex", r"(20\d{2})")
        base_url = self.cfg.get("base_url", "")

        resp = self.client.get(index_url)
        resp.raise_for_status()
        tree = HTMLParser(resp.text)

        all_articles: list[Article] = []

        for a_node in tree.css(link_sel):
            href = a_node.attributes.get("href", "")
            label = a_node.text(strip=True)
            if not href:
                continue

            issue_url = _resolve_url(href, base_url)

            # Year filter
            year_match = re.search(year_regex, label)
            if year_match:
                year = int(year_match.group(1))
                if year < self.since_year:
                    continue

            articles = self._fetch_page(issue_url, issue_label=label)
            if articles:
                print(f"  [{self.jc.short}] {label}: {len(articles)} Artikel")
                all_articles.extend(articles)

        return all_articles

    def fetch(self) -> list[Article]:
        """Fetch articles using the configured strategy."""
        strategy = self.cfg.get("strategy", "single_page")

        if strategy == "single_page":
            articles = self._fetch_single_page()
        elif strategy == "paginated":
            articles = self._fetch_paginated()
        elif strategy == "issue_list":
            articles = self._fetch_issue_list()
        else:
            raise ValueError(f"Unbekannte Strategie: {strategy}")

        # Optional detail-page enrichment
        _enrich_from_detail(articles, self.cfg, self.client)

        self.client.close()

        print(f"  [{self.jc.short}] {len(articles)} Artikel total")
        return articles
