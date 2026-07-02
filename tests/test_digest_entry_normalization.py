"""Tests für die Digest-Entry-Normalisierung (journal_bot.store).

Hintergrund: Der Agent (v.a. Gemini 3.5 Flash) lässt `kernthese` im
submit_digest_entry-Tool-Call gelegentlich weg, obwohl das Tool-Schema es als
`required` führt. Im Lauf vom 2026-05-30 fehlte das Feld bei 26 von 454
Einträgen und hat die Web-Digest-View mit einem 500 lahmgelegt. Die Display-
Schicht ist robust (web/app.py _normalize_agent_entry), aber die Datenqualität
muss an der Schreibseite garantiert werden.

`normalize_digest_entry` ist die einzige Wahrheitsquelle: sie stellt alle
display-kritischen Felder sicher und rekonstruiert eine fehlende `kernthese`
rein lokal (kein LLM-Repair → keine API-Kosten).
"""

from __future__ import annotations

import json

from journal_bot.store import Store, StoredArticle, normalize_digest_entry


# ---------------------------------------------------------- Reine Funktion ---


def _full_entry() -> dict:
    return {
        "kernthese": "Der Artikel untersucht algorithmische Sichtbarkeit.",
        "verdict_begruendung": "Hohes Anregungspotenzial für Cultural Resilience.",
        "theoretisch_methodisch": "Konzeptueller Essay auf Basis von Barad.",
        "bezuege": [{"pub_id": "x", "pub_kurz": "Y", "bezug": "z", "relation": "erweitert"}],
        "bemerkenswert": ["Verknüpft Barad mit Multispecies-Studies."],
        "verdict": "lesenswert",
    }


def test_full_entry_passes_through_unchanged():
    entry = _full_entry()
    before = json.loads(json.dumps(entry))  # deep copy
    out = normalize_digest_entry(entry)
    assert out == before  # nichts Vorhandenes verändert


def test_missing_kernthese_derived_from_theoretisch_methodisch():
    entry = _full_entry()
    del entry["kernthese"]
    out = normalize_digest_entry(entry)
    assert out["kernthese"] == "Konzeptueller Essay auf Basis von Barad."


def test_kernthese_derivation_falls_back_to_bemerkenswert_then_begruendung():
    # theoretisch_methodisch leer → bemerkenswert[0]
    e1 = {
        "theoretisch_methodisch": "",
        "bemerkenswert": ["Importiert STS in die Medienpädagogik."],
        "verdict_begruendung": "Begründung.",
    }
    assert normalize_digest_entry(e1)["kernthese"] == "Importiert STS in die Medienpädagogik."

    # theoretisch_methodisch + bemerkenswert leer → verdict_begruendung
    e2 = {
        "theoretisch_methodisch": "",
        "bemerkenswert": [],
        "verdict_begruendung": "Nur Begründung übrig.",
    }
    assert normalize_digest_entry(e2)["kernthese"] == "Nur Begründung übrig."


def test_empty_entry_gets_all_keys_with_safe_defaults():
    out = normalize_digest_entry({})
    assert out["kernthese"] == ""
    assert out["verdict_begruendung"] == ""
    assert out["theoretisch_methodisch"] == ""
    assert out["bezuege"] == []
    assert out["bemerkenswert"] == []


def test_non_dict_input_yields_default_dict():
    for bad in (None, "string", 42, ["list"]):
        out = normalize_digest_entry(bad)
        assert isinstance(out, dict)
        assert out["kernthese"] == ""
        assert out["bezuege"] == []


def test_wrong_types_are_coerced():
    # kernthese=None, bezuege als unparsbarer String, bemerkenswert=None
    entry = {
        "kernthese": None,
        "theoretisch_methodisch": "Deskriptiver Satz.",
        "bezuege": "kaputt",
        "bemerkenswert": None,
    }
    out = normalize_digest_entry(entry)
    assert out["bezuege"] == []
    assert out["bemerkenswert"] == []
    # kernthese war None/leer → aus theoretisch_methodisch abgeleitet
    assert out["kernthese"] == "Deskriptiver Satz."


def test_stringified_list_is_recovered_not_dropped():
    """Gemini kodiert Listen-Felder gelegentlich als JSON-String doppelt.

    Der Inhalt muss erhalten bleiben (verlustarme Rekonstruktion), nicht
    nach [] verworfen werden — sonst gingen echte Bemerkungen verloren.
    """
    entry = {
        "kernthese": "K",
        "bemerkenswert": '["Verknüpft Barad mit STS.", "Ungewöhnlicher Methodenmix."]',
        "bezuege": '[{"pub_id": "p1", "pub_kurz": "A 2024", "bezug": "b", "relation": "erweitert"}]',
    }
    out = normalize_digest_entry(entry)
    assert out["bemerkenswert"] == ["Verknüpft Barad mit STS.", "Ungewöhnlicher Methodenmix."]
    assert out["bezuege"] == [
        {"pub_id": "p1", "pub_kurz": "A 2024", "bezug": "b", "relation": "erweitert"}
    ]


