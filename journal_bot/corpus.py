"""Corpus-Ingest aus der konfigurierten Zotero-Collection (ZOTERO_COLLECTION).

Liest die Collection via lokaler Zotero-HTTP-API (Zotero muss laufen),
extrahiert PDF-Volltexte aus Zotero-Storage, schreibt corpus.json.

Kein LLM-Call. Reine Mechanik.
"""

from __future__ import annotations

import contextlib
import io
import json
import re
import sys
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Iterator

from pyzotero import zotero

from journal_bot.settings import (
    CORPUS_JSON,
    SINCE_YEAR,
    ZOTERO_COLLECTION,
    ZOTERO_STORAGE,
)


YEAR_RE = re.compile(r"(19|20)\d{2}")


@dataclass
class Publication:
    pub_id: str                 # Zotero item key
    item_type: str
    title: str
    authors: list[str]
    year: int | None
    venue: str
    doi: str
    abstract: str               # aus Zotero, kann leer sein
    fulltext: str               # aus PDF extrahiert, kann leer sein
    fulltext_chars: int
    fulltext_source: str        # "pdf:<attachment_key>" oder "" oder "no_pdf"
    extraction_notes: list[str] = field(default_factory=list)


@contextlib.contextmanager
def _silence_stderr() -> Iterator[None]:
    """pypdf ist laut. Wir fangen seine Warnings weg."""
    saved = sys.stderr
    sys.stderr = io.StringIO()
    try:
        yield
    finally:
        sys.stderr = saved


def _parse_year(date_str: str) -> int | None:
    if not date_str:
        return None
    m = YEAR_RE.search(date_str)
    if not m:
        return None
    y = int(m.group(0))
    return y if 1900 <= y <= 2100 else None


def _extract_pdf_text(pdf_path: Path, max_pages: int = 80) -> str:
    import pypdf

    try:
        with _silence_stderr():
            reader = pypdf.PdfReader(str(pdf_path))
            pages = reader.pages[:max_pages]
            return "\n".join(p.extract_text() or "" for p in pages)
    except Exception as e:
        return f"[[EXTRACTION_ERROR: {e}]]"


def _collect_authors(creators: list[dict]) -> list[str]:
    authors: list[str] = []
    for c in creators or []:
        if c.get("creatorType") != "author":
            continue
        first = (c.get("firstName") or "").strip()
        last = (c.get("lastName") or "").strip()
        name = (c.get("name") or "").strip()
        full = name or f"{last}, {first}".strip(", ")
        if full:
            authors.append(full)
    return authors


def _best_pdf_for_item(zot: zotero.Zotero, item_key: str) -> tuple[Path | None, str]:
    """Sucht das beste PDF-Attachment zu einem Item.

    Rückgabe: (path, source_string). path ist None wenn nichts gefunden.
    """
    try:
        children = zot.children(item_key)
    except Exception as e:
        return None, f"children_failed:{e}"

    pdfs = [
        c for c in children
        if c.get("data", {}).get("contentType") == "application/pdf"
    ]
    if not pdfs:
        return None, "no_pdf_attachment"

    for att in pdfs:
        att_key = att["key"]
        folder = ZOTERO_STORAGE / att_key
        if not folder.is_dir():
            continue
        files = sorted(folder.glob("*.pdf"))
        if files:
            return files[0], f"pdf:{att_key}"

    return None, "pdf_metadata_but_file_missing"


