"""Tests für den Profil-Bereich der Web-UI (`/profil`).

Schwerpunkt ist die Kosten-Schranke: der Lauf darf NUR nach einer zweiten,
ausdrücklichen Bestätigung starten. Es wird in keinem Test ein echter Prozess
gestartet — `subprocess.Popen` ist immer gemockt.
"""

from __future__ import annotations

import json
import sqlite3

import pytest

from journal_bot.web import app as app_mod


# ── Fixtures ───────────────────────────────────────────────────────────────


def _make_own_refs_db(path, rows: list[tuple]) -> None:
    """Minimale own_refs.db: nur die Spalten, die der Bereich liest.

    `fulltext_chars` trägt die routenabhängige Kostenschätzung; fehlt die
    Spalte, liefert `_own_texts()` still eine leere Liste (die Abfrage läuft in
    OperationalError, der dort abgefangen wird).
    """
    conn = sqlite3.connect(path)
    conn.execute(
        "CREATE TABLE publications ("
        "canonical_id TEXT, title TEXT, year INTEGER, venue TEXT, "
        "authors_json TEXT, fulltext_path TEXT, fulltext_chars INTEGER DEFAULT 0)"
    )
    conn.executemany(
        "INSERT INTO publications "
        "(canonical_id, title, year, venue, authors_json, fulltext_path) "
        "VALUES (?,?,?,?,?,?)",
        rows,
    )
    conn.commit()
    conn.close()


