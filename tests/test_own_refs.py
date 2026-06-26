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


# ----- Test 4: leere Source-Stubs (titellos + ohne PDF) -----------------------


def test_empty_stub_not_ingested(tmp_path, monkeypatch):
    """Ein titelloser DOI-Eintrag ohne PDF (wie die 5 AI&Society-Stubs in
    QM7TZT44) darf KEINEN Werk-Record erzeugen — er trägt null Erdungssignal
    und verfälscht jede Coverage-Zahl. Ein echtes (betiteltes) Werk daneben
    bleibt erhalten."""
    empty = DiscoveredItem(
        source_type="zotero", source_key="TESTCOLL", source_item_id="EMPTY1",
        title="", authors=[], doi="10.1007/s00146-025-99999-9", year=None,
        item_type="journalArticle", venue=None, pdf_path=None,
    )
    real = DiscoveredItem(
        source_type="zotero", source_key="TESTCOLL", source_item_id="REAL1",
        title="Digital-kulturelle Praktiken als immaterielles Erbe",
        authors=["Klepacki, L.", "Jörissen, Benjamin", "Pino, M."],
        doi="10.1515/para-2024-0043", year=2024,
        item_type="journalArticle", venue="Paragrana", pdf_path=None,
    )
    monkeypatch.setattr(build_mod, "extract_refs", _mock_extract_factory({}))
    monkeypatch.setattr(build_mod, "resolve_dois", _mock_resolve_factory({}))

    db = tmp_path / "own_refs.db"
    stats = build([_FakeZoteroSource([empty, real])], db_path=db, verbose=False)

    assert stats.items_skipped_empty == 1
    with OwnRefsStore(db) as store:
        pubs = list(store.iter_publications())
        assert len(pubs) == 1, f"empty stub leaked in: {[p.canonical_id for p in pubs]}"
        assert pubs[0].canonical_id == "doi:10.1515/para-2024-0043"


def test_empty_stub_self_heals_existing(tmp_path, monkeypatch):
    """Ein bereits eingebauter Leer-Stub (additiver Alt-Lauf) wird beim
    nächsten Build entfernt, sobald die Quelle ihn weiterhin titellos liefert
    — die Reinigung hängt nicht an einem manuellen Purge."""
    from journal_bot.own_refs.store import Publication

    db = tmp_path / "own_refs.db"
    # Alt-Zustand: Leer-Stub liegt schon in der DB.
    with OwnRefsStore(db) as store:
        store.upsert_publication(Publication(
            canonical_id="doi:10.1007/s00146-025-99999-9",
            title="", authors=[], doi="10.1007/s00146-025-99999-9",
            year=None, item_type="journalArticle", venue=None,
            discourse=None, notes=["no_pdf_attachment", "no_pdf"],
        ))
        assert store.count_publications() == 1

    empty = DiscoveredItem(
        source_type="zotero", source_key="TESTCOLL", source_item_id="EMPTY1",
        title="", authors=[], doi="10.1007/s00146-025-99999-9", year=None,
        item_type="journalArticle", venue=None, pdf_path=None,
    )
    monkeypatch.setattr(build_mod, "extract_refs", _mock_extract_factory({}))
    monkeypatch.setattr(build_mod, "resolve_dois", _mock_resolve_factory({}))

    stats = build([_FakeZoteroSource([empty])], db_path=db, verbose=False)
    assert stats.items_skipped_empty == 1
    with OwnRefsStore(db) as store:
        assert store.count_publications() == 0, "stale empty stub was not purged"


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


# ----- Header-Erkennung (§2.3) ----------------------------------------------


