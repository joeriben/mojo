"""Tests für die Themen-Trajektorien-Fähigkeit (corpus_explore.trajectories).

Kern der Disziplin (docs/mojo2_korpus_exploration_goal.md): die
Within-Journal-Dekomposition ist der EINZIGE Befund-Pfad. Der Test konstruiert
einen Kompositions-Confound — ein Journal, das spät stark wächst und ein Topic
fast durchgängig trägt — und prüft, dass:

  * der Befund (within-Δ) für dieses Topic FLACH bleibt (within-journal ändert
    sich nichts), während
  * der bloße Korpus-Anteil (Komp-Δ, KEIN Befund) massiv ausschlägt.

Dazu: ein Topic mit echtem Within-Journal-Anstieg wird als Aufsteiger erkannt,
und das Panel enthält nur in beiden Fenstern hinreichend belegte Journals.

Schnelle Tests: synthetische articles.db in tmp_path, kein Netz, kein LLM.
"""
from __future__ import annotations

import json
from pathlib import Path

from journal_bot.corpus_explore.coupling import (
    compute_coupling_communities,
    render_report as render_coupling_report,
)
from journal_bot.corpus_explore.trajectories import (
    TrajectoryResult,
    _topic_names,
    compute_trajectories,
)
from journal_bot.store import Store, StoredArticle


# ----- Helpers --------------------------------------------------------------


def _topics(*names: str) -> list[dict]:
    return [{"name": n, "score": 0.9} for n in names]


def _add(store: Store, n: int, *, journal: str, year: int, topics: list[dict], tag: str) -> None:
    for i in range(n):
        store.upsert_article(
            StoredArticle(
                id=f"{tag}-{i}",
                journal_short=journal,
                journal_full=journal.upper(),
                title=f"{tag}-{i}",
                year=year,
                openalex_topics=topics,
            )
        )


def _find(result: TrajectoryResult, name: str):
    for r in result.risers + result.fallers:
        if r.name == name:
            return r
    raise AssertionError(f"Topic '{name}' nicht im Ergebnis")


def _build_confounded_store(tmp_path: Path) -> Store:
    """Korpus mit (a) Kompositions-Confound, (b) echtem Within-Anstieg, (c) Panel-Gate."""
    store = Store(path=tmp_path / "articles.db")

    # AIJ: Volumen-Explosion 5 -> 40, Topic T_comp in JEDEM Artikel beider Fenster.
    # within-journal flach (100% -> 100%), aber zieht den Korpus-Anteil hoch.
    _add(store, 5, journal="AIJ", year=2016, topics=_topics("T_comp"), tag="aij-e")
    _add(store, 40, journal="AIJ", year=2022, topics=_topics("T_comp"), tag="aij-l")

    # J1, J2: echter Within-Anstieg von U_real; Rest Filler-Topic F.
    _add(store, 1, journal="J1", year=2016, topics=_topics("U_real"), tag="j1-e-u")
    _add(store, 9, journal="J1", year=2016, topics=_topics("F"), tag="j1-e-f")
    _add(store, 8, journal="J1", year=2022, topics=_topics("U_real"), tag="j1-l-u")
    _add(store, 2, journal="J1", year=2022, topics=_topics("F"), tag="j1-l-f")

    _add(store, 2, journal="J2", year=2016, topics=_topics("U_real"), tag="j2-e-u")
    _add(store, 8, journal="J2", year=2016, topics=_topics("F"), tag="j2-e-f")
    _add(store, 9, journal="J2", year=2022, topics=_topics("U_real"), tag="j2-l-u")
    _add(store, 1, journal="J2", year=2022, topics=_topics("F"), tag="j2-l-f")

    # J3: Panel-Journal ohne U_real-Bewegung (verdünnt, kippt den Befund aber nicht).
    _add(store, 8, journal="J3", year=2016, topics=_topics("F"), tag="j3-e")
    _add(store, 8, journal="J3", year=2022, topics=_topics("F"), tag="j3-l")

    # J4: früh zu dünn (2 < min_journal) -> darf NICHT ins Panel, obwohl spät U_real-stark.
    _add(store, 2, journal="J4", year=2016, topics=_topics("F"), tag="j4-e")
    _add(store, 10, journal="J4", year=2022, topics=_topics("U_real"), tag="j4-l")

    return store


_KW = dict(
    early=(2016, 2017), late=(2022, 2023),
    score_min=0.5, min_journal=5, min_panel=2, min_total=4, top_n=10,
)


# ----- Tests ----------------------------------------------------------------


