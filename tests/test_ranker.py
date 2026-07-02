"""Tests für den M-E-Keep-Ranker (journal_bot.ranker) + Wochenlauf-Politik.

Invarianten (aus der 50er-Serie):
  - Formel iter_46: mc = z(z(rich) + 0.5·z(max(0, pj−G))), Biblio-Veto 1+mc,
    z = Min-Max mit EINGEFRORENEN Parametern (Clipping statt Auslaufen).
  - Der Ranker entscheidet nie allein: Drop nur im Konsens mit dem Screening
    (combine_votes), Dissens wird recall-schützend behalten; kein Urteil ohne
    Abstract (iter_49); Biblio-Anker sind nie droppbar.
  - Fehlende Parameter-Datei → Ranker.load() = None (transparente Degradation).

Offline: Encoder wird gemockt, kein Modell-Load, keine Netz-Calls.
"""

from __future__ import annotations

import numpy as np

from journal_bot import ranker as rk
from journal_bot.batch_digest import _combine_screen_with_ranker
from journal_bot.ranker import RankedArticle, Ranker, eb_journal_prior, _z
from journal_bot.store import StoredArticle


def _article(aid: str, journal: str = "AAA", abstract: str = "Text.", **over):
    base = dict(
        id=aid, journal_short=journal, journal_full=journal,
        title=f"Artikel {aid}", abstract=abstract,
    )
    base.update(over)
    return StoredArticle(**base)


PARAMS = {
    "z": {"rich_min": 0.0, "rich_max": 1.0, "lift_max": 0.1,
          "mc_min": 0.0, "mc_max": 1.5},
    "t_lo": 0.25,
    "journal_prior": {"HOT": 0.5},
    "global_keep_rate": 0.4,
}


def _ranker_with_rich(rich_values: list[float]) -> Ranker:
    r = Ranker(PARAMS, pub_emb=np.eye(2, dtype="float32"))
    r.rich_sims = lambda sas: np.array(rich_values, dtype="float32")
    return r


# ------------------------------------------------------------ Bausteine ------


def test_z_is_minmax_with_clipping():
    assert abs(_z(0.5, 0.0, 1.0) - 0.5) < 1e-6
    assert _z(-3.0, 0.0, 1.0) == 0.0   # unterhalb des Gold-Rahmens
    assert _z(9.0, 0.0, 1.0) == 1.0    # oberhalb


def test_eb_journal_prior_shrinks_thin_journals():
    # Journal A: 2/2 keep, aber nur n=2 → stark zur Globalrate gezogen
    pairs = [("A", 1), ("A", 1)] + [("B", 0)] * 8
    prior, g = eb_journal_prior(pairs, k=5)
    assert abs(g - 0.2) < 1e-9
    # A: (2 + 0.2·5)/(2+5) = 3/7 ≈ 0.4286 — weit unter roh 1.0
    assert abs(prior["A"] - 3 / 7) < 1e-6
    # B: (0 + 1)/(8+5) ≈ 0.0769 — leicht über roh 0.0
    assert abs(prior["B"] - 1 / 13) < 1e-6


# ---------------------------------------------------------------- Zonen ------


def test_score_formula_and_zones():
    arts = [
        _article("low"),                    # rich 0.05 → unter t_lo → drop-Stimme
        _article("mid"),                    # rich 0.60 → Mittelband
        _article("hot", journal="HOT"),     # Prior-Lift hebt zusätzlich
    ]
    r = _ranker_with_rich([0.05, 0.60, 0.60])
    out = r.score(arts, biblio_flags={})
    assert out["low"].zone == "drop"
    assert out["mid"].zone == "mid"
    # Prior-Lift: HOT (pj=0.5, G=0.4 → lift 0.1 = lift_max → +0.5 vor mc-z)
    assert out["hot"].mc > out["mid"].mc
    # Formel-Nachrechnung für "mid": z(0.6) + 0.5·z(0) = 0.6 → /1.5 = 0.4
    assert abs(out["mid"].mc - 0.4) < 1e-6


def test_biblio_veto_lifts_above_one_and_never_drops():
    arts = [_article("a")]
    r = _ranker_with_rich([0.0])  # ohne Veto wäre das ein sicherer Drop
    out = r.score(arts, biblio_flags={"a": True})
    assert out["a"].biblio is True
    assert out["a"].mc >= 1.0
    assert out["a"].zone == "mid"


def test_no_abstract_never_judged_on_metadata():
    arts = [_article("a", abstract="", openalex_abstract="")]
    r = _ranker_with_rich([0.0])
    out = r.score(arts, biblio_flags={})
    assert out["a"].zone == "no_abstract"  # iter_49: 0.532-AUC = Rauschen


def test_load_returns_none_without_params(tmp_path):
    assert Ranker.load(
        params_path=tmp_path / "missing.json",
        summaries_path=tmp_path / "missing_summaries.json",
    ) is None


def test_rich_sims_uses_max_cosine(monkeypatch):
    # Zwei Eigenwerk-Vektoren; Artikel-Vektor liegt auf dem zweiten
    pub = np.array([[1.0, 0.0], [0.0, 1.0]], dtype="float32")
    monkeypatch.setattr(
        rk, "_encode_normed",
        lambda texts: np.array([[0.0, 1.0]] * len(texts), dtype="float32"),
    )
    r = Ranker(PARAMS, pub_emb=pub)
    sims = r.rich_sims([_article("a")])
    assert abs(float(sims[0]) - 1.0) < 1e-6


# ------------------------------------------- Konsens-Politik (Wochenlauf) ----


def test_screen_drop_needs_ranker_consensus():
    dropped = [_article("d1"), _article("d2"), _article("d3")]
    ranked = {
        "d1": RankedArticle("d1", 0.1, 0.1, "drop", False),   # Konsens → weg
        "d2": RankedArticle("d2", 0.7, 0.6, "mid", False),    # Dissens → Rescue
        # d3 ohne Algo-Stimme → Screening entscheidet (wie bisher)
    }
    consensus, rescued = _combine_screen_with_ranker(dropped, ranked)
    assert [sa.id for sa in consensus] == ["d1", "d3"]
    assert [sa.id for sa in rescued] == ["d2"]


def test_without_ranker_policy_is_unchanged():
    dropped = [_article("d1")]
    consensus, rescued = _combine_screen_with_ranker(dropped, {})
    assert consensus == dropped and rescued == []