def test_malformed_stringified_bemerkenswert_preserved_as_single_note():
    """Echtes DB-Muster: ['…'] mit un-escaptem inneren `"` → json.loads scheitert.

    Inhalt darf NICHT verloren gehen (Datenqualität ist das Ziel der Aufgabe):
    Die Notiz wird verlustfrei als Einzel-Eintrag erhalten und der kaputte
    Array-Wrapper sauber abgeschält.
    """
    broken = '["Der Diskurs der „Bildung" (BNE) wird radikal infrage gestellt."]'
    out = normalize_digest_entry({"kernthese": "K", "bemerkenswert": broken})
    assert out["bemerkenswert"] == [
        'Der Diskurs der „Bildung" (BNE) wird radikal infrage gestellt.'
    ]


def test_malformed_stringified_bezuege_drops_to_empty():
    """Objekt-Listen dürfen NICHT als String-Item gewrappt werden — das würde
    die Templates (b.get('pub_kurz')) sprengen. Unparsbar → []."""
    out = normalize_digest_entry({"kernthese": "K", "bezuege": '[{"pub_id": "p" oops]'})
    assert out["bezuege"] == []


def test_idempotent():
    entry = {"verdict_begruendung": "B", "theoretisch_methodisch": "T"}
    once = normalize_digest_entry(dict(entry))
    twice = normalize_digest_entry(normalize_digest_entry(dict(entry)))
    assert once == twice
    # zweiter Lauf darf die abgeleitete kernthese nicht erneut überschreiben
    assert twice["kernthese"] == "T"


def test_blank_kernthese_with_no_sources_stays_empty():
    out = normalize_digest_entry({"kernthese": "   "})
    assert out["kernthese"] == ""


def test_mutates_in_place_and_returns_same_object():
    """Vertrag, auf den der Markdown-Export baut: digest.process_article reicht
    DENSELBEN entry-Dict an update_agent_result UND an render_markdown. Weil
    die Normalisierung in-place mutiert, sieht render_markdown die ergänzte
    kernthese ebenfalls (statt eines leeren Headings im .md-File)."""
    entry = {"theoretisch_methodisch": "Deskriptiver Satz."}
    out = normalize_digest_entry(entry)
    assert out is entry  # gleiche Referenz
    assert entry["kernthese"] == "Deskriptiver Satz."  # Aufrufer-Dict ergänzt


# -------------------------------------------------- Integration über Store ---


def _minimal_store(tmp_path) -> Store:
    return Store(path=tmp_path / "articles.db")


def _insert_article(store: Store, article_id: str = "art1") -> None:
    store.upsert_article(
        StoredArticle(
            id=article_id,
            journal_short="zfpaed",
            journal_full="Zeitschrift für Pädagogik",
            title="Test-Artikel",
        )
    )


def test_update_agent_result_persists_normalized_entry(tmp_path):
    """Schreib-Choke-point: ein Entry ohne kernthese wird normalisiert abgelegt."""
    store = _minimal_store(tmp_path)
    _insert_article(store)

    entry_without_kernthese = {
        "verdict": "scannen",
        "verdict_begruendung": "Berührt Diskursraum digitale Kultur.",
        "theoretisch_methodisch": "Empirische Interviewstudie zu Datafizierung.",
        "bezuege": [],
        "bemerkenswert": [],
    }
    assert "kernthese" not in entry_without_kernthese

    store.update_agent_result(
        "art1",
        verdict="scannen",
        entry=entry_without_kernthese,
        citation_hits=[],
        tokens_in=0,
        tokens_out=0,
        tokens_cached_read=0,
        tokens_cache_write=0,
        cost_usd=0.0,
        iterations=0,
    )

    a = store.get("art1")
    assert isinstance(a.agent_entry, dict)
    assert "kernthese" in a.agent_entry
    # aus theoretisch_methodisch abgeleitet
    assert a.agent_entry["kernthese"] == "Empirische Interviewstudie zu Datafizierung."

    # und das rohe JSON in der DB ist ebenfalls vollständig
    with store._conn() as c:
        raw = c.execute(
            "SELECT agent_entry_json FROM articles WHERE id = ?", ("art1",)
        ).fetchone()[0]
    stored = json.loads(raw)
    assert stored["kernthese"]
    for key in ("verdict_begruendung", "theoretisch_methodisch", "bezuege", "bemerkenswert"):
        assert key in stored
