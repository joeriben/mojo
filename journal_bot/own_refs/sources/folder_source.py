"""Filesystem-Folder als Source.

Rekursiv `.rglob("*.pdf")` über einen User-Pfad, ableiten von Title aus dem
Dateinamen, optional Match-Score gegen einen Hint (z. B. Zotero-Item-Titel)
falls jemand das später als Cross-Source-Validierung nutzen will. Im
Standardfall liefert FolderSource ein PDF pro Discovery, mit:

- `title`: aus dem Dateinamen (Stem, Underscore/Dash → Space, simple Heuristik)
- `year`: aus 4-stelligem Number-Token im Dateinamen, falls plausibel
- `pdf_path`: absoluter Pfad
- `pdf_mtime`: stat().st_mtime
- `doi`: None (Filesystem hat keine DOI-Info)
- `match_score`: None (wird vom Build-Orchestrator gesetzt, wenn er nach
  Folder-Ingest gegen die Zotero-DOI-Index Reconciliation versucht)

Portierungs-Hinweise aus `scripts/iter11_inventory_own_bibliography.py`:
- Title-Token-Match-Score und Author-/Year-/DOI-Boni werden hier NICHT
  ausgeführt — das ist eine Cross-Source-Reconciliation-Aufgabe, die im
  Build-Orchestrator gegen die `publications`-Tabelle läuft (siehe
  `build.merge_duplicates`).
- FAUbox-Subtree-Filter (z. B. nur `01_Projekte`) wird über die Konfiguration
  des `folder_path` erreicht — keine Hardcoded-Default-Wurzeln.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from journal_bot.own_refs.sources.base import DiscoveredItem


YEAR_RE = re.compile(r"(?<!\d)(19|20)\d{2}(?!\d)")


@dataclass
class FolderSource:
    folder_path: Path                   # absoluter Pfad, rekursiv durchsucht
    skip_symlinks: bool = False         # default: Symlinks folgen (FAUbox/iCloud nutzen Symlinks)

    source_type: str = "folder"

    @property
    def source_key(self) -> str:
        return str(self.folder_path.resolve())

    # ---- discovery -----------------------------------------------------------

    def discover(self) -> Iterator[DiscoveredItem]:
        root = self.folder_path
        if not root.exists():
            return
        if not root.is_dir():
            return
        iterator = (
            (p for p in root.rglob("*.pdf") if not p.is_symlink())
            if self.skip_symlinks
            else root.rglob("*.pdf")
        )
        for pdf in sorted(iterator):
            if not pdf.is_file():
                # is_file() folgt Symlinks, also gilt der Test auch für Symlink-Ziele
                continue
            try:
                mtime = pdf.stat().st_mtime
            except OSError:
                continue
            title = _title_from_filename(pdf.stem)
            year = _year_from_filename(pdf.stem)
            yield DiscoveredItem(
                source_type="folder",
                source_key=self.source_key,
                source_item_id=str(pdf.resolve()),
                title=title,
                authors=[],
                doi=None,
                year=year,
                item_type=None,
                venue=None,
                pdf_path=str(pdf.resolve()),
                pdf_mtime=mtime,
            )


# ----- helpers ---------------------------------------------------------------


def _title_from_filename(stem: str) -> str:
    """Aus PDF-Dateinamen einen plausiblen Titel rekonstruieren.

    Konvertiert Underscores/Dashes zu Spaces, kollabiert Whitespace, entfernt
    typische Garbage-Suffixe (`_OCR`, `_v2`, `_final` etc.).
    """
    t = stem
    t = re.sub(r"[_\-]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    # Strip trivial trailing garbage tokens
    t = re.sub(
        r"\s+(OCR|v\d+|final|draft|rev\d*|copy|kopie|scan)\s*$",
        "",
        t,
        flags=re.IGNORECASE,
    )
    return t


def _year_from_filename(stem: str) -> int | None:
    m = YEAR_RE.search(stem)
    if not m:
        return None
    y = int(m.group(0))
    return y if 1900 <= y <= 2100 else None
