"""Tests für `journal_bot.fallgestalt` — parse_profile-Zeilen-Grammatik
(Härtung 2026-07-10: keine stillen Drops) und Verbatim-BELEG-Gate.

Spiegelt 1:1 den Verhaltens-Vertrag aus SARAHs
src/lib/server/ai/h7/profile-parse.test.ts (10 Fälle, siehe Docstrings der
einzelnen Testmethoden — die Nummerierung folgt der dortigen Reihenfolge).
Pure functions, keine DB-/LLM-/Netz-Abhängigkeit.
"""

from __future__ import annotations

from journal_bot.fallgestalt import normalize_for_beleg_match, parse_profile, verify_belege

# Leere Topologie (analog SARAHs Test-Fixture `topo` mit sources: []) — für die
# Parser-Grammatik-Tests irrelevant, nur für die Quellen-Anreicherung gebraucht.
EMPTY_TOPOLOGY: dict = {}


def _block(lines: list[str]) -> str:
    return "\n".join(lines)


class TestParseProfileLenientGrammar:
    """Spiegelt SARAHs describe('parseProfile — tolerante Zeilen-Grammatik')."""

    def test_list_marker_and_markdown_emphasis_parsed(self):
        """(1) Quellen-Zeilen mit führendem Listenzeichen + Markdown-Emphasis geparst."""
        raw = _block(
            [
                "**[QUELLEN]**",
                "- QUELLE: Brown 2015 | RELATION: extends | ADRESSE: Resilienz-Grundlage | BELEG: «resilience should be understood»",
                "* **QUELLE:** Haraway 2016 | RELATION: affirms | BELEG: «staying with the trouble»",
            ]
        )
        p = parse_profile(raw, EMPTY_TOPOLOGY)
        labels = [n["label"] for n in p.nodes if n["nodeType"] == "source"]
        assert labels == ["Brown 2015", "Haraway 2016"]
        assert [e["edgeKind"] for e in p.edges] == ["extends", "affirms"]

    def test_relation_with_qualifier_normalizes_to_known_vocab(self):
        """(2) RELATION mit Zusatz „affirms (mit Vorbehalt)" → affirms, unparsed leer."""
        raw = _block(
            [
                "[QUELLEN]",
                "QUELLE: Sennett 2000 | RELATION: affirms (mit Vorbehalt) | BELEG: «der flexible mensch»",
            ]
        )
        p = parse_profile(raw, EMPTY_TOPOLOGY)
        assert len(p.edges) == 1
        assert p.edges[0]["edgeKind"] == "affirms"
        assert len(p.unparsed) == 0

    def test_multiple_relation_mentions_take_first_in_text_order(self):
        """(3) Mehrfachnennung „contrasts, stellenweise extends" → contrasts."""
        raw = _block(
            [
                "[QUELLEN]",
                "QUELLE: X | RELATION: contrasts, stellenweise extends | BELEG: «zwölf zeichen mindestens hier»",
            ]
        )
        p = parse_profile(raw, EMPTY_TOPOLOGY)
        assert p.edges[0]["edgeKind"] == "contrasts"

    def test_line_without_key_form_goes_to_unparsed(self):
        """(4) Präambel-Zeile → unparsed statt still weg."""
        raw = _block(
            [
                "Hier ist das diskursive Profil:",
                "[QUELLEN]",
                "QUELLE: A | RELATION: affirms | BELEG: «beleg beleg beleg»",
            ]
        )
        p = parse_profile(raw, EMPTY_TOPOLOGY)
        assert "Hier ist das diskursive Profil:" in p.unparsed
        assert any(n["label"] == "A" for n in p.nodes)

    def test_unknown_relation_vocab_leaves_source_unparsed(self):
        """(5) unbekanntes Relations-Vokabular → Quelle nicht angelegt + Zeile in unparsed."""
        raw = _block(["[QUELLEN]", "QUELLE: B | RELATION: bewundert | BELEG: «x»"])
        p = parse_profile(raw, EMPTY_TOPOLOGY)
        assert len([n for n in p.nodes if n["nodeType"] == "source"]) == 0
        assert len(p.unparsed) == 1


