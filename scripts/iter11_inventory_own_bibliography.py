"""Iter 11 / Phase 1: Inventory von Benjamins eigener Publikations-Bibliothek.

Zieht aus der laufenden Zotero-DB die Collection "Benjamin's publications"
(key QM7TZT44, collectionID=5) und listet pro Item:
- Metadata (title, type, year, DOI, authors)
- PDF-Pfad in Zotero-Storage (falls vorhanden)
- Fallback-Suche in /Users/joerissen/FAUbox/01_Projekte und
  /Users/joerissen/01_Archiv Projekte für Items ohne Zotero-PDF.

Output: backtest_data/own_bibliography/inventory.json

Hintergrund (Iter 10 Befund + Benjamin-Feedback 2026-05-24):
- Bibliometrie aus 3 Trigger-Autoren ist erschöpft (M9_Cascade_TunedBase=0.607 F1).
- Benjamin: "Gibt es z.B. Informationen über Korrelationen der von mir zitierten
  Werke mit den Literaturlisten der durchsuchten Titel?"
- Hebel: bisheriges f_ref_overlap_authored ist EINSEITIG (article cites Benjamin).
  Iter 11 baut ZWEISEITIGES Coupling: |article_refs ∩ benjamin_cited_refs|.

KEINE LLM-Calls. Reine Filesystem- + SQLite-Operationen.
"""

from __future__ import annotations

import json
import re
import shutil
import sqlite3
import sys
import unicodedata
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = PROJECT_ROOT / "backtest_data" / "own_bibliography"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_PATH = OUT_DIR / "inventory.json"

ZOTERO_LIVE_DB = Path("/Users/joerissen/FAUbox/Zotero/zotero.sqlite")
ZOTERO_STORAGE = Path("/Users/joerissen/FAUbox/Zotero/storage")
SNAPSHOT_DB = Path("/tmp/zotero_snapshot.sqlite")

COLLECTION_KEY = "QM7TZT44"  # "Benjamin's publications"
ACADEMIC_TYPES = ("bookSection", "journalArticle", "book", "thesis", "magazineArticle")

# Fallback-Verzeichnisse, in denen Benjamin eigene PDFs ablegt.
FALLBACK_DIRS = [
    Path("/Users/joerissen/FAUbox/01_Projekte"),
    Path("/Users/joerissen/01_Archiv Projekte"),
]


def ensure_snapshot() -> Path:
    """Snapshot der laufenden Zotero-DB nehmen, um Locking zu vermeiden."""
    if not ZOTERO_LIVE_DB.exists():
        sys.exit(f"Zotero-DB nicht gefunden: {ZOTERO_LIVE_DB}")
    # Snapshot nur erneuern wenn älter als die Live-DB oder fehlend.
    if (not SNAPSHOT_DB.exists()) or SNAPSHOT_DB.stat().st_mtime < ZOTERO_LIVE_DB.stat().st_mtime:
        shutil.copy2(ZOTERO_LIVE_DB, SNAPSHOT_DB)
    return SNAPSHOT_DB


def get_collection_id(con: sqlite3.Connection, key: str) -> int:
    row = con.execute("SELECT collectionID FROM collections WHERE key=?", (key,)).fetchone()
    if not row:
        sys.exit(f"Collection mit key {key} nicht gefunden")
    return int(row[0])


def fetch_field(con: sqlite3.Connection, item_id: int, field: str) -> str:
    row = con.execute(
        """
        SELECT idv.value
        FROM itemData id
        JOIN itemDataValues idv ON id.valueID = idv.valueID
        JOIN fields f ON id.fieldID = f.fieldID
        WHERE id.itemID=? AND f.fieldName=?
        """,
        (item_id, field),
    ).fetchone()
    return (row[0] if row else "") or ""


def fetch_authors(con: sqlite3.Connection, item_id: int) -> list[str]:
    rows = con.execute(
        """
        SELECT cr.firstName, cr.lastName
        FROM itemCreators ic
        JOIN creators cr ON ic.creatorID = cr.creatorID
        JOIN creatorTypes ct ON ic.creatorTypeID = ct.creatorTypeID
        WHERE ic.itemID=? AND ct.creatorType IN ('author','editor','translator')
        ORDER BY ic.orderIndex
        """,
        (item_id,),
    ).fetchall()
    names: list[str] = []
    for fn, ln in rows:
        fn = (fn or "").strip()
        ln = (ln or "").strip()
        if fn and ln:
            names.append(f"{ln}, {fn}")
        elif ln:
            names.append(ln)
        elif fn:
            names.append(fn)
    return names


