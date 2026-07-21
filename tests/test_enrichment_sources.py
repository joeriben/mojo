"""Abstract-Quellen: DOAJ-Titelabgleich, Cache-TTL, Tier-0-Reihenfolge.

Hermetisch — kein Netz. Der Titelabgleich ist der heikle Teil: zu lax hängt er
einen falschen Abstract an, zu streng verfehlt er Untertitel-Varianten.
"""

from __future__ import annotations

from journal_bot import enrichment as E


# --- DOAJ-Titelabgleich ---

def test_titles_match_untertitel_variante():
    # Realfall: DOAJ kürzt/ändert den Untertitel, Artikel ist derselbe.
    a = "Finding Shimmer: Immersive nonfiction media and entangled ecological imagination"
    b = "FINDING SHIMMER: IMMERSIVE NONFICTION MEDIA AND ENTANGLEMENT"
    assert E._titles_match(a, b) is True


def test_titles_match_fuehrende_woerter_reichen():
    a = "Digitale Hochschulbildung nach 2020: Mut zum Machen in der Lehre"
    b = "Digitale Hochschulbildung nach 2020: Mut zum Machen"
    assert E._titles_match(a, b) is True


def test_titles_match_verschiedene_artikel_nein():
    a = "Finding Shimmer: Immersive nonfiction media and ecological imagination"
    b = "Machine learning approaches to protein folding in silico"
    assert E._titles_match(a, b) is False


def test_titles_match_teilueberlappung_reicht_nicht():
    # Teilen ein paar generische Wörter, sind aber verschiedene Artikel.
    a = "Digital media and education in the age of platforms"
    b = "Digital media literacy for teachers: a survey study"
    assert E._titles_match(a, b) is False


def test_titles_match_kurze_titel_exakt():
    assert E._titles_match("Mediensozialisation", "Mediensozialisation") is True
    assert E._titles_match("Editorial", "Mediensozialisation") is False


# --- Cache-TTL ---

def test_cache_age_days_fehlende_datei_ist_unendlich(tmp_path):
    assert E._cache_age_days(tmp_path / "gibtsnicht.json") == float("inf")


def test_cached_get_frisch_nutzt_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(E, "CACHE_DIR", tmp_path)
    cp = E._cache_path("k", "key1")
    cp.write_text('{"v": 1}', encoding="utf-8")

    def _boom(*a, **k):
        raise AssertionError("darf bei frischem Cache nicht ans Netz gehen")
    monkeypatch.setattr(E.httpx, "get", _boom)
    # max_age_days gross → frisch → Cache, kein Netz.
    assert E._cached_get("k", "key1", "http://x", max_age_days=9999) == {"v": 1}


def test_cached_get_force_umgeht_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(E, "CACHE_DIR", tmp_path)
    cp = E._cache_path("k", "key2")
    cp.write_text('{"v": "alt"}', encoding="utf-8")

    class _Resp:
        status_code = 200
        def json(self):
            return {"v": "neu"}
    monkeypatch.setattr(E.httpx, "get", lambda *a, **k: _Resp())
    assert E._cached_get("k", "key2", "http://x", force=True) == {"v": "neu"}


def test_cached_get_netzfehler_behaelt_alten_stand(tmp_path, monkeypatch):
    monkeypatch.setattr(E, "CACHE_DIR", tmp_path)
    cp = E._cache_path("k", "key3")
    cp.write_text('{"v": "alt"}', encoding="utf-8")

    def _boom(*a, **k):
        raise RuntimeError("Netz weg")
    monkeypatch.setattr(E.httpx, "get", _boom)
    # force → will neu holen, scheitert → alter Stand bleibt (besser als nichts).
    assert E._cached_get("k", "key3", "http://x", force=True) == {"v": "alt"}


# --- Tier-0-Reihenfolge im Backfill ---

def test_try_enrichment_bevorzugt_openalex(monkeypatch):
    from journal_bot import abstract_backfill as B
    monkeypatch.setattr(
        "journal_bot.enrichment.enrich",
        lambda *a, **k: {"openalex": {"abstract": "x" * 200}, "doaj_abstract": "y" * 200},
    )
    ab, src = B._try_enrichment("10.1/x", "Titel", "Journal")
    assert src == "openalex" and len(ab) == 200


def test_try_enrichment_faellt_auf_doaj(monkeypatch):
    from journal_bot import abstract_backfill as B
    monkeypatch.setattr(
        "journal_bot.enrichment.enrich",
        lambda *a, **k: {"openalex": {"abstract": ""}, "doaj_abstract": "y" * 200},
    )
    ab, src = B._try_enrichment("10.1/x", "Titel", "Journal")
    assert src == "doaj" and len(ab) == 200


def test_try_enrichment_zu_kurz_zaehlt_nicht(monkeypatch):
    from journal_bot import abstract_backfill as B
    monkeypatch.setattr(
        "journal_bot.enrichment.enrich",
        lambda *a, **k: {"openalex": {"abstract": "zu kurz"}, "doaj_abstract": ""},
    )
    ab, src = B._try_enrichment("10.1/x", "Titel", "Journal")
    assert ab == "" and src == ""
