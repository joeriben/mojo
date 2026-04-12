"""Abstract-Backfill: fills missing abstracts from cached or external sources.

Tier strategy (stops at first success):
  1. Crossref cache  — extract abstract from already-cached Crossref responses (free)
  2. curl_cffi       — HTTP with browser TLS fingerprint (bypasses Cloudflare, fast)
  3. Playwright       — headless browser for JS-rendered pages (Wiley, De Gruyter)
  4. Zotero           — read abstractNote from local Zotero library

curl_cffi handles Taylor & Francis (Cloudflare Turnstile) and Springer.
Playwright handles JS-rendered pages where meta tags aren't in the raw HTML.

Usage:
  mojo backfill [--limit N] [--dry-run] [--journal ZfE]
"""

from __future__ import annotations

import hashlib
import html as html_mod
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from journal_bot.settings import PROJECT_ROOT
from journal_bot.store import Store

CACHE_DIR = PROJECT_ROOT / ".enrichment_cache"
BACKFILL_CACHE_DIR = PROJECT_ROOT / ".backfill_cache"

# -- Selectors for abstract extraction --
META_NAMES = [
    "citation_abstract",       # Google Scholar / Highwire Press
    "dc.description",          # Dublin Core (Springer, T&F, Wiley)
    "dcterms.abstract",        # Dublin Core terms
    "description",             # generic HTML meta
    "og:description",          # OpenGraph
    "twitter:description",     # Twitter cards
]

CSS_SELECTORS = [
    "div.c-article-section__content[id*=Abs]",  # Springer
    "div.abstract-content",                       # T&F
    "div.abstractSection",                        # Wiley
    "section.abstract",                           # SAGE
    "div#abstract",                               # generic
    "div.abstract",                               # generic
    "p.summary",                                  # JSTOR
]


@dataclass
class BackfillStats:
    total_missing: int = 0
    filled_crossref: int = 0
    filled_curl: int = 0
    filled_playwright: int = 0
    filled_zotero: int = 0
    still_missing: int = 0
    errors: list[str] = field(default_factory=list)


def _strip_jats(text: str) -> str:
    """Remove JATS/XML tags from Crossref abstracts, keep text."""
    if not text:
        return ""
    text = re.sub(r"<jats:title>.*?</jats:title>", "", text, flags=re.S)
    text = re.sub(r"<[^>]+>", "", text)
    text = html_mod.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _is_boilerplate(text: str) -> bool:
    """Detect publisher boilerplate that aren't real abstracts."""
    t = text.lower()
    if t.startswith("article ") and "was published on" in t:
        return True  # De Gruyter boilerplate
    if len(text) < 80:
        return True
    return False


def _backfill_cache_path(doi: str) -> Path:
    safe = hashlib.sha256(doi.strip().rstrip(".").encode()).hexdigest()[:24]
    return BACKFILL_CACHE_DIR / f"{safe}.json"


def _load_backfill_cache(doi: str) -> str | None:
    """Load cached result. Returns abstract, '' (tried/failed), or None (untried)."""
    p = _backfill_cache_path(doi)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text("utf-8"))
        return data.get("abstract", "")
    except Exception:
        return None


def _save_backfill_cache(doi: str, abstract: str, source: str) -> None:
    BACKFILL_CACHE_DIR.mkdir(exist_ok=True)
    p = _backfill_cache_path(doi)
    p.write_text(json.dumps({
        "doi": doi, "abstract": abstract, "source": source,
    }, ensure_ascii=False), "utf-8")