def fetch_year(date_str: str) -> int | None:
    """Aus Zotero-Date-Feld (variabel formatiert) das Jahr extrahieren."""
    if not date_str:
        return None
    m = re.search(r"(\d{4})", date_str)
    return int(m.group(1)) if m else None


def fetch_pdf_attachments(con: sqlite3.Connection, item_id: int) -> list[dict]:
    """Liefert alle PDF-Attachments eines Items, inklusive resolved file path."""
    rows = con.execute(
        """
        SELECT i2.key, ia.path
        FROM itemAttachments ia
        JOIN items i2 ON ia.itemID = i2.itemID
        WHERE ia.parentItemID = ?
          AND ia.contentType = 'application/pdf'
          AND i2.itemID NOT IN (SELECT itemID FROM deletedItems)
        """,
        (item_id,),
    ).fetchall()
    attachments: list[dict] = []
    for att_key, path in rows:
        resolved = resolve_storage_path(att_key, path or "")
        attachments.append(
            {
                "attachment_key": att_key,
                "raw_path": path,
                "resolved_path": str(resolved) if resolved else None,
                "exists": bool(resolved and resolved.exists()),
            }
        )
    return attachments


def resolve_storage_path(att_key: str, raw_path: str) -> Path | None:
    """Resolved den Zotero storage:-Pfad zu einer absoluten Datei."""
    storage_dir = ZOTERO_STORAGE / att_key
    if not raw_path:
        # Suche irgendeine PDF im Storage-Folder.
        if storage_dir.exists():
            pdfs = list(storage_dir.glob("*.pdf"))
            if pdfs:
                return pdfs[0]
        return None
    if raw_path.startswith("storage:"):
        filename = raw_path.replace("storage:", "", 1)
        candidate = storage_dir / filename
        if candidate.exists():
            return candidate
        # Sometimes filename in DB diverges (umlaut normalization). Fallback: erste PDF.
        if storage_dir.exists():
            pdfs = list(storage_dir.glob("*.pdf"))
            if pdfs:
                return pdfs[0]
        return None
    # Absolute external path (rare)
    p = Path(raw_path)
    return p if p.exists() else None


# --------- Fallback-Suche in FAUbox-Projektordnern ---------

UMLAUT_FOLD = str.maketrans(
    {
        "ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
        "Ä": "Ae", "Ö": "Oe", "Ü": "Ue",
    }
)


def normalize_text(s: str) -> str:
    s = s or ""
    s = s.translate(UMLAUT_FOLD)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-zA-Z0-9]+", " ", s)
    return s.lower().strip()


def title_tokens(title: str, min_len: int = 4) -> set[str]:
    return {t for t in normalize_text(title).split() if len(t) >= min_len}


def collect_all_fallback_pdfs() -> list[Path]:
    """Listet alle PDFs in den Fallback-Verzeichnissen rekursiv."""
    pdfs: list[Path] = []
    for base in FALLBACK_DIRS:
        if not base.exists():
            continue
        for p in base.rglob("*.pdf"):
            if p.is_file():
                pdfs.append(p)
    return pdfs


def score_pdf_match(pdf_path: Path, item: dict) -> float:
    """Score wie gut ein PDF zu einem Item passt."""
    pdf_norm = normalize_text(pdf_path.stem)
    pdf_tokens = set(pdf_norm.split())

    title = item.get("title") or ""
    title_set = title_tokens(title)
    if not title_set:
        return 0.0
    overlap = len(title_set & pdf_tokens)
    base = overlap / max(1, len(title_set))

    # Jahres-Bonus.
    year = item.get("year")
    if year and str(year) in pdf_norm:
        base += 0.1

    # Author-Bonus (Nachname Jörissen ist auf jedem Eigentext).
    if "jorissen" in pdf_norm or "joerissen" in pdf_norm:
        base += 0.1

    # DOI-Bonus (selten, aber stark).
    doi = (item.get("doi") or "").lower()
    if doi:
        # PDF-Filename trägt selten den DOI direkt; nur als kleines Plus.
        last = doi.split("/")[-1]
        if last and last in pdf_norm:
            base += 0.2

    return min(base, 1.0)


def find_fallback_pdf(item: dict, all_pdfs: list[Path]) -> dict | None:
    title = item.get("title") or ""
    title_set = title_tokens(title)
    # Bei Titeln mit weniger als 2 disambiguierenden Tokens würden Fuzzy-Matches
    # zu False-Positives führen ("Einleitung", "Vorwort", "Introduction"...).
    if len(title_set) < 2:
        return None
    best_score = 0.0
    best_path: Path | None = None
    for pdf in all_pdfs:
        s = score_pdf_match(pdf, item)
        if s > best_score:
            best_score = s
            best_path = pdf
    if best_path and best_score >= 0.55:
        return {
            "fallback_path": str(best_path),
            "match_score": round(best_score, 3),
        }
    return None


