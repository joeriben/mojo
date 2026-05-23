"""Export articles to Zotero via the cloud Web API (api.zotero.org).

We don't use the local connector endpoints (port 23119) because:
  - /connector/saveItems ignores the `collections` field and dumps items
    into whatever collection happens to be selected in the Zotero UI.
  - /api/users/0/... on the local server is read-only.
  - /connector/updateSession behaves erratically when driven without the
    browser-popup flow.

The cloud Web API supports `collections` properly. Items sync back to the
desktop client via Zotero Sync (usually within seconds). Requires:
  - ~/.config/mojo/zotero_user_id   (numeric user ID from
                                     https://www.zotero.org/settings/keys)
  - ~/.config/mojo/zotero_api_key   (private key with write permission
                                     on the personal library)
"""

from __future__ import annotations

import html
import json

from pyzotero import zotero

from journal_bot.settings import ZOTERO_API_KEY_FILE, ZOTERO_USER_ID_FILE
from journal_bot.store import Store, StoredArticle


COLLECTION_NAME = "mojo"


def _esc(s: object) -> str:
    """Escape arbitrary value for safe embedding in HTML notes."""
    return html.escape(str(s)) if s is not None else ""


class ZoteroConfigMissing(Exception):
    pass


class ZoteroCollectionMissing(Exception):
    pass


def _load_credentials() -> tuple[str, str]:
    if not ZOTERO_USER_ID_FILE.exists() or not ZOTERO_API_KEY_FILE.exists():
        raise ZoteroConfigMissing(
            "Zotero Web-API nicht konfiguriert. Bitte im Setup → System-Tab "
            "die Zotero User-ID und den API-Key eintragen "
            "(zu finden auf https://www.zotero.org/settings/keys)."
        )
    user_id = ZOTERO_USER_ID_FILE.read_text().strip()
    api_key = ZOTERO_API_KEY_FILE.read_text().strip()
    if not user_id:
        raise ZoteroConfigMissing("Zotero User-ID ist leer.")
    if not api_key:
        raise ZoteroConfigMissing("Zotero API-Key ist leer.")
    return user_id, api_key


def _find_collection_key(zot: zotero.Zotero, name: str) -> str:
    for c in zot.collections():
        if c["data"]["name"] == name:
            return c["key"]
    raise ZoteroCollectionMissing(
        f"Collection '{name}' existiert nicht in deiner Zotero-Library — "
        "bitte einmalig in Zotero anlegen (top-level, in der persönlichen "
        "Library)."
    )


