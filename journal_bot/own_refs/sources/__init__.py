"""Quellen-Discovery für die Refs-Pipeline.

Eine Source ist eine Iterable über `DiscoveredItem`s. Jede Source ist
gleichberechtigt; im Build-Orchestrator werden die Items aus allen
konfigurierten Sources zusammengeführt, dedupliziert (per `canonical_id`)
und kumulativ persistiert.
"""

from journal_bot.own_refs.sources.base import DiscoveredItem, Source
from journal_bot.own_refs.sources.folder_source import FolderSource
from journal_bot.own_refs.sources.zotero_source import ZoteroSource

__all__ = ["DiscoveredItem", "Source", "FolderSource", "ZoteroSource"]
