"""Tests für `journal_bot.profile_form` — Aggregation mehrerer Werk-Fallgestalten
zur Profilform.

Synthetische Fallgestalt-Dicts (Form wie `fallgestalt.assemble_fallgestalt`:
meta/V/E), drei Werke über drei Jahre. Geprüft wird der relationale Kern
(Ko-Okkurrenz), die Zeit-Achse (shift, Perioden) und die Ehrlichkeit der
unscharfen Label-Zusammenführung (label_variants, fuzzy_matched_keys).
Pure functions, keine DB-/LLM-/Netz-Abhängigkeit.
"""

from __future__ import annotations

import json

from journal_bot.profile_form import (
    build_profile_form,
    load_fallgestalten,
    source_key,
    term_key,
)


# ── Fixtures: drei Werke, drei Jahre ──────────────────────────────────────


def _source_node(label: str, **props) -> dict:
    return {
        "id": f"source:{label}",
        "type": "source",
        "label": label,
        "props": props,
        "prov": "s",
    }


def _stance_edge(idx: int, label: str, kind: str) -> dict:
    sigma = "+" if kind in ("affirms", "extends") else "-"
    return {
        "id": f"edge-{idx}",
        "kind": "affirms" if kind in ("affirms", "extends") else "reserves",
        "from": "position:self",
        "to": f"source:{label}",
        "sigma": sigma,
        "anchors": [],
        "prov": "s",
        "internalKind": kind,
    }


def _term_node(label: str) -> dict:
    return {"id": f"term:{label}", "type": "term", "label": label, "props": {}, "prov": "s"}


def _coins_edge(idx: int, label: str) -> dict:
    return {
        "id": f"edge-{idx}",
        "kind": "coins",
        "from": "position:self",
        "to": f"term:{label}",
        "sigma": None,
        "anchors": [],
        "prov": "s",
        "internalKind": "coins",
    }


def _work(doc_id: str, year: str | None, title: str, sources, terms=()) -> dict:
    """sources = [(label, internalKind)], terms = [label]."""
    v: list[dict] = [
        {
            "id": "position:self",
            "type": "position",
            "label": f"Selbstverortung {title}",
            "props": {"goal": f"Selbstverortung {title}"},
            "prov": "s",
        }
    ]
    e: list[dict] = []
    for label, _ in sources:
        v.append(_source_node(label))
    for i, (label, kind) in enumerate(sources):
        e.append(_stance_edge(i, label, kind))
    for j, label in enumerate(terms):
        v.append(_term_node(label))
        e.append(_coins_edge(len(sources) + j, label))
    return {
        "meta": {
            "document_id": doc_id,
            "title": title,
            "authors": ["Jörissen, Benjamin"],
            "year": year,
            "venue": "Testband",
            "disc": None,
        },
        "V": v,
        "E": e,
    }


WORK_2019 = _work(
    "hash:aaa",
    "2019",
    "Frühes Werk",
    [("Brown (2015), *Resilience*", "affirms"), ("Barad (2007)", "affirms")],
    terms=["kulturelle Resilienz"],
)
WORK_2022 = _work(
    "hash:bbb",
    "2022",
    "Mittleres Werk",
    [("Brown 2015", "affirms"), ("Rancière (2002)", "extends")],
    terms=["kulturelle Resilienz", "planetarer Dissens"],
)
WORK_2025 = _work(
    "hash:ccc",
    "2025",
    "Spätes Werk",
    [("Brown, K. (2015)", "contrasts"), ("Barad (2007), *Meeting the Universe*", "extends")],
)

ALL_WORKS = [WORK_2019, WORK_2022, WORK_2025]


# ── Label-Normalisierung ──────────────────────────────────────────────────


class TestKeyNormalisierung:
    def test_author_year_key(self):
        assert source_key("Brown (2015), *Resilience, Development*") == "brown:2015"
        assert source_key("Brown 2015") == "brown:2015"
        assert source_key("source:Brown, K. (2015)") == "brown:2015"

    def test_diacritics_folded(self):
        assert source_key("Rancière (2002; 2008)") == "ranciere:2002"
        assert source_key("Ranciere 2002") == "ranciere:2002"

    def test_particle_kept_with_surname(self):
        assert source_key("van Dijk (2013)") == "van-dijk:2013"

    def test_without_year_surname_only(self):
        assert source_key("Foucault") == "foucault"

    def test_without_name_full_text(self):
        assert source_key("*** ---") == "?"

    def test_term_key_is_full_normalized_text(self):
        assert term_key("Planetary Dissensus") == "planetary dissensus"
        # Konservativ: Klammerzusatz trennt, statt still zusammenzuführen.
        assert term_key("Cultural Resilience (kulturelle Resilienz)") != term_key(
            "Cultural Resilience"
        )


# ── Substrat + Ko-Okkurrenz ───────────────────────────────────────────────


