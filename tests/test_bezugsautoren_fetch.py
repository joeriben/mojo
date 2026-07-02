"""Tests für die gehärtete OpenAlex-Fetch-Schicht (journal_bot.bezugsautoren).

Vorfall 2026-07-02: Werk-Listen-Queries liefen in ein anhaltendes 429; die
alte Fehlerbehandlung schluckte das und speicherte 3 002 Autoren mit leerem
Œuvre als „fertig". Invarianten seitdem:
  - 429/5xx wird mit Backoff (und Retry-After) erneut versucht,
  - endgültiges Scheitern wirft WorksFetchError statt [] zu liefern,
  - ein Fehlschlag überschreibt/löscht NIE ein bestehendes Œuvre und
    markiert den Autor nicht als refreshed (bleibt Repair-Kandidat).

Offline: httpx-Client wird durch ein Duck-Type-Fake ersetzt; die Backoff-
Sleeps werden weggepatcht.
"""

from __future__ import annotations

import json
import sqlite3

import pytest

from journal_bot import bezugsautoren as bz


class _Resp:
    def __init__(self, status: int, results=None, headers=None):
        self.status_code = status
        self.headers = headers or {}
        self._results = results or []

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx
            raise httpx.HTTPStatusError("err", request=None, response=None)

    def json(self):
        return {"results": self._results, "meta": {"count": len(self._results)}}


class _FakeClient:
    """Liefert eine vordefinierte Antwort-Sequenz, danach die letzte weiter."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = 0

    def get(self, *a, **kw):
        self.calls += 1
        return self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]

    def close(self):
        pass


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    monkeypatch.setattr(bz.time, "sleep", lambda s: None)


def _work(wid: str):
    return {"id": f"https://openalex.org/{wid}", "title": "T", "doi": None,
            "publication_year": 2020, "cited_by_count": 1,
            "referenced_works": ["https://openalex.org/W1"]}


def test_429_is_retried_until_success():
    client = _FakeClient([_Resp(429), _Resp(429), _Resp(200, [_work("W9")])])
    results, total = bz._fetch_works_sorted(client, "A1", "publication_date:desc", 5)
    assert client.calls == 3
    assert total == 1 and results[0]["id"].endswith("W9")


def test_persistent_429_raises_instead_of_empty():
    client = _FakeClient([_Resp(429)])
    with pytest.raises(bz.WorksFetchError):
        bz._fetch_works_sorted(client, "A1", "publication_date:desc", 5)


def test_failure_preserves_existing_oeuvre(tmp_path):
    con = sqlite3.connect(str(tmp_path / "bez.db"))
    con.row_factory = sqlite3.Row
    bz.init_db(con)
    # Bestehendes Œuvre aus einem früheren, erfolgreichen Lauf
    con.execute("INSERT INTO authors VALUES ('A1','Alte Autorin',10,50,1,datetime('now'))")
    con.execute(
        "INSERT INTO author_works VALUES ('A1','W1','Altwerk','',2019,5,?,1,'recent',datetime('now'))",
        (json.dumps(["W2"]),),
    )
    con.commit()

    with pytest.raises(bz.WorksFetchError):
        bz._store_author(con, _FakeClient([_Resp(429)]), "A1", "Alte Autorin")

    # Nichts gelöscht, nichts überschrieben
    n = con.execute("SELECT count(*) FROM author_works WHERE author_oa_id='A1'").fetchone()[0]
    assert n == 1
    assert con.execute("SELECT display_name FROM authors WHERE author_oa_id='A1'").fetchone()[0] == "Alte Autorin"
    con.close()
