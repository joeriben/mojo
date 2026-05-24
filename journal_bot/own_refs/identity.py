"""Canonical-ID-Auflösung für eigene Publikationen.

Strategie:
1. DOI bekannt: `canonical_id = "doi:" + normalize_doi(raw)`
2. DOI fehlt: `canonical_id = "hash:" + sha1(normalize(title)|year|first_author_lastname)[:16]`

Konsequenz: dasselbe Item aus Zotero (mit DOI) und aus einem User-Ordner
(ohne DOI in den Metadaten, aber identischer Titel) wird in der Regel zu
*zwei* canonical_ids führen, weil die Folder-Quelle den DOI nicht kennt. Der
Build-Orchestrator gleicht das in einem zweiten Schritt aus, indem er nach
Folder-Ingest noch einmal Title-Hash → DOI-Lookup gegen die `publications`-
Tabelle macht und Duplikate verschmilzt (siehe `build.merge_duplicates`).

Idempotent: gleiche Eingabe → gleiche canonical_id.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata

_UMLAUT_FOLD = str.maketrans(
    {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
     "Ä": "Ae", "Ö": "Oe", "Ü": "Ue"}
)

_DOI_URL_PREFIXES = (
    "https://doi.org/",
    "http://doi.org/",
    "https://dx.doi.org/",
    "http://dx.doi.org/",
    "doi:",
)


def normalize_doi(raw: str | None) -> str:
    """Lowercase, strip URL-Prefixes und nachstehende Satzzeichen."""
    if not raw:
        return ""
    d = raw.strip().lower().rstrip(".,;:)]")
    for pfx in _DOI_URL_PREFIXES:
        if d.startswith(pfx):
            d = d[len(pfx):]
            break
    return d


def normalize_text(s: str | None) -> str:
    """Umlaut-fold, NFKD, drop combining marks, non-alnum → single spaces, lower."""
    if not s:
        return ""
    s = s.translate(_UMLAUT_FOLD)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-zA-Z0-9]+", " ", s)
    return s.lower().strip()


def first_author_lastname(authors: list[str]) -> str:
    """Aus einer Zotero-Author-Liste ('Lastname, Firstname' oder 'Lastname')
    den Nachnamen des Erstautors ziehen.
    """
    if not authors:
        return ""
    first = authors[0].strip()
    if "," in first:
        return first.split(",", 1)[0].strip()
    parts = first.split()
    return parts[-1] if parts else ""


def canonical_id_for(
    doi: str | None,
    title: str,
    year: int | None,
    authors: list[str],
) -> str:
    """Liefert eine stabile canonical_id.

    DOI hat Vorrang. Ohne DOI: Hash über title|year|first_author_lastname.
    Identische Werte → identische ID.
    """
    norm_doi = normalize_doi(doi)
    if norm_doi:
        return f"doi:{norm_doi}"
    seed = (
        f"{normalize_text(title)}|{year if year is not None else ''}"
        f"|{normalize_text(first_author_lastname(authors))}"
    )
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:16]
    return f"hash:{digest}"