def ingest(
    collection_name: str = ZOTERO_COLLECTION,
    since_year: int = SINCE_YEAR,
    output: Path = CORPUS_JSON,
) -> dict:
    print(f"Verbinde mit lokaler Zotero-API …")
    zot = zotero.Zotero(library_id="0", library_type="user", local=True)

    print(f"Suche Collection {collection_name!r} …")
    collections = zot.collections()
    match = next(
        (c for c in collections if c["data"]["name"] == collection_name),
        None,
    )
    if not match:
        raise SystemExit(
            f"Collection {collection_name!r} nicht gefunden in Zotero. "
            f"Verfügbar: {[c['data']['name'] for c in collections[:20]]}"
        )

    print(f"Ziehe Items (kann ein paar Sekunden dauern) …")
    items = zot.everything(zot.collection_items(match["key"]))
    pubs_raw = [
        it for it in items
        if it.get("data", {}).get("itemType") not in ("attachment", "note")
    ]
    print(f"  {len(pubs_raw)} Publikationen insgesamt in der Collection")

    # authored_all: minimale Metadaten ALLER Publikationen (auch prä-2018).
    # Wird vom Citation-Tracker verwendet, um Zitate in neuen Beiträgen zu finden.
    authored_all: list[dict] = []
    for it in pubs_raw:
        data = it["data"]
        authored_all.append({
            "pub_id": it["key"],
            "item_type": data.get("itemType", ""),
            "title": (data.get("title") or "").strip(),
            "authors": _collect_authors(data.get("creators", [])),
            "year": _parse_year(data.get("date", "") or ""),
            "doi": (data.get("DOI") or "").strip(),
            "venue": (data.get("publicationTitle") or data.get("bookTitle") or "").strip(),
        })

    filtered: list[Publication] = []
    skipped_year = 0
    skipped_nopdf = 0
    pdf_errors = 0
    total_chars = 0

    for i, it in enumerate(pubs_raw, 1):
        data = it["data"]
        year = _parse_year(data.get("date", "") or "")
        if year is None or year < since_year:
            skipped_year += 1
            continue

        title = (data.get("title") or "").strip()
        pdf_path, source = _best_pdf_for_item(zot, it["key"])
        fulltext = ""
        notes: list[str] = []

        if pdf_path is not None:
            fulltext = _extract_pdf_text(pdf_path)
            if fulltext.startswith("[[EXTRACTION_ERROR"):
                pdf_errors += 1
                notes.append(fulltext)
                fulltext = ""
            elif not fulltext.strip():
                pdf_errors += 1
                notes.append("pdf_empty_text")
                fulltext = ""
        else:
            skipped_nopdf += 1
            notes.append(source)

        pub = Publication(
            pub_id=it["key"],
            item_type=data.get("itemType", ""),
            title=title,
            authors=_collect_authors(data.get("creators", [])),
            year=year,
            venue=(data.get("publicationTitle") or data.get("bookTitle") or "").strip(),
            doi=(data.get("DOI") or "").strip(),
            abstract=(data.get("abstractNote") or "").strip(),
            fulltext=fulltext,
            fulltext_chars=len(fulltext),
            fulltext_source=source if fulltext else "",
            extraction_notes=notes,
        )
        filtered.append(pub)
        total_chars += pub.fulltext_chars
        print(
            f"  [{i:>3}/{len(pubs_raw)}] {year}  "
            f"{pub.title[:70]:<70}  "
            f"{pub.fulltext_chars:>8,d} chars"
        )

    with_text = [p for p in filtered if p.fulltext_chars > 0]
    print()
    print("=== Ergebnis ===")
    print(f"In Collection:                  {len(pubs_raw)}")
    print(f"Publikationen ab {since_year}:         {len(filtered)}")
    print(f"  davon mit Volltext:           {len(with_text)}")
    print(f"  davon ohne PDF:               {skipped_nopdf}")
    print(f"  davon mit PDF-Fehler:         {pdf_errors}")
    print(f"Gesamt-Volltext (Zeichen):      {total_chars:,}")
    print(f"Grobe Token-Schätzung (÷4):     ~{total_chars // 4:,}")
    print(f"Übersprungen (Jahr < {since_year}):     {skipped_year}")

    payload = {
        "collection": collection_name,
        "since_year": since_year,
        "count": len(filtered),
        "count_with_fulltext": len(with_text),
        "count_authored_all": len(authored_all),
        "total_chars": total_chars,
        "publications": [asdict(p) for p in filtered],
        "authored_all": authored_all,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nGeschrieben: {output}")
    return payload
