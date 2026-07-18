"""Tests für profile.json-Persistenz und Trigger-Autor:innen-Status.

Hintergrund (Vorfall 2026-07-18): Die Trigger-Autor:innen-Eskalation war über
Wochen wirkungslos, ohne dass irgendetwas darauf hinwies. Zwei Defekte lagen
übereinander:

  1. Commit 99e476b (2026-05-25) verschob die Namen aus dem Code nach
     profile.json — und trug sie dort nie ein. Leere Liste = Eskalation aus.
  2. `save_profile()` schrieb das übergebene Dict wörtlich. Jeder Aufrufer
     kennt nur die Felder, die er rendert; das Web-Formular kennt zehn. Ein
     Profil-Speichern löschte damit `refs_sources`, `trigger_author_*`,
     `openalex_mailto` und `ranker_enabled` von der Platte.

Defekt 2 ist die Klasse, nicht der Einzelfall — deshalb prüfen die Tests hier
das Merge-Verhalten allgemein, nicht nur die Trigger-Schlüssel.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import journal_bot.settings as settings


@pytest.fixture
def tmp_profile(tmp_path: Path, monkeypatch):
    """Isoliertes profile.json + zurücksetzbare Modul-Globals."""
    path = tmp_path / "profile.json"
    monkeypatch.setattr(settings, "PROFILE_JSON", path)
    monkeypatch.setattr(settings, "TRIGGER_AUTHOR_PATTERNS", ("macgilchrist", "jarke"))
    monkeypatch.setattr(settings, "TRIGGER_AUTHOR_SLUGS", ("macgilchrist", "jarke"))
    monkeypatch.setattr(settings, "RESEARCHER_NAME", "Alt")
    return path


def _write(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


# ----- save_profile: Merge statt Überschreiben -------------------------------


def test_save_profile_preserves_unknown_keys(tmp_profile):
    """Ein Teil-Speichern darf keine fremden Schlüssel von der Platte löschen."""
    _write(tmp_profile, {
        "name": "Alt",
        "refs_sources": [{"type": "zotero", "key": "QM7TZT44"}],
        "trigger_author_patterns": ["macgilchrist", "jarke"],
        "openalex_mailto": "b@example.org",
        "ranker_enabled": True,
    })

    # Genau die Form, die journal_bot/web/app.py:api_setup_profile() schickt
    settings.save_profile({"name": "Neu"})

    after = json.loads(tmp_profile.read_text(encoding="utf-8"))
    assert after["name"] == "Neu"
    assert after["refs_sources"] == [{"type": "zotero", "key": "QM7TZT44"}]
    assert after["trigger_author_patterns"] == ["macgilchrist", "jarke"]
    assert after["openalex_mailto"] == "b@example.org"
    assert after["ranker_enabled"] is True


def test_save_profile_partial_does_not_reset_globals(tmp_profile):
    """Ein Teil-Speichern darf Modul-Konstanten nicht auf leer zurücksetzen."""
    _write(tmp_profile, {"trigger_author_patterns": ["macgilchrist", "jarke"]})

    settings.save_profile({"name": "Neu"})

    assert settings.TRIGGER_AUTHOR_PATTERNS == ("macgilchrist", "jarke")
    assert settings.TRIGGER_AUTHOR_SLUGS == ("macgilchrist", "jarke")


def test_save_profile_manages_removes_cleared_field(tmp_profile):
    """`manages` erhält die Bedeutung von "Feld geleert" für eigene Felder."""
    _write(tmp_profile, {
        "name": "Alt",
        "institution": "FAU",
        "refs_sources": [{"type": "zotero", "key": "QM7TZT44"}],
    })

    # Formular besitzt name+institution; institution wurde geleert (fällt raus)
    settings.save_profile({"name": "Neu"}, manages=("name", "institution"))

    after = json.loads(tmp_profile.read_text(encoding="utf-8"))
    assert after["name"] == "Neu"
    assert "institution" not in after          # eigenes Feld: entfernt
    assert "refs_sources" in after             # fremdes Feld: bleibt


def test_save_profile_writes_values_through(tmp_profile):
    """Trigger-Schlüssel lassen sich weiterhin setzen und wirken sofort."""
    settings.save_profile({
        "name": "Neu",
        "trigger_author_patterns": ["chun"],
        "trigger_author_slugs": ["wendy_chun"],
    })

    after = json.loads(tmp_profile.read_text(encoding="utf-8"))
    assert after["trigger_author_patterns"] == ["chun"]
    assert settings.TRIGGER_AUTHOR_PATTERNS == ("chun",)
    assert settings.TRIGGER_AUTHOR_SLUGS == ("wendy_chun",)


# ----- trigger_authors_status: der stille Ausfall wird laut -------------------


def test_status_reports_unarmed_when_empty(monkeypatch):
    """Leere Liste → `armed` False und ein Hinweis in Domänensprache."""
    monkeypatch.setattr(settings, "TRIGGER_AUTHOR_PATTERNS", ())
    monkeypatch.setattr(settings, "TRIGGER_AUTHOR_SLUGS", ())

    status = settings.trigger_authors_status()

    assert status["armed"] is False
    assert status["n_patterns"] == 0
    assert status["hinweis"]  # nicht None und nicht leer


def test_status_flags_missing_bibliography(tmp_path, monkeypatch):
    """Eingetragener Slug ohne Bibliographie-Datei wird benannt."""
    monkeypatch.setattr(settings, "TRIGGER_AUTHOR_PATTERNS", ("jarke",))
    monkeypatch.setattr(settings, "TRIGGER_AUTHOR_SLUGS", ("jarke", "fehlt"))
    monkeypatch.setattr(settings, "TRIGGER_BIBLIOGRAPHIES_DIR", tmp_path)
    (tmp_path / "jarke.json").write_text("{}", encoding="utf-8")

    status = settings.trigger_authors_status()

    assert status["armed"] is True
    assert status["missing_bibliographies"] == ["fehlt"]
    assert "fehlt" in status["hinweis"]


def test_status_silent_when_complete(tmp_path, monkeypatch):
    """Vollständig konfiguriert → kein Hinweis."""
    monkeypatch.setattr(settings, "TRIGGER_AUTHOR_PATTERNS", ("jarke",))
    monkeypatch.setattr(settings, "TRIGGER_AUTHOR_SLUGS", ("jarke",))
    monkeypatch.setattr(settings, "TRIGGER_BIBLIOGRAPHIES_DIR", tmp_path)
    (tmp_path / "jarke.json").write_text("{}", encoding="utf-8")

    status = settings.trigger_authors_status()

    assert status["armed"] is True
    assert status["hinweis"] is None


# ----- Der Digest-Lauf sagt es ebenfalls -------------------------------------


def _digest_log(tmp_path, monkeypatch, patterns: tuple[str, ...]) -> list[str]:
    """Kopf eines Digest-Laufs mitschneiden — ohne Screening, Agent, Netz.

    Screening UND `digest.process_article` sind gemockt. Beides ist Pflicht:
    ohne den zweiten Mock ruft der Lauf das Agent-Modell echt auf und der Test
    kostet bei jedem Durchlauf Geld (hier einmal passiert, $0.009).
    """
    from journal_bot import batch_digest
    from journal_bot.store import Store, StoredArticle

    monkeypatch.setattr(batch_digest, "TRIGGER_AUTHOR_PATTERNS", patterns)
    monkeypatch.setattr(batch_digest, "RANKER_ENABLED", False)
    monkeypatch.setattr(batch_digest, "load_authored_all", lambda: [], raising=False)
    monkeypatch.setattr(batch_digest, "find_citations", lambda refs, authored: [])
    monkeypatch.setattr(batch_digest.agent_mod, "batch_screen",
                        lambda items, verbose=False: {
                            it["id"]: {"verdict": "ignorieren", "grund": "Test"}
                            for it in items
                        })

    def _no_llm(sa, store_, verbose=True, model=None, mode="assess_verify"):
        return {"agent_result": {"est_cost_usd": 0.0,
                                 "entry": {"verdict": "ignorieren"}}}

    monkeypatch.setattr(batch_digest.digest, "process_article", _no_llm)

    store = Store(path=tmp_path / "articles.db")
    art = StoredArticle(
        id="a1", journal_short="TST", journal_full="Testjournal",
        title="Ein Titel", abstract="Ein Abstract.", authors=["Autor X"],
    )
    store.upsert_article(art)

    lines: list[str] = []
    batch_digest.run_batch_digest(
        [art], store, verbose=True, logger=lines.append,
    )
    return lines


def test_digest_start_warns_when_trigger_list_empty(tmp_path, monkeypatch):
    """Der Lauf sagt beim Start, dass die Eskalation aus ist."""
    lines = _digest_log(tmp_path, monkeypatch, ())

    hinweise = [ln for ln in lines if "Trigger-Autor:innen" in ln]
    assert hinweise, f"kein Hinweis im Log: {lines}"
    assert "trigger_author_patterns" in hinweise[0]


def test_digest_start_silent_when_configured(tmp_path, monkeypatch):
    """Konfiguriert → kein Rauschen im Lauf-Kopf."""
    lines = _digest_log(tmp_path, monkeypatch, ("macgilchrist",))

    assert not [ln for ln in lines if "Trigger-Autor:innen" in ln]