def test_topic_names_tolerant_parse():
    raw = [
        {"name": "A", "score": 0.9},
        {"name": "B", "score": 0.3},          # unter Schwelle
        {"display_name": "C", "score": 0.6},  # display_name-Fallback
        {"name": "A", "score": 0.7},          # Dublette
        "garbage",                            # kein dict
        {"name": "", "score": 0.9},           # leerer Name
    ]
    assert _topic_names(raw, 0.5) == ["A", "C"]
    assert _topic_names(None, 0.5) == []
    assert _topic_names([], 0.5) == []


def test_panel_excludes_journal_thin_in_one_window(tmp_path):
    result = compute_trajectories(_build_confounded_store(tmp_path), **_KW)
    # J4 ist spät groß, aber früh zu dünn -> nicht im balancierten Panel.
    assert "J4" not in result.panel
    assert set(result.panel) == {"AIJ", "J1", "J2", "J3"}


def test_composition_confound_is_not_a_finding(tmp_path):
    """T_comp: within-journal flach, aber Korpus-Anteil explodiert -> kein Befund."""
    result = compute_trajectories(_build_confounded_store(tmp_path), **_KW)
    t = _find(result, "T_comp")
    # Befund (within-Δ) flach — kein einziges Panel-Journal bewegt sich.
    assert abs(t.within_delta) < 1e-9
    # Kontrast (Korpus-Anteil) schlägt massiv aus: 5/35 -> 40/78 = +37 pp.
    assert t.composition_delta > 0.35
    # Genau die Lücke, die die Disziplin sichtbar macht: Komposition, nicht Diffusion.
    assert t.composition_delta - t.within_delta > 0.35


def test_real_within_journal_rise_is_found(tmp_path):
    """U_real: steigt INNERHALB J1/J2 -> positiver Befund, über T_comp gerankt."""
    result = compute_trajectories(_build_confounded_store(tmp_path), **_KW)
    u = _find(result, "U_real")
    t = _find(result, "T_comp")
    # gleichgew. Panel-Mittel: (0 + 0.70 + 0.70 + 0)/4 = 0.35
    assert u.within_delta > 0.30
    assert u.within_delta > t.within_delta
    # U_real ist ein Aufsteiger (oberste Liste, nach within-Δ sortiert).
    assert any(r.name == "U_real" for r in result.risers)


def test_render_report_marks_befund_vs_kontrast(tmp_path):
    from journal_bot.corpus_explore.trajectories import render_report

    result = compute_trajectories(_build_confounded_store(tmp_path), **_KW)
    report = render_report(result)
    assert "within-Δ" in report and "Kontrast" in report
    assert "Konditionierung" in report          # Watchlist-Vorbehalt steht drin
    assert "neutrale Feld-Wahrheit" in report


# ===== Bibliografische Kopplungs-Communities (corpus_explore.coupling) =======
#
# Disziplin: die Kopplung ist GEERDET — eine Kante entsteht nur durch belegte
# geteilte Zitation, nie durch Ähnlichkeit. Der synthetische Korpus prüft, dass
#   * zwei Gruppen mit disjunkter Referenzbasis sauber getrennt werden,
#   * eine vielzitierte „Stoppwort"-Referenz (df > max_df) NICHT brückt,
#   * eine einzige geteilte Referenz (< min_shared) keine Kante macht,
#   * die Diskursraum-Verankerung cross-field korrekt erkennt,
#   * das Verfahren deterministisch ist.


def _add_coup(store: Store, aid: str, *, journal: str, year: int, refs: list[str]) -> None:
    store.upsert_article(StoredArticle(
        id=aid, journal_short=journal, journal_full=journal, title=aid,
        year=year, openalex_refs=list(refs),
    ))


def _write_discourse(tmp_path: Path) -> Path:
    """Hermetisches diskursraeume.json: JA1→alpha, JA2→beta, JB1/JC1→gamma."""
    p = tmp_path / "diskursraeume.json"
    p.write_text(json.dumps({
        "discourse_spaces": {
            "alpha": {"name": "Alpha"}, "beta": {"name": "Beta"}, "gamma": {"name": "Gamma"},
        },
        "journal_clusters": {
            "JA1": ["alpha"], "JA2": ["beta"], "JB1": ["gamma"], "JC1": ["gamma"],
        },
    }), encoding="utf-8")
    return p


