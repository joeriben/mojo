"""Tests für Iter-11-Veto-Up-Regel auf den produktiven Refs-Index.

Was hier validiert wird (HANDOVER §2.1):
  - Loader `load_own_refs_index` über eine frisch gebaute `own_refs.db`
  - `signal_own_coupling` matcht Article-Refs gegen Benjamins Refs-Wolke
  - Veto-Up-Regel `f_own_coupling_union ≥ 1`:
      * setzt `discourse_indicator = "starker_indikator"` AUCH wenn der Agent
        `verdict="ignorieren"` gesagt hat — das ist der +5.2 pp-LES-Recall-Hebel
      * setzt `selection_mode = "own_coupling"` als eigene Mode-Kategorie

Snapshot-Vermeidung: alle Tests bauen ihre eigene `own_refs.db` in tmp_path
und schreiben über `OwnRefsStore` direkt — kein Build-Orchestrator, kein
pdftotext, keine Netz-Calls. Das hält die Tests <100 ms.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from journal_bot.own_refs.index import (
    OwnRefsIndex, clear_cache, load_own_refs_index,
)
from journal_bot.own_refs.schema import connect
from journal_bot.own_refs.store import OwnRefsStore, Publication, PubRef
from journal_bot.own_refs.corpus_freq import CorpusFreq
from journal_bot.signals import (
    OWN_COUPLING_STRONG_SCORE, OWN_COUPLING_WEAK_SCORE,
    SELECTION_MODES, SignalProfile,
    _infer_discourse_indicator, _infer_selection_mode,
    compute_signals, derive_attention_profile,
    signal_own_coupling,
)


# ----- Fixtures -------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clear_index_cache():
    """Verhindert Cross-Test-Pollution durch den Modul-Cache in index.py."""
    clear_cache()
    yield
    clear_cache()


@pytest.fixture
def tmp_db(tmp_path: Path) -> Path:
    """Frische, leere own_refs.db unter tmp_path."""
    db_path = tmp_path / "own_refs.db"
    con = connect(db_path)
    con.close()
    return db_path


def _seed_pub(store: OwnRefsStore, canonical_id: str) -> None:
    """Minimalpublikation, damit FK auf pub_refs hält."""
    store.upsert_publication(
        Publication(
            canonical_id=canonical_id,
            doi="10.1000/seed",
            title="Seed publication",
            year=2020,
            item_type="article",
            venue="Test Journal",
            authors=["Test Author"],
            discourse=[],
            fulltext_path=None,
            fulltext_chars=0,
            refs_extracted_at=None,
            refs_header_label=None,
            notes=[],
        )
    )


def _seed_refs(
    db_path: Path,
    refs: list[tuple[str | None, str | None]],
) -> None:
    """Lege Test-Refs (doi, oa_id)-Paare in die DB."""
    with OwnRefsStore(db_path) as store:
        _seed_pub(store, "doi:10.1000/seed")
        pub_refs = []
        for i, (doi, oa) in enumerate(refs):
            ref_key = doi or oa or f"unk_{i}"
            pub_refs.append(
                PubRef(
                    canonical_id="doi:10.1000/seed",
                    ref_id=f"doi:{ref_key}" if doi else f"oa:{ref_key}",
                    ref_doi=doi,
                    ref_oa_id=oa,
                    ref_year=2018,
                    resolution_state="doi_resolved" if oa else "doi_unresolved",
                )
            )
        store.replace_pub_refs("doi:10.1000/seed", pub_refs)


# ----- Index-Loader ---------------------------------------------------------


def test_load_index_missing_db(tmp_path: Path):
    """Fehlende DB → leerer Index, keine Exception."""
    idx = load_own_refs_index(tmp_path / "does_not_exist.db")
    assert idx.is_empty
    assert idx.oa_ids == frozenset()
    assert idx.dois == frozenset()
    assert idx.n_pubs_with_refs == 0


def test_load_index_empty_db(tmp_db: Path):
    """DB ohne pub_refs → leerer Index."""
    idx = load_own_refs_index(tmp_db)
    assert idx.is_empty
    assert idx.db_path == str(tmp_db)


def test_load_index_with_data(tmp_db: Path):
    """DB mit zwei Refs → korrekte OA- und DOI-Sets."""
    _seed_refs(
        tmp_db,
        [
            ("10.1234/foo", "W111"),
            (None, "W222"),
            ("10.5678/bar", None),
        ],
    )
    idx = load_own_refs_index(tmp_db)
    assert not idx.is_empty
    assert idx.oa_ids == frozenset({"W111", "W222"})
    assert idx.dois == frozenset({"10.1234/foo", "10.5678/bar"})
    assert idx.n_pubs_with_refs == 1
    assert idx.n_refs_total == 3


def test_load_index_normalizes_oa_urls(tmp_db: Path):
    """OA-URLs werden zu Bare-IDs normalisiert (Iter-11-Konvention)."""
    _seed_refs(tmp_db, [(None, "https://openalex.org/W999")])
    idx = load_own_refs_index(tmp_db)
    assert idx.oa_ids == frozenset({"W999"})


def test_index_cache_invalidates_on_mtime(tmp_db: Path):
    """Wenn die DB neu geschrieben wird, liefert der Loader frische Daten."""
    _seed_refs(tmp_db, [(None, "W001")])
    idx1 = load_own_refs_index(tmp_db)
    assert "W001" in idx1.oa_ids

    # Schreibe einen weiteren Ref und stelle mtime sicher
    import time
    time.sleep(0.01)
    with OwnRefsStore(tmp_db) as store:
        existing = store.get_pub_refs("doi:10.1000/seed")
        existing.append(
            PubRef(
                canonical_id="doi:10.1000/seed",
                ref_id="oa:W002",
                ref_doi=None,
                ref_oa_id="W002",
                ref_year=2019,
                resolution_state="doi_resolved",
            )
        )
        store.replace_pub_refs("doi:10.1000/seed", existing)

    idx2 = load_own_refs_index(tmp_db)
    assert idx2.oa_ids == frozenset({"W001", "W002"})


# ----- signal_own_coupling --------------------------------------------------


def test_signal_own_coupling_empty_index():
    """Leerer Index → kein Signal."""
    idx = OwnRefsIndex()
    out = signal_own_coupling([], [], idx)
    assert out == {}


def test_signal_own_coupling_no_refs_in_article():
    """Article ohne Refs → kein Signal."""
    idx = OwnRefsIndex(oa_ids=frozenset({"W1"}), dois=frozenset({"10.1/x"}))
    assert signal_own_coupling([], [], idx) == {}
    assert signal_own_coupling(None, None, idx) == {}


def test_signal_own_coupling_oa_hit():
    """1 OA-Hit → n_union=1, oa_hits=[W1], score>0."""
    idx = OwnRefsIndex(oa_ids=frozenset({"W1", "W2"}), dois=frozenset())
    out = signal_own_coupling(
        crossref_refs=[],
        openalex_refs=["https://openalex.org/W1", "https://openalex.org/W999"],
        own_refs_index=idx,
    )
    assert out["n_union"] == 1
    assert out["oa_hits"] == ["W1"]
    assert out["doi_hits"] == []
    assert out["score"] > 0


def test_signal_own_coupling_doi_hit():
    """1 DOI-Hit über crossref_refs.[].doi → n_union=1."""
    idx = OwnRefsIndex(oa_ids=frozenset(), dois=frozenset({"10.1/x"}))
    out = signal_own_coupling(
        crossref_refs=[{"doi": "10.1/x", "raw": "..."},
                       {"doi": "10.9/y", "raw": "..."}],
        openalex_refs=[],
        own_refs_index=idx,
    )
    assert out["n_union"] == 1
    assert out["doi_hits"] == ["10.1/x"]
    assert out["oa_hits"] == []


def test_signal_own_coupling_union_is_max():
    """Union = max(|oa_hits|, |doi_hits|), siehe Iter-11-Begründung."""
    idx = OwnRefsIndex(
        oa_ids=frozenset({"W1", "W2"}),
        dois=frozenset({"10.1/x"}),
    )
    out = signal_own_coupling(
        crossref_refs=[{"doi": "10.1/x"}],
        openalex_refs=["W1", "W2"],
        own_refs_index=idx,
    )
    # max(2, 1) = 2 (konservatives Iter-11-Modell)
    assert out["n_union"] == 2


# ----- IDF-Scoring (§2.1b) --------------------------------------------------


def test_signal_own_coupling_idf_discounts_bestseller():
    """Bestseller (hohe globale Häufigkeit) → niedriger IDF-Score."""
    idx = OwnRefsIndex(oa_ids=frozenset({"W_bestseller", "W_rare"}), dois=frozenset())
    freq = CorpusFreq(
        oa_counts={"W_bestseller": 249, "W_rare": 1},
        n_articles_scanned=18000,
    )
    s_bestseller = signal_own_coupling([], ["W_bestseller"], idx, freq)
    s_rare = signal_own_coupling([], ["W_rare"], idx, freq)
    # rare hit → ~1.44, bestseller hit → ~0.18 (Faktor ~8)
    assert s_rare["score"] > s_bestseller["score"] * 5


def test_signal_own_coupling_single_bestseller_below_weak_threshold():
    """Genau das Verhalten, das Benjamin gefordert hat: 1 Bestseller-Hit
    alleine darf den WEAK-Threshold NICHT überschreiten."""
    idx = OwnRefsIndex(oa_ids=frozenset({"W_bestseller"}), dois=frozenset())
    freq = CorpusFreq(
        oa_counts={"W_bestseller": 249},
        n_articles_scanned=18000,
    )
    out = signal_own_coupling([], ["W_bestseller"], idx, freq)
    assert out["score"] < OWN_COUPLING_WEAK_SCORE


def test_signal_own_coupling_multiple_specific_hits_passes_strong():
    """Drei spezifische Refs zusammen erreichen den STRONG-Threshold."""
    idx = OwnRefsIndex(oa_ids=frozenset({"W1", "W2", "W3"}), dois=frozenset())
    freq = CorpusFreq(
        oa_counts={"W1": 1, "W2": 1, "W3": 1},
        n_articles_scanned=18000,
    )
    out = signal_own_coupling([], ["W1", "W2", "W3"], idx, freq)
    assert out["score"] >= OWN_COUPLING_STRONG_SCORE


def test_signal_own_coupling_fallback_without_corpus_freq():
    """Ohne corpus_freq: Default-Gewicht 1/log(2) ≈ 1.44 pro Hit."""
    idx = OwnRefsIndex(oa_ids=frozenset({"W1"}), dois=frozenset())
    out = signal_own_coupling([], ["W1"], idx, corpus_freq=None)
    # 1 Hit * 1/log(2) ≈ 1.44
    assert 1.4 < out["score"] < 1.5


def test_signal_own_coupling_normalizes_doi_prefixes():
    """DOI-Präfix-Varianten matchen alle gegen dieselbe normalisierte DOI."""
    idx = OwnRefsIndex(oa_ids=frozenset(), dois=frozenset({"10.1/x"}))
    out = signal_own_coupling(
        crossref_refs=[{"doi": "https://doi.org/10.1/X"}],
        openalex_refs=[],
        own_refs_index=idx,
    )
    assert out["doi_hits"] == ["10.1/x"]


# ----- SignalProfile-Integration --------------------------------------------


def test_signal_profile_f_own_coupling_union_property():
    """Property liest n_union aus dem own_coupling-Dict."""
    sp = SignalProfile(article_id="x", own_coupling={"n_union": 3})
    assert sp.f_own_coupling_union == 3

    sp_empty = SignalProfile(article_id="y", own_coupling={})
    assert sp_empty.f_own_coupling_union == 0


def test_signal_profile_summary_includes_own_coupling():
    """summary() listet own_coupling auf wenn ≥ 1 Hit."""
    sp = SignalProfile(
        article_id="x",
        own_coupling={"n_union": 2, "oa_hits": ["W1", "W2"], "doi_hits": []},
    )
    assert "own_coupling" in sp.summary


def test_compute_signals_passes_through_own_index():
    """compute_signals reicht openalex_refs und own_refs_index an Signal-Func."""
    idx = OwnRefsIndex(oa_ids=frozenset({"W1"}), dois=frozenset())
    sp = compute_signals(
        article_id="x",
        title="",
        crossref_refs_json=[],
        openalex_refs_json=["W1"],
        own_refs_index=idx,
    )
    assert sp.f_own_coupling_union == 1
    assert sp.has_any_signal


# ----- Cascade-Veto-Up ------------------------------------------------------


def test_veto_up_strong_overrides_ignorieren_verdict():
    """Score ≥ STRONG → starker_indikator, auch bei verdict=ignorieren."""
    sp = SignalProfile(
        article_id="x",
        own_coupling={
            "n_union": 2, "oa_hits": ["W1", "W2"], "doi_hits": [],
            "score": OWN_COUPLING_STRONG_SCORE + 0.1,
        },
    )
    indicator = _infer_discourse_indicator(
        explicit="",
        verdict="ignorieren",
        bemerkenswert=[],
        project_hits=[],
        signal_profile=sp,
    )
    assert indicator == "starker_indikator"


def test_veto_up_weak_returns_schwacher_indikator():
    """Score im WEAK-Bereich → schwacher_indikator, nicht starker."""
    sp = SignalProfile(
        article_id="x",
        own_coupling={
            "n_union": 1, "oa_hits": ["W1"], "doi_hits": [],
            "score": OWN_COUPLING_WEAK_SCORE + 0.05,
        },
    )
    indicator = _infer_discourse_indicator(
        explicit="",
        verdict="ignorieren",
        bemerkenswert=[],
        project_hits=[],
        signal_profile=sp,
    )
    assert indicator == "schwacher_indikator"


def test_veto_up_below_weak_no_lift():
    """Score unter WEAK-Schwelle → bisheriges Verhalten, kein Lift.
    Das ist der Bestseller-Schutz: 1 Standardwerk-Hit allein lift nichts."""
    sp = SignalProfile(
        article_id="x",
        own_coupling={
            "n_union": 1, "oa_hits": ["W_bestseller"], "doi_hits": [],
            "score": 0.20,  # typischer Bestseller-IDF
        },
    )
    indicator = _infer_discourse_indicator(
        explicit="",
        verdict="ignorieren",
        bemerkenswert=[],
        project_hits=[],
        signal_profile=sp,
    )
    assert indicator == "kein_indikator"


def test_veto_up_selection_mode_own_coupling_at_weak():
    """selection_mode='own_coupling' wird ab WEAK-Schwelle gesetzt."""
    sp = SignalProfile(
        article_id="x",
        own_coupling={
            "n_union": 1, "oa_hits": ["W1"], "doi_hits": [],
            "score": OWN_COUPLING_WEAK_SCORE + 0.05,
        },
    )
    mode = _infer_selection_mode(
        explicit="",
        signal_profile=sp,
        trigger_author_hit=False,
        project_hits=[],
        bezuege=[],
        verdict="ignorieren",
        discourse_indicator="schwacher_indikator",
    )
    assert mode == "own_coupling"
    assert "own_coupling" in SELECTION_MODES


def test_veto_up_below_weak_no_selection_mode_change():
    """Score unter WEAK → kein 'own_coupling'-Mode (Bestseller-Schutz)."""
    sp = SignalProfile(
        article_id="x",
        own_coupling={
            "n_union": 1, "oa_hits": ["W_bestseller"], "doi_hits": [],
            "score": 0.20,
        },
    )
    mode = _infer_selection_mode(
        explicit="",
        signal_profile=sp,
        trigger_author_hit=False,
        project_hits=[],
        bezuege=[],
        verdict="ignorieren",
        discourse_indicator="kein_indikator",
    )
    assert mode != "own_coupling"


def test_citation_wins_over_own_coupling():
    """Wenn der Artikel Benjamin direkt zitiert, ist das stärker als Coupling."""
    sp = SignalProfile(
        article_id="x",
        cites_researcher=[{"author": "Joerissen", "year": 2020}],
        own_coupling={
            "n_union": 5, "oa_hits": ["W1"] * 5, "doi_hits": [],
            "score": 5.0,
        },
    )
    mode = _infer_selection_mode(
        explicit="",
        signal_profile=sp,
        trigger_author_hit=False,
        project_hits=[],
        bezuege=[],
        verdict="ignorieren",
        discourse_indicator="starker_indikator",
    )
    assert mode == "citation"


def test_trigger_wins_over_own_coupling():
    """Trigger-Autor schlägt own_coupling."""
    sp = SignalProfile(
        article_id="x",
        own_coupling={
            "n_union": 2, "oa_hits": ["W1", "W2"], "doi_hits": [],
            "score": OWN_COUPLING_STRONG_SCORE + 0.5,
        },
    )
    mode = _infer_selection_mode(
        explicit="",
        signal_profile=sp,
        trigger_author_hit=True,
        project_hits=[],
        bezuege=[],
        verdict="ignorieren",
        discourse_indicator="starker_indikator",
    )
    assert mode == "trigger"


def test_no_coupling_no_veto_up():
    """Ohne own_coupling-Hit bleibt das bisherige Verhalten unverändert."""
    sp = SignalProfile(article_id="x")
    indicator = _infer_discourse_indicator(
        explicit="",
        verdict="ignorieren",
        bemerkenswert=[],
        project_hits=[],
        signal_profile=sp,
    )
    assert indicator == "kein_indikator"


# ----- End-to-End mit derive_attention_profile ------------------------------


def test_attention_profile_end_to_end_strong(tmp_db: Path):
    """E2E: mehrere spezifische (nicht-Bestseller) Refs + verdict=ignorieren →
    starker_indikator + selection_mode=own_coupling. Score ~2.88 (>STRONG)."""
    _seed_refs(
        tmp_db,
        [(None, "W001"), (None, "W002"), ("10.1/x", None), ("10.1/y", None)],
    )

    resources = {
        "authored_all": [],
        "key_terms": set(),
        "zotero_doi_index": {},
        "zotero_word_index": {},
        "own_refs_index": load_own_refs_index(tmp_db),
        # Alle Refs nur 1× im Korpus → IDF=1.44 pro Hit
        "corpus_freq": CorpusFreq(
            oa_counts={"W001": 1, "W002": 1},
            doi_counts={"10.1/x": 1, "10.1/y": 1},
            n_articles_scanned=18000,
        ),
    }
    profile = derive_attention_profile(
        article_id="art-1",
        title="A cited article",
        authors=["Anon"],
        crossref_refs=[{"doi": "10.1/x"}, {"doi": "10.1/y"}],
        openalex_refs=["W001", "W002"],
        entry={"verdict": "ignorieren"},
        signal_resources=resources,
    )
    assert profile.discourse_indicator == "starker_indikator"
    assert profile.selection_mode == "own_coupling"

    sig = profile.deterministic_signals["own_coupling"]
    assert sig["n_union"] == 2
    assert sig["score"] >= OWN_COUPLING_STRONG_SCORE


def test_attention_profile_end_to_end_bestseller_filtered(tmp_db: Path):
    """E2E mit Bestseller-Hit: Score unter WEAK → kein Lift."""
    _seed_refs(tmp_db, [(None, "W_bestseller")])

    resources = {
        "authored_all": [],
        "key_terms": set(),
        "zotero_doi_index": {},
        "zotero_word_index": {},
        "own_refs_index": load_own_refs_index(tmp_db),
        # 249× im Korpus → IDF ≈ 0.18 (unter WEAK 0.60)
        "corpus_freq": CorpusFreq(
            oa_counts={"W_bestseller": 249},
            n_articles_scanned=18000,
        ),
    }
    profile = derive_attention_profile(
        article_id="art-1",
        title="A cited article",
        authors=["Anon"],
        crossref_refs=[],
        openalex_refs=["W_bestseller"],
        entry={"verdict": "ignorieren"},
        signal_resources=resources,
    )
    # Trotz Hit kein Veto-Up — Bestseller schlägt nicht durch
    assert profile.discourse_indicator == "kein_indikator"
    assert profile.selection_mode != "own_coupling"
    # Signal selbst ist da, nur nicht stark genug
    assert profile.deterministic_signals["own_coupling"]["n_union"] == 1


# ----- §2.6: Citation-Mode + Double-Hit Veto-Up -----------------------------


def test_section_2_6_citation_mode_double_hit_lifts_to_strong(tmp_db: Path):
    """§2.6 — Citation-Mode UND ≥2 own_coupling-Hits → starker_indikator.

    Klinge/Tost-Fall: Artikel wurde via Citation-Pfad selektiert
    (`entry["selection_mode"]="citation"` als explicit), und der OpenAlex-Refs-
    Schnitt liefert 2 Eigenwerk-Hits, die unter der WEAK-Score-Schwelle (0.60)
    bleiben würden (Bestseller-Refs). Ohne §2.6 wäre der discourse_indicator
    'kein_indikator'/'schwacher_indikator' — mit §2.6 wird er auf
    'starker_indikator' gehoben.
    """
    _seed_refs(tmp_db, [(None, "W_bestseller_1"), (None, "W_bestseller_2")])

    resources = {
        "authored_all": [],
        "key_terms": set(),
        "zotero_doi_index": {},
        "zotero_word_index": {},
        "own_refs_index": load_own_refs_index(tmp_db),
        # Beide Refs sind Bestseller (~249× im Korpus) → Score < WEAK,
        # aber n_union = 2.
        "corpus_freq": CorpusFreq(
            oa_counts={"W_bestseller_1": 249, "W_bestseller_2": 249},
            n_articles_scanned=18000,
        ),
    }
    profile = derive_attention_profile(
        article_id="klinge-tost-like",
        title="Design als Vergangenheit",
        authors=["Klinge", "Tost"],
        crossref_refs=[],
        openalex_refs=["W_bestseller_1", "W_bestseller_2"],
        # selection_mode='citation' explizit gesetzt (in der echten Pipeline
        # kommt das aus cites_researcher via DOI-Match in crossref_refs)
        entry={
            "verdict": "scannen",
            "selection_mode": "citation",
        },
        signal_resources=resources,
    )
    # n_union=2, beide Bestseller → score unter WEAK
    sig = profile.deterministic_signals["own_coupling"]
    assert sig["n_union"] == 2
    assert sig["score"] < OWN_COUPLING_WEAK_SCORE
    assert profile.selection_mode == "citation"
    # §2.6 hebt discourse_indicator trotz Bestseller-Score auf starker_indikator
    assert profile.discourse_indicator == "starker_indikator"


def test_section_2_6_citation_mode_single_hit_no_lift(tmp_db: Path):
    """§2.6 greift NICHT bei n_union=1 — Single-Hit ist nicht verlässlich genug."""
    _seed_refs(tmp_db, [(None, "W_bestseller")])

    resources = {
        "authored_all": [],
        "key_terms": set(),
        "zotero_doi_index": {},
        "zotero_word_index": {},
        "own_refs_index": load_own_refs_index(tmp_db),
        "corpus_freq": CorpusFreq(
            oa_counts={"W_bestseller": 249},
            n_articles_scanned=18000,
        ),
    }
    profile = derive_attention_profile(
        article_id="single-hit",
        title="Random article",
        authors=["X"],
        crossref_refs=[],
        openalex_refs=["W_bestseller"],
        entry={
            "verdict": "scannen",
            "selection_mode": "citation",
        },
        signal_resources=resources,
    )
    sig = profile.deterministic_signals["own_coupling"]
    assert sig["n_union"] == 1
    assert profile.selection_mode == "citation"
    # Kein Veto-Up bei n_union=1
    assert profile.discourse_indicator != "starker_indikator"


def test_section_2_6_no_citation_mode_no_lift(tmp_db: Path):
    """§2.6 greift NICHT, wenn selection_mode != 'citation' — die Doppel-Hit-
    Regel ist spezifisch für den Citation-Pfad."""
    _seed_refs(tmp_db, [(None, "W_bestseller_1"), (None, "W_bestseller_2")])

    resources = {
        "authored_all": [],
        "key_terms": set(),
        "zotero_doi_index": {},
        "zotero_word_index": {},
        "own_refs_index": load_own_refs_index(tmp_db),
        "corpus_freq": CorpusFreq(
            oa_counts={"W_bestseller_1": 249, "W_bestseller_2": 249},
            n_articles_scanned=18000,
        ),
    }
    profile = derive_attention_profile(
        article_id="non-citation",
        title="A cited article",
        authors=["Anon"],
        crossref_refs=[],
        openalex_refs=["W_bestseller_1", "W_bestseller_2"],
        # selection_mode='similarity' explizit gesetzt — KEIN citation-Pfad
        entry={
            "verdict": "scannen",
            "selection_mode": "similarity",
        },
        signal_resources=resources,
    )
    sig = profile.deterministic_signals["own_coupling"]
    assert sig["n_union"] == 2
    assert sig["score"] < OWN_COUPLING_WEAK_SCORE
    assert profile.selection_mode != "citation"
    # Ohne citation-Pfad bleibt es bei schwachem/keinem Indikator
    assert profile.discourse_indicator != "starker_indikator"


def test_section_2_6_preserves_existing_strong(tmp_db: Path):
    """§2.6 überschreibt nichts — wenn discourse_indicator bereits starker_indikator
    ist (z.B. via IDF-Score), bleibt es unverändert."""
    _seed_refs(tmp_db, [(None, "W_specific_1"), (None, "W_specific_2")])

    resources = {
        "authored_all": [],
        "key_terms": set(),
        "zotero_doi_index": {},
        "zotero_word_index": {},
        "own_refs_index": load_own_refs_index(tmp_db),
        # Spezifische Refs (1× im Korpus) → hoher IDF-Score
        "corpus_freq": CorpusFreq(
            oa_counts={"W_specific_1": 1, "W_specific_2": 1},
            n_articles_scanned=18000,
        ),
    }
    profile = derive_attention_profile(
        article_id="strong-already",
        title="A cited article",
        authors=["Klinge"],
        crossref_refs=[],
        openalex_refs=["W_specific_1", "W_specific_2"],
        entry={
            "verdict": "scannen",
            "selection_mode": "citation",
        },
        signal_resources=resources,
    )
    sig = profile.deterministic_signals["own_coupling"]
    assert sig["n_union"] == 2
    assert sig["score"] >= OWN_COUPLING_STRONG_SCORE
    assert profile.selection_mode == "citation"
    assert profile.discourse_indicator == "starker_indikator"


def test_attention_profile_graceful_without_db(tmp_path: Path):
    """Fehlende own_refs.db → keine Exception, own_coupling bleibt leer."""
    resources = {
        "authored_all": [],
        "key_terms": set(),
        "zotero_doi_index": {},
        "zotero_word_index": {},
        "own_refs_index": load_own_refs_index(tmp_path / "missing.db"),
        "corpus_freq": CorpusFreq(),
    }
    profile = derive_attention_profile(
        article_id="art-1",
        title="A cited article",
        authors=["Anon"],
        crossref_refs=[{"doi": "10.1/x"}],
        openalex_refs=["W001"],
        entry={"verdict": "ignorieren"},
        signal_resources=resources,
    )
    assert profile.deterministic_signals["own_coupling"] == {}
    assert profile.discourse_indicator == "kein_indikator"
    assert profile.selection_mode == "screening"