def _extract_abstract_from_html(raw_html: str) -> str:
    """Extract abstract from raw HTML. Prefers DOM over meta tags (meta often truncated)."""
    best = ""

    # 1) DOM selectors first — usually contain the full abstract
    for pattern in [
        r'<div[^>]*class="c-article-section__content"[^>]*id="Abs[^"]*"[^>]*>(.*?)</div>',  # Springer
        r'<div[^>]*class="[^"]*hlFld-Abstract[^"]*"[^>]*>(.*?)</div>',  # T&F
        r'<div[^>]*class="[^"]*abstractSection[^"]*"[^>]*>(.*?)</div>',  # Wiley
        r'<div[^>]*class="[^"]*abstract[^"]*"[^>]*>(.*?)</div>',         # generic
        r'<section[^>]*class="[^"]*abstract[^"]*"[^>]*>(.*?)</section>', # SAGE
    ]:
        m = re.search(pattern, raw_html, re.S | re.I)
        if m:
            text = re.sub(r"<[^>]+>", "", m.group(1))
            text = html_mod.unescape(text).strip()
            text = re.sub(r"\s+", " ", text)
            # Strip leading "Abstract" header
            text = re.sub(r"^Abstract\s*", "", text)
            if len(text) > 100 and not _is_boilerplate(text):
                if len(text) > len(best):
                    best = text

    if best:
        return best

    # 2) Meta tags as fallback (often truncated to ~200 chars, but better than nothing)
    for attr in META_NAMES:
        for pattern in [
            rf'<meta\s+[^>]*?name=[\"\'](?i:{re.escape(attr)})[\"\']\s+content=[\"\'](.*?)[\"\']',
            rf'<meta\s+content=[\"\'](.*?)[\"\']\s+[^>]*?name=[\"\'](?i:{re.escape(attr)})[\"\']',
            rf'<meta\s+[^>]*?property=[\"\'](?i:{re.escape(attr)})[\"\']\s+content=[\"\'](.*?)[\"\']',
            rf'<meta\s+content=[\"\'](.*?)[\"\']\s+[^>]*?property=[\"\'](?i:{re.escape(attr)})[\"\']',
        ]:
            m = re.search(pattern, raw_html, re.S)
            if m:
                text = html_mod.unescape(m.group(1)).strip()
                if len(text) > 100 and not _is_boilerplate(text):
                    return text

    return ""


# ---------------------------------------------------------------- Tier 1: Crossref cache

def _try_crossref_cache(doi: str) -> str:
    """Extract abstract from existing Crossref cache (no API call)."""
    if not doi:
        return ""
    doi_clean = doi.strip().rstrip(".")
    safe = hashlib.sha256(doi_clean.encode()).hexdigest()[:24]
    cache_file = CACHE_DIR / f"crossref_{safe}.json"
    if not cache_file.exists():
        return ""
    try:
        data = json.loads(cache_file.read_text(encoding="utf-8"))
        raw = data.get("message", {}).get("abstract", "")
        return _strip_jats(raw)
    except Exception:
        return ""


# ---------------------------------------------------------------- Tier 2: curl_cffi

def _curl_cffi_available() -> bool:
    try:
        from curl_cffi import requests as _  # noqa: F401
        return True
    except ImportError:
        return False


def _resolve_doi_url(doi: str) -> str:
    """Resolve DOI to final publisher URL via HTTP redirect."""
    try:
        r = httpx.head(
            f"https://doi.org/{doi}",
            follow_redirects=True,
            timeout=15,
            headers={"User-Agent": "mojo/0.1 (abstract-backfill)"},
        )
        return str(r.url)
    except Exception:
        return f"https://doi.org/{doi}"


def _try_curl_cffi(doi: str, verbose: bool = False) -> str:
    """Fetch publisher page with browser TLS fingerprint, extract abstract."""
    if not _curl_cffi_available():
        return ""

    from curl_cffi import requests

    url = _resolve_doi_url(doi)
    if verbose:
        print(f"    [curl] {url}")

    # Try impersonation targets (chrome124 works for Cloudflare as of 2026)
    for browser in ("chrome124", "safari17_2_ios"):
        try:
            r = requests.get(url, impersonate=browser, timeout=20)
            if r.status_code == 200 and "just a moment" not in r.text[:500].lower():
                abstract = _extract_abstract_from_html(r.text)
                if abstract:
                    return abstract
        except Exception:
            continue

    return ""


# ---------------------------------------------------------------- Tier 3: Playwright

def _playwright_available() -> bool:
    try:
        from playwright.sync_api import sync_playwright  # noqa: F401
        return True
    except ImportError:
        return False


