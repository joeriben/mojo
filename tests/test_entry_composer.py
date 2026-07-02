"""Tests für den substitutiven Eintrags-Komponisten (journal_bot.entry_composer).

Invarianten:
  - grounded attributiert geteilte Referenzen (OA + DOI) auf konkrete
    Eigenwerke; Null-Überschneidung ergibt eine ehrliche Leerstelle.
  - Umfeld-Annotation schließt den eigenen Erstautor aus (Selbstzitationen
    zählen nicht als Umfeld) und bleibt Annotation — der Komponist verändert
    weder Verdikt noch agent_entry (iter_44: Kopplung trennt nicht Relevanz).
  - Fehlende Quell-DBs degradieren sichtbar (available=False) statt zu raten.
  - Store: Migration + composed_entry-Roundtrip.

Alles offline (resolve_titles=False), keine Netz-Calls.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from journal_bot import bezugsautoren as bz
from journal_bot.entry_composer import (
    ComposerResources,
    compose_and_store,
    compose_entry,
    load_composer_resources,
)
from journal_bot.store import Store, StoredArticle


# ------------------------------------------------------------- Fixtures ------


def _make_own_refs_db(path: Path) -> None:
    con = sqlite3.connect(str(path))
    con.executescript(
        """
        CREATE TABLE publications (canonical_id TEXT, title TEXT, year INTEGER);
        CREATE TABLE pub_refs (canonical_id TEXT, ref_doi TEXT, ref_oa_id TEXT);
        CREATE TABLE source_refs (canonical_id TEXT, source_item_id TEXT,
                                  source_type TEXT);
        """
    )
    con.executemany(
        "INSERT INTO publications VALUES (?,?,?)",
        [
            ("pub_a", "Medienbildung und das Postdigitale", 2019),
            ("pub_b", "Ästhetische Bildung in digitalen Kulturen", 2022),
        ],
    )
    con.executemany(
        "INSERT INTO pub_refs VALUES (?,?,?)",
        [
            ("pub_a", None, "https://openalex.org/W1000"),
            ("pub_a", "10.1000/shared-doi", None),
            ("pub_b", None, "https://openalex.org/W1000"),
            ("pub_b", None, "https://openalex.org/W2000"),
        ],
    )
    con.execute("INSERT INTO source_refs VALUES ('pub_a', 'ZKEY_A', 'zotero')")
    con.commit()
    con.close()


def _make_bezugsautoren_db(path: Path) -> None:
    """Autor SELF ist Erstautor des Testartikels (Seed art-1), Autor OTHER
    stammt aus einer früheren Sichtung (Seed art-99)."""
    con = sqlite3.connect(str(path))
    bz.init_db(con)
    con.executemany(
        "INSERT INTO authors VALUES (?,?,?,?,?,datetime('now'))",
        [
            ("A_SELF", "Self Author", 40, 100, 2),
            ("A_OTHER", "Umfeld Author", 60, 500, 1),
        ],
    )
    con.executemany(
        "INSERT INTO author_seed VALUES (?,?,?,datetime('now'))",
        [("A_SELF", "art-1", "first_author"),
         ("A_OTHER", "art-99", "first_author")],
    )
    # Werke: W_SELF gehört dem eigenen Erstautor, W_UMFELD dem Umfeld-Autor.
    # Das Œuvre von A_SELF referenziert W2000 (koppelt mit pub_b).
    con.executemany(
        "INSERT INTO author_works VALUES (?,?,?,?,?,?,?,?,?,datetime('now'))",
        [
            ("A_SELF", "W_SELF", "Eigenwerk des Erstautors", "", 2021, 10,
             json.dumps(["W2000", "W5555"]), 2, "recent"),
            ("A_OTHER", "W_UMFELD", "Werk aus dem Umfeld", "", 2020, 300,
             json.dumps(["W7777"]), 1, "cited"),
        ],
    )
    con.commit()
    con.close()


def _resources(tmp_path: Path, with_bez: bool = True) -> ComposerResources:
    own = tmp_path / "own_refs.db"
    if not own.exists():
        _make_own_refs_db(own)
    bezdb = tmp_path / "bezugsautoren.db"
    if with_bez and not bezdb.exists():
        _make_bezugsautoren_db(bezdb)
    return load_composer_resources(own_refs_db=own, bezugsautoren_db=bezdb)


def _article(**over) -> StoredArticle:
    base = dict(
        id="art-1",
        journal_short="TST",
        journal_full="Testjournal",
        title="Testartikel",
        openalex_refs=[],
        crossref_refs=[],
        citation_hits=[],
    )
    base.update(over)
    return StoredArticle(**base)


# ------------------------------------------------------------- grounded ------


def test_grounded_attribution_oa_and_doi(tmp_path):
    res = _resources(tmp_path, with_bez=False)
    sa = _article(
        openalex_refs=["https://openalex.org/W1000", "https://openalex.org/W9999"],
        crossref_refs=[{"doi": "10.1000/SHARED-DOI", "article-title": "Shared Ref"}],
    )
    c = compose_entry(sa, res, resolve_titles=False)
    g = c["grounded"]
    assert g["available"] is True
    assert g["n_shared_refs"] == 2  # W1000 + DOI
    by_id = {w["pub_id"]: w for w in g["works"]}
    # pub_a über W1000 UND die DOI (2 via), pub_b nur über W1000
    assert by_id["pub_a"]["n_shared"] == 2
    assert by_id["pub_a"]["zotero_key"] == "ZKEY_A"
    assert by_id["pub_b"]["n_shared"] == 1
    # meist-gekoppeltes Werk zuerst
    assert g["works"][0]["pub_id"] == "pub_a"
    # DOI-Titel aus Crossref durchgereicht (Normalisierung lowercased)
    doi_via = [v for v in by_id["pub_a"]["via"] if v["kind"] == "doi"]
    assert doi_via and doi_via[0]["title"] == "Shared Ref"
    assert c["einordnung"] == "konkret"


def test_honest_null_without_overlap(tmp_path):
    res = _resources(tmp_path, with_bez=False)
    sa = _article(openalex_refs=["https://openalex.org/W9999"])
    c = compose_entry(sa, res, resolve_titles=False)
    assert c["grounded"]["n_shared_refs"] == 0
    assert c["grounded"]["works"] == []
    assert c["einordnung"] == "leer"


def test_citation_hits_alone_are_konkret(tmp_path):
    res = _resources(tmp_path, with_bez=False)
    sa = _article(openalex_refs=["https://openalex.org/W9999"])
    c = compose_entry(
        sa, res, citation_hits=[{"pub_id": "pub_a", "confidence": "high"}],
        resolve_titles=False,
    )
    assert c["n_citation_hits"] == 1
    assert c["einordnung"] == "konkret"


# --------------------------------------------------------------- umfeld ------


def test_umfeld_excludes_own_first_author(tmp_path):
    res = _resources(tmp_path)
    # Artikel zitiert je ein Werk des eigenen Erstautors und des Umfelds
    sa = _article(openalex_refs=["W_SELF", "W_UMFELD"])
    c = compose_entry(sa, res, resolve_titles=False)
    u = c["umfeld"]
    assert u["available"] is True
    cited_ids = {w["oa_id"] for w in u["cited_works"]}
    assert cited_ids == {"W_UMFELD"}  # Selbstzitation zählt nicht als Umfeld
    assert u["cited_works"][0]["authors"] == ["Umfeld Author"]
    assert c["einordnung"] == "konkret"


def test_first_author_coupling_yields_umfeld_tier(tmp_path):
    res = _resources(tmp_path)
    # Artikel selbst koppelt nicht (fremde Refs), aber das Œuvre des
    # Erstautors (A_SELF) referenziert W2000 → own pub_b
    sa = _article(openalex_refs=["W9999"])
    c = compose_entry(sa, res, resolve_titles=False)
    fa = c["umfeld"]["first_author"]
    assert fa["name"] == "Self Author"
    assert fa["n_shared_refs"] == 1
    assert fa["n_own_works"] == 1
    assert c["grounded"]["n_shared_refs"] == 0
    assert c["einordnung"] == "umfeld"


def test_missing_dbs_degrade_visibly(tmp_path):
    res = load_composer_resources(
        own_refs_db=tmp_path / "missing_own.db",
        bezugsautoren_db=tmp_path / "missing_bez.db",
    )
    sa = _article(openalex_refs=["W1000"])
    c = compose_entry(sa, res, resolve_titles=False)
    assert c["grounded"]["available"] is False
    assert c["umfeld"]["available"] is False
    assert c["einordnung"] == "leer"


# ---------------------------------------------------------------- store ------


def test_store_migration_and_roundtrip(tmp_path):
    store = Store(path=tmp_path / "articles.db")
    sa = _article()
    store.upsert_article(sa)

    store.update_composed_entry(sa.id, {"composer_version": 1, "einordnung": "leer"})
    got = store.get(sa.id)
    assert got.composed_entry == {"composer_version": 1, "einordnung": "leer"}

    store.update_composed_entry(sa.id, None)
    assert store.get(sa.id).composed_entry is None


def test_compose_and_store_touches_neither_verdict_nor_entry(tmp_path):
    store = Store(path=tmp_path / "articles.db")
    sa = _article(openalex_refs=["https://openalex.org/W1000"])
    store.upsert_article(sa)
    store.update_agent_result(
        sa.id, verdict="scannen",
        entry={"kernthese": "These.", "verdict": "scannen",
               "verdict_begruendung": "B.", "bezuege": []},
        citation_hits=[], tokens_in=1, tokens_out=1, tokens_cached_read=0,
        tokens_cache_write=0, cost_usd=0.0, iterations=1,
    )
    before = store.get(sa.id)

    res = _resources(tmp_path, with_bez=False)
    composed = compose_and_store(store, before, res, resolve_titles=False)
    assert composed["grounded"]["n_shared_refs"] == 1

    after = store.get(sa.id)
    assert after.agent_verdict == before.agent_verdict == "scannen"
    assert after.agent_entry == before.agent_entry
    assert after.composed_entry["einordnung"] == "konkret"
