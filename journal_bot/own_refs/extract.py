"""PDF → Plain-Text → Refs-Section → DOIs + Free-Text-Citations.

Portiert aus `scripts/iter11_extract_own_refs.py` (Iter-11-Backtest, dort
gegen 109 echte PDFs validiert) mit folgenden Änderungen für den Produktiv-
Track:
- Cache-Verzeichnis ist konfigurierbar (Default:
  `<project_root>/.own_refs_cache/fulltext/`).
- Cache-Key ist sha1(absolute pdf-path), nicht zotero_key — Folder-Sources
  haben keinen Zotero-Key.
- Funktionen liefern Dataclass-Strukturen statt JSON-Files zu schreiben.
- Idempotenz: ist der `.txt`-Cache jünger als das PDF, wird pdftotext
  übersprungen.

KEINE LLM-Calls. Reine pdftotext + Regex.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FULLTEXT_CACHE = PROJECT_ROOT / ".own_refs_cache" / "fulltext"

# Auf macOS Homebrew. Auf Linux i. d. R. /usr/bin/pdftotext.
PDFTOTEXT_CANDIDATES = (
    "/opt/homebrew/bin/pdftotext",
    "/usr/local/bin/pdftotext",
    "/usr/bin/pdftotext",
    "pdftotext",
)


# -- Regexes ------------------------------------------------------------------

HEADER_RE = re.compile(
    r"^[ \t]*("
    r"references"
    r"|literatur(?:verzeichnis)?"
    r"|bibliograph(?:y|ie)"
    r"|bibliografie"
    r"|works[ \t]+cited"
    r"|quellen(?:verzeichnis)?"
    r"|cited[ \t]+works"
    r"|literatur[ \t]+und[ \t]+quellen"
    r")[ \t:.]*$",
    re.IGNORECASE,
)

DOI_RE = re.compile(r"\b10\.\d{4,9}/[A-Za-z0-9._;()/:\-]+", re.IGNORECASE)

CITATION_START_RE = re.compile(
    r"^[A-ZÄÖÜ][A-Za-zÄÖÜäöüß\-'\.]+(?:,\s+|[ \t]+(?:and|und|&)\s+)"
)

POST_REFS_CUT_RE = re.compile(
    r"^[ \t]*("
    r"(?:open[ \t]+)?access\s+this\s+chapter\s+is\s+licensed"
    r"|über[ \t]+(?:die[ \t]+)?autor"
    r"|about[ \t]+the[ \t]+author"
    r"|biographische[ \t]+notiz"
    r"|autorenangaben"
    r"|impressum"
    r"|copyright[ \t]+©"
    r"|appendix"
    r"|anhang"
    r")\b",
    re.IGNORECASE,
)


# -- Dataclasses --------------------------------------------------------------


@dataclass
class ExtractionResult:
    pdf_path: str
    txt_path: str | None
    fulltext_chars: int = 0
    refs_text: str = ""
    refs_header_line: int | None = None
    refs_header_label: str | None = None
    used_fallback_section: bool = False
    dois_in_refs: list[str] = field(default_factory=list)
    raw_citations: list[str] = field(default_factory=list)
    status: str = "ok"                  # ok | no_pdf | pdftotext_failed | pdf_empty
    notes: list[str] = field(default_factory=list)


# -- pdftotext ----------------------------------------------------------------


def _resolve_pdftotext() -> str | None:
    import shutil
    for cand in PDFTOTEXT_CANDIDATES:
        if Path(cand).exists() or shutil.which(cand):
            return cand
    return None


def _pdf_cache_path(pdf_path: Path, cache_dir: Path) -> Path:
    h = hashlib.sha1(str(pdf_path.resolve()).encode("utf-8")).hexdigest()[:16]
    return cache_dir / f"{h}.txt"


def ensure_fulltext(
    pdf_path: Path,
    cache_dir: Path = DEFAULT_FULLTEXT_CACHE,
    force: bool = False,
) -> tuple[Path | None, str]:
    """Stellt sicher, dass für `pdf_path` ein Plain-Text-Cache existiert.

    Returns: (txt_path | None, status). Status ∈ {ok, no_pdf, pdftotext_failed,
    pdftotext_missing}.
    Idempotent: wenn txt-Cache aktueller als PDF, wird pdftotext nicht erneut
    aufgerufen.
    """
    if not pdf_path.exists() or not pdf_path.is_file():
        return None, "no_pdf"

    cache_dir.mkdir(parents=True, exist_ok=True)
    txt_path = _pdf_cache_path(pdf_path, cache_dir)

    if not force and txt_path.exists():
        try:
            if txt_path.stat().st_mtime >= pdf_path.stat().st_mtime:
                return txt_path, "ok"
        except OSError:
            pass

    pdftotext = _resolve_pdftotext()
    if pdftotext is None:
        return None, "pdftotext_missing"

    try:
        subprocess.run(
            [pdftotext, "-layout", "-enc", "UTF-8", str(pdf_path), str(txt_path)],
            check=True, capture_output=True, timeout=120,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        print(f"  [warn] pdftotext failed for {pdf_path}: {e}", file=sys.stderr)
        return None, "pdftotext_failed"

    return (txt_path, "ok") if txt_path.exists() else (None, "pdftotext_failed")


# -- Refs-Section + Heuristiken ----------------------------------------------


def find_references_block(text: str) -> tuple[str, int | None, str | None]:
    """Liefert (refs_text, header_line_no, header_label).

    Strategie: nimm das LETZTE Header-Vorkommen ab 40 % Dokumentenlänge.
    Body-Erwähnungen ('die Literatur zu X ist breit ...') sollen so vermieden
    werden.
    """
    lines = text.splitlines()
    n = len(lines)
    if n == 0:
        return "", None, None
    min_line = int(n * 0.40)
    header_line = None
    header_label = None
    for i, line in enumerate(lines):
        if i < min_line:
            continue
        m = HEADER_RE.match(line.strip())
        if m:
            header_line = i
            header_label = m.group(1)
    if header_line is None:
        return "", None, None
    return "\n".join(lines[header_line + 1:]), header_line, header_label


def cut_post_refs_garbage(refs_text: str) -> str:
    """Schneidet typische Anhänge nach der Refs-Section ab."""
    lines = refs_text.splitlines()
    for i, line in enumerate(lines):
        if POST_REFS_CUT_RE.match(line):
            return "\n".join(lines[:i])
    return refs_text


def extract_dois(text: str) -> list[str]:
    raw = DOI_RE.findall(text)
    seen: set[str] = set()
    out: list[str] = []
    for d in raw:
        d = d.rstrip(".,;:)]")
        d = re.sub(r"-\s*\n\s*", "", d)
        d_lc = d.lower()
        if d_lc not in seen and len(d_lc) > 7:
            seen.add(d_lc)
            out.append(d_lc)
    return out


def split_citations(refs_text: str) -> list[str]:
    """Heuristisches Splitting in einzelne Citations.

    Eine neue Citation startet, wenn die Zeile links beginnt (≤ 3 Spaces)
    und mit `Lastname, …` / `Lastname and …` / `Lastname & …` einsetzt.
    Folgezeilen werden eingerückt erwartet und gehören zur laufenden Citation.
    """
    lines = refs_text.splitlines()
    citations: list[list[str]] = []
    current: list[str] = []
    for raw_line in lines:
        line = raw_line.rstrip()
        if not line.strip():
            if current:
                citations.append(current)
                current = []
            continue
        leading = len(line) - len(line.lstrip(" \t"))
        is_start = leading <= 3 and bool(CITATION_START_RE.match(line.lstrip()))
        if is_start and current:
            citations.append(current)
            current = [line.strip()]
        else:
            current.append(line.strip())
    if current:
        citations.append(current)
    out: list[str] = []
    for block in citations:
        joined = re.sub(r"\s+", " ", " ".join(block)).strip()
        if len(joined) >= 20:
            out.append(joined)
    return out


# -- Hauptfunktion ------------------------------------------------------------


def extract_refs(
    pdf_path: Path,
    cache_dir: Path = DEFAULT_FULLTEXT_CACHE,
    force: bool = False,
) -> ExtractionResult:
    """Vollständige Extraktion eines PDFs: Fulltext → Refs-Section → DOIs + Citations."""
    txt_path, status = ensure_fulltext(pdf_path, cache_dir, force=force)
    if txt_path is None:
        return ExtractionResult(
            pdf_path=str(pdf_path), txt_path=None, status=status,
            notes=[f"ensure_fulltext={status}"],
        )

    text = txt_path.read_text(encoding="utf-8", errors="replace")
    chars = len(text)
    if not text.strip():
        return ExtractionResult(
            pdf_path=str(pdf_path), txt_path=str(txt_path),
            fulltext_chars=chars, status="pdf_empty",
        )

    refs_text, header_line, header_label = find_references_block(text)
    used_fallback = False
    if not refs_text:
        refs_text = text
        used_fallback = True

    refs_text = cut_post_refs_garbage(refs_text)
    dois = extract_dois(refs_text)
    citations = [] if used_fallback else split_citations(refs_text)

    return ExtractionResult(
        pdf_path=str(pdf_path),
        txt_path=str(txt_path),
        fulltext_chars=chars,
        refs_text=refs_text,
        refs_header_line=header_line,
        refs_header_label=header_label,
        used_fallback_section=used_fallback,
        dois_in_refs=dois,
        raw_citations=citations,
        status="ok",
    )