def _build_note_html(a: StoredArticle) -> str:
    e = a.agent_entry
    if isinstance(e, str):
        e = json.loads(e)
    if not e:
        e = {}

    parts: list[str] = ["<h2>MOJO-Analyse</h2>"]
    parts.append(
        f"<p><strong>Verdict:</strong> "
        f"{_esc((a.user_verdict or a.agent_verdict or '').upper())}</p>"
    )
    if e.get("verdict_begruendung"):
        parts.append(f"<p>{_esc(e['verdict_begruendung'])}</p>")

    # Citation hits — wichtiger Befund, war bisher nur im Obsidian-Export
    citation_hits = a.citation_hits or []
    if citation_hits:
        parts.append("<h3>Zitiert Dich</h3><ul>")
        for h in citation_hits:
            if not isinstance(h, dict):
                continue
            authors = ", ".join(h.get("pub_authors", [])[:2]) or "?"
            conf = h.get("confidence", "")
            prefix = "<em>(wahrscheinlich)</em> " if conf == "medium" else ""
            parts.append(
                f"<li>{prefix}<strong>{_esc(authors)}</strong> "
                f"({_esc(h.get('pub_year', ''))}): "
                f"{_esc((h.get('pub_title', '') or '')[:100])} "
                f"· <code>{_esc(h.get('pub_id', ''))}</code></li>"
            )
        parts.append("</ul>")

    if e.get("kernthese"):
        parts.append(f"<h3>Kernthese</h3><p>{_esc(e['kernthese'])}</p>")

    bezuege = e.get("bezuege") or []
    if bezuege:
        parts.append("<h3>Bezüge zu Deinem Werk</h3>")
        for b in bezuege:
            parts.append(
                f"<p><strong>{_esc(b.get('pub_kurz', '?'))}</strong> "
                f"(<code>{_esc(b.get('pub_id', '?'))}</code>, "
                f"{_esc(b.get('relation', '?'))}): "
                f"{_esc(b.get('bezug', ''))}</p>"
            )

    bemerkenswert = e.get("bemerkenswert") or []
    if bemerkenswert:
        parts.append("<h3>Bemerkenswert</h3><ul>")
        for note in bemerkenswert:
            parts.append(f"<li>{_esc(note)}</li>")
        parts.append("</ul>")

    if e.get("theoretisch_methodisch"):
        parts.append(
            f"<h3>Methodisch / Theoretisch</h3>"
            f"<p>{_esc(e['theoretisch_methodisch'])}</p>"
        )

    if a.user_memo:
        parts.append(f"<h3>User-Memo</h3><p><em>{_esc(a.user_memo)}</em></p>")

    # Triage-Verortung — Metadata, wie der Verdict zustandekam. Hilfreich beim
    # späteren Wiederauffinden in Zotero (z.B. nach Diskursraum filtern).
    verortung_items: list[str] = []
    if a.selection_mode:
        verortung_items.append(f"<li>Triage-Modus: {_esc(a.selection_mode)}</li>")
    if a.discourse_indicator:
        verortung_items.append(f"<li>Diskursraum: {_esc(a.discourse_indicator)}</li>")
    if a.signal_group:
        verortung_items.append(f"<li>Signal-Gruppe: {_esc(a.signal_group)}</li>")
    if a.suggested_subgroup:
        sg_line = f"<li>Subgruppen-Vorschlag: {_esc(a.suggested_subgroup)}"
        if a.suggested_subgroup_confidence:
            sg_line += f" (conf {a.suggested_subgroup_confidence:.2f})"
        if a.suggested_subgroup_reason:
            sg_line += f" — {_esc(a.suggested_subgroup_reason)}"
        sg_line += "</li>"
        verortung_items.append(sg_line)
    if verortung_items:
        parts.append("<h3>Verortung</h3><ul>")
        parts.extend(verortung_items)
        parts.append("</ul>")

    # Footer — analog Obsidian-Export
    parts.append("<hr>")
    parts.append(
        f"<p><em>{a.iterations} Iterationen · "
        f"{a.tokens_in:,} in / {a.tokens_out:,} out · "
        f"${a.cost_usd:.3f}</em></p>"
    )

    return "\n".join(parts)


def export_to_zotero(article_id: str, store: Store) -> str:
    """Export article to Zotero via Web API. Returns the Zotero item key."""
    a = store.get(article_id)
    if not a:
        raise ValueError(f"Article {article_id} not found")

    if a.zotero_key:
        return a.zotero_key

    user_id, api_key = _load_credentials()
    zot = zotero.Zotero(library_id=user_id, library_type="user", api_key=api_key)
    coll_key = _find_collection_key(zot, COLLECTION_NAME)

    creators = []
    for name in (a.authors or []):
        parts = name.rsplit(" ", 1)
        if len(parts) == 2:
            creators.append({"creatorType": "author", "firstName": parts[0], "lastName": parts[1]})
        else:
            creators.append({"creatorType": "author", "lastName": name})

    item = zot.item_template("journalArticle")
    item["title"] = a.title
    item["creators"] = creators
    item["abstractNote"] = a.abstract or a.openalex_abstract or ""
    item["publicationTitle"] = a.journal_full or a.journal_short or ""
    item["DOI"] = a.doi or ""
    item["url"] = a.url or ""
    item["date"] = str(a.year or "")
    item["collections"] = [coll_key]

    resp = zot.create_items([item])
    item_key = _extract_created_key(resp)
    if not item_key:
        raise RuntimeError(f"Zotero create_items lieferte keinen Key: {resp}")

    note = zot.item_template("note")
    note["note"] = _build_note_html(a)
    note["parentItem"] = item_key
    note["tags"] = [{"tag": "mojo-analysis"}]
    note_resp = zot.create_items([note])
    if not _extract_created_key(note_resp):
        # Item created, note failed — don't fail the whole export.
        # User still has the article in the right collection.
        pass

    store.set_zotero_key(article_id, item_key)
    return item_key


def _extract_created_key(resp: dict) -> str:
    if not isinstance(resp, dict):
        return ""
    successes = resp.get("successful") or resp.get("success") or {}
    if not successes:
        return ""
    first = next(iter(successes.values()))
    if isinstance(first, dict):
        return first.get("key") or first.get("data", {}).get("key", "")
    return str(first) if first else ""