class TestRefsHeaderDetection:
    """Header-Erkennung in find_references_block (§2.3-Erweiterung)."""

    def _build_text(self, body_lines, header_line, ref_lines):
        """Bauen einen Volltext mit 50% Body + Header + Refs am Ende."""
        # Body muss >40% des Dokuments sein, damit Header über 30%-Schwelle liegt
        return "\n".join(body_lines + [header_line] + ref_lines)

    def test_classic_header_literatur(self):
        from journal_bot.own_refs.extract import find_references_block
        text = self._build_text(
            ["body line"] * 50, "Literatur", ["Müller, K. (2020): ..."],
        )
        _, line, label = find_references_block(text)
        assert label == "Literatur"
        assert line == 50

    def test_sammelband_primaerliteratur(self):
        """Primärliteratur als Sammelband-Header (§2.3)."""
        from journal_bot.own_refs.extract import find_references_block
        text = self._build_text(
            ["body"] * 50, "Primärliteratur", ["Mead, G. H. (1934): Mind, Self ..."],
        )
        _, _, label = find_references_block(text)
        assert label == "Primärliteratur"

    def test_section_prefix(self):
        """VIII. Literaturverzeichnis ist Header (kein TOC)."""
        from journal_bot.own_refs.extract import find_references_block
        text = self._build_text(
            ["body"] * 50, "VIII. Literaturverzeichnis", ["Adorno, T. (1966): ..."],
        )
        _, _, label = find_references_block(text)
        assert label == "Literaturverzeichnis"

    def test_header_with_section_refs(self):
        """'Literaturverzeichnis I.1; I.4; I.5' ist Sammelband-Header,
        kein TOC-Eintrag (kein Spacing/Punkt-Linie zur Section-Reference)."""
        from journal_bot.own_refs.extract import find_references_block
        text = self._build_text(
            ["body"] * 50, "Literaturverzeichnis I.1; I.4; I.5", ["Adorno ..."],
        )
        _, _, label = find_references_block(text)
        assert label == "Literaturverzeichnis"

    def test_toc_entry_excluded(self):
        """'Literaturverzeichnis ...... 245' = TOC-Eintrag, KEIN Header."""
        from journal_bot.own_refs.extract import find_references_block
        text = self._build_text(
            ["body"] * 50,
            "VIII. Literaturverzeichnis                                                 249",
            ["Adorno ..."],
        )
        _, _, label = find_references_block(text)
        # Fallback greift, weil kein echter Header gefunden
        assert label == "(fallback)"

    def test_no_header_uses_fallback(self):
        """Bei kein Header: letzte 25% als (fallback)."""
        from journal_bot.own_refs.extract import find_references_block
        text = "\n".join(["irgendein body text"] * 200)
        _, _, label = find_references_block(text)
        assert label == "(fallback)"

    def test_no_header_short_doc_no_fallback(self):
        """Sehr kurze Docs (< 40 Lines): kein Fallback, leerer return."""
        from journal_bot.own_refs.extract import find_references_block
        text = "\n".join(["body"] * 10)
        refs, line, label = find_references_block(text)
        assert refs == ""
        assert label is None


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


# ----- §2.4 text_resolve: Parser-Tests --------------------------------------


class TestParseRefText:
    """Unit-Tests für `parse_ref_text` — heuristisches Author+Year+Title-Parsing.

    Deckt die wichtigsten in der Bibliothek beobachteten Citation-Stile ab:
    APA mit (YYYY)., APA mit (YYYY, Month Day)., Chicago mit Jahresende,
    Sammelband-Stil mit "In:", Monographien mit Einwort-Titeln.
    """

    def test_apa_simple_article(self):
        from journal_bot.own_refs.text_resolve import parse_ref_text
        p = parse_ref_text(
            "Barad, K. (2007). Meeting the universe halfway. Duke University Press."
        )
        assert p is not None
        assert p.first_author_lastname == "Barad"
        assert p.year == 2007
        assert "Meeting the universe halfway" in p.title

    def test_year_with_extra_in_parens(self):
        """'(2017, November 15)' — Online-Posts und Blog-Refs."""
        from journal_bot.own_refs.text_resolve import parse_ref_text
        p = parse_ref_text(
            "Alspach, B. (2017, November 15). The story behind how an Alaska Native "
            "story led to a video game."
        )
        assert p is not None
        assert p.first_author_lastname == "Alspach"
        assert p.year == 2017
        assert p.title.lower().startswith("the story behind")

    def test_einwort_titel_monographie(self):
        """Monographien-Titel können einwortig sein und brauchen author+year."""
        from journal_bot.own_refs.text_resolve import parse_ref_text
        p = parse_ref_text("Holzer, Boris (2006). Netzwerke. Bielefeld: transcript Verlag.")
        assert p is not None
        assert p.first_author_lastname == "Holzer"
        assert p.year == 2006
        assert "Netzwerke" in p.title

    def test_multi_sentence_title_preserved(self):
        """'Title. Subtitle. Venue' — Titel inkl. Subtitle, Venue rausschneiden."""
        from journal_bot.own_refs.text_resolve import parse_ref_text
        p = parse_ref_text(
            "Alkemeyer, T., Buschmann, N. (2021). Kosmologie des Toilettengangs. "
            "Zum Imaginären einer nachhaltigen Lebensform. Soziologie und "
            "Nachhaltigkeit, 7(02), 72–89."
        )
        assert p is not None
        assert p.first_author_lastname == "Alkemeyer"
        assert p.year == 2021
        assert "Kosmologie" in p.title
        # Vol-Pattern ", 7(02)" sollte abschneiden
        assert "7(02)" not in p.title

    def test_returns_none_for_no_year(self):
        from journal_bot.own_refs.text_resolve import parse_ref_text
        assert parse_ref_text("Some random text without year metadata.") is None

    def test_returns_none_for_too_short(self):
        from journal_bot.own_refs.text_resolve import parse_ref_text
        assert parse_ref_text("Short.") is None

    def test_year_suffix_letter_stripped(self):
        """'(2020a)' — APA Disambiguierungs-Letter darf das Jahr nicht stören."""
        from journal_bot.own_refs.text_resolve import parse_ref_text
        p = parse_ref_text("Author, A. (2020a). Some title here for testing.")
        assert p is not None
        assert p.year == 2020