class TestSubstratUndKoOkkurrenz:
    def test_substrate_sorted_by_year_desc(self):
        p = build_profile_form(ALL_WORKS)
        assert [w["year"] for w in p["substrate"]["works"]] == [2025, 2022, 2019]
        assert p["substrate"]["n_works"] == 3
        assert p["substrate"]["years"] == [2019, 2022, 2025]
        assert p["substrate"]["year_span"] == [2019, 2025]
        assert p["substrate"]["works"][0]["authors"] == ["Jörissen, Benjamin"]

    def test_year_none_stays_out_of_time_axis(self):
        p = build_profile_form([_work("hash:x", None, "Ohne Jahr", [("Brown 2015", "affirms")])])
        assert p["substrate"]["years"] == []
        assert p["substrate"]["year_span"] is None
        assert p["periods"] == []
        # bleibt aber im Substrat und in den Quellen
        assert p["substrate"]["n_works"] == 1
        assert p["sources"][0]["key"] == "brown:2015"

    def test_cooccurrence_pairs_and_weights(self):
        p = build_profile_form(ALL_WORKS)
        net = {(c["a"], c["b"]): c for c in p["cooccurrence"]}
        # Brown+Barad in 2019 UND 2025 → weight 2, das stärkste Paar
        assert net[("barad:2007", "brown:2015")]["weight"] == 2
        assert sorted(net[("barad:2007", "brown:2015")]["works"]) == ["hash:aaa", "hash:ccc"]
        # Brown+Rancière nur 2022
        assert net[("brown:2015", "ranciere:2002")]["weight"] == 1
        # Barad+Rancière treten nie gemeinsam auf
        assert ("barad:2007", "ranciere:2002") not in net
        # sortiert nach weight absteigend
        assert p["cooccurrence"][0]["weight"] == 2

    def test_no_self_pairs_and_pairs_are_ordered(self):
        p = build_profile_form(ALL_WORKS)
        for c in p["cooccurrence"]:
            assert c["a"] < c["b"]
            assert c["weight"] >= 1


# ── Haltung, shift, label_variants ────────────────────────────────────────


class TestHaltungUndShift:
    def test_stance_counts_aggregated(self):
        p = build_profile_form(ALL_WORKS)
        brown = next(s for s in p["sources"] if s["key"] == "brown:2015")
        assert brown["n_works"] == 3
        assert brown["stance"] == {
            "affirms": 2,
            "extends": 0,
            "contrasts": 1,
            "reserves": 0,
            "rejects": 0,
        }
        assert brown["sigma"] == {"+": 2, "-": 1}
        assert brown["years"] == [2019, 2022, 2025]

    def test_shift_detected_across_years(self):
        p = build_profile_form(ALL_WORKS)
        brown = next(s for s in p["sources"] if s["key"] == "brown:2015")
        assert brown["shift"] == {
            "from": {"year": 2019, "stance": "affirms"},
            "to": {"year": 2025, "stance": "contrasts"},
        }

    def test_no_shift_when_stance_stable(self):
        p = build_profile_form(ALL_WORKS)
        # Barad: 2019 affirms, 2025 extends → das IST eine Verschiebung
        barad = next(s for s in p["sources"] if s["key"] == "barad:2007")
        assert barad["shift"]["from"]["stance"] == "affirms"
        assert barad["shift"]["to"]["stance"] == "extends"
        # Rancière kommt nur in einem Jahr vor → keine Verschiebung
        ranciere = next(s for s in p["sources"] if s["key"] == "ranciere:2002")
        assert ranciere["shift"] is None

    def test_label_variants_expose_the_fuzzy_merge(self):
        p = build_profile_form(ALL_WORKS)
        brown = next(s for s in p["sources"] if s["key"] == "brown:2015")
        assert sorted(brown["label_variants"]) == [
            "Brown (2015), *Resilience*",
            "Brown 2015",
            "Brown, K. (2015)",
        ]
        assert p["reliability"]["fuzzy_matched_keys"] >= 2  # Brown + Barad

    def test_own_work_flag(self):
        own = _work("hash:own", "2021", "Mit Selbstbezug", [])
        own["V"].append(
            {
                "id": "own:0",
                "type": "source",
                "label": "Jörissen & Klepacki (2021)",
                "props": {"ownWork": True},
                "prov": "s",
            }
        )
        own["E"].append(
            {
                "id": "edge-0",
                "kind": "trajectory",
                "from": "position:self",
                "to": "own:0",
                "sigma": None,
                "anchors": [],
                "prov": "s",
                "internalKind": "trajectory",
            }
        )
        p = build_profile_form([own])
        entry = next(s for s in p["sources"] if s["key"] == "jorissen:2021")
        assert entry["own_work"] is True
        # trajectory ist keine Haltung → kein stance-Zähler
        assert sum(entry["stance"].values()) == 0


# ── Begriffe + Selbstverortungen ──────────────────────────────────────────


