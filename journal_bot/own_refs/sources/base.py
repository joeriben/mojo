"""Source-Protocol für die Multi-Source-Refs-Pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator, Protocol


@dataclass
class DiscoveredItem:
    """Ein während Source-Discovery gefundenes Item, vor Identity-Auflösung.

    Felder, die optional sind (DOI, Year, ...), sind je nach Source unterschiedlich
    vorhanden:
    - ZoteroSource liefert i. d. R. vollständige Metadaten + ggf. PDF-Pfad.
    - FolderSource muss aus dem PDF-Dateinamen heuristisch ableiten und liefert
      meist nur Title (aus dem Dateinamen oder via PDF-Metadaten) + PDF-Pfad,
      ggf. ein Match-Score.
    """

    source_type: str            # "zotero" | "folder"
    source_key: str             # Collection-Key oder absoluter Folder-Pfad
    source_item_id: str         # Zotero-Item-Key oder absoluter PDF-Pfad
    title: str
    authors: list[str] = field(default_factory=list)
    doi: str | None = None
    year: int | None = None
    item_type: str | None = None
    venue: str | None = None
    pdf_path: str | None = None
    pdf_mtime: float | None = None
    zotero_date_modified: str | None = None
    match_score: float | None = None
    notes: list[str] = field(default_factory=list)


class Source(Protocol):
    """Ein Source-Objekt liefert eine endliche Iteration über `DiscoveredItem`s.

    Implementierungen dürfen Caching, Snapshots etc. nutzen — der Build-Orchestrator
    konsumiert nur die Items und entscheidet anhand der Identity-Auflösung, ob ein
    Item neu, geändert oder unverändert ist.
    """

    source_type: str
    source_key: str

    def discover(self) -> Iterator[DiscoveredItem]: ...