# ----- §2.4 text_resolve: Matching-Tests ------------------------------------


class TestTextResolveMatcher:
    """Tests für `_best_match` und Such-Query-Konstruktion.

    Nutzt synthetische OpenAlex-Search-Responses (dicts wie aus der API),
    KEINE Netzwerk-Calls.
    """

    def test_best_match_token_containment(self):
        """Lange noisy parsed_title + kurzer cand_title → containment-ratio."""
        from journal_bot.own_refs.text_resolve import _best_match, ParsedRef
        parsed = ParsedRef(
            first_author_lastname="Arnaud", year=2023,
            title=("Promoting cultural rights for inhabitants of segregated "
                   "neighbourhoods in Cape Town. From cultural insurrection "
                   "to Epistemic Action."),
            raw="…",
        )
        cands = [{
            "id": "https://openalex.org/W123",
            "doi": "https://doi.org/10.x/y",
            "title": "Promoting Cultural Rights for Inhabitants of Segregated Neighbourhoods",
            "publication_year": 2023,
            "authorships": [{"author": {"display_name": "Lionel Arnaud"}}],
        }]
        result = _best_match(parsed, cands)
        assert result.oa_id == "https://openalex.org/W123"
        assert result.matched_doi == "10.x/y"

    def test_best_match_rejects_year_mismatch(self):
        from journal_bot.own_refs.text_resolve import _best_match, ParsedRef
        parsed = ParsedRef(
            first_author_lastname="Barad", year=2007,
            title="Meeting the universe halfway", raw="…",
        )
        cands = [{
            "id": "https://openalex.org/W1",
            "title": "Meeting the universe halfway",
            "publication_year": 2015,  # zu weit weg
            "authorships": [{"author": {"display_name": "Karen Barad"}}],
        }]
        assert _best_match(parsed, cands).oa_id is None

    def test_best_match_rejects_author_mismatch(self):
        from journal_bot.own_refs.text_resolve import _best_match, ParsedRef
        parsed = ParsedRef(
            first_author_lastname="Barad", year=2007,
            title="Meeting the universe halfway", raw="…",
        )
        cands = [{
            "id": "https://openalex.org/W1",
            "title": "Meeting the universe halfway",
            "publication_year": 2007,
            "authorships": [{"author": {"display_name": "Someone Else"}}],
        }]
        assert _best_match(parsed, cands).oa_id is None

    def test_best_match_rejects_low_ratio(self):
        from journal_bot.own_refs.text_resolve import _best_match, ParsedRef
        parsed = ParsedRef(
            first_author_lastname="Barad", year=2007,
            title="Meeting the universe halfway", raw="…",
        )
        cands = [{
            "id": "https://openalex.org/W1",
            "title": "Quantum physics and unrelated topics for testing",
            "publication_year": 2007,
            "authorships": [{"author": {"display_name": "Karen Barad"}}],
        }]
        # Token-Overlap zwischen Titel und unrelated topics ist niedrig
        assert _best_match(parsed, cands).oa_id is None

    def test_search_query_preserves_diacritics(self):
        """OpenAlex' BM25 ist umlaut-sensitiv — Diakritika dürfen NICHT
        weg-normalisiert werden, sonst missen wir deutsche Refs."""
        from journal_bot.own_refs.text_resolve import _build_search_query
        q = _build_search_query("Kosmologie des Toilettengangs")
        assert "Kosmologie" in q

    def test_search_query_drops_stopwords(self):
        from journal_bot.own_refs.text_resolve import _build_search_query
        q = _build_search_query("Der und die das von für mit Title")
        # "Title" sollte als einziges Nicht-Stopwort übrig sein
        assert q.lower().strip() == "title"

    def test_search_query_caps_at_max_words(self):
        """5-Wort-Cap: zu lange Queries drücken OAs Recall."""
        from journal_bot.own_refs.text_resolve import _build_search_query, MAX_QUERY_WORDS
        long_title = "Eins zwei drei vier fünf sechs sieben acht neun zehn elf"
        q = _build_search_query(long_title)
        # Nach Stopwort-Filter + Cap maximal MAX_QUERY_WORDS Tokens
        assert len(q.split()) <= MAX_QUERY_WORDS

    def test_search_query_strips_smart_quotes_and_ligatures(self):
        """PDF-Ligaturen 'ﬁ', Smart-Quotes '“”' verfälschen OA-Suche."""
        from journal_bot.own_refs.text_resolve import _build_search_query
        q = _build_search_query("‘Artiﬁcial’ Intelligence “Position” Paper")
        assert "ﬁ" not in q
        assert "“" not in q
        assert "‘" not in q


