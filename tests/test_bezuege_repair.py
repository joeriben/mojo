"""bezuege-Repair-Kaskade (agent._coerce_bezuege) — GLM-5.2-Härtung.

Fixtures: die 3 REALEN defekten bezuege-Strings aus dem A/B-Lauf 2026-07-10
(tests/fixtures_bezuege_glm52.json, extrahiert aus
scripts/out/glm52_vs_gemini_ab_2026-07-10.json). GLM-5.2 serialisierte das
bezuege-Array als JSON-String, dessen Inneres an unescapeten deutschen
Anführungszeichen („…" mit ASCII-Quote als Schlusszeichen) bricht.

Invarianten (Sichtbarkeits-Prinzip, feedback_hardening_must_expose_not_hide):
  - Jeder Repair markiert das Entry (`bezuege_repaired` + Methode) und
    liefert Repair-Info zurück — nie stilles Glätten.
  - Nicht Parsebares wird NICHT verworfen, sondern landet roh in
    `bezuege_unparsed`.
  - Valide Arrays bleiben byte-identisch unangetastet (Gemini-Regression:
    0/20 Defekte dürfen 0/20 Marker bleiben).
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from journal_bot.agent import _coerce_bezuege, render_markdown

FIXTURES = json.loads(
    (Path(__file__).parent / "fixtures_bezuege_glm52.json").read_text(encoding="utf-8")
)["fixtures"]


# ------------------------------------------------------- reale GLM-Fixtures --


def test_all_three_real_glm_fixtures_unpack_or_stay_visible():
    """Jede der 3 realen Payloads wird entweder korrekt entpackt oder bleibt
    sichtbar als Roh-String erhalten — nichts verschwindet."""
    assert len(FIXTURES) == 3
    for fx in FIXTURES:
        entry = {"bezuege": fx["raw_bezuege"], "verdict": "lesenswert"}
        info = _coerce_bezuege(entry)
        assert info is not None, fx["article_id"]
        assert entry.get("bezuege_repaired") is True
        if entry.get("bezuege_unparsed"):
            # Sichtbar erhalten, nicht verworfen
            assert entry["bezuege_unparsed"] == fx["raw_bezuege"]
            assert entry["bezuege"] == []
        else:
            # Korrekt entpackt: list of dicts mit den Pflichtfeldern
            assert isinstance(entry["bezuege"], list) and entry["bezuege"]
            for b in entry["bezuege"]:
                assert isinstance(b, dict)
                assert b.get("pub_id")
                assert b.get("bezug")
                assert b.get("relation")


def test_real_glm_fixtures_actually_unpack_via_quote_escape():
    """Die 3 realen Payloads sind mit der Quote-Escape-Stufe vollständig
    entpackbar (nicht bloß als unparsed geparkt) — das ist der Kern der
    Kaskade. Bricht dieser Test, hat sich die Defekt-Signatur geändert."""
    for fx in FIXTURES:
        entry = {"bezuege": fx["raw_bezuege"]}
        info = _coerce_bezuege(entry)
        assert info["method"] == "quote_escape_json_loads", (
            fx["article_id"], info["method"])
        assert "bezuege_unparsed" not in entry
        # Inhalt: deutsche Anführungszeichen-Passagen bleiben wortgleich
        joined = " ".join(b["bezug"] for b in entry["bezuege"])
        assert '„' in joined  # öffnende Anführungszeichen unangetastet


# ----------------------------------------------------------- Kaskadenstufen --


def test_valid_list_untouched_no_marker():
    """Gemini-Regression: valide Arrays bekommen KEINE Marker/Änderung."""
    bez = [{"pub_id": "X", "pub_kurz": "Y 2020", "bezug": "Z", "relation": "erweitert"}]
    entry = {"bezuege": copy.deepcopy(bez), "verdict": "scannen"}
    before = copy.deepcopy(entry)
    assert _coerce_bezuege(entry) is None
    assert entry == before


def test_empty_list_and_missing_field_untouched():
    for entry in ({"bezuege": []}, {"verdict": "ignorieren"}):
        before = copy.deepcopy(entry)
        assert _coerce_bezuege(entry) is None
        assert entry == before


def test_clean_json_string_unpacks_first_stage():
    payload = [{"pub_id": "A", "pub_kurz": "B", "bezug": "C", "relation": "importiert"}]
    entry = {"bezuege": json.dumps(payload, ensure_ascii=False)}
    info = _coerce_bezuege(entry)
    assert info["method"] == "json_loads"
    assert entry["bezuege"] == payload
    assert entry["bezuege_repaired"] is True


def test_single_dict_gets_wrapped():
    b = {"pub_id": "A", "pub_kurz": "B", "bezug": "C", "relation": "tangential"}
    entry = {"bezuege": copy.deepcopy(b)}
    info = _coerce_bezuege(entry)
    assert info["method"] == "wrapped_single_object"
    assert entry["bezuege"] == [b]


def test_garbage_string_kept_raw_as_unparsed():
    raw = "das ist kein json [{kaputt"
    entry = {"bezuege": raw}
    info = _coerce_bezuege(entry)
    assert info["method"] == "unparsed_kept_raw"
    assert entry["bezuege"] == []
    assert entry["bezuege_unparsed"] == raw


def test_char_exploded_list_kept_visible():
    """Liste aus Nicht-dict-Items (z. B. explodierte Zeichen) verliert nichts."""
    entry = {"bezuege": ["[", "{", "x"]}
    info = _coerce_bezuege(entry)
    assert info["method"] == "unparsed_kept_raw"
    assert entry["bezuege"] == []
    assert json.loads(entry["bezuege_unparsed"]) == ["[", "{", "x"]


# -------------------------------------------------------------- Rendering ---


def _render(entry):
    return render_markdown({
        "new_article": {"title": "T", "authors": [], "journal": "J"},
        "entry": entry,
        "iterations": 1,
        "tool_calls": [],
        "tokens_in": 0,
        "tokens_out": 0,
        "est_cost_usd": 0.0,
    })


def test_render_survives_unparsed_and_shows_raw():
    entry = {"bezuege": FIXTURES[0]["raw_bezuege"], "verdict": "lesenswert",
             "kernthese": "K", "verdict_begruendung": "B",
             "theoretisch_methodisch": "M", "bemerkenswert": []}
    _coerce_bezuege(entry)
    # künstlich auf unparsed zwingen, um den Anzeige-Pfad zu testen
    entry["bezuege"], entry["bezuege_unparsed"] = [], FIXTURES[0]["raw_bezuege"]
    md = _render(entry)
    assert "defektem Format" in md
    assert FIXTURES[0]["raw_bezuege"][:60] in md


def test_render_survives_legacy_string_bezuege_without_repair():
    """Alt-Daten-Pfad: ein nie repariertes String-bezuege crasht das
    Rendering nicht mehr (vorher: AttributeError auf str.get)."""
    entry = {"bezuege": "[{broken", "verdict": "scannen", "kernthese": "K",
             "verdict_begruendung": "B", "theoretisch_methodisch": "M",
             "bemerkenswert": []}
    md = _render(entry)
    assert "Keine substantiellen Bezüge" in md
