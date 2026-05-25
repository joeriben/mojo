"""Tests für `journal_bot.escalation` (MOJO 2.0 §2.5).

Drei Aspekte:
1. Selection-Logik (`select_candidates`): Filterung nach selection_mode,
   verdict, PrioScore-Sortierung, only_wrong_les-Flag.
2. PrioScore-Berechnung: own_coupling + adversarial, Verdict-Bonus/-Malus.
3. Fulltext-Cache-Pfade & Extract-Stub: kein Netz, kein pdftotext.

Wir mocken die Signal-Berechnung (own_coupling/adversarial) durch eine
leere own_refs.db — dann liefern die Signals leere Dicts und PrioScore
hängt nur am Indikator/Verdict. So testen wir die SELECTION-Kette
deterministisch, ohne articles.db oder ein wirkliches own_refs.db zu brauchen.

Network-Tests für `fulltext.fetch_fulltext_for_article` sind in einem
separaten Modul (test_escalation_live.py, manuell auszuführen) — die
Tests hier mocken `httpx.Client` komplett.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from journal_bot.escalation.fulltext import (
    FetchResult,
    cache_paths,
)
from journal_bot.escalation.select import (
    EscalationCandidate,
    _build_reason,
    _compute_prio_score,
    _parse_openalex_refs,
    select_candidates,
    summarize_pool,
)


# ----- Helpers: synthetische articles.db ------------------------------------


def _make_articles_db(tmp_path: Path, articles: list[dict]) -> Path:
    """Lege ein minimales articles.db an mit allen Feldern, die select_candidates
    erwartet.

    Jede `articles`-Zeile ist ein dict mit Keys: id, journal_short, title,
    selection_mode, agent_verdict (+ optional weitere).
    """
    db = tmp_path / "articles.db"
    con = sqlite3.connect(str(db))
    con.execute("""
        CREATE TABLE articles (
            id TEXT PRIMARY KEY,
            journal_short TEXT,
            journal_full TEXT,
            title TEXT,
            authors_json TEXT,
            doi TEXT,
            year INTEGER,
            fetched_at TEXT NOT NULL,
            openalex_id TEXT,
            openalex_refs TEXT,
            crossref_refs TEXT,
            agent_processed_at TEXT,
            agent_verdict TEXT,
            agent_entry_json TEXT,
            user_verdict TEXT,
            selection_mode TEXT,
            discourse_indicator TEXT
        )
    """)
    for a in articles:
        con.execute(
            """INSERT INTO articles
               (id, journal_short, title, fetched_at, openalex_refs,
                agent_processed_at, agent_verdict, user_verdict,
                selection_mode, discourse_indicator)
               VALUES (?, ?, ?, '2026-01-01', ?, '2026-01-01', ?, ?, ?, ?)""",
            (a["id"], a.get("journal_short", "TEST"), a.get("title", "T"),
             json.dumps(a.get("openalex_refs") or []),
             a.get("agent_verdict"), a.get("user_verdict"),
             a.get("selection_mode"), a.get("discourse_indicator")),
        )
    con.commit()
    con.close()
    return db


def _make_empty_own_refs_db(tmp_path: Path) -> Path:
    """Leere own_refs.db — Signals liefern leere Dicts → PrioScore nur aus
    indicator/verdict."""
    db = tmp_path / "own_refs.db"
    from journal_bot.own_refs.schema import connect
    connect(db).close()
    return db


# ----- PrioScore ------------------------------------------------------------


class TestPrioScore:
    def test_starker_indikator_bonus(self):
        assert _compute_prio_score(
            verdict="scannen", indicator="starker_indikator",
            own_score=0, adv_score=0,
        ) == pytest.approx(0.7)  # 0.5 + 0.2

    def test_ignorieren_malus(self):
        assert _compute_prio_score(
            verdict="ignorieren", indicator="schwacher_indikator",
            own_score=0, adv_score=0,
        ) == pytest.approx(-0.5)

    def test_own_and_adv_scores_added(self):
        p = _compute_prio_score(
            verdict="scannen", indicator="kein_indikator",
            own_score=3.0, adv_score=2.0,
        )
        assert p == pytest.approx(5.2)  # 3 + 2 + 0.2

    def test_strong_signal_overrides_ignore_malus(self):
        """Hoher own_coupling reicht, um trotz IGN-Malus oben in der Liste
        zu landen — das ist genau der Sinn der Eskalation."""
        p_strong = _compute_prio_score(
            verdict="ignorieren", indicator="kein_indikator",
            own_score=8.0, adv_score=0,
        )
        p_weak = _compute_prio_score(
            verdict="scannen", indicator="starker_indikator",
            own_score=0, adv_score=0,
        )
        assert p_strong > p_weak


# ----- _parse_openalex_refs --------------------------------------------------


class TestParseOpenAlexRefs:
    def test_parses_list(self):
        assert _parse_openalex_refs('["W1","W2"]') == ["W1", "W2"]

    def test_handles_none(self):
        assert _parse_openalex_refs(None) == []

    def test_handles_invalid_json(self):
        assert _parse_openalex_refs("not json") == []

    def test_handles_non_list(self):
        assert _parse_openalex_refs('{"foo": "bar"}') == []


# ----- _build_reason --------------------------------------------------------


class TestBuildReason:
    def test_minimal(self):
        s = _build_reason(None, None, None, 0, 0)
        assert s == "(keine Signale)"

    def test_includes_mode_indicator_verdict(self):
        s = _build_reason(
            "scannen", "starker_indikator", "complementarity", 1.2, 0.5,
        )
        assert "mode=complementarity" in s
        assert "starker_indikator" in s
        assert "own_coupling=1.20" in s
        assert "adversarial=0.50" in s
        assert "agent=scannen" in s

    def test_skips_kein_indikator(self):
        s = _build_reason("scannen", "kein_indikator", "screening", 0, 0)
        assert "kein_indikator" not in s


# ----- select_candidates ----------------------------------------------------


class TestSelectCandidates:
    """End-to-End-Tests: synthetische articles.db + leere own_refs.db."""

    def test_returns_empty_when_db_missing(self, tmp_path):
        result = select_candidates(
            articles_db=tmp_path / "missing.db",
        )
        assert result == []

    def test_filters_to_eligible_modes(self, tmp_path):
        """citation und trigger werden ausgeschlossen — die brauchen keine LLM-
        Eskalation, sie sind schon klassifiziert."""
        own_refs_db = _make_empty_own_refs_db(tmp_path)
        articles_db = _make_articles_db(tmp_path, [
            {"id": "a1", "selection_mode": "screening",
             "agent_verdict": "scannen", "discourse_indicator": "schwacher_indikator"},
            {"id": "a2", "selection_mode": "citation",       # exclude
             "agent_verdict": "scannen", "discourse_indicator": "starker_indikator"},
            {"id": "a3", "selection_mode": "trigger",        # exclude
             "agent_verdict": "scannen", "discourse_indicator": "starker_indikator"},
            {"id": "a4", "selection_mode": "complementarity",
             "agent_verdict": "scannen", "discourse_indicator": "schwacher_indikator"},
        ])
        cands = select_candidates(articles_db, own_refs_db=own_refs_db)
        ids = {c.article_id for c in cands}
        assert ids == {"a1", "a4"}

    def test_filters_to_eligible_verdicts(self, tmp_path):
        """lesenswert/pflichtlektuere brauchen keine Eskalation — sie sind LES."""
        own_refs_db = _make_empty_own_refs_db(tmp_path)
        articles_db = _make_articles_db(tmp_path, [
            {"id": "a1", "selection_mode": "screening",
             "agent_verdict": "lesenswert",   # exclude
             "discourse_indicator": "starker_indikator"},
            {"id": "a2", "selection_mode": "screening",
             "agent_verdict": "scannen",
             "discourse_indicator": "schwacher_indikator"},
            {"id": "a3", "selection_mode": "screening",
             "agent_verdict": "ignorieren",
             "discourse_indicator": "kein_indikator"},
        ])
        cands = select_candidates(articles_db, own_refs_db=own_refs_db,
                                  min_prio_score=-99)  # auch ignorieren mit
        ids = {c.article_id for c in cands}
        assert ids == {"a2", "a3"}

    def test_sorted_by_prio_descending(self, tmp_path):
        own_refs_db = _make_empty_own_refs_db(tmp_path)
        articles_db = _make_articles_db(tmp_path, [
            {"id": "a1", "selection_mode": "screening",
             "agent_verdict": "ignorieren",
             "discourse_indicator": "schwacher_indikator"},  # prio=-0.5
            {"id": "a2", "selection_mode": "screening",
             "agent_verdict": "scannen",
             "discourse_indicator": "starker_indikator"},    # prio=0.7
            {"id": "a3", "selection_mode": "screening",
             "agent_verdict": "scannen",
             "discourse_indicator": "schwacher_indikator"},  # prio=0.2
        ])
        cands = select_candidates(articles_db, own_refs_db=own_refs_db,
                                  min_prio_score=-99)
        assert [c.article_id for c in cands] == ["a2", "a3", "a1"]

    def test_min_prio_filter(self, tmp_path):
        own_refs_db = _make_empty_own_refs_db(tmp_path)
        articles_db = _make_articles_db(tmp_path, [
            {"id": "a1", "selection_mode": "screening",
             "agent_verdict": "ignorieren",
             "discourse_indicator": "schwacher_indikator"},  # prio=-0.5
            {"id": "a2", "selection_mode": "screening",
             "agent_verdict": "scannen",
             "discourse_indicator": "starker_indikator"},    # prio=0.7
        ])
        cands = select_candidates(articles_db, own_refs_db=own_refs_db,
                                  min_prio_score=0.5)
        assert [c.article_id for c in cands] == ["a2"]

    def test_only_wrong_les_filter(self, tmp_path):
        own_refs_db = _make_empty_own_refs_db(tmp_path)
        articles_db = _make_articles_db(tmp_path, [
            {"id": "a1", "selection_mode": "screening",
             "agent_verdict": "scannen", "user_verdict": "lesenswert",
             "discourse_indicator": "schwacher_indikator"},  # wrong-LES
            {"id": "a2", "selection_mode": "screening",
             "agent_verdict": "scannen", "user_verdict": "scannen",
             "discourse_indicator": "schwacher_indikator"},
            {"id": "a3", "selection_mode": "screening",
             "agent_verdict": "scannen", "user_verdict": None,
             "discourse_indicator": "schwacher_indikator"},
        ])
        cands = select_candidates(articles_db, own_refs_db=own_refs_db,
                                  min_prio_score=-99, only_wrong_les=True)
        assert [c.article_id for c in cands] == ["a1"]

    def test_journals_filter(self, tmp_path):
        own_refs_db = _make_empty_own_refs_db(tmp_path)
        articles_db = _make_articles_db(tmp_path, [
            {"id": "a1", "journal_short": "X", "selection_mode": "screening",
             "agent_verdict": "scannen", "discourse_indicator": "starker_indikator"},
            {"id": "a2", "journal_short": "Y", "selection_mode": "screening",
             "agent_verdict": "scannen", "discourse_indicator": "starker_indikator"},
        ])
        cands = select_candidates(articles_db, own_refs_db=own_refs_db,
                                  journals=["X"], min_prio_score=-99)
        assert [c.article_id for c in cands] == ["a1"]


# ----- summarize_pool -------------------------------------------------------


class TestSummarizePool:
    def test_empty(self):
        s = summarize_pool([])
        assert s["n_total"] == 0
        assert s["prio_score_max"] == 0.0

    def test_aggregates(self):
        cands = [
            EscalationCandidate(
                article_id="a1", journal_short="J1", title="T1", year=2020,
                doi=None, openalex_id=None, agent_verdict="scannen",
                user_verdict="lesenswert", selection_mode="complementarity",
                discourse_indicator="starker_indikator",
                own_coupling_score=1.0, adversarial_score=0.0,
                prio_score=1.7, reason="…",
            ),
            EscalationCandidate(
                article_id="a2", journal_short="J2", title="T2", year=2020,
                doi=None, openalex_id=None, agent_verdict="ignorieren",
                user_verdict=None, selection_mode="similarity",
                discourse_indicator="schwacher_indikator",
                own_coupling_score=0.0, adversarial_score=2.0,
                prio_score=1.5, reason="…",
            ),
        ]
        s = summarize_pool(cands)
        assert s["n_total"] == 2
        assert s["n_with_own_coupling"] == 1
        assert s["n_with_adversarial"] == 1
        assert s["n_wrong_les"] == 1
        assert s["by_mode"] == {"complementarity": 1, "similarity": 1}


# ----- fulltext: Cache-Pfade + Extract --------------------------------------


class TestFulltextCache:
    def test_cache_paths_deterministic(self, tmp_path):
        p1 = cache_paths("article_xyz", tmp_path)
        p2 = cache_paths("article_xyz", tmp_path)
        assert p1 == p2
        assert p1["pdf"].suffix == ".pdf"
        assert p1["txt"].suffix == ".txt"
        assert "meta.json" in p1["meta"].name

    def test_cache_paths_differ_per_article(self, tmp_path):
        p1 = cache_paths("article_a", tmp_path)
        p2 = cache_paths("article_b", tmp_path)
        assert p1["pdf"] != p2["pdf"]


class TestFulltextFetcher:
    """Network-free Tests via Mock-Client.

    Wir patchen `httpx.Client` so, dass keine echten Requests passieren.
    Tests prüfen Status-Maschine: no_pdf_url, cache_hit.
    """

    def test_no_pdf_url_when_all_sources_fail(self, tmp_path, monkeypatch):
        from journal_bot.escalation import fulltext as ft

        mock_client = MagicMock()
        mock_client.__enter__ = lambda s: s
        mock_client.__exit__ = lambda *a: None
        mock_response = MagicMock(status_code=404, text="not found")
        mock_client.get.return_value = mock_response

        def mock_httpx(*a, **kw):
            return mock_client
        monkeypatch.setattr(ft.httpx, "Client", mock_httpx)

        result = ft.fetch_fulltext_for_article(
            article_id="test1", openalex_id="W123", doi="10.1/x",
            cache_dir=tmp_path,
            zotero_root=tmp_path / "no_zotero",  # nicht existent → fall-through
        )
        assert result.status == "no_pdf_url"
        assert result.fulltext_chars == 0
        assert not result.cache_hit

    def test_cache_hit_when_txt_and_meta_present(self, tmp_path, monkeypatch):
        """Wenn txt + meta.json existieren, kein Netz-Call."""
        from journal_bot.escalation import fulltext as ft

        paths = ft.cache_paths("test2", tmp_path)
        paths["txt"].parent.mkdir(parents=True, exist_ok=True)
        paths["txt"].write_text("Volltext-Inhalt")
        paths["meta"].write_text(json.dumps({
            "fulltext_chars": 14, "source": "openalex", "pdf_url": "http://x",
        }))

        # Wenn httpx benutzt würde, schlagen wir fehl
        def fail(*a, **kw):
            raise AssertionError("Cache-Hit darf nicht netzen")
        monkeypatch.setattr(ft.httpx, "Client", fail)

        result = ft.fetch_fulltext_for_article(
            article_id="test2", openalex_id="W123", doi="10.1/x",
            cache_dir=tmp_path,
            zotero_root=tmp_path / "no_zotero",
        )
        assert result.status == "cache_hit"
        assert result.cache_hit is True
        assert result.fulltext_chars == 14
        assert result.source == "openalex"


# ----- Zotero-Lookup --------------------------------------------------------


def _make_zotero_db(tmp_path: Path, items: list[dict]) -> Path:
    """Lege eine minimale Zotero-SQLite an mit fields, itemData,
    itemDataValues, items, itemAttachments — gerade genug für
    _zotero_pdf_path.

    `items` ist Liste von dicts mit Keys:
      - doi (str)
      - attach_key (str)
      - attach_path (str, mit 'storage:'-Präfix)
      - link_mode (int, default 1)
      - content_type (str, default 'application/pdf')
    """
    zotero_root = tmp_path / "Zotero"
    storage = zotero_root / "storage"
    storage.mkdir(parents=True)
    db_path = zotero_root / "zotero.sqlite"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE fields (fieldID INTEGER PRIMARY KEY, fieldName TEXT);
        CREATE TABLE items (itemID INTEGER PRIMARY KEY, key TEXT);
        CREATE TABLE itemData (itemID INT, fieldID INT, valueID INT);
        CREATE TABLE itemDataValues (valueID INTEGER PRIMARY KEY, value TEXT);
        CREATE TABLE itemAttachments (
            itemID INT, parentItemID INT, linkMode INT,
            contentType TEXT, path TEXT
        );
        INSERT INTO fields (fieldID, fieldName) VALUES (1, 'DOI');
        """
    )
    next_iid = 1
    next_vid = 1
    for spec in items:
        parent_iid = next_iid
        next_iid += 1
        # Parent-Item
        conn.execute(
            "INSERT INTO items (itemID, key) VALUES (?, ?)",
            (parent_iid, f"P{parent_iid:06d}"),
        )
        # DOI-Eintrag
        conn.execute(
            "INSERT INTO itemDataValues (valueID, value) VALUES (?, ?)",
            (next_vid, spec["doi"]),
        )
        conn.execute(
            "INSERT INTO itemData (itemID, fieldID, valueID) VALUES (?, 1, ?)",
            (parent_iid, next_vid),
        )
        next_vid += 1
        # Attachment-Item
        attach_iid = next_iid
        next_iid += 1
        conn.execute(
            "INSERT INTO items (itemID, key) VALUES (?, ?)",
            (attach_iid, spec["attach_key"]),
        )
        conn.execute(
            "INSERT INTO itemAttachments "
            "(itemID, parentItemID, linkMode, contentType, path) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                attach_iid, parent_iid,
                spec.get("link_mode", 1),
                spec.get("content_type", "application/pdf"),
                spec["attach_path"],
            ),
        )
        # Dummy-PDF-Datei anlegen, wenn path "storage:..." ist
        if spec["attach_path"].startswith("storage:"):
            filename = spec["attach_path"][len("storage:"):]
            attach_dir = storage / spec["attach_key"]
            attach_dir.mkdir(parents=True, exist_ok=True)
            (attach_dir / filename).write_bytes(b"%PDF-1.4\n%dummy")
    conn.commit()
    conn.close()
    return zotero_root


