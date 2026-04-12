"""Export articles to Zotero via local Connector API.

Uses the /connector/saveItems endpoint (port 23119) which supports
item creation with embedded child notes. Requires Zotero to be running.
"""

from __future__ import annotations

import json
import httpx
from pyzotero import zotero

from journal_bot.store import Store, StoredArticle


COLLECTION_NAME = "mojo"
ZOTERO_LOCAL = "http://localhost:23119"


class ZoteroNotRunning(Exception):
    pass


class ZoteroCollectionMissing(Exception):
    pass


def _check_zotero_running() -> None:
    try:
        httpx.get(f"{ZOTERO_LOCAL}/api/users/0/collections", timeout=3).raise_for_status()
    except (httpx.ConnectError, httpx.TimeoutException):
        raise ZoteroNotRunning(
            "Zotero läuft nicht. Bitte Zotero starten und nochmal versuchen."
        )


def _find_collection_key(zot: zotero.Zotero, name: str) -> str:
    for c in zot.collections():
        if c["data"]["name"] == name:
            return c["key"]
    raise ZoteroCollectionMissing(
        f"Collection '{name}' existiert nicht in Zotero — bitte manuell anlegen."
    )


def _build_note_html(a: StoredArticle) -> str:
    e = a.agent_entry
    if isinstance(e, str):
        e = json.loads(e)
    if not e:
        return "<p>(Keine Agent-Analyse vorhanden.)</p>"

    parts = ["<h2>MOJO-Analyse</h2>"]
    parts.append(f"<p><strong>Verdict:</strong> {(a.user_verdict or a.agent_verdict).upper()}</p>")
    if e.get("verdict_begruendung"):
        parts.append(f"<p>{e['verdict_begruendung']}</p>")

    if e.get("kernthese"):
        parts.append(f"<h3>Kernthese</h3><p>{e['kernthese']}</p>")

    bezuege = e.get("bezuege") or []
    if bezuege:
        parts.append("<h3>Bezüge</h3>")
        for b in bezuege:
            parts.append(
                f"<p><strong>{b.get('pub_kurz', '?')}</strong> "
                f"(<code>{b.get('pub_id', '?')}</code>, {b.get('relation', '?')}): "
                f"{b.get('bezug', '')}</p>"
            )

    bemerkenswert = e.get("bemerkenswert") or []
    if bemerkenswert:
        parts.append("<h3>Bemerkenswert</h3><ul>")
        for note in bemerkenswert:
            parts.append(f"<li>{note}</li>")
        parts.append("</ul>")

    if e.get("theoretisch_methodisch"):
        parts.append(f"<h3>Methodisch/Theoretisch</h3><p>{e['theoretisch_methodisch']}</p>")

    if a.user_memo:
        parts.append(f"<h3>User-Memo</h3><p><em>{a.user_memo}</em></p>")

    return "\n".join(parts)


def export_to_zotero(article_id: str, store: Store) -> str:
    """Export article to local Zotero. Returns the Zotero item key."""
    a = store.get(article_id)
    if not a:
        raise ValueError(f"Article {article_id} not found")

    if a.zotero_key:
        return a.zotero_key

    _check_zotero_running()

    zot = zotero.Zotero(library_id="0", library_type="user", local=True)
    coll_key = _find_collection_key(zot, COLLECTION_NAME)

    # Build creators
    creators = []
    for name in (a.authors or []):
        parts = name.rsplit(" ", 1)
        if len(parts) == 2:
            creators.append({"creatorType": "author", "firstName": parts[0], "lastName": parts[1]})
        else:
            creators.append({"creatorType": "author", "lastName": name})

    # Single request: item + embedded note
    payload = {
        "items": [{
            "itemType": "journalArticle",
            "title": a.title,
            "creators": creators,
            "abstractNote": a.abstract or a.openalex_abstract or "",
            "publicationTitle": a.journal_full or a.journal_short,
            "DOI": a.doi or "",
            "url": a.url or "",
            "date": str(a.year or ""),
            "collections": [coll_key],
            "notes": [{
                "note": _build_note_html(a),
                "tags": [{"tag": "mojo-analysis"}],
            }],
        }],
        "uri": a.url or f"https://doi.org/{a.doi}" if a.doi else "https://mojo.local",
    }

    r = httpx.post(f"{ZOTERO_LOCAL}/connector/saveItems", json=payload, timeout=15)
    if r.status_code != 201:
        raise RuntimeError(f"Zotero saveItems fehlgeschlagen: {r.status_code} {r.text[:200]}")

    # Find the created item key
    items = zot.items(q=a.title[:60], limit=5)
    item_key = ""
    for it in items:
        if it["data"].get("DOI") == a.doi or it["data"]["title"] == a.title:
            item_key = it["key"]
            break

    if item_key:
        store.set_zotero_key(article_id, item_key)

    return item_key or "(erstellt)"
