"""Beispiel-Abruf: Nachbarwahl, Titelgleich-Ausschluss, Prompt-Verdrahtung.

Hermetisch — kein MiniLM-Modell: `textembed.encode` und der Index werden durch
kontrollierte Vektoren ersetzt, damit die Auswahl-Logik testbar ist, ohne einen
echten Einbettungslauf.
"""

from __future__ import annotations

import numpy as np
import pytest

from journal_bot import beispiele


@pytest.fixture
def fake_index(monkeypatch):
    """Drei beurteilte Artikel mit orthogonalen Vektoren."""
    ix = beispiele._Index.__new__(beispiele._Index)
    ix.emb = np.array([[1, 0, 0], [0, 1, 0], [0, 0, 1]], dtype="float32")
    ix.titles = ["Alpha decolonial infrastructures",
                 "Beta nursing competence RCT",
                 "Gamma avatar subjectivation"]
    ix.verdicts = ["lesenswert", "ignorieren", "scannen"]
    ix.memos = ["sehr nah am Werk", "", "x" * 80]  # letztes Memo zu lang → raus
    ix.norm_titles = [beispiele._norm_titel(t) for t in ix.titles]
    monkeypatch.setattr(beispiele, "_STATE", ix)
    monkeypatch.setattr(beispiele, "_GELADEN", True)
    return ix


def _fake_encode(vecs):
    def encode(texte, **kw):
        return np.array(vecs, dtype="float32")
    return encode


def test_naechster_nachbar_wird_gewaehlt(fake_index, monkeypatch):
    # Query zeigt exakt auf Beta (Achse 1) → Beta zuerst.
    monkeypatch.setattr("journal_bot.textembed.encode", _fake_encode([[0, 1, 0]]))
    out = beispiele.bloecke([{"id": "a1", "title": "some query", "abstract": "x"}], k=3)
    assert "a1" in out
    assert out["a1"].startswith("Frühere Urteile des Nutzers zu ähnlichen Artikeln:")
    # Beta (nächster) steht als erstes, mit Verdikt.
    assert '"Beta nursing competence RCT" -> ignorieren' in out["a1"]


def test_verdikt_und_kurzes_memo_erscheinen(fake_index, monkeypatch):
    monkeypatch.setattr("journal_bot.textembed.encode", _fake_encode([[1, 0, 0]]))
    out = beispiele.bloecke([{"id": "a1", "title": "q", "abstract": ""}], k=1)
    # Alpha: Verdikt + kurzes Memo in Klammern.
    assert '"Alpha decolonial infrastructures" -> lesenswert (sehr nah am Werk)' in out["a1"]


def test_langes_memo_wird_weggelassen(fake_index, monkeypatch):
    monkeypatch.setattr("journal_bot.textembed.encode", _fake_encode([[0, 0, 1]]))
    out = beispiele.bloecke([{"id": "a1", "title": "q", "abstract": ""}], k=1)
    assert "Gamma avatar subjectivation" in out["a1"]
    assert "(xxxx" not in out["a1"]  # 80-Zeichen-Memo unterdrückt


def test_titelgleicher_nachbar_faellt_raus(fake_index, monkeypatch):
    # Query-Titel gleicht Beta → Beta darf sich nicht selbst zitieren.
    monkeypatch.setattr("journal_bot.textembed.encode", _fake_encode([[0, 1, 0]]))
    out = beispiele.bloecke(
        [{"id": "a1", "title": "Beta nursing competence RCT", "abstract": ""}], k=3)
    assert "Beta nursing competence RCT" not in out["a1"]
    # stattdessen die übrigen zwei.
    assert "Alpha" in out["a1"] and "Gamma" in out["a1"]


def test_leerer_index_gibt_nichts(monkeypatch):
    monkeypatch.setattr(beispiele, "_STATE", None)
    monkeypatch.setattr(beispiele, "_GELADEN", True)
    assert beispiele.verfuegbar() is False
    assert beispiele.bloecke([{"id": "a1", "title": "q", "abstract": ""}]) == {}


# --- Verdrahtung in batch_screen (_mit_beispielen) ---

def test_mit_beispielen_gated_aus_laesst_prompt_unveraendert(monkeypatch):
    import journal_bot.agent as agent
    monkeypatch.setattr("journal_bot.settings.BEISPIELE_ENABLED", False)
    arts = [{"id": "a1", "title": "q"}]
    assert agent._mit_beispielen(arts, "PROMPT") == "PROMPT"
    assert "beispiele" not in arts[0]


def test_mit_beispielen_gated_an_haengt_hinweis_und_setzt_block(monkeypatch):
    import journal_bot.agent as agent
    monkeypatch.setattr("journal_bot.settings.BEISPIELE_ENABLED", True)
    monkeypatch.setattr(beispiele, "verfuegbar", lambda: True)
    monkeypatch.setattr(beispiele, "bloecke", lambda arts, k=5: {"a1": "BLOCK-A1"})
    arts = [{"id": "a1", "title": "q"}, {"id": "a2", "title": "r"}]
    prompt = agent._mit_beispielen(arts, "PROMPT")
    assert prompt.startswith("PROMPT")
    assert beispiele.HINWEIS in prompt
    assert arts[0]["beispiele"] == "BLOCK-A1"
    assert "beispiele" not in arts[1]  # kein Nachbar → kein Block


def test_mit_beispielen_faengt_fehler_ab(monkeypatch):
    import journal_bot.agent as agent
    monkeypatch.setattr("journal_bot.settings.BEISPIELE_ENABLED", True)
    monkeypatch.setattr(beispiele, "verfuegbar", lambda: True)

    def boom(*a, **k):
        raise RuntimeError("Einbettung kaputt")
    monkeypatch.setattr(beispiele, "bloecke", boom)
    # Darf nie werfen — der Lauf läuft unverändert weiter.
    assert agent._mit_beispielen([{"id": "a1"}], "PROMPT") == "PROMPT"