class TestBegriffeUndSelbstverortung:
    def test_terms_with_year_span(self):
        p = build_profile_form(ALL_WORKS)
        kr = next(t for t in p["terms"] if t["key"] == "kulturelle resilienz")
        assert kr["n_works"] == 2
        assert kr["first_year"] == 2019
        assert kr["last_year"] == 2022
        assert sorted(kr["works"]) == ["hash:aaa", "hash:bbb"]

    def test_self_positions_chronological_one_per_work(self):
        p = build_profile_form(ALL_WORKS)
        assert [s["year"] for s in p["self_positions"]] == [2019, 2022, 2025]
        assert p["self_positions"][0]["label"] == "Selbstverortung Frühes Werk"


# ── Perioden ──────────────────────────────────────────────────────────────


class TestPerioden:
    def test_period_blocks_aligned_to_span_without_empty_blocks(self):
        p = build_profile_form(ALL_WORKS, period_size=4)
        # Spanne 2019–2025, Blöcke ab 2019: [2019–2022], [2023–2026]
        assert [pd["label"] for pd in p["periods"]] == ["2019–2022", "2025"]
        assert p["periods"][0]["years"] == [2019, 2022]
        assert p["periods"][0]["n_works"] == 2
        assert p["periods"][1]["n_works"] == 1

    def test_period_size_one_gives_one_period_per_year(self):
        p = build_profile_form(ALL_WORKS, period_size=1)
        assert [pd["label"] for pd in p["periods"]] == ["2019", "2022", "2025"]

    def test_new_and_dropped_sources_are_diff_to_previous_period(self):
        p = build_profile_form(ALL_WORKS, period_size=4)
        first, second = p["periods"]
        # erste Periode hat keine Vorgängerin
        assert first["new_sources"] == []
        assert first["dropped_sources"] == []
        assert first["new_terms"] == []
        # 2025: Barad kehrt zurück (in Periode 1 vorhanden), Rancière fällt weg
        assert second["new_sources"] == []
        assert second["dropped_sources"] == ["ranciere:2002"]

    def test_period_dominant_stance(self):
        p = build_profile_form(ALL_WORKS, period_size=4)
        second = p["periods"][1]
        brown = next(s for s in second["sources"] if s["key"] == "brown:2015")
        assert brown["stance_dominant"] == "contrasts"

    def test_single_year_gives_no_periods(self):
        p = build_profile_form([WORK_2019])
        assert p["periods"] == []


# ── Laden + Verlässlichkeit ───────────────────────────────────────────────


class TestLadenUndVerlaesslichkeit:
    def test_broken_and_foreign_files_are_skipped_not_raised(self, tmp_path):
        (tmp_path / "gut.json").write_text(json.dumps(WORK_2019), encoding="utf-8")
        (tmp_path / "kaputt.json").write_text("{ das ist kein JSON", encoding="utf-8")
        (tmp_path / "fremd.json").write_text(json.dumps({"hallo": "welt"}), encoding="utf-8")

        loaded = load_fallgestalten(tmp_path)
        assert len(loaded) == 1
        assert loaded[0]["meta"]["document_id"] == "hash:aaa"
        assert len(loaded.skipped) == 2
        assert any("kaputt.json" in s for s in loaded.skipped)
        assert any("fremd.json" in s for s in loaded.skipped)

        p = build_profile_form(loaded)
        assert len(p["reliability"]["skipped_files"]) == 2
        assert p["substrate"]["n_works"] == 1

    def test_missing_path_is_reported_not_raised(self, tmp_path):
        loaded = load_fallgestalten(tmp_path / "gibtsnicht.json")
        assert list(loaded) == []
        assert any("nicht gefunden" in s for s in loaded.skipped)

    def test_explicit_path_list(self, tmp_path):
        a = tmp_path / "a.json"
        b = tmp_path / "b.json"
        a.write_text(json.dumps(WORK_2019), encoding="utf-8")
        b.write_text(json.dumps(WORK_2022), encoding="utf-8")
        loaded = load_fallgestalten([a, str(b)])
        assert len(loaded) == 2

    def test_plain_list_input_needs_no_skipped_attribute(self):
        p = build_profile_form(ALL_WORKS)
        assert p["reliability"]["skipped_files"] == []

    def test_beleg_failures_counted_from_node_props(self):
        work = _work("hash:bf", "2020", "Mit Belegfehlern", [("Brown 2015", "affirms")])
        work["V"][1]["props"]["belegVerified"] = False
        work["V"][0]["props"]["belegVerified"] = False
        p = build_profile_form([work])
        assert p["substrate"]["works"][0]["beleg_failures"] == 2
        assert p["reliability"]["total_beleg_failures"] == 2
        assert p["reliability"]["works_with_beleg_failures"] == 1

    def test_empty_input(self):
        p = build_profile_form([])
        assert p["substrate"]["n_works"] == 0
        assert p["sources"] == []
        assert p["cooccurrence"] == []
        assert p["periods"] == []
        assert p["substrate"]["year_span"] is None
