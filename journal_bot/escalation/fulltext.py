"""Volltext-Beschaffung für Eskalations-Kandidaten.

Vier-Quellen-Kaskade (alle frei, keine API-Keys nötig — Polite-Pool):
  0) **Zotero lokal** — User hat ein Item in seiner Zotero-Bibliothek
     (`~/FAUbox/Zotero/zotero.sqlite`) inkl. PDF-Anhang. Höchste Priorität,
     weil das die Items sind, die der User selbst gespeichert hat (oft
     genau die wrong-LES-Fälle, die er lesen wollte).
  1) OpenAlex `best_oa_location.pdf_url` — meist Verlags-OA-PDF, am
     verlässlichsten verlinkt; aus dem Article-Objekt zu holen.
  2) Unpaywall (`https://api.unpaywall.org/v2/<doi>?email=...`) —
     Self-Archive-Locations (Repository, Pre-Print), wenn OA fehlt.
  3) Crossref (`https://api.crossref.org/works/<doi>`) — fallweise
     Volltext-URLs via `link`-Feld (nur wenn Verlag das exponiert).

Cache: `.escalation_cache/<sha1(article_id)>.{pdf,txt,meta.json}`.
PDF wird über `httpx` heruntergeladen (bzw. aus Zotero kopiert), Text
über `pdftotext` extrahiert (gleiches Binary wie in own_refs/extract.py).
KEINE LLM-Calls.

Idempotent: zweiter Aufruf liefert Cache-Hit, kein Netz, kein pdftotext.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import subprocess
from dataclasses import dataclass
from pathlib import Path

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE_DIR = PROJECT_ROOT / ".escalation_cache"

# Zotero-Pfad (lokal, nicht über API). User-Konvention aus CLAUDE.md:
# Zotero-Daten unter ~/FAUbox/Zotero, NICHT ~/Zotero.
DEFAULT_ZOTERO_ROOT = Path.home() / "FAUbox" / "Zotero"
ZOTERO_DB_NAME = "zotero.sqlite"
ZOTERO_STORAGE_NAME = "storage"

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
    source: str | None = None         # "zotero" | "openalex" | "unpaywall" | "crossref"
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


# -- PDF-Quellen --------------------------------------------------------------


def _normalize_doi(doi: str) -> str:
    """Kanonische DOI-Form (kleinbuchstaben, ohne URL-Präfix)."""
    return doi.strip().lower().replace("https://doi.org/", "").replace("http://doi.org/", "")


def _zotero_pdf_path(
    doi: str | None,
    zotero_root: Path = DEFAULT_ZOTERO_ROOT,
) -> tuple[Path, str] | None:
    """Sucht im lokalen Zotero nach einem PDF-Anhang für die DOI.

    Returns (pdf_path, attach_key) bei Treffer, sonst None.

    linkMode 0 (imported file) und 1 (imported URL) liegen unter
    `storage/<attachKey>/<filename>` — wir greifen nicht über die Zotero-API
    zu, sondern lesen die SQLite direkt (read-only Kopie nach /tmp). Damit
    bleibt der laufende Zotero-Client unberührt.
    """
    if not doi:
        return None
    doi_norm = _normalize_doi(doi)
    if not doi_norm:
        return None

    zotero_db = zotero_root / ZOTERO_DB_NAME
    storage_root = zotero_root / ZOTERO_STORAGE_NAME
    if not zotero_db.exists() or not storage_root.exists():
        return None

    # Read-only Snapshot ins tmp kopieren, damit ein offener Zotero-Client
    # nicht stört (SQLite WAL-Mode). Snapshot wird bei jedem Lookup neu
    # gezogen — kein Caching, weil Zotero-DB sich ändert, wenn der User
    # neue PDFs hinzufügt; aber das ist billig (~5 MB copy).
    snapshot = Path("/tmp/mojo_zotero_ro.sqlite")
    try:
        shutil.copy2(zotero_db, snapshot)
    except OSError:
        return None

    try:
        conn = sqlite3.connect(f"file:{snapshot}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            """
            SELECT ki.key AS attach_key, att.path AS att_path
              FROM items i
              JOIN itemData id ON id.itemID = i.itemID
              JOIN fields f ON f.fieldID = id.fieldID
              JOIN itemDataValues idv ON idv.valueID = id.valueID
              JOIN itemAttachments att ON att.parentItemID = i.itemID
              JOIN items ki ON ki.itemID = att.itemID
             WHERE f.fieldName = 'DOI'
               AND LOWER(idv.value) = ?
               AND att.contentType = 'application/pdf'
               AND att.linkMode IN (0, 1)
            """,
            (doi_norm,),
        )
        rows = cur.fetchall()
        conn.close()
    except sqlite3.Error:
        return None

    if not rows:
        return None

    for row in rows:
        attach_key = row["attach_key"]
        att_path = row["att_path"] or ""
        # path liegt typisch als "storage:<filename>" vor (linkMode 0/1).
        if att_path.startswith("storage:"):
            filename = att_path[len("storage:"):]
        else:
            # Selten: kein "storage:"-Präfix; trotzdem unter storage/<key>/
            filename = att_path
        if not filename:
            continue
        candidate = storage_root / attach_key / filename
        if candidate.exists() and candidate.is_file():
            return candidate, attach_key

    return None


# -- PDF-URL-Quellen (Web) ---------------------------------------------------


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
    doi = _normalize_doi(doi)
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
    doi = _normalize_doi(doi)
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
    zotero_root: Path = DEFAULT_ZOTERO_ROOT,
) -> FetchResult:
    """Versuche, einen Volltext für den Artikel zu beschaffen.

    Reihenfolge: Cache → Zotero lokal → OpenAlex best_oa_location →
    Unpaywall → Crossref. Bei Zotero-Treffer wird das PDF in den Cache
    kopiert, sonst heruntergeladen; danach pdftotext extrahiert, Cache
    geschrieben und das Resultat zurückgegeben.

    Returns FetchResult mit status:
      - "cache_hit": Volltext lag schon im Cache, kein Netz nötig
      - "ok":        Frischer Fetch + Extraktion erfolgreich
      - "no_pdf_url": Weder Zotero noch eine der drei Web-Quellen lieferte
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

    # 2) Zotero lokal — höchste Priorität (eigene Bibliothek, keine Paywall)
    source: str | None = None
    url: str | None = None
    zotero_hit = _zotero_pdf_path(doi, zotero_root=zotero_root)
    if zotero_hit is not None:
        src_pdf, attach_key = zotero_hit
        try:
            paths["pdf"].parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_pdf, paths["pdf"])
            source = "zotero"
            url = f"zotero://select/library/items/{attach_key}"
            if verbose:
                print(f"  [zotero] {article_id}: lokal aus {attach_key}")
        except OSError as e:
            notes.append(f"zotero copy failed: {e}")
            zotero_hit = None  # fall through to web sources

    # 3) Web-Quellen, falls Zotero kein Treffer
    if source is None:
        client = httpx.Client(headers={"User-Agent": USER_AGENT})
        try:
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
                    print(f"  [no_pdf_url] {article_id}: weder Zotero, OA, Unpaywall noch Crossref")
                return FetchResult(
                    article_id=article_id, status="no_pdf_url", notes=notes,
                )

            # Download
            if not _download_pdf(client, url, paths["pdf"]):
                notes.append(f"download failed for {url}")
                return FetchResult(
                    article_id=article_id, status="download_failed",
                    pdf_url=url, source=source, notes=notes,
                )
        finally:
            client.close()

    # 4) pdftotext-Extraktion (gemeinsamer Pfad für Zotero + Web)
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
