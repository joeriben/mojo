"""Volltext-Beschaffung für Eskalations-Kandidaten.

Drei-Quellen-Kaskade (alle frei, keine API-Keys nötig — Polite-Pool):
  1) OpenAlex `best_oa_location.pdf_url` — meist Verlags-OA-PDF, am
     verlässlichsten verlinkt; aus dem Article-Objekt zu holen.
  2) Unpaywall (`https://api.unpaywall.org/v2/<doi>?email=...`) —
     Self-Archive-Locations (Repository, Pre-Print), wenn OA fehlt.
  3) Crossref (`https://api.crossref.org/works/<doi>`) — fallweise
     Volltext-URLs via `link`-Feld (nur wenn Verlag das exponiert).

Cache: `.escalation_cache/<sha1(article_id)>.{pdf,txt,meta.json}`.
PDF wird über `httpx` heruntergeladen, Text über `pdftotext` extrahiert
(gleiches Binary wie in own_refs/extract.py). KEINE LLM-Calls.

Idempotent: zweiter Aufruf liefert Cache-Hit, kein Netz, kein pdftotext.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE_DIR = PROJECT_ROOT / ".escalation_cache"

POLITE_MAILTO = "mojo@localhost"
USER_AGENT = f"mojo/2.0 escalation (mailto:{POLITE_MAILTO})"

# Reuse the same pdftotext lookup as own_refs/extract.py.
PDFTOTEXT_CANDIDATES = (
    "/opt/homebrew/bin/pdftotext",
    "/usr/local/bin/pdftotext",
    "/usr/bin/pdftotext",
    "pdftotext",
)


# -- Datenklassen -------------------------------------------------------------


@dataclass
class FetchResult:
    """Ergebnis eines Volltext-Fetch-Versuchs."""
    article_id: str
    status: str                       # "ok" | "no_pdf_url" | "download_failed"
                                      # | "pdftotext_failed" | "cache_hit"
    pdf_path: Path | None = None
    txt_path: Path | None = None
    source: str | None = None         # "openalex" | "unpaywall" | "crossref"
    pdf_url: str | None = None
    fulltext_chars: int = 0
    cache_hit: bool = False
    notes: list[str] | None = None


# -- Cache-Pfade --------------------------------------------------------------


def cache_paths(article_id: str, cache_dir: Path = DEFAULT_CACHE_DIR) -> dict[str, Path]:
    """Liefert die drei Cache-Pfade {pdf, txt, meta} für einen article_id."""
    h = hashlib.sha1(article_id.encode("utf-8")).hexdigest()
    return {
        "pdf": cache_dir / f"{h}.pdf",
        "txt": cache_dir / f"{h}.txt",
        "meta": cache_dir / f"{h}.meta.json",
    }


# -- pdftotext-Lookup ---------------------------------------------------------


def _find_pdftotext() -> str | None:
    """Erstes funktionierendes pdftotext-Binary (gleiche Reihenfolge wie own_refs)."""
    for cand in PDFTOTEXT_CANDIDATES:
        try:
            r = subprocess.run(
                [cand, "-v"], capture_output=True, timeout=5, text=True,
            )
            # pdftotext -v gibt Version auf stderr aus, exit 0 oder 99
            if r.returncode in (0, 99):
                return cand
        except (FileNotFoundError, subprocess.SubprocessError):
            continue
    return None


def extract_fulltext(pdf_path: Path) -> str:
    """PDF → reiner Text via pdftotext. Leer-String bei Fehler."""
    binary = _find_pdftotext()
    if binary is None:
        return ""
    try:
        # -layout erhält Spalten; -nopgbrk verhindert Form-Feed.
        r = subprocess.run(
            [binary, "-layout", "-nopgbrk", str(pdf_path), "-"],
            capture_output=True, timeout=60,
        )
        if r.returncode != 0:
            return ""
        return r.stdout.decode("utf-8", errors="replace")
    except subprocess.SubprocessError:
        return ""


# -- PDF-URL-Quellen ---------------------------------------------------------


def _openalex_pdf_url(client: httpx.Client, openalex_id: str) -> str | None:
    """Hole `best_oa_location.pdf_url` aus OpenAlex (free, Polite-Pool)."""
    if not openalex_id:
        return None
    oid = openalex_id.rsplit("/", 1)[-1]
    try:
        r = client.get(
            f"https://api.openalex.org/works/{oid}",
            params={"mailto": POLITE_MAILTO,
                    "select": "best_oa_location,open_access"},
            timeout=20.0,
        )
        if r.status_code != 200:
            return None
        d = r.json() or {}
        loc = (d.get("best_oa_location") or {})
        return loc.get("pdf_url") or None
    except httpx.HTTPError:
        return None


def _unpaywall_pdf_url(client: httpx.Client, doi: str) -> str | None:
    """Hole OA-PDF-URL über Unpaywall (free, requires email param)."""
    if not doi:
        return None
    doi = doi.strip().lower().replace("https://doi.org/", "")
    try:
        r = client.get(
            f"https://api.unpaywall.org/v2/{doi}",
            params={"email": POLITE_MAILTO}, timeout=20.0,
        )
        if r.status_code != 200:
            return None
        d = r.json() or {}
        loc = (d.get("best_oa_location") or {})
        return loc.get("url_for_pdf") or None
    except httpx.HTTPError:
        return None


def _crossref_pdf_url(client: httpx.Client, doi: str) -> str | None:
    """Crossref `link[]`-Feld auf `application/pdf` filtern."""
    if not doi:
        return None
    doi = doi.strip().lower().replace("https://doi.org/", "")
    try:
        r = client.get(
            f"https://api.crossref.org/works/{doi}",
            params={"mailto": POLITE_MAILTO}, timeout=20.0,
        )
        if r.status_code != 200:
            return None
        d = (r.json() or {}).get("message") or {}
        for link in (d.get("link") or []):
            if (link.get("content-type") or "").lower() in (
                "application/pdf", "unspecified",
            ):
                return link.get("URL") or None
        return None
    except httpx.HTTPError:
        return None


def _download_pdf(client: httpx.Client, url: str, dest: Path) -> bool:
    """Lade PDF nach `dest`. Returns True bei Erfolg, False bei Fehler."""
    try:
        with client.stream("GET", url, timeout=60.0, follow_redirects=True) as r:
            if r.status_code != 200:
                return False
            ctype = (r.headers.get("content-type") or "").lower()
            if "pdf" not in ctype and "octet-stream" not in ctype:
                # Manche Verlage liefern HTML; das nehmen wir nicht an.
                return False
            dest.parent.mkdir(parents=True, exist_ok=True)
            with open(dest, "wb") as f:
                for chunk in r.iter_bytes(chunk_size=64 * 1024):
                    f.write(chunk)
        # Sanity: PDFs starten mit "%PDF-"
        with open(dest, "rb") as f:
            head = f.read(5)
        if not head.startswith(b"%PDF-"):
            dest.unlink(missing_ok=True)
            return False
        return True
    except (httpx.HTTPError, OSError):
        return False


# -- Public API ---------------------------------------------------------------


def fetch_fulltext_for_article(
    article_id: str,
    openalex_id: str | None,
    doi: str | None,
    cache_dir: Path = DEFAULT_CACHE_DIR,
    verbose: bool = False,
) -> FetchResult:
    """Versuche, einen Volltext für den Artikel zu beschaffen.

    Reihenfolge: Cache → OpenAlex best_oa_location → Unpaywall → Crossref.
    Bei jedem positiven Hit wird die PDF heruntergeladen, pdftotext extrahiert,
    Cache geschrieben und das Resultat zurückgegeben.

    Returns FetchResult mit status:
      - "cache_hit": Volltext lag schon im Cache, kein Netz nötig
      - "ok":        Frischer Download + Extraktion erfolgreich
      - "no_pdf_url": Keine der drei Quellen lieferte eine PDF-URL
      - "download_failed": URL gefunden, Download/PDF-Validierung schlug fehl
      - "pdftotext_failed": PDF da, Text-Extraktion ergab 0 Zeichen
    """
    paths = cache_paths(article_id, cache_dir)
    notes: list[str] = []

    # 1) Cache: existieren txt + meta?
    if paths["txt"].exists() and paths["meta"].exists():
        try:
            meta = json.loads(paths["meta"].read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            meta = {}
        chars = int(meta.get("fulltext_chars") or 0)
        if chars > 0:
            return FetchResult(
                article_id=article_id, status="cache_hit",
                pdf_path=paths["pdf"] if paths["pdf"].exists() else None,
                txt_path=paths["txt"],
                source=meta.get("source"),
                pdf_url=meta.get("pdf_url"),
                fulltext_chars=chars,
                cache_hit=True,
            )

    # 2) PDF-URL beschaffen
    client = httpx.Client(headers={"User-Agent": USER_AGENT})
    try:
        url: str | None = None
        source: str | None = None
        if openalex_id:
            url = _openalex_pdf_url(client, openalex_id)
            if url:
                source = "openalex"
        if not url and doi:
            url = _unpaywall_pdf_url(client, doi)
            if url:
                source = "unpaywall"
        if not url and doi:
            url = _crossref_pdf_url(client, doi)
            if url:
                source = "crossref"

        if not url:
            if verbose:
                print(f"  [no_pdf_url] {article_id}: weder OA noch Unpaywall noch Crossref")
            return FetchResult(
                article_id=article_id, status="no_pdf_url", notes=notes,
            )

        # 3) Download
        if not _download_pdf(client, url, paths["pdf"]):
            notes.append(f"download failed for {url}")
            return FetchResult(
                article_id=article_id, status="download_failed",
                pdf_url=url, source=source, notes=notes,
            )

        # 4) pdftotext-Extraktion
        text = extract_fulltext(paths["pdf"])
        if not text:
            notes.append("pdftotext returned empty")
            return FetchResult(
                article_id=article_id, status="pdftotext_failed",
                pdf_path=paths["pdf"], pdf_url=url, source=source, notes=notes,
            )

        paths["txt"].write_text(text, encoding="utf-8")
        meta = {
            "article_id": article_id,
            "source": source,
            "pdf_url": url,
            "fulltext_chars": len(text),
            "openalex_id": openalex_id,
            "doi": doi,
        }
        paths["meta"].write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")

        return FetchResult(
            article_id=article_id, status="ok",
            pdf_path=paths["pdf"], txt_path=paths["txt"],
            source=source, pdf_url=url,
            fulltext_chars=len(text),
        )
    finally:
        client.close()