def _extract_abstract_from_page(page) -> str:
    """Extract abstract from rendered Playwright page."""
    for selector in META_NAMES:
        try:
            el = page.query_selector(f'meta[name="{selector}" i]')
            if not el:
                el = page.query_selector(f'meta[property="{selector}" i]')
            if el:
                content = el.get_attribute("content") or ""
                content = html_mod.unescape(content).strip()
                if len(content) > 100 and not _is_boilerplate(content):
                    return content
        except Exception:
            continue

    for selector in CSS_SELECTORS:
        try:
            el = page.query_selector(selector)
            if el:
                text = el.inner_text().strip()
                if len(text) > 100 and not _is_boilerplate(text):
                    return text
        except Exception:
            continue

    return ""


class PlaywrightScraper:
    """Reusable browser instance for batch scraping."""

    def __init__(self) -> None:
        self._pw = None
        self._browser = None
        self._context = None

    def start(self) -> None:
        from playwright.sync_api import sync_playwright
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        self._context = self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="en-US",
        )
        self._context.add_init_script(
            'Object.defineProperty(navigator, "webdriver", {get: () => undefined});'
        )

    def stop(self) -> None:
        if self._browser:
            self._browser.close()
        if self._pw:
            self._pw.stop()
        self._browser = None
        self._pw = None
        self._context = None

    def fetch_abstract(self, doi: str, verbose: bool = False) -> str:
        if not self._context:
            return ""

        url = _resolve_doi_url(doi)
        if verbose:
            print(f"    [playwright] {url}")

        try:
            page = self._context.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2000)

            title = page.title() or ""
            if "just a moment" in title.lower() or "moment" in title.lower():
                page.close()
                return ""

            abstract = _extract_abstract_from_page(page)
            page.close()
            return abstract
        except Exception as e:
            if verbose:
                print(f"    [playwright] Fehler: {e}")
            return ""

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()


# ---------------------------------------------------------------- Tier 4: Zotero (read-only)

def _zotero_available() -> bool:
    """Check if Zotero is running locally."""
    try:
        r = httpx.get("http://localhost:23119/api/users/0/items", timeout=3,
                       params={"limit": "1"})
        return r.status_code == 200
    except Exception:
        return False


def _try_zotero(doi: str, verbose: bool = False) -> str:
    """Search local Zotero library for abstract by DOI (read-only, no import)."""
    if not doi:
        return ""

    from pyzotero import zotero
    zot = zotero.Zotero(library_id="0", library_type="user", local=True)

    doi_clean = doi.strip().rstrip(".").lower()
    try:
        items = zot.items(q=doi_clean, limit=10)
    except Exception:
        return ""

    for item in items:
        item_doi = (item["data"].get("DOI") or "").strip().rstrip(".").lower()
        if item_doi == doi_clean:
            abstract = item["data"].get("abstractNote", "")
            if abstract:
                if verbose:
                    print(f"    [zotero] Gefunden ({len(abstract)} Zeichen)")
                return abstract
    return ""


# ---------------------------------------------------------------- Main

