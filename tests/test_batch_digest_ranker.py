"""Integrationstest: M-E-Ranker im Batch-Digest-Geldpfad (ohne LLM-Calls).

Verdrahtungs-Invarianten:
  - Konsens-Drop: Screening-ignorieren + Algo-drop → verdict ignorieren,
    Begründung nennt beide Stimmen.
  - Rescue: Screening-ignorieren + Algo-mid → Artikel geht doch zum Agent
    (recall-schützend, FN-Halbierung der Union).
  - Auto-Pass (Zitation/Trigger) bleibt vor allem anderen; Rest nach mc
    absteigend sortiert.
  - algo_mc/algo_zone werden persistiert (Nachkalibrierung, iter_48-Caveat).
  - Ranker.load()=None (keine Parameter) → Verhalten exakt wie bisher.

Screening und Agent sind gemockt — keine API-Kosten, keine Netz-Calls.
"""

from __future__ import annotations

import numpy as np

from journal_bot import batch_digest
from journal_bot.ranker import RankedArticle
from journal_bot.store import Store, StoredArticle


def _article(aid: str, title: str, refs=None) -> StoredArticle:
    return StoredArticle(
        id=aid, journal_short="TST", journal_full="Testjournal",
        title=title, abstract="Ein Abstract.", authors=["Autor X"],
        crossref_refs=refs or [],
    )


class _FakeRanker:
    def __init__(self, by_id: dict[str, RankedArticle]):
        self.by_id = by_id

    def score(self, sas, biblio_flags):
        return {sa.id: self.by_id[sa.id] for sa in sas if sa.id in self.by_id}


def _run(tmp_path, monkeypatch, *, with_ranker: bool):
    store = Store(path=tmp_path / "articles.db")
    arts = {
        "cite": _article("cite", "Zitiert Benjamin", refs=[{"doi": "10.1/x"}]),
        "kons": _article("kons", "Konsens-Drop-Kandidat"),
        "resc": _article("resc", "Rescue-Kandidat"),
        "keep": _article("keep", "Screening-Keeper"),
    }
    for sa in arts.values():
        store.upsert_article(sa)

    ranked = {
        "cite": RankedArticle("cite", 1.8, 0.8, "mid", True),
        "kons": RankedArticle("kons", 0.05, 0.05, "drop", False),
        "resc": RankedArticle("resc", 0.9, 0.7, "mid", False),
        "keep": RankedArticle("keep", 0.5, 0.5, "mid", False),
    }

    monkeypatch.setattr(batch_digest, "RANKER_ENABLED", True)
    monkeypatch.setattr(batch_digest, "TRIGGER_AUTHOR_PATTERNS", ())
    monkeypatch.setattr(
        batch_digest, "load_authored_all", lambda: [{"dummy": True}], raising=False
    )
    # Zitations-Hit nur für "cite" (→ Auto-Pass), Rest leer
    monkeypatch.setattr(
        batch_digest, "find_citations",
        lambda refs, authored: [{"pub_id": "p"}] if refs else [],
    )

    import journal_bot.ranker as ranker_mod
    if with_ranker:
        monkeypatch.setattr(
            ranker_mod.Ranker, "load", classmethod(lambda cls, **kw: _FakeRanker(ranked))
        )
        import journal_bot.signals as signals_mod
        monkeypatch.setattr(signals_mod, "load_signal_resources", lambda: {})
        monkeypatch.setattr(
            signals_mod, "signal_own_coupling", lambda *a, **kw: {}
        )
    else:
        monkeypatch.setattr(
            ranker_mod.Ranker, "load", classmethod(lambda cls, **kw: None)
        )

    # Screening: kons + resc raus, keep weiter
    def fake_screen(items, verbose=False):
        out = {}
        for it in items:
            drop = it["id"] in {"kons", "resc"}
            out[it["id"]] = {
                "verdict": "ignorieren" if drop else "weitergeben",
                "grund": "kein Bezug" if drop else "",
            }
        return out

    monkeypatch.setattr(batch_digest.agent_mod, "batch_screen", fake_screen)

    analyzed: list[str] = []

    def fake_process(sa, store_, verbose=True, model=None, mode="assess_verify"):
        analyzed.append(sa.id)
        return {"agent_result": {"est_cost_usd": 0.0, "entry": {"verdict": "scannen"}}}

    monkeypatch.setattr(batch_digest.digest, "process_article", fake_process)

    result = batch_digest.run_batch_digest(
        list(arts.values()), store, verbose=False, logger=None
    )
    return store, result, analyzed


def test_ranker_consensus_drop_rescue_and_sorting(tmp_path, monkeypatch):
    store, result, analyzed = _run(tmp_path, monkeypatch, with_ranker=True)

    assert result.ranker_active is True
    # Konsens-Drop: nur "kons" (beide Stimmen ignorieren)
    kons = store.get("kons")
    assert kons.agent_verdict == "ignorieren"
    assert "Konsens beider Stimmen" in kons.agent_entry["verdict_begruendung"]
    assert result.ranker_consensus_dropped == 1
    # Rescue: "resc" wurde trotz Screening-Drop analysiert
    assert result.ranker_rescued == 1
    assert "resc" in analyzed
    # Sortierung: Auto-Pass (cite) zuerst, dann mc absteigend (resc 0.9 > keep 0.5)
    assert analyzed == ["cite", "resc", "keep"]
    # Score-Persistenz für die Nachkalibrierung
    assert store.get("resc").algo_zone == "mid"
    assert abs(store.get("kons").algo_mc - 0.05) < 1e-9
    assert store.get("kons").algo_zone == "drop"


def test_without_params_behavior_unchanged(tmp_path, monkeypatch):
    store, result, analyzed = _run(tmp_path, monkeypatch, with_ranker=False)

    assert result.ranker_active is False
    assert result.ranker_rescued == 0
    # Beide Screening-Drops werden wie bisher verworfen
    assert store.get("kons").agent_verdict == "ignorieren"
    assert store.get("resc").agent_verdict == "ignorieren"
    assert "Konsens" not in store.get("resc").agent_entry["verdict_begruendung"]
    # Nur Auto-Pass + Screening-Keeper zum Agent, Original-Reihenfolge
    assert analyzed == ["cite", "keep"]
    assert store.get("keep").algo_mc is None
