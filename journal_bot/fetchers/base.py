"""Basisklasse für Fetcher und das normalisierte Article-Schema."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from journal_bot.settings import JournalConfig


@dataclass
class Article:
    """Ein normalisierter Eintrag, Journal-unabhängig."""

    journal: str           # short name, z.B. "ZfE"
    journal_full: str      # voller Name
    title: str
    authors: list[str] = field(default_factory=list)
    abstract: str = ""
    url: str = ""
    doi: str = ""
    published: str = ""    # ISO-Datum oder Fallback-String
    issue: str = ""

    def identifier(self) -> str:
        return self.doi or self.url or self.title


class Fetcher(Protocol):
    jc: JournalConfig

    def fetch(self) -> list[Article]:
        ...
