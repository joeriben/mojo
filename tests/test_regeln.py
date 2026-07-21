"""Regeln als Daten: Ordnung, Typen, Prompt-Block, Ausfallverhalten."""

from __future__ import annotations

import json

import pytest

from journal_bot.regeln import (
    TYPEN,
    WEGE,
    Regel,
    build_regel_block,
    lade_regeln,
    sortiere,
    speichere_regeln,
)


def _regel(id_="r1", typ="terminale_sperre", position=1, wortlaut="Text", **kw):
    return Regel(id=id_, typ=typ, position=position, wortlaut=wortlaut, **kw)


def test_unbekannter_typ_wird_abgelehnt():
    with pytest.raises(ValueError, match="unbekannter Regeltyp"):
        _regel(typ="sperre")


def test_leerer_wortlaut_wird_abgelehnt():
    with pytest.raises(ValueError, match="keinen Wortlaut"):
        _regel(wortlaut="   ")


def test_sortierung_nach_position():
    regeln = [_regel("c", position=3), _regel("a", position=1), _regel("b", position=2)]
    assert [r.id for r in sortiere(regeln)] == ["a", "b", "c"]


def test_oeffnung_landet_nie_vor_der_sperre_die_sie_aufheben_soll():
    """Bei gleicher Position entscheidet der Typ-Rang — sonst wäre die Regel
    stillschweigend eine andere."""
    regeln = [
        _regel("oeffnung", typ="oeffnung", position=1),
        _regel("sperre", typ="aufhebbare_sperre", position=1),
    ]
    assert [r.id for r in sortiere(regeln)] == ["sperre", "oeffnung"]


def test_fehlende_datei_ergibt_keine_regeln(tmp_path):
    assert lade_regeln(tmp_path / "gibtsnicht.json") == []


def test_kaputte_datei_haelt_den_lauf_nicht_an(tmp_path):
    pfad = tmp_path / "regeln.json"
    pfad.write_text("{kein json", encoding="utf-8")
    assert lade_regeln(pfad) == []


def test_einzelne_kaputte_regel_verliert_nicht_die_uebrigen(tmp_path):
    pfad = tmp_path / "regeln.json"
    pfad.write_text(json.dumps({"regeln": [
        {"id": "gut", "typ": "oeffnung", "position": 1, "wortlaut": "brauchbar"},
        {"id": "schlecht", "typ": "quatsch", "position": 2, "wortlaut": "x"},
        {"id": "ohne_wortlaut", "typ": "oeffnung", "position": 3},
    ]}), encoding="utf-8")
    assert [r.id for r in lade_regeln(pfad)] == ["gut"]


def test_speichern_und_laden_erhaelt_alles(tmp_path):
    pfad = tmp_path / "regeln.json"
    speichere_regeln([
        _regel("b", typ="oeffnung", position=2, herkunft="vom Nutzer", belege=["x"]),
        _regel("a", position=1),
    ], pfad)
    wieder = lade_regeln(pfad)
    assert [r.id for r in wieder] == ["a", "b"]
    assert wieder[1].belege == ["x"]
    assert wieder[1].herkunft == "vom Nutzer"


def test_ohne_regeln_kein_block():
    assert build_regel_block([]) is None


def test_inaktive_regeln_erscheinen_nicht():
    assert build_regel_block([_regel(aktiv=False)]) is None


def test_block_haelt_die_reihenfolge_und_den_wortlaut():
    block = build_regel_block([
        _regel("zweite", typ="oeffnung", position=2, wortlaut="dekoloniale Anteile"),
        _regel("erste", typ="terminale_sperre", position=1, wortlaut="healthcare"),
    ])
    assert block.index("healthcare") < block.index("dekoloniale Anteile")
    assert "1. [terminale_sperre]" in block
    assert "2. [oeffnung]" in block


def test_block_sagt_dass_terminale_sperren_nicht_aufhebbar_sind():
    block = build_regel_block([_regel(typ="terminale_sperre")])
    assert "no later rule lifts it" in block


def test_jeder_typ_hat_eine_anweisung():
    for typ in TYPEN:
        block = build_regel_block([_regel(typ=typ)])
        assert block is not None and "→" in block


def test_wege_enthalten_den_dritten_ausgang():
    assert WEGE == ("weitergeben", "vertiefen", "ignorieren")


