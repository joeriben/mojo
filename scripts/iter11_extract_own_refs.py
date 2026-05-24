"""Iter 11 / Phase 2: PDFs aus inventory.json → Plain Text → Refs-Extraktion.

Für jedes Item mit primary_pdf oder fallback_pdf:
1. pdftotext -layout {pdf} → backtest_data/own_bibliography/pdf_text/{zotero_key}.txt
   (idempotent: skip wenn schon da und PDF nicht neuer).
2. References-Section finden via Header-Regex (Literatur/References/Bibliographie/...).
3. Aus der Section:
   - alle DOIs via Regex (10.\\d{4,9}/...)
   - rohes Block-Splitting in einzelne Citation-Lines (heuristisch)
4. Output: backtest_data/own_bibliography/refs/{zotero_key}.json

Zur Kosten- und Datenhygiene:
- KEIN LLM, KEIN OpenAlex. Reine Regex + pdftotext (poppler).
- Idempotent: jeder Run ist ein No-Op, falls Cache existiert.

Hintergrund: Iter 10 Modell-Plateau bei 0.607 F1; Iter 11 testet ob ZWEISEITIGES
Bibliographic-Coupling (article_refs ∩ benjamin_cited_refs) das Plateau bricht.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "backtest_data" / "own_bibliography"
INVENTORY_PATH = DATA_DIR / "inventory.json"
PDF_TEXT_DIR = DATA_DIR / "pdf_text"
REFS_DIR = DATA_DIR / "refs"
PDF_TEXT_DIR.mkdir(parents=True, exist_ok=True)
REFS_DIR.mkdir(parents=True, exist_ok=True)

PDFTOTEXT = "/opt/homebrew/bin/pdftotext"

# Erkennt Header wie:
#   "References", "References:", "REFERENCES"
#   "Literatur", "Literaturverzeichnis", "Literatur:"
#   "Bibliografie" / "Bibliographie"
#   "Works Cited", "Quellen"
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

# DOI-Pattern. Bewusst etwas konservativ, um keine fortlaufenden Worttokens zu fressen.
DOI_RE = re.compile(
    r"\b10\.\d{4,9}/[A-Za-z0-9._;()/:\-]+", re.IGNORECASE
)

# Citation-Start-Pattern: Zeile beginnt links (kein bzw. wenig Einzug) mit "Nachname,"
# oder "Nachname und/and/&". Bewusst LL, weil Folgezeilen meist eingerückt sind.
CITATION_START_RE = re.compile(
    r"^[A-ZÄÖÜ][A-Za-zÄÖÜäöüß\-'\.]+(?:,\s+|[ \t]+(?:and|und|&)\s+)"
)


def ensure_pdf_text(pdf_path: Path, txt_path: Path) -> bool:
    """Erzeuge plain-text aus PDF, idempotent. True = ok, False = fail."""
    if not pdf_path.exists():
        return False
    if txt_path.exists() and txt_path.stat().st_mtime >= pdf_path.stat().st_mtime:
        return True
    try:
        subprocess.run(
            [PDFTOTEXT, "-layout", "-enc", "UTF-8", str(pdf_path), str(txt_path)],
            check=True,
            capture_output=True,
            timeout=120,
        )
        return txt_path.exists()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        print(f"  [warn] pdftotext failed for {pdf_path}: {e}", file=sys.stderr)
        return False


def find_references_block(text: str) -> tuple[str, int | None, str | None]:
    """Liefert (refs_text, header_line_no, header_label).

    Strategie: nimm das LETZTE Header-Vorkommen, das in der zweiten Hälfte des
    Dokuments liegt. So vermeiden wir, dass Body-Erwähnungen ("die Literatur
    zu X ist breit ...") als Refs-Anker missinterpretiert werden.
    """
    lines = text.splitlines()
    n = len(lines)
    min_line = int(n * 0.40)  # Header darf frühestens bei 40% liegen
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
    return "\n".join(lines[header_line + 1 :]), header_line, header_label


def cut_post_refs_garbage(refs_text: str) -> str:
    """Schneidet typische Anhänge nach der Refs-Section ab (Autorenbio, Copyright)."""
    cut_markers_re = re.compile(
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
    lines = refs_text.splitlines()
    for i, line in enumerate(lines):
        if cut_markers_re.match(line):
            return "\n".join(lines[:i])
    return refs_text


def extract_dois(text: str) -> list[str]:
    raw = DOI_RE.findall(text)
    cleaned = []
    seen = set()
    for d in raw:
        d = d.rstrip(".,;:)]")
        # Trim trailing umbrochene Bindestriche, die pdftotext einfügt.
        d = re.sub(r"-\s*\n\s*", "", d)
        d_lc = d.lower()
        if d_lc not in seen and len(d) > 7:
            seen.add(d_lc)
            cleaned.append(d_lc)
    return cleaned


def split_citations(refs_text: str) -> list[str]:
    """Heuristisches Splitting in einzelne Citations."""
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
        # Wenn die Zeile am linken Rand startet (≤ 3 spaces) UND wie ein
        # Citation-Start aussieht → neue Citation.
        leading = len(line) - len(line.lstrip(" \t"))
        is_start = leading <= 3 and CITATION_START_RE.match(line.lstrip())
        if is_start and current:
            citations.append(current)
            current = [line.strip()]
        else:
            current.append(line.strip())
    if current:
        citations.append(current)
    # Joine die Zeilen jeder Citation, killen multiple whitespace.
    joined = []
    for block in citations:
        text = re.sub(r"\s+", " ", " ".join(block)).strip()
        if len(text) >= 20:  # killt Müll wie "Seite 16 von 16"
            joined.append(text)
    return joined


def extract_refs_for_item(item: dict) -> dict:
    """Hauptarbeit pro Inventory-Item."""
    zkey = item["zotero_key"]
    txt_path = PDF_TEXT_DIR / f"{zkey}.txt"
    out_path = REFS_DIR / f"{zkey}.json"

    pdf_path_str = item.get("primary_pdf") or item.get("fallback_pdf")
    if not pdf_path_str:
        return {
            "zotero_key": zkey,
            "status": "no_pdf",
            "n_dois": 0,
            "n_citations": 0,
        }
    pdf_path = Path(pdf_path_str)
    if not ensure_pdf_text(pdf_path, txt_path):
        return {
            "zotero_key": zkey,
            "status": "pdftotext_failed",
            "n_dois": 0,
            "n_citations": 0,
        }
    text = txt_path.read_text(encoding="utf-8", errors="replace")
    refs_text, header_line, header_label = find_references_block(text)

    # Edge case: kein Header. Wir scannen das gesamte Dokument für DOIs (regex
    # ist robust gegen Layout-Artefakte) und verzichten auf raw_citations
    # (Body-Text wäre nur Noise).
    fallback_section = False
    if not refs_text:
        refs_text = text
        fallback_section = True

    refs_text = cut_post_refs_garbage(refs_text)
    dois = extract_dois(refs_text)
    # Bei fallback (kein Header) sind raw_citations nicht vertrauenswürdig,
    # darum überspringen.
    citations = [] if fallback_section else split_citations(refs_text)

    payload = {
        "zotero_key": zkey,
        "title": item.get("title"),
        "year": item.get("year"),
        "item_type": item.get("item_type"),
        "doi_of_item": item.get("doi"),
        "pdf_source": "zotero" if item.get("primary_pdf") else "fallback",
        "pdf_path": str(pdf_path),
        "txt_path": str(txt_path),
        "header_line_no": header_line,
        "header_label": header_label,
        "used_fallback_section": fallback_section,
        "dois_in_refs": dois,
        "n_dois": len(dois),
        "raw_citations": citations,
        "n_citations": len(citations),
        "status": "ok",
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    return {
        "zotero_key": zkey,
        "status": "ok",
        "n_dois": len(dois),
        "n_citations": len(citations),
        "used_fallback_section": fallback_section,
    }


def main() -> None:
    if not INVENTORY_PATH.exists():
        sys.exit(f"Inventory fehlt: {INVENTORY_PATH}. Erst iter11_inventory_own_bibliography.py laufen lassen.")
    inv = json.loads(INVENTORY_PATH.read_text())
    items = inv["items"]

    print(f"[refs] {len(items)} items im Inventory, extrahiere Refs aus PDFs ...")

    stats = defaultdict(int)
    per_item_summary = []
    for it in items:
        result = extract_refs_for_item(it)
        per_item_summary.append(result)
        stats[result["status"]] += 1
        stats["dois_total"] += result["n_dois"]
        stats["citations_total"] += result["n_citations"]
        if result.get("used_fallback_section"):
            stats["used_fallback_section"] += 1

    print(f"[refs] Status-Statistik:")
    for k in sorted(stats):
        print(f"  {k}: {stats[k]}")

    # Gesamtschnitt: Anzahl Items mit ≥ 1 DOI in Refs.
    n_ok = sum(1 for r in per_item_summary if r["status"] == "ok")
    n_with_dois = sum(1 for r in per_item_summary if r["n_dois"] > 0)
    n_with_citations = sum(1 for r in per_item_summary if r["n_citations"] > 0)
    print(
        f"[refs] {n_ok} extrahiert; {n_with_dois} mit ≥1 DOI; {n_with_citations} mit ≥1 raw-citation."
    )

    # Schreibe Sammelreport.
    report = {
        "stats": dict(stats),
        "n_items": len(items),
        "n_extracted_ok": n_ok,
        "n_items_with_dois": n_with_dois,
        "n_items_with_citations": n_with_citations,
        "per_item": per_item_summary,
    }
    (DATA_DIR / "refs_extraction_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2)
    )
    print(f"[refs] Report: {DATA_DIR / 'refs_extraction_report.json'}")


if __name__ == "__main__":
    main()
