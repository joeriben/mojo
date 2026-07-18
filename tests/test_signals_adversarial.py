"""Tests für Adversarial-Blind-Spot-Signal (MOJO 2.0 §2.2).

Validiert:
  - AdversarialIndex baut die Set-Differenz `trigger_refs \\ benjamin_refs`
    korrekt aus den Trigger-Bibliographie-JSONs.
  - AdversarialCorpusFreq berechnet IDF-Gewichte aus articles.db.
  - signal_adversarial_blindspot matcht Article-Refs gegen das
    Adversarial-Set und gewichtet mit IDF.
  - Cascade-Regel:
    * Adversarial-Score ≥ STRONG → starker_indikator + Mode "adversarial"
    * Adversarial-Score ≥ WEAK   → schwacher_indikator (ohne Mode-Override)
    * own_coupling schlägt adversarial (Reihenfolge in der Cascade)

Schreibt eigene minimale Trigger-Bibliographie-Files in tmp_path, baut eine
leere own_refs.db, prüft Set-Differenz und Scoring isoliert.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from journal_bot.adversarial.corpus_freq import AdversarialCorpusFreq
from journal_bot.adversarial.trigger_refs import (
    AdversarialIndex,
    compute_adversarial_index,
    load_or_compute_adversarial_index,
)
from journal_bot.own_refs.index import OwnRefsIndex, clear_cache
from journal_bot.own_refs.schema import connect
from journal_bot.signals import (
    ADVERSARIAL_STRONG_SCORE, ADVERSARIAL_WEAK_SCORE,
    OWN_COUPLING_STRONG_SCORE,
    SELECTION_MODES, SignalProfile,
    _infer_discourse_indicator, _infer_selection_mode,
    signal_adversarial_blindspot,
)


# ----- Fixtures -------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_index_cache():
    clear_cache()
    yield
    clear_cache()


# Slugs der Fixture-Files unten. Werden explizit übergeben, statt sich auf
# `settings.TRIGGER_AUTHOR_SLUGS` als Default zu verlassen: der Wert kommt aus
# profile.json, und profile.json ist wie `backtest_data/` nicht im Repo. Ein
# Test, der darauf baut, prüft die Konfiguration der Maschine statt der Logik —
# genau daran sind diese Tests gescheitert, als die Slugs 2026-05 aus dem Code
# nach profile.json wanderten und dort nie eintrafen.
FIXTURE_TRIGGER_SLUGS = ("macgilchrist", "jarke", "wendy_chun")


@pytest.fixture
def tmp_trigger_dir(tmp_path: Path) -> Path:
    """Drei Trigger-Bibliographie-JSONs mit überschaubaren Refs."""
    tdir = tmp_path / "trigger_bibliographies"
    tdir.mkdir()
    (tdir / "macgilchrist.json").write_text(json.dumps({
        "trigger_author": "Macgilchrist",
        "works": [
            {"id": "W1", "referenced_works": [
                "https://openalex.org/Wa1", "https://openalex.org/Wshared",
            ]},
        ],
    }))
    (tdir / "jarke.json").write_text(json.dumps({
        "trigger_author": "Jarke",
        "works": [
            {"id": "W2", "referenced_works": [
                "https://openalex.org/Wa2", "https://openalex.org/Wshared",
            ]},
        ],
    }))
    (tdir / "wendy_chun.json").write_text(json.dumps({
        "trigger_author": "Chun",
        "works": [
            {"id": "W3", "referenced_works": ["https://openalex.org/Wa3"]},
        ],
    }))
    return tdir


@pytest.fixture
def benjamin_index_with_one_shared(tmp_path: Path) -> OwnRefsIndex:
    """Benjamin zitiert Wshared (redundant) und Wb1 (eigen)."""
    db = tmp_path / "own_refs.db"
    con = connect(db)
    con.close()
    return OwnRefsIndex(
        oa_ids=frozenset({"Wshared", "Wb1"}),
        dois=frozenset(),
        db_mtime=db.stat().st_mtime,
        db_path=str(db),
    )


# ----- AdversarialIndex ------------------------------------------------------


def test_adversarial_index_set_difference(tmp_trigger_dir, benjamin_index_with_one_shared):
    """Trigger-Union ohne Benjamins eigene Refs."""
    adv = compute_adversarial_index(
        tmp_trigger_dir, benjamin_index_with_one_shared,
        author_keys=FIXTURE_TRIGGER_SLUGS,
    )
    # Trigger-Union: Wa1, Wa2, Wa3, Wshared
    # Minus Benjamin (Wshared, Wb1): Wa1, Wa2, Wa3
    assert adv.oa_ids == frozenset({"Wa1", "Wa2", "Wa3"})
    assert adv.n_trigger_total == 4
    assert adv.n_redundant_with_benjamin == 1
    assert adv.per_author["macgilchrist"] == 2
    assert adv.per_author["jarke"] == 2
    assert adv.per_author["wendy_chun"] == 1


def test_adversarial_index_empty_when_no_files(tmp_path, benjamin_index_with_one_shared):
    """Kein Trigger-Dir → leerer Index, keine Exception."""
    adv = compute_adversarial_index(tmp_path / "missing", benjamin_index_with_one_shared)
    assert adv.is_empty


def test_adversarial_index_cache_roundtrip(
    tmp_path, tmp_trigger_dir, benjamin_index_with_one_shared
):
    """Index-Cache schreibt JSON-Sidecar, lädt es korrekt zurück."""
    adv1 = load_or_compute_adversarial_index(
        tmp_trigger_dir, benjamin_index_with_one_shared,
        own_refs_db=Path(benjamin_index_with_one_shared.db_path),
        author_keys=FIXTURE_TRIGGER_SLUGS,
    )
    assert adv1.oa_ids == frozenset({"Wa1", "Wa2", "Wa3"})

    # Cache existiert
    cache = Path(benjamin_index_with_one_shared.db_path).parent / "trigger_refs_index.json"
    assert cache.exists()

    # Zweiter Aufruf liefert identisch (aus Cache)
    adv2 = load_or_compute_adversarial_index(
        tmp_trigger_dir, benjamin_index_with_one_shared,
        own_refs_db=Path(benjamin_index_with_one_shared.db_path),
        author_keys=FIXTURE_TRIGGER_SLUGS,
    )
    assert adv2.oa_ids == adv1.oa_ids


# ----- signal_adversarial_blindspot -----------------------------------------


def test_signal_adversarial_empty_index():
    """Leerer Index → kein Signal."""
    assert signal_adversarial_blindspot(["W1"], AdversarialIndex()) == {}


def test_signal_adversarial_no_refs():
    """Article ohne OA-Refs → kein Signal."""
    adv = AdversarialIndex(oa_ids=frozenset({"Wa1"}))
    assert signal_adversarial_blindspot([], adv) == {}
    assert signal_adversarial_blindspot(None, adv) == {}


def test_signal_adversarial_one_hit_uses_default_idf():
    """Ohne corpus_freq: 1 Hit → score = 1/log(2) ≈ 1.44."""
    adv = AdversarialIndex(oa_ids=frozenset({"Wa1"}))
    out = signal_adversarial_blindspot(["Wa1", "W_irrelevant"], adv)
    assert out["n_hits"] == 1
    assert out["oa_hits"] == ["Wa1"]
    assert 1.4 < out["score"] < 1.5


def test_signal_adversarial_normalizes_oa_urls():
    """OA-URL-Form normalisieren zu Bare-IDs."""
    adv = AdversarialIndex(oa_ids=frozenset({"Wa1"}))
    out = signal_adversarial_blindspot(["https://openalex.org/Wa1"], adv)
    assert out["oa_hits"] == ["Wa1"]


def test_signal_adversarial_idf_discounts_bestseller():
    """Bestseller im Adversarial-Korpus → niedriger IDF-Score."""
    adv = AdversarialIndex(oa_ids=frozenset({"W_bestseller", "W_rare"}))
    freq = AdversarialCorpusFreq(
        oa_counts={"W_bestseller": 400, "W_rare": 1},
        n_articles_scanned=18000,
    )
    s_b = signal_adversarial_blindspot(["W_bestseller"], adv, freq)
    s_r = signal_adversarial_blindspot(["W_rare"], adv, freq)
    assert s_r["score"] > s_b["score"] * 5


# ----- Cascade-Wirkung ------------------------------------------------------


def test_adversarial_strong_lifts_starker_indikator():
    """Score ≥ STRONG → starker_indikator, auch bei verdict=ignorieren."""
    sp = SignalProfile(
        article_id="x",
        adversarial={"n_hits": 9, "oa_hits": [f"W{i}" for i in range(9)],
                     "score": ADVERSARIAL_STRONG_SCORE + 0.5},
    )
    indicator = _infer_discourse_indicator(
        explicit="", verdict="ignorieren", bemerkenswert=[],
        project_hits=[], signal_profile=sp,
    )
    assert indicator == "starker_indikator"


def test_adversarial_weak_lifts_schwacher_indikator():
    """WEAK ≤ Score < STRONG → schwacher_indikator."""
    sp = SignalProfile(
        article_id="x",
        adversarial={"n_hits": 4, "oa_hits": ["W1","W2","W3","W4"],
                     "score": ADVERSARIAL_WEAK_SCORE + 0.5},
    )
    indicator = _infer_discourse_indicator(
        explicit="", verdict="ignorieren", bemerkenswert=[],
        project_hits=[], signal_profile=sp,
    )
    assert indicator == "schwacher_indikator"


def test_adversarial_below_weak_no_lift():
    """Score unter WEAK → bisheriges Verhalten."""
    sp = SignalProfile(
        article_id="x",
        adversarial={"n_hits": 1, "oa_hits": ["W1"], "score": 0.5},
    )
    indicator = _infer_discourse_indicator(
        explicit="", verdict="ignorieren", bemerkenswert=[],
        project_hits=[], signal_profile=sp,
    )
    assert indicator == "kein_indikator"


def test_adversarial_strong_sets_own_mode():
    """selection_mode 'adversarial' bei Score ≥ STRONG."""
    sp = SignalProfile(
        article_id="x",
        adversarial={"n_hits": 9, "oa_hits": [f"W{i}" for i in range(9)],
                     "score": ADVERSARIAL_STRONG_SCORE + 0.5},
    )
    mode = _infer_selection_mode(
        explicit="", signal_profile=sp, trigger_author_hit=False,
        project_hits=[], bezuege=[], verdict="ignorieren",
        discourse_indicator="starker_indikator",
    )
    assert mode == "adversarial"
    assert "adversarial" in SELECTION_MODES


def test_adversarial_weak_does_not_set_mode():
    """WEAK-Score allein ändert selection_mode NICHT (bleibt screening etc.)."""
    sp = SignalProfile(
        article_id="x",
        adversarial={"n_hits": 4, "oa_hits": ["W1","W2","W3","W4"],
                     "score": ADVERSARIAL_WEAK_SCORE + 0.5},
    )
    mode = _infer_selection_mode(
        explicit="", signal_profile=sp, trigger_author_hit=False,
        project_hits=[], bezuege=[], verdict="ignorieren",
        discourse_indicator="schwacher_indikator",
    )
    assert mode != "adversarial"


def test_own_coupling_wins_over_adversarial():
    """Wenn own_coupling-WEAK schon greift, kommt adversarial nicht zum Zug."""
    sp = SignalProfile(
        article_id="x",
        own_coupling={"n_union": 2, "score": OWN_COUPLING_STRONG_SCORE + 0.5},
        adversarial={"n_hits": 10, "score": ADVERSARIAL_STRONG_SCORE + 0.5},
    )
    mode = _infer_selection_mode(
        explicit="", signal_profile=sp, trigger_author_hit=False,
        project_hits=[], bezuege=[], verdict="ignorieren",
        discourse_indicator="starker_indikator",
    )
    assert mode == "own_coupling"  # priorisiert