class TestZoteroPDFLookup:
    """Tests für `_zotero_pdf_path` — DOI → lokales PDF."""

    def test_returns_none_for_empty_doi(self, tmp_path):
        from journal_bot.escalation.fulltext import _zotero_pdf_path
        z = _make_zotero_db(tmp_path, [])
        assert _zotero_pdf_path("", zotero_root=z) is None
        assert _zotero_pdf_path(None, zotero_root=z) is None

    def test_returns_none_when_db_missing(self, tmp_path):
        from journal_bot.escalation.fulltext import _zotero_pdf_path
        result = _zotero_pdf_path("10.1/x", zotero_root=tmp_path / "nope")
        assert result is None

    def test_finds_pdf_by_exact_doi(self, tmp_path):
        from journal_bot.escalation.fulltext import _zotero_pdf_path
        z = _make_zotero_db(tmp_path, [{
            "doi": "10.1234/foo",
            "attach_key": "AAAABBBB",
            "attach_path": "storage:Foo - 2024 - Title.pdf",
        }])
        result = _zotero_pdf_path("10.1234/foo", zotero_root=z)
        assert result is not None
        pdf_path, key = result
        assert key == "AAAABBBB"
        assert pdf_path.exists()
        assert pdf_path.read_bytes().startswith(b"%PDF-")

    def test_doi_lookup_case_insensitive(self, tmp_path):
        from journal_bot.escalation.fulltext import _zotero_pdf_path
        z = _make_zotero_db(tmp_path, [{
            "doi": "10.1234/Foo",
            "attach_key": "CCCCDDDD",
            "attach_path": "storage:Foo.pdf",
        }])
        assert _zotero_pdf_path("10.1234/foo", zotero_root=z) is not None
        assert _zotero_pdf_path("10.1234/FOO", zotero_root=z) is not None

    def test_doi_url_form_stripped(self, tmp_path):
        from journal_bot.escalation.fulltext import _zotero_pdf_path
        z = _make_zotero_db(tmp_path, [{
            "doi": "10.1234/bar",
            "attach_key": "EEEEFFFF",
            "attach_path": "storage:Bar.pdf",
        }])
        result = _zotero_pdf_path(
            "https://doi.org/10.1234/bar", zotero_root=z,
        )
        assert result is not None

    def test_skips_non_pdf_attachments(self, tmp_path):
        from journal_bot.escalation.fulltext import _zotero_pdf_path
        z = _make_zotero_db(tmp_path, [{
            "doi": "10.1234/html",
            "attach_key": "GGGGHHHH",
            "attach_path": "storage:snapshot.html",
            "content_type": "text/html",
        }])
        assert _zotero_pdf_path("10.1234/html", zotero_root=z) is None

    def test_skips_linked_file_modes(self, tmp_path):
        """linkMode 2/3 (linked file/URL) liegen außerhalb von storage/ —
        wir nehmen nur imported (linkMode 0/1)."""
        from journal_bot.escalation.fulltext import _zotero_pdf_path
        z = _make_zotero_db(tmp_path, [{
            "doi": "10.1234/linked",
            "attach_key": "IIIIJJJJ",
            "attach_path": "storage:Linked.pdf",
            "link_mode": 2,
        }])
        assert _zotero_pdf_path("10.1234/linked", zotero_root=z) is None

    def test_returns_none_when_file_missing(self, tmp_path):
        """DB sagt Anhang existiert, aber Datei fehlt → None."""
        from journal_bot.escalation.fulltext import _zotero_pdf_path
        z = _make_zotero_db(tmp_path, [{
            "doi": "10.1234/ghost",
            "attach_key": "KKKKLLLL",
            "attach_path": "storage:Ghost.pdf",
        }])
        # Datei wegmachen
        (z / "storage" / "KKKKLLLL" / "Ghost.pdf").unlink()
        assert _zotero_pdf_path("10.1234/ghost", zotero_root=z) is None