@pytest.fixture
def substrate(tmp_path, monkeypatch):
    """Zwei eigene Texte mit Volltext, einer davon bereits ausgewertet."""
    db = tmp_path / "own_refs.db"
    _make_own_refs_db(
        db,
        [
            ("hash:aaa", "Erster Text über Resilienz", 2024, "Zeitschrift A",
             json.dumps(["Jörissen, Benjamin"]), "/tmp/a.txt"),
            ("hash:bbb", "Zweiter Text über Bildung", 2023, "Zeitschrift B",
             json.dumps(["Jörissen, Benjamin"]), "/tmp/b.txt"),
            # ohne Volltext → gehört nicht zum auswertbaren Substrat
            ("hash:ccc", "Text ohne Volltext", 2022, "", "[]", ""),
        ],
    )
    out_dir = tmp_path / "fallgestalt"
    out_dir.mkdir()
    (out_dir / "hash_aaa.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(app_mod, "OWN_REFS_DB", db)
    monkeypatch.setattr(app_mod, "FALLGESTALT_DIR", out_dir)
    monkeypatch.setattr(app_mod, "PROFIL_LOG", tmp_path / "profil_auswertung.log")
    # Profilform-Verdichtung hier neutralisieren — sie hat eigene Tests.
    monkeypatch.setattr(app_mod, "_load_profil_form", lambda: (None, "nicht verfügbar"))
    app_mod._profil_run.clear()
    yield
    app_mod._profil_run.clear()


@pytest.fixture
def empty_substrate(tmp_path, monkeypatch):
    """Kein Text ausgewertet — Leerzustand."""
    db = tmp_path / "own_refs.db"
    _make_own_refs_db(
        db,
        [("hash:aaa", "Erster Text", 2024, "Zeitschrift A", "[]", "/tmp/a.txt")],
    )
    out_dir = tmp_path / "fallgestalt"
    out_dir.mkdir()
    monkeypatch.setattr(app_mod, "OWN_REFS_DB", db)
    monkeypatch.setattr(app_mod, "FALLGESTALT_DIR", out_dir)
    monkeypatch.setattr(app_mod, "PROFIL_LOG", tmp_path / "profil_auswertung.log")
    monkeypatch.setattr(app_mod, "_load_profil_form", lambda: (None, None))
    app_mod._profil_run.clear()
    yield
    app_mod._profil_run.clear()


@pytest.fixture
def client():
    app_mod.app.config["TESTING"] = True
    return app_mod.app.test_client()


class _FakeProc:
    """Popen-Ersatz: läuft nie wirklich, meldet sich als beendet."""

    def __init__(self, *args, **kwargs):
        self.args = args[0] if args else kwargs.get("args")
        self.returncode = 0

    def poll(self):
        return 0


@pytest.fixture
def no_real_process(monkeypatch):
    """Jeder Popen-Aufruf wird abgefangen und protokolliert — nie echt gestartet."""
    calls: list = []

    def fake_popen(cmd, **kwargs):
        calls.append(cmd)
        return _FakeProc(cmd)

    monkeypatch.setattr(app_mod.subprocess, "Popen", fake_popen)
    return calls


# ── Seite ──────────────────────────────────────────────────────────────────


def test_profil_page_loads(client, substrate):
    r = client.get("/profil")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "Profil" in html
    # "N von M Texten ausgewertet" — nur Werke mit Volltext zählen (2, nicht 3)
    assert "1 von 2 Texten ausgewertet" in html
    # Substrat nach Jahr gruppiert, Status je Werk
    assert "2024" in html and "2023" in html
    assert "ausgewertet" in html and "noch nicht" in html


def test_profil_page_offers_year_and_single_work_selection(client, substrate):
    html = client.get("/profil").get_data(as_text=True)
    assert 'name="year" value="2024"' in html
    assert 'name="work" value="hash:aaa"' in html
    assert 'name="work" value="hash:bbb"' in html
    # Werke ohne Volltext tauchen im Substrat nicht auf
    assert "hash:ccc" not in html


def test_profil_page_is_in_nav(client, substrate):
    html = client.get("/profil").get_data(as_text=True)
    assert '<a href="/profil"' in html


def test_empty_state_explains_and_links_to_selection(client, empty_substrate):
    html = client.get("/profil").get_data(as_text=True)
    assert "0 von 1 Texten ausgewertet" in html
    assert "noch kein Profil" in html
    assert 'href="#substrat"' in html
    # Leerzustand darf kein Shell-Kommando zeigen
    assert "python " not in html
    assert "h7_run" not in html


# ── Kosten-Schranke ────────────────────────────────────────────────────────


def test_confirm_shows_cost_estimate_and_starts_nothing(client, substrate, no_real_process):
    r = client.post("/api/profil/confirm", data={"year": "2023"})
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "Geschätzte Kosten" in html
    assert "US-Dollar" in html
    assert "Geschätzte Dauer" in html
    assert "1 Text" in html
    # Erste Stufe startet nichts.
    assert no_real_process == []


def test_confirm_skips_already_analysed(client, substrate, no_real_process):
    """Jahr 2024 enthält nur den bereits ausgewerteten Text → nichts zu bezahlen."""
    r = client.post("/api/profil/confirm", data={"year": "2024"})
    html = r.get_data(as_text=True)
    assert "bereits ausgewertet" in html
    assert no_real_process == []


def test_confirm_combines_year_and_single_work(client, substrate, no_real_process):
    r = client.post("/api/profil/confirm", data={"year": "2024", "work": "hash:bbb"})
    html = r.get_data(as_text=True)
    assert "Ausgewählt" in html and "2 Texte" in html
    # Der ausgewertete zählt als übersprungen, nur einer wird neu gelesen.
    assert "wird übersprungen" in html
    assert no_real_process == []


def test_start_without_confirmation_starts_no_process(client, substrate, no_real_process):
    r = client.post("/api/profil/start", data={"work": "hash:bbb"})
    assert r.status_code == 200
    assert no_real_process == [], "Ohne Bestätigung darf kein Prozess starten"
    assert "Bestätigung" in r.get_data(as_text=True)


def test_start_with_confirmation_launches_background_run(client, substrate, no_real_process):
    r = client.post("/api/profil/start", data={"work": "hash:bbb", "confirmed": "ja"})
    assert r.status_code == 200
    assert len(no_real_process) == 1
    cmd = no_real_process[0]
    assert "h7_run.py" in " ".join(cmd)
    assert "hash:bbb" in cmd          # nur der noch nicht ausgewertete Text
    assert "hash:aaa" not in cmd      # bereits ausgewertet → nicht erneut bezahlt
    assert "--yes" in cmd             # keine Rückfrage im Hintergrundlauf


def test_start_passes_only_pending_works(client, substrate, no_real_process):
    """Auswahl aller Jahre: der ausgewertete Text darf nicht mitlaufen."""
    client.post(
        "/api/profil/start",
        data={"year": ["2023", "2024"], "confirmed": "ja"},
    )
    cmd = no_real_process[0]
    assert "hash:bbb" in cmd
    assert "hash:aaa" not in cmd


def test_start_with_nothing_pending_starts_no_process(client, substrate, no_real_process):
    r = client.post("/api/profil/start", data={"work": "hash:aaa", "confirmed": "ja"})
    assert no_real_process == []
    assert "bereits ausgewertet" in r.get_data(as_text=True)


def test_only_one_run_at_a_time(client, substrate, monkeypatch):
    """Bei laufendem Prozess wird kein zweiter gestartet."""
    calls: list = []

    class Running(_FakeProc):
        def poll(self):
            return None  # läuft noch

    def fake_popen(cmd, **kwargs):
        calls.append(cmd)
        return Running(cmd)

    monkeypatch.setattr(app_mod.subprocess, "Popen", fake_popen)

    first = client.post("/api/profil/start", data={"work": "hash:bbb", "confirmed": "ja"})
    assert first.status_code == 200
    assert len(calls) == 1

    second = client.post("/api/profil/start", data={"work": "hash:bbb", "confirmed": "ja"})
    assert len(calls) == 1, "Ein zweiter Lauf darf nicht starten"
    assert "läuft bereits" in second.get_data(as_text=True)

    # Solange etwas läuft, ist der Startknopf auf der Seite gesperrt.
    page = client.get("/profil").get_data(as_text=True)
    assert 'class="btn btn-primary" disabled' in page
    assert "läuft bereits eine Auswertung" in page


def test_start_button_is_enabled_when_nothing_runs(client, substrate):
    """Gegenprobe zur Sperre — sonst würde die Sperr-Prüfung nichts zeigen."""
    page = client.get("/profil").get_data(as_text=True)
    assert 'class="btn btn-primary" disabled' not in page


# ── Status ─────────────────────────────────────────────────────────────────


def test_status_route_reports_progress(client, substrate, no_real_process):
    client.post("/api/profil/start", data={"work": "hash:bbb", "confirmed": "ja"})
    r = client.get("/api/profil/status")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "Auswertung" in html
    assert "von 1 Text" in html


# ── Profilform-Panel ───────────────────────────────────────────────────────


@pytest.fixture
def profil_form(substrate, monkeypatch):
    """Eine synthetische Profilform in genau der Form, die die Verdichtung liefert."""
    form = {
        "substrate": {
            "works": [
                {"document_id": "hash:aaa", "title": "Erster Text über Resilienz",
                 "year": 2024, "venue": "Zeitschrift A", "authors": [],
                 "n_sources": 2, "n_terms": 1, "beleg_failures": 3},
                {"document_id": "hash:bbb", "title": "Zweiter Text über Bildung",
                 "year": 2023, "venue": "Zeitschrift B", "authors": [],
                 "n_sources": 1, "n_terms": 0, "beleg_failures": 0},
            ],
            "n_works": 2, "years": [2023, 2024], "year_span": [2023, 2024],
        },
        "sources": [
            {"key": "barad:2007", "label": "Barad (2007), *Meeting the Universe Halfway*",
             "n_works": 2, "works": ["hash:aaa", "hash:bbb"], "years": [2023, 2024],
             "stance": {"affirms": 1, "extends": 0, "contrasts": 1, "reserves": 0, "rejects": 0},
             "sigma": {"+": 1, "-": 1}, "own_work": False,
             "shift": {"from": "affirms", "to": "contrasts", "from_year": 2023, "to_year": 2024},
             "label_variants": ["Barad (2007)", "Barad 2007, Meeting the Universe Halfway"]},
            {"key": "haraway:2016", "label": "Haraway (2016), Staying with the Trouble",
             "n_works": 1, "works": ["hash:aaa"], "years": [2024],
             "stance": {"affirms": 1, "extends": 0, "contrasts": 0, "reserves": 0, "rejects": 0},
             "sigma": {"+": 1, "-": 0}, "own_work": False, "shift": None,
             "label_variants": ["Haraway (2016), Staying with the Trouble"]},
        ],
        "cooccurrence": [
            {"a": "barad:2007", "b": "haraway:2016", "weight": 1, "works": ["hash:aaa"]},
        ],
        "terms": [
            {"key": "kulturelle resilienz", "label": "Kulturelle Resilienz", "n_works": 2,
             "works": ["hash:aaa", "hash:bbb"], "years": [2023, 2024],
             "first_year": 2023, "last_year": 2024,
             "label_variants": ["Kulturelle Resilienz", "kulturelle Resilienz"]},
        ],
        "self_positions": [
            {"document_id": "hash:bbb", "year": 2023, "title": "Zweiter Text über Bildung",
             "label": "Das Werk will Bildung als Strukturmoment verankern."},
        ],
        "periods": [
            {"label": "2020–2023", "years": [2023], "n_works": 1, "sources": ["barad:2007"],
             "new_sources": [], "dropped_sources": [], "new_terms": []},
            {"label": "2024–2027", "years": [2024], "n_works": 1,
             "sources": ["barad:2007", "haraway:2016"], "new_sources": ["haraway:2016"],
             "dropped_sources": [], "new_terms": ["kulturelle resilienz"]},
        ],
        "reliability": {"n_works": 2, "works_with_beleg_failures": 1,
                        "total_beleg_failures": 3, "fuzzy_matched_keys": 1,
                        "skipped_files": []},
    }
    monkeypatch.setattr(app_mod, "_load_profil_form", lambda: (form, None))
    return form


def test_bezugsnetz_shows_sources_with_their_company(client, profil_form):
    """Kern des Panels: die Miteinander-Beziehung, nicht bloß eine Rangliste."""
    html = client.get("/profil").get_data(as_text=True)
    assert "Bezugsnetz" in html
    assert "Barad (2007), Meeting the Universe Halfway" in html  # ohne Markdown-Sternchen
    assert "tritt gemeinsam auf mit" in html
    assert "Haraway (2016), Staying with the Trouble" in html


def test_stance_is_shown_in_german(client, profil_form):
    html = client.get("/profil").get_data(as_text=True)
    from journal_bot.web.app import _stance_label
    assert _stance_label("affirms") in html
    assert _stance_label("contrasts") in html


def test_shift_section_is_prominent(client, profil_form):
    html = client.get("/profil").get_data(as_text=True)
    assert "Verschiebungen" in html
    assert "Haltung verschiebt sich" in html


def test_periods_show_labels_not_internal_keys(client, profil_form):
    html = client.get("/profil").get_data(as_text=True)
    assert "neu hinzugekommen" in html
    assert "Kulturelle Resilienz" in html
    assert "haraway:2016" not in html, "interne Schlüssel dürfen nicht in die Seite"
    assert "kulturelle resilienz" not in html


def test_terms_and_self_positions_render(client, profil_form):
    html = client.get("/profil").get_data(as_text=True)
    assert "Eigene Begriffe" in html
    assert "Selbstverortungen" in html
    assert "Das Werk will Bildung als Strukturmoment verankern." in html


def test_epistemic_status_is_visible(client, profil_form):
    """Pflicht: maschinelle Lektüre, heuristische Zusammenführung, Beleg-Fehlschläge."""
    html = client.get("/profil").get_data(as_text=True)
    assert "Gelesen, nicht gerechnet" in html
    assert "maschinelle Lektüren" in html
    assert "heuristisch" in html
    assert "Schreibweisen" in html          # fuzzy_matched_keys sichtbar gemacht
    assert "Belegprüfung" in html
    assert "3 Stellen" in html              # total_beleg_failures
    assert "Schreibweisen zusammengeführt" in html  # label_variants einsehbar


def test_no_accuracy_claims_or_check_marks(client, profil_form):
    """Kein Anschein gerechneter Gültigkeit: keine ✓-Marker, keine Genauigkeitsquoten."""
    html = client.get("/profil").get_data(as_text=True)
    for forbidden in ("✓", "✔", "Genauigkeit", "Trefferquote", "% korrekt", "validiert"):
        assert forbidden not in html, f"{forbidden!r} behauptet gerechnete Gültigkeit"


# ── Sprache ────────────────────────────────────────────────────────────────


def _visible_text(html: str) -> str:
    """Sichtbarer Text der Seite — ohne CSS/JS und ohne Tags/Attribute."""
    import re
    body = re.sub(r"<(style|script)\b.*?</\1>", " ", html, flags=re.S | re.I)
    return re.sub(r"<[^>]+>", " ", body)


def test_no_implementation_language_in_visible_text(client, profil_form):
    """UI-Sprachregel: keine rohen Enums, Dateinamen, Pfade oder Kürzel im Sichtbaren."""
    text = _visible_text(client.get("/profil").get_data(as_text=True))
    for leak in ("affirms", "contrasts", "reserves", "rejects", "own_refs",
                 "fallgestalt", "canonical_id", "h7_run", "H7", ".json", "hash:"):
        assert leak not in text, f"{leak!r} darf nicht im sichtbaren Text stehen"