# ----- §2.4 text_resolve: Cache-Tests ---------------------------------------


class TestTextResolveCache:
    """File-Cache speichert positive UND negative Ergebnisse."""

    def test_cache_roundtrip_resolved(self, tmp_path):
        from journal_bot.own_refs.text_resolve import (
            _save_cache, _load_cached, _parsed_signature, ParsedRef,
        )
        parsed = ParsedRef("Barad", 2007, "Meeting the universe halfway", "…")
        sig = _parsed_signature(parsed)
        _save_cache(sig, {
            "oa_id": "https://openalex.org/W1",
            "title": "Meeting the universe halfway",
            "year": 2007,
            "doi": "10.x/y",
            "score": 0.95,
        }, tmp_path)
        loaded = _load_cached(sig, tmp_path)
        assert loaded is not None
        assert loaded.oa_id == "https://openalex.org/W1"
        assert loaded.matched_year == 2007
        assert loaded.cache_hit is True

    def test_cache_roundtrip_unresolved(self, tmp_path):
        """Empty-dict-Cache verhindert Re-Query."""
        from journal_bot.own_refs.text_resolve import (
            _save_cache, _load_cached, _parsed_signature, ParsedRef,
        )
        parsed = ParsedRef("Nobody", 1999, "Unknown work", "…")
        sig = _parsed_signature(parsed)
        _save_cache(sig, {}, tmp_path)
        loaded = _load_cached(sig, tmp_path)
        assert loaded is not None
        assert loaded.oa_id is None
        assert loaded.cache_hit is True

    def test_resolve_text_refs_uses_cache_no_network(self, tmp_path, monkeypatch):
        """Mit voll gefülltem Cache wird KEIN httpx.Client erstellt."""
        from journal_bot.own_refs import text_resolve as tr

        # Lege Cache-Einträge für die beiden Test-Refs ab
        parsed_test_refs = [
            ("txt:abc", "Barad, K. (2007). Meeting the universe halfway. Duke UP."),
            ("txt:def", "Holzer, B. (2006). Netzwerke. transcript Verlag."),
        ]
        for ref_id, raw in parsed_test_refs:
            p = tr.parse_ref_text(raw)
            assert p is not None
            sig = tr._parsed_signature(p)
            tr._save_cache(sig, {
                "oa_id": f"https://openalex.org/W{ref_id[-3:]}",
                "title": "x", "year": p.year, "doi": None, "score": 1.0,
            }, tmp_path)

        # Wenn httpx.Client jetzt aufgerufen würde, schlägt es fehl
        def fail(*a, **kw):
            raise AssertionError("Cache-Hit sollte keinen Network-Call brauchen")
        monkeypatch.setattr(tr.httpx, "Client", fail)

        out = tr.resolve_text_refs(parsed_test_refs, cache_dir=tmp_path, verbose=False)
        assert len(out) == 2
        assert all(r.cache_hit for r in out.values())
        assert all(r.oa_id for r in out.values())

    def test_resolve_text_refs_max_calls_zero_is_cache_only(self, tmp_path, monkeypatch):
        """max_calls=0 → keine Live-Calls, nur Cache-Hits."""
        from journal_bot.own_refs import text_resolve as tr

        def fail(*a, **kw):
            raise AssertionError("max_calls=0 darf nicht ins Netz")
        monkeypatch.setattr(tr.httpx, "Client", fail)

        # leeres Cache-Dir, kein Match möglich
        pairs = [("txt:xyz", "Author, A. (2020). Some Work. Some Venue.")]
        out = tr.resolve_text_refs(pairs, cache_dir=tmp_path, max_calls=0)
        # Refs ohne Cache-Hit und ohne Call landen NICHT im Output
        assert "txt:xyz" not in out