# --- Der dritte Weg darf nirgends stillschweigend verlorengehen ---------------

def test_screening_parser_kennt_vertiefen():
    """Regression: ein Gleichheitstest auf »weitergeben« verwarf die Fälle,
    bei denen eine Öffnung eine Sperre aufgehoben hat."""
    import journal_bot.agent as agent

    assert "vertiefen" in agent.SCREENING_SUFFIX
    assert "weitergeben|vertiefen|ignorieren" in agent.SCREENING_SUFFIX


def test_screening_verlangt_keine_zitationsangabe_mehr():
    """Diese Stufe sieht kein Literaturverzeichnis — die alte Regel
    »Cites <Name> or cites works from the bibliography« war unerfüllbar."""
    import journal_bot.agent as agent

    assert "cites works from the bibliography" not in agent.SCREENING_SUFFIX
    assert "No reference list" in agent.SCREENING_SUFFIX


def test_batch_digest_reicht_vertiefen_weiter():
    import inspect

    import journal_bot.batch_digest as bd

    quelle = inspect.getsource(bd)
    assert '("weitergeben", "vertiefen")' in quelle, \
        "vertiefen muss wie weitergeben weitergereicht werden, nicht gefiltert"


# --- Kein stiller Verlust im Batch-Screening ---------------------------------

class _FakeMsg:
    def __init__(self, content): self.content = content
class _FakeChoice:
    def __init__(self, content): self.message = _FakeMsg(content)
class _FakeUsage:
    prompt_tokens = 100
    def model_dump(self): return {"cost": 0.0, "prompt_tokens": 100,
                                  "prompt_tokens_details": {"cached_tokens": 90}}
class _FakeResp:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]
        self.usage = _FakeUsage()


class _FlakyClient:
    """Lässt im ERSTEN Aufruf zwei Artikel weg, liefert sie erst bei der
    Nachforderung — genau der 24/25-, 20/25-Fall aus der Messung."""
    def __init__(self, ids):
        self.ids = ids
        self.aufrufe = 0
        self.chat = self
        self.completions = self

    def create(self, *, model, messages, **kw):
        assert "max_tokens" not in kw, "Screening darf keinen Ausgabedeckel setzen"
        self.aufrufe += 1
        payload = messages[-1]["content"]
        drin = [i for i in self.ids if i[:8] in payload]
        if self.aufrufe == 1:
            drin = drin[:-2]  # zwei fehlen absichtlich
        zeilen = [f"[{i[:8]}] ignorieren — weg" for i in drin]
        return _FakeResp("\n".join(zeilen))


def test_batch_screen_fordert_fehlende_nach(tmp_path, monkeypatch):
    import journal_bot.agent as agent

    ids = [f"aaaaaaa{n}" + "0" * 24 for n in range(5)]  # erste 8 Zeichen distinct
    artikel = [{"id": i, "title": f"T{i[:4]}", "journal": "J", "abstract": "a"} for i in ids]
    client = _FlakyClient(ids)

    monkeypatch.setattr(agent, "build_client", lambda: client)
    monkeypatch.setattr(agent, "_regel_block", lambda: None)
    monkeypatch.setattr(agent, "_profile_block", lambda: None)

    res = agent.batch_screen(artikel, verbose=False)

    # Alle fünf haben ein Urteil ...
    assert set(res) == set(ids)
    # ... und keiner ist still auf »weitergeben« gefallen: die zwei zunächst
    # fehlenden wurden nachgefordert und kamen als »ignorieren« zurück.
    assert all(r["verdict"] == "ignorieren" for r in res.values()), \
        {i[:4]: r["verdict"] for i, r in res.items()}
    assert client.aufrufe >= 2, "die fehlenden Zeilen wurden nicht nachgefordert"


def test_parse_screen_lines_ignoriert_fremde_ids():
    import journal_bot.agent as agent

    batch = [{"id": "a" * 32}, {"id": "b" * 32}]
    raw = (f"[{'a'*8}] vertiefen — offen\n"
           f"[{'c'*8}] ignorieren — gehört nicht zu diesem Batch\n")
    out = agent._parse_screen_lines(raw, batch)
    assert out == {"a" * 32: {"verdict": "vertiefen", "grund": "offen"}}