FULL_TEXT = (
    "Das resiliente Subjekt bleibt – wie Sennett zeigt – prekär. "
    "Following Brown, resilience should be understood as a property of individuals."
)


class TestVerifyBelegeGate:
    """Spiegelt SARAHs describe('verifyBelege — Verbatim-Gate gegen den Volltext')."""

    def test_verifies_across_glyph_variants(self):
        """(6) Glyphen-Varianten (Striche/Anführung/Doppelspaces) verifizieren."""
        raw = _block(
            [
                "[QUELLEN]",
                "QUELLE: Sennett | RELATION: contrasts | BELEG: «Das resiliente  Subjekt bleibt — wie Sennett zeigt — prekär»",
            ]
        )
        p = parse_profile(raw, EMPTY_TOPOLOGY)
        g = verify_belege(p, FULL_TEXT)
        assert g.failed == 0
        assert "belegVerified" not in p.nodes[0]["properties"]

    def test_confabulated_beleg_marks_node_and_edge_counts_once(self):
        """(7) konfabulierter Beleg markiert Knoten UND Kante mit
        belegVerified=False und zählt genau einmal."""
        raw = _block(
            [
                "[QUELLEN]",
                "QUELLE: Erfunden | RELATION: affirms | BELEG: «dieser satz steht nirgends im volltext»",
            ]
        )
        p = parse_profile(raw, EMPTY_TOPOLOGY)
        g = verify_belege(p, FULL_TEXT)
        assert g.failed == 1
        assert "Erfunden" in g.failures[0]["where"]
        assert p.nodes[0]["properties"]["belegVerified"] is False
        assert p.edges[0]["properties"]["belegVerified"] is False

    def test_multi_quote_beleg_checked_piecewise_guillemet_split(self):
        """(10, SARAH-Nachzug 7308ad9) Mehrfach-Zitate in einem BELEG-Feld
        stückweise geprüft (Guillemet-Split). Realfall MiMo/JK26: zwei
        wörtliche Zitate, mit »sowie« verkettet — die Verkettung steht so
        nicht im Text, die Stücke schon."""
        text = (
            "Sustainability has to be understood within a broader, culturally sensitized framework. "
            "Das resiliente Subjekt bleibt – wie Sennett zeigt – prekär."
        )
        raw = _block(
            [
                "[SELBSTPOSITION]",
                "ZIEL: Verankerung | BELEG: «sustainability has to be understood within a broader, "
                "culturally sensitized framework» sowie «Das resiliente Subjekt bleibt — wie Sennett zeigt — prekär»",
            ]
        )
        p = parse_profile(raw, EMPTY_TOPOLOGY)
        g = verify_belege(p, text)
        assert g.failed == 0

    def test_ellipsis_beleg_checked_piecewise_ignores_short_pieces(self):
        """(8) Ellipsen-Beleg stückweise geprüft + unprüfbar kurze Stücke ignoriert."""
        raw = _block(
            [
                "[QUELLEN]",
                "QUELLE: Brown | RELATION: extends | BELEG: «Following Brown, resilience […] prekär»",
            ]
        )
        p = parse_profile(raw, EMPTY_TOPOLOGY)
        g = verify_belege(p, FULL_TEXT)
        assert g.failed == 0

    def test_normalize_for_beleg_match_unifies_quotes_dashes_whitespace(self):
        """(9) normalize-Gleichheiten: „Wort — Wort" → "wort - wort";
        "  L'essai  –  Test " → "lessai - test"."""
        assert normalize_for_beleg_match("„Wort — Wort“") == "wort - wort"
        assert normalize_for_beleg_match("  L'essai  –  Test ") == "lessai - test"