class TestFulltextFetcherWithZotero:
    """Integration: Zotero hat Vorrang vor OpenAlex/Unpaywall/Crossref."""

    def test_zotero_source_wins_over_web(self, tmp_path, monkeypatch):
        """Wenn Zotero PDF hat, kein httpx-Call."""
        from journal_bot.escalation import fulltext as ft
        z = _make_zotero_db(tmp_path, [{
            "doi": "10.9/test",
            "attach_key": "MOJO0001",
            "attach_path": "storage:Mojo.pdf",
        }])
        # pdftotext mocken (kein Binary nötig)
        monkeypatch.setattr(
            ft, "extract_fulltext", lambda p: "Zotero-Volltext (dummy)",
        )
        # httpx darf NICHT aufgerufen werden
        def fail(*a, **kw):
            raise AssertionError("Zotero-Hit darf nicht netzen")
        monkeypatch.setattr(ft.httpx, "Client", fail)

        result = ft.fetch_fulltext_for_article(
            article_id="art_z1", openalex_id="W999", doi="10.9/test",
            cache_dir=tmp_path / "cache", zotero_root=z,
        )
        assert result.status == "ok"
        assert result.source == "zotero"
        assert result.pdf_url == "zotero://select/library/items/MOJO0001"
        assert result.fulltext_chars == len("Zotero-Volltext (dummy)")
        # Cache geschrieben
        paths = ft.cache_paths("art_z1", tmp_path / "cache")
        assert paths["txt"].exists()
        assert paths["meta"].exists()
        meta = json.loads(paths["meta"].read_text())
        assert meta["source"] == "zotero"

    def test_falls_through_to_web_when_zotero_misses(self, tmp_path, monkeypatch):
        """Zotero hat das DOI nicht → httpx-Call wird gemacht."""
        from journal_bot.escalation import fulltext as ft
        z = _make_zotero_db(tmp_path, [])  # leere Zotero-DB

        called = {"openalex": False}

        def mock_oa(client, oid):
            called["openalex"] = True
            return None  # auch OA findet nix
        monkeypatch.setattr(ft, "_openalex_pdf_url", mock_oa)
        monkeypatch.setattr(ft, "_unpaywall_pdf_url", lambda c, d: None)
        monkeypatch.setattr(ft, "_crossref_pdf_url", lambda c, d: None)

        mock_client = MagicMock()
        mock_client.__enter__ = lambda s: s
        mock_client.__exit__ = lambda *a: None
        monkeypatch.setattr(ft.httpx, "Client", lambda **kw: mock_client)

        result = ft.fetch_fulltext_for_article(
            article_id="art_z2", openalex_id="W123", doi="10.9/missing",
            cache_dir=tmp_path / "cache", zotero_root=z,
        )
        assert called["openalex"] is True
        assert result.status == "no_pdf_url"