def find_missing(store: Store, journal: str | None = None) -> list[dict]:
    """Articles with DOI but no abstract from any source."""
    sql = """
        SELECT id, doi, title, journal_short, journal_full
        FROM articles
        WHERE doi IS NOT NULL AND doi != ''
          AND (abstract IS NULL OR abstract = '')
          AND (openalex_abstract IS NULL OR openalex_abstract = '')
    """
    params: list = []
    if journal:
        sql += " AND journal_short = ?"
        params.append(journal)
    sql += " ORDER BY year DESC, fetched_at DESC"

    import sqlite3
    conn = sqlite3.connect(store.path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def _update_abstract(store: Store, article_id: str, abstract: str) -> None:
    """Write abstract to the abstract field (only if currently empty)."""
    import sqlite3
    conn = sqlite3.connect(store.path)
    conn.execute(
        "UPDATE articles SET abstract = ? "
        "WHERE id = ? AND (abstract IS NULL OR abstract = '')",
        (abstract, article_id),
    )
    conn.commit()
    conn.close()


def run(
    store: Store | None = None,
    limit: int | None = None,
    journal: str | None = None,
    dry_run: bool = False,
    verbose: bool = True,
    delay: float = 2.0,
) -> BackfillStats:
    """Fill missing abstracts: Crossref → curl_cffi → Playwright → Zotero."""
    store = store or Store()
    stats = BackfillStats()

    missing = find_missing(store, journal=journal)
    if limit:
        missing = missing[:limit]
    stats.total_missing = len(missing)

    if not missing:
        if verbose:
            print("[backfill] Keine Artikel ohne Abstract gefunden.")
        return stats

    curl_ok = _curl_cffi_available()
    pw_ok = _playwright_available()
    zot_ok = _zotero_available()

    if verbose:
        print(f"[backfill] {len(missing)} Artikel ohne Abstract")
        sources = ["Crossref-Cache ✓"]
        sources.append(f"curl_cffi {'✓' if curl_ok else '✗ (pip install curl_cffi)'}")
        sources.append(f"Playwright {'✓' if pw_ok else '✗'}")
        sources.append(f"Zotero {'✓' if zot_ok else '✗'}")
        print(f"[backfill] Quellen: {'  '.join(sources)}")
        if dry_run:
            print("[backfill] DRY RUN — keine Änderungen")
        print()

    # Reuse Playwright browser across articles
    scraper = None
    if pw_ok:
        try:
            scraper = PlaywrightScraper()
            scraper.start()
        except Exception:
            scraper = None
            pw_ok = False

    try:
        for i, row in enumerate(missing, 1):
            doi = row["doi"]
            title = row["title"][:70]
            journal_name = row["journal_full"] or row["journal_short"]
            source = ""

            if verbose:
                print(f"[{i}/{len(missing)}] {journal_name}: {title}")

            # Check backfill cache
            cached = _load_backfill_cache(doi)
            if cached is not None:
                if cached:
                    abstract = cached
                    source = "cache"
                    stats.filled_crossref += 1
                else:
                    stats.still_missing += 1
                    if verbose:
                        print("  — bereits geprüft, kein Abstract")
                    continue
            else:
                abstract = ""

                # Tier 1: Crossref cache
                if not abstract:
                    abstract = _try_crossref_cache(doi)
                    if abstract:
                        source = "crossref"
                        stats.filled_crossref += 1

                # Tier 2: curl_cffi (fast, handles Cloudflare)
                if not abstract and curl_ok:
                    abstract = _try_curl_cffi(doi, verbose=verbose)
                    if abstract:
                        source = "curl"
                        stats.filled_curl += 1

                # Tier 3: Playwright (JS-rendered pages)
                if not abstract and scraper:
                    abstract = scraper.fetch_abstract(doi, verbose=verbose)
                    if abstract:
                        source = "playwright"
                        stats.filled_playwright += 1

                # Tier 4: Zotero (read existing items)
                if not abstract and zot_ok:
                    abstract = _try_zotero(doi, verbose=verbose)
                    if abstract:
                        source = "zotero"
                        stats.filled_zotero += 1

                # Cache result (even empty = negative cache)
                _save_backfill_cache(doi, abstract, source)

            if abstract:
                if verbose:
                    print(f"  ✓ [{source}] {len(abstract)} Zeichen")
                if not dry_run:
                    _update_abstract(store, row["id"], abstract)
            else:
                stats.still_missing += 1
                if verbose:
                    print("  ✗ kein Abstract gefunden")

            # Rate limiting for external calls
            if source not in ("crossref", "cache", ""):
                time.sleep(delay)

    finally:
        if scraper:
            scraper.stop()

    if verbose:
        total_filled = (stats.filled_crossref + stats.filled_curl
                        + stats.filled_playwright + stats.filled_zotero)
        print()
        print("=== Backfill fertig ===")
        print(f"Geprüft:           {stats.total_missing}")
        print(f"Crossref-Cache:    {stats.filled_crossref}")
        print(f"curl_cffi:         {stats.filled_curl}")
        print(f"Playwright:        {stats.filled_playwright}")
        print(f"Zotero:            {stats.filled_zotero}")
        print(f"Gesamt gefüllt:    {total_filled}")
        print(f"Noch fehlend:      {stats.still_missing}")

    return stats
