"""Akzeptanz-Tests für `journal_bot.own_refs` (MOJO 2.0 §3.1).

Drei Systemtests aus HANDOVER §1 Akzeptanzkriterium 7:
1. Folder-Ingest-Idempotenz (zweiter Lauf = no-op, alles unchanged)
2. Dedup über DOI bei Zotero + Folder mit demselben Item
   (eine `canonical_id`, zwei `source_refs`)
3. Re-Ingest mit neuem PDF im bekannten Folder (genau das eine neu, Rest skipped)

Plus Unit-Tests für `identity` und `discourse`, weil das die zwei Stellen sind,
an denen sich Output-Stabilität / Reproduzierbarkeit entscheidet.

Extract und OpenAlex-Resolve werden gemockt — der Test-Run macht KEINE
pdftotext-Subprozesse und KEINE Netz-Calls.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator
from unittest.mock import MagicMock

import pytest

from journal_bot.own_refs import build as build_mod
from journal_bot.own_refs import extract as extract_mod
from journal_bot.own_refs import resolve as resolve_mod
from journal_bot.own_refs.build import build
from journal_bot.own_refs.discourse import classify, available_discourses
from journal_bot.own_refs.extract import ExtractionResult
from journal_bot.own_refs.identity import (
    canonical_id_for, first_author_lastname, normalize_doi, normalize_text,
)
from journal_bot.own_refs.resolve import ResolvedRef
from journal_bot.own_refs.sources import FolderSource
from journal_bot.own_refs.sources.base import DiscoveredItem
from journal_bot.own_refs.store import OwnRefsStore


# ----- Mock-Helpers ---------------------------------------------------------


def _mock_extract_factory(per_pdf_dois: dict[str, list[str]]):
    """Liefert eine Mock-`extract_refs`, die nach pdf-Dateinamen DOIs aus
    `per_pdf_dois` zurückgibt (Default: leere Liste).
    """
    def fake_extract(pdf_path: Path, cache_dir=None, force: bool = False):
        name = Path(pdf_path).name
        dois = per_pdf_dois.get(name, [])
        return ExtractionResult(
            pdf_path=str(pdf_path),
            txt_path=str(pdf_path) + ".txt",
            fulltext_chars=1234,
            refs_text="\n".join(dois),
            refs_header_label="References",
            refs_header_line=10,
            dois_in_refs=dois,
            raw_citations=[],
            status="ok",
        )
    return fake_extract


def _mock_resolve_factory(resolved_oa: dict[str, str | None]):
    """`resolved_oa[doi] = oa_id | None`."""
    def fake_resolve(dois, cache_dir=None, verbose=False):
        out = {}
        for d in dois:
            oa = resolved_oa.get(d)
            out[d] = ResolvedRef(doi=d, oa_id=oa, year=2020 if oa else None)
        return out
    return fake_resolve


# ----- Test 1: Folder-Ingest-Idempotenz -------------------------------------


def test_folder_ingest_idempotent(tmp_path, monkeypatch):
    """Zweiter Lauf einer unveränderten Folder-Source: 0 new, alle skipped."""
    base = tmp_path / "pubs"
    base.mkdir()
    (base / "Joerissen_2020_Bildung.pdf").write_bytes(b"%PDF-1.4 a")
    (base / "Joerissen_2024_Resilienz.pdf").write_bytes(b"%PDF-1.4 b")

    monkeypatch.setattr(
        build_mod, "extract_refs",
        _mock_extract_factory({
            "Joerissen_2020_Bildung.pdf": ["10.1234/x.1"],
            "Joerissen_2024_Resilienz.pdf": ["10.1234/x.2"],
        }),
    )
    monkeypatch.setattr(
        build_mod, "resolve_dois",
        _mock_resolve_factory({
            "10.1234/x.1": "https://openalex.org/W1",
            "10.1234/x.2": "https://openalex.org/W2",
        }),
    )

    db = tmp_path / "own_refs.db"
    src = FolderSource(folder_path=base)

    s1 = build([src], db_path=db, verbose=False)
    assert s1.items_discovered == 2
    assert s1.items_new == 2
    assert s1.items_skipped_unchanged == 0
    assert s1.pdfs_extracted == 2
    assert s1.refs_total == 2
    assert s1.dois_resolved == 2

    s2 = build([src], db_path=db, verbose=False)
    assert s2.items_discovered == 2
    assert s2.items_new == 0
    assert s2.items_updated == 0
    assert s2.items_skipped_unchanged == 2
    assert s2.pdfs_extracted == 0   # nichts neu extrahiert


# ----- Test 2: Dedup über DOI bei Zotero + Folder ---------------------------


class _FakeZoteroSource:
    """Source-Stub, der einen DiscoveredItem-Stream simuliert."""
    source_type = "zotero"
    source_key = "TESTCOLL"

    def __init__(self, items: list[DiscoveredItem]):
        self._items = items

    def discover(self) -> Iterator[DiscoveredItem]:
        yield from self._items


def test_dedup_zotero_folder_same_doi(tmp_path, monkeypatch):
    """Dasselbe Item kommt aus Zotero (mit DOI) und Folder (ohne DOI, gleicher
    Titel/Autor/Jahr) — am Ende: 1 canonical_id (doi:...) mit 2 source_refs.
    """
    base = tmp_path / "folder"
    base.mkdir()
    folder_pdf = base / "Joerissen_2020_Bildung.pdf"
    folder_pdf.write_bytes(b"%PDF-1.4")

    # Zotero kennt DOI + denselben Title, identischer first-author
    zot_item = DiscoveredItem(
        source_type="zotero",
        source_key="TESTCOLL",
        source_item_id="ZK0001",
        title="Joerissen 2020 Bildung",
        authors=["Jörissen, Benjamin"],
        doi="10.5555/bildung.2020",
        year=2020,
        item_type="journalArticle",
        venue="Some Journal",
        pdf_path="/fake/zotero/storage/ZK0001/something.pdf",
        pdf_mtime=1000.0,
        zotero_date_modified="2020-01-01T00:00:00Z",
    )

    monkeypatch.setattr(
        build_mod, "extract_refs",
        _mock_extract_factory({
            "something.pdf": ["10.7777/cited.1"],   # für Zotero-PDF
            "Joerissen_2020_Bildung.pdf": [],       # Folder-PDF leer
        }),
    )
    monkeypatch.setattr(
        build_mod, "resolve_dois", _mock_resolve_factory({}),
    )
    # extract.ensure_fulltext wird vom Mock umgangen (extract_refs ist gemockt)

    db = tmp_path / "own_refs.db"
    zot = _FakeZoteroSource([zot_item])
    fld = FolderSource(folder_path=base)

    stats = build([zot, fld], db_path=db, verbose=False)
    assert stats.dupes_merged == 1

    with OwnRefsStore(db) as store:
        all_pubs = list(store.iter_publications())
        assert len(all_pubs) == 1, f"expected 1 dedup'd pub, got {len(all_pubs)}: {[p.canonical_id for p in all_pubs]}"
        pub = all_pubs[0]
        assert pub.canonical_id == "doi:10.5555/bildung.2020"
        assert pub.doi == "10.5555/bildung.2020"

        srs = store.get_source_refs(pub.canonical_id)
        assert len(srs) == 2, f"expected 2 source_refs after merge, got {len(srs)}: {srs}"
        types = {s.source_type for s in srs}
        assert types == {"zotero", "folder"}


# ----- Test 3: Re-Ingest mit neuem PDF im bekannten Folder ------------------


def test_incremental_new_pdf(tmp_path, monkeypatch):
    """Bekannter Folder, zweiter Lauf mit +1 PDF → genau 1 new, Rest unchanged."""
    base = tmp_path / "pubs"
    base.mkdir()
    (base / "Joerissen_2020.pdf").write_bytes(b"%PDF-1.4 a")
    (base / "Joerissen_2024.pdf").write_bytes(b"%PDF-1.4 b")

    monkeypatch.setattr(
        build_mod, "extract_refs",
        _mock_extract_factory({}),  # leere refs für simplicity
    )
    monkeypatch.setattr(
        build_mod, "resolve_dois", _mock_resolve_factory({}),
    )

    db = tmp_path / "own_refs.db"
    src = FolderSource(folder_path=base)

    s1 = build([src], db_path=db, verbose=False)
    assert s1.items_new == 2

    # +1 PDF
    import time
    time.sleep(0.05)
    (base / "Joerissen_2026.pdf").write_bytes(b"%PDF-1.4 c")

    s2 = build([src], db_path=db, verbose=False)
    assert s2.items_discovered == 3
    assert s2.items_new == 1
    assert s2.items_skipped_unchanged == 2, (
        f"expected 2 skipped, got new={s2.items_new}, "
        f"updated={s2.items_updated}, skipped={s2.items_skipped_unchanged}"
    )


# ----- Unit-Tests: identity --------------------------------------------------


class TestIdentity:
    def test_normalize_doi_strips_url_prefixes(self):
        assert normalize_doi("https://doi.org/10.1/x.y") == "10.1/x.y"
        assert normalize_doi("http://dx.doi.org/10.1/X.Y") == "10.1/x.y"
        assert normalize_doi("doi:10.1/X") == "10.1/x"
        assert normalize_doi("10.5555/foo-bar.") == "10.5555/foo-bar"
        assert normalize_doi(None) == ""
        assert normalize_doi("") == ""

    def test_normalize_text_folds_umlauts(self):
        assert normalize_text("Jörissen, Benjamin") == "joerissen benjamin"
        assert normalize_text("Über das Ästhetische") == "ueber das aesthetische"

    def test_first_author_lastname(self):
        assert first_author_lastname(["Jörissen, Benjamin", "Schmidt, Anna"]) == "Jörissen"
        assert first_author_lastname(["Jane Doe", "John Roe"]) == "Doe"
        assert first_author_lastname([]) == ""

    def test_canonical_id_doi_wins(self):
        cid_doi = canonical_id_for("10.1/x", "Title", 2020, ["Smith, A"])
        cid_no_doi = canonical_id_for(None, "Title", 2020, ["Smith, A"])
        assert cid_doi == "doi:10.1/x"
        assert cid_no_doi.startswith("hash:")
        assert cid_doi != cid_no_doi

    def test_canonical_id_hash_stable(self):
        a = canonical_id_for(None, "Bildung im digitalen Raum", 2019, ["Jörissen, B"])
        b = canonical_id_for(None, "Bildung im digitalen Raum", 2019, ["Jörissen, B"])
        assert a == b

    def test_canonical_id_hash_changes_with_input(self):
        a = canonical_id_for(None, "Title A", 2019, ["X"])
        b = canonical_id_for(None, "Title B", 2019, ["X"])
        assert a != b


# ----- Unit-Tests: discourse -------------------------------------------------


class TestDiscourse:
    def test_classify_returns_sorted_multi_label(self):
        labels = classify("Bildung im digitalen Raum", "Zeitschrift für Pädagogik")
        assert labels == sorted(labels)

    def test_classify_resilienz(self):
        labels = classify("Resilience and Sustainability", "Educational Research")
        assert "resilienz" in labels

    def test_classify_empty_input_returns_empty(self):
        assert classify("", "") == []
        assert classify(None, None) == []

    def test_classify_aesthetische_kulturelle_bildung(self):
        labels = classify("Kulturelle Bildung im Wandel", "Some Journal")
        assert "aesthetische_kulturelle_bildung" in labels

    def test_available_discourses(self):
        d = available_discourses()
        assert "resilienz" in d
        assert "aesthetische_kulturelle_bildung" in d
        assert len(d) == 7


# ----- Regression: dedup im store -------------------------------------------


def test_replace_pub_refs_dedupes_on_ref_id(tmp_path):
    """Regression für Live-Build-Crash 2026-05-24: zwei refs mit identischem
    ref_id (z. B. zwei identische Citation-Strings → gleicher SHA1-Hash)
    dürfen `replace_pub_refs` nicht mit IntegrityError abbrechen.
    """
    from journal_bot.own_refs.store import OwnRefsStore, Publication, PubRef

    db = tmp_path / "own_refs.db"
    with OwnRefsStore(db) as store:
        store.upsert_publication(Publication(
            canonical_id="doi:10.1/x", title="X", authors=["A, B"], year=2020,
        ))
        # zwei refs mit identischem ref_id, eine resolved, eine nicht
        refs = [
            PubRef(
                canonical_id="doi:10.1/x", ref_id="txt:abc123",
                ref_text="Some citation", resolution_state="text_unresolved",
            ),
            PubRef(
                canonical_id="doi:10.1/x", ref_id="txt:abc123",
                ref_text="Some citation", ref_oa_id="https://openalex.org/W1",
                resolution_state="text_resolved",
            ),
        ]
        # Darf nicht crashen
        store.replace_pub_refs("doi:10.1/x", refs)
        result = store.get_pub_refs("doi:10.1/x")
        assert len(result) == 1, f"expected 1 deduped ref, got {len(result)}"
        # bevorzugte Variante = resolved
        assert result[0].resolution_state == "text_resolved"
        assert result[0].ref_oa_id == "https://openalex.org/W1"
