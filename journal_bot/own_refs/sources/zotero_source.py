"""Zotero-Collection als Source.

Portiert aus `journal_bot/corpus.py`, aber zwei wichtige Unterschiede:
1. **Liefert ALLE Items der Collection** (nicht gefiltert nach SINCE_YEAR).
   Eigenwerk-Bibliographic-Coupling braucht den Refs-Index der älteren
   Pubs genauso wie den der jüngeren.
2. **Liefert pro Item den DateModified-Wert**, damit Build-Orchestrator
   inkrementell entscheiden kann.

Keine Volltext-Extraktion hier — das geschieht in `extract.py`. Die Source
liefert nur Metadaten + den PDF-Pfad (falls in Zotero-Storage auflösbar).

Greift auf die lokale Zotero-HTTP-API zu (pyzotero `local=True`). Zotero
muss laufen — sonst Exception.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from pyzotero import zotero

from journal_bot.own_refs.sources.base import DiscoveredItem


_ACADEMIC_ITEM_TYPES = {
    "journalArticle", "bookSection", "book", "thesis",
    "magazineArticle", "conferencePaper", "preprint", "report",
}


@dataclass
class ZoteroSource:
    collection_key: str                 # z.B. "QM7TZT44"
    zotero_storage: Path                # /Users/joerissen/FAUbox/Zotero/storage
    library_id: str = "0"
    library_type: str = "user"

    source_type: str = "zotero"

    @property
    def source_key(self) -> str:
        return self.collection_key

    # ---- discovery -----------------------------------------------------------

    def discover(self) -> Iterator[DiscoveredItem]:
        zot = zotero.Zotero(
            library_id=self.library_id, library_type=self.library_type, local=True
        )
        items = zot.everything(zot.collection_items(self.collection_key))
        pubs_raw = [
            it for it in items
            if it.get("data", {}).get("itemType") in _ACADEMIC_ITEM_TYPES
        ]
        for it in pubs_raw:
            data = it["data"]
            zkey = it["key"]
            pdf_path, pdf_mtime, notes = self._resolve_pdf(zot, zkey)
            yield DiscoveredItem(
                source_type="zotero",
                source_key=self.collection_key,
                source_item_id=zkey,
                title=(data.get("title") or "").strip(),
                authors=_collect_authors(data.get("creators", [])),
                doi=(data.get("DOI") or "").strip() or None,
                year=_parse_year(data.get("date", "") or ""),
                item_type=data.get("itemType") or None,
                venue=(
                    data.get("publicationTitle")
                    or data.get("bookTitle")
                    or data.get("publisher")
                    or None
                ),
                pdf_path=str(pdf_path) if pdf_path else None,
                pdf_mtime=pdf_mtime,
                zotero_date_modified=data.get("dateModified") or None,
                notes=notes,
            )

    # ---- helpers -------------------------------------------------------------

    def _resolve_pdf(
        self, zot: zotero.Zotero, item_key: str
    ) -> tuple[Path | None, float | None, list[str]]:
        try:
            children = zot.children(item_key)
        except Exception as e:  # network / API hiccup, non-fatal
            return None, None, [f"children_failed:{e}"]

        pdfs = [
            c for c in children
            if c.get("data", {}).get("contentType") == "application/pdf"
        ]
        if not pdfs:
            return None, None, ["no_pdf_attachment"]

        for att in pdfs:
            att_key = att["key"]
            folder = self.zotero_storage / att_key
            if not folder.is_dir():
                continue
            files = sorted(folder.glob("*.pdf"))
            if files:
                p = files[0]
                try:
                    mtime = p.stat().st_mtime
                except OSError:
                    mtime = None
                return p, mtime, []
        return None, None, ["pdf_metadata_but_file_missing"]


# ----- module-level helpers -----------------------------------------------------


def _parse_year(date_str: str) -> int | None:
    import re

    m = re.search(r"(19|20)\d{2}", date_str or "")
    if not m:
        return None
    y = int(m.group(0))
    return y if 1900 <= y <= 2100 else None


def _collect_authors(creators: list[dict]) -> list[str]:
    out: list[str] = []
    for c in creators or []:
        if c.get("creatorType") not in ("author", "editor", "translator"):
            continue
        first = (c.get("firstName") or "").strip()
        last = (c.get("lastName") or "").strip()
        name = (c.get("name") or "").strip()
        full = name or (f"{last}, {first}".strip(", ") if (first or last) else "")
        if full:
            out.append(full)
    return out