# --------- Hauptlauf ---------


def main() -> None:
    snap = ensure_snapshot()
    con = sqlite3.connect(snap)
    coll_id = get_collection_id(con, COLLECTION_KEY)

    placeholders = ",".join("?" * len(ACADEMIC_TYPES))
    rows = con.execute(
        f"""
        SELECT i.itemID, i.key, it.typeName
        FROM collectionItems ci
        JOIN items i ON ci.itemID = i.itemID
        JOIN itemTypes it ON i.itemTypeID = it.itemTypeID
        WHERE ci.collectionID = ?
          AND i.itemID NOT IN (SELECT itemID FROM deletedItems)
          AND it.typeName IN ({placeholders})
        ORDER BY i.itemID DESC
        """,
        (coll_id, *ACADEMIC_TYPES),
    ).fetchall()

    items: list[dict] = []
    for item_id, key, type_name in rows:
        title = fetch_field(con, item_id, "title")
        date = fetch_field(con, item_id, "date")
        year = fetch_year(date)
        doi = (fetch_field(con, item_id, "DOI") or "").strip().lower()
        venue = (
            fetch_field(con, item_id, "publicationTitle")
            or fetch_field(con, item_id, "bookTitle")
            or fetch_field(con, item_id, "publisher")
        )
        authors = fetch_authors(con, item_id)
        pdfs = fetch_pdf_attachments(con, item_id)
        primary_pdf = next((p for p in pdfs if p["exists"]), None)

        items.append(
            {
                "zotero_item_id": item_id,
                "zotero_key": key,
                "item_type": type_name,
                "title": title,
                "year": year,
                "doi": doi or None,
                "venue": venue,
                "authors": authors,
                "pdf_attachments": pdfs,
                "primary_pdf": primary_pdf["resolved_path"] if primary_pdf else None,
                "has_pdf_in_zotero": bool(primary_pdf),
            }
        )
    con.close()

    # Für Items OHNE Zotero-PDF: Fallback-Suche.
    missing = [it for it in items if not it["has_pdf_in_zotero"]]
    print(f"[inventory] {len(items)} academic items, {len(missing)} ohne Zotero-PDF.")
    print(f"[inventory] Scanne Fallback-PDFs aus {len(FALLBACK_DIRS)} Wurzeln ...")
    all_fallback_pdfs = collect_all_fallback_pdfs()
    print(f"[inventory]   {len(all_fallback_pdfs)} PDFs in Fallback-Wurzeln gefunden.")

    fallback_hits = 0
    for it in missing:
        match = find_fallback_pdf(it, all_fallback_pdfs)
        if match:
            it["fallback_pdf"] = match["fallback_path"]
            it["fallback_match_score"] = match["match_score"]
            fallback_hits += 1
        else:
            it["fallback_pdf"] = None
            it["fallback_match_score"] = None

    # Zusammenfassung.
    summary = {
        "total_items": len(items),
        "have_zotero_pdf": sum(1 for it in items if it["has_pdf_in_zotero"]),
        "have_fallback_pdf_only": fallback_hits,
        "no_pdf": sum(
            1 for it in items if not it["has_pdf_in_zotero"] and not it.get("fallback_pdf")
        ),
        "have_doi": sum(1 for it in items if it.get("doi")),
        "by_type": {},
    }
    for it in items:
        t = it["item_type"]
        bucket = summary["by_type"].setdefault(
            t, {"total": 0, "with_pdf": 0, "with_doi": 0}
        )
        bucket["total"] += 1
        if it["has_pdf_in_zotero"] or it.get("fallback_pdf"):
            bucket["with_pdf"] += 1
        if it.get("doi"):
            bucket["with_doi"] += 1

    out = {
        "source": {
            "zotero_db": str(ZOTERO_LIVE_DB),
            "snapshot_db": str(snap),
            "zotero_storage": str(ZOTERO_STORAGE),
            "collection_key": COLLECTION_KEY,
            "academic_types": list(ACADEMIC_TYPES),
            "fallback_dirs": [str(p) for p in FALLBACK_DIRS],
        },
        "summary": summary,
        "items": items,
    }
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(f"[inventory] Geschrieben: {OUT_PATH}")
    print(f"[inventory] Summary: {json.dumps(summary, ensure_ascii=False)}")


if __name__ == "__main__":
    main()