def _build_coupling_store(tmp_path: Path) -> Store:
    """Zwei ref-disjunkte Gruppen + universelles Stoppwort WU + Einzel-Share C1.

    df über 13 ref-tragende Artikel: WA1=7 (>max_df, gekappt), WA2/WA3=6,
    WB1/WB2/WB3=6 (alle gekappt-tauglich), WU=12 (>max_df, gekappt). Damit:
    Gruppe A koppelt über {WA2,WA3} (2 ≥ min_shared), Gruppe B über {WB1,WB2,WB3};
    A↔B teilen nur WU (gekappt) → keine Brücke; C1 teilt nur WA1 (gekappt) → isoliert.
    """
    store = Store(path=tmp_path / "articles.db")
    for i in range(3):  # Gruppe A, Hälfte in JA1 (alpha)
        _add_coup(store, f"A-ja1-{i}", journal="JA1", year=2020,
                  refs=["WA1", "WA2", "WA3", "WU", f"WUA-{i}"])
    for i in range(3):  # Gruppe A, Hälfte in JA2 (beta) → spannt 2 Räume
        _add_coup(store, f"A-ja2-{i}", journal="JA2", year=2020,
                  refs=["WA1", "WA2", "WA3", "WU", f"WUA-{3 + i}"])
    for i in range(6):  # Gruppe B, alle in JB1 (gamma) → ein Raum
        _add_coup(store, f"B-{i}", journal="JB1", year=2018,
                  refs=["WB1", "WB2", "WB3", "WU", f"WUB-{i}"])
    # C1 teilt GENAU EINE (gekappte) Referenz mit A → darf keine Kante bekommen.
    _add_coup(store, "C1", journal="JC1", year=2019, refs=["WA1", "WC-x", "WC-y"])
    return store


_COUP_KW = dict(min_df=2, max_df=6, min_shared=2, resolution=1.0, seed=42,
                min_community=3, top_refs=8)

_GROUP_A = frozenset({f"A-ja1-{i}" for i in range(3)} | {f"A-ja2-{i}" for i in range(3)})
_GROUP_B = frozenset({f"B-{i}" for i in range(6)})


def test_coupling_separates_shared_reference_groups(tmp_path):
    res = compute_coupling_communities(
        _build_coupling_store(tmp_path), discourse_path=_write_discourse(tmp_path), **_COUP_KW
    )
    assert len(res.communities) == 2
    parts = {frozenset(c.article_ids) for c in res.communities}
    assert parts == {_GROUP_A, _GROUP_B}


def test_single_shared_reference_makes_no_edge(tmp_path):
    """C1 teilt nur 1 (gekappte) Referenz → unter min_shared → isoliert, kein Cluster."""
    res = compute_coupling_communities(
        _build_coupling_store(tmp_path), discourse_path=_write_discourse(tmp_path), **_COUP_KW
    )
    all_ids = {i for c in res.communities for i in c.article_ids}
    assert "C1" not in all_ids


def test_stopword_reference_does_not_bridge(tmp_path):
    """WU wird von allen A+B zitiert (df > max_df) → gekappt, koppelt A und B NICHT."""
    res = compute_coupling_communities(
        _build_coupling_store(tmp_path), discourse_path=_write_discourse(tmp_path), **_COUP_KW
    )
    assert len(res.communities) == 2          # trotz gemeinsamem WU getrennt
    # WU taucht ehrlich in der Referenzbasis auf (korpusweit 12×), aber als Brücke gekappt.
    base = {b.ref_id: b for c in res.communities for b in c.intellectual_base}
    assert "WU" in base and base["WU"].global_df == 12


def test_cross_field_flag_from_discourse_anchoring(tmp_path):
    res = compute_coupling_communities(
        _build_coupling_store(tmp_path), discourse_path=_write_discourse(tmp_path), **_COUP_KW
    )
    by = {frozenset(c.article_ids): c for c in res.communities}
    assert by[_GROUP_A].cross_field is True    # alpha 50% + beta 50% → 2 thematische Räume
    assert by[_GROUP_B].cross_field is False   # gamma 100% → ein Raum


def test_coupling_is_deterministic(tmp_path):
    store = _build_coupling_store(tmp_path)
    dp = _write_discourse(tmp_path)
    r1 = compute_coupling_communities(store, discourse_path=dp, **_COUP_KW)
    r2 = compute_coupling_communities(store, discourse_path=dp, **_COUP_KW)
    assert {frozenset(c.article_ids) for c in r1.communities} == \
           {frozenset(c.article_ids) for c in r2.communities}
    assert r1.modularity == r2.modularity


def test_coupling_report_carries_conditioning_and_grounding(tmp_path):
    res = compute_coupling_communities(
        _build_coupling_store(tmp_path), discourse_path=_write_discourse(tmp_path), **_COUP_KW
    )
    rep = render_coupling_report(res)
    assert "Konditionierung" in rep
    assert "neutrale Feld-Struktur" in rep          # Watchlist-Vorbehalt
    assert "dasselbe Werk zitieren" in rep          # Erdung explizit benannt
