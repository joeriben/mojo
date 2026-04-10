"""Diagnose: warum findet der Inspector keine PDFs?
Prüft die ersten 10 Einträge der Collection im Detail — welche Attachment-Typen,
welche linkModes, welche Dateipfade."""

from __future__ import annotations

import json
from pathlib import Path

from pyzotero import zotero

COLLECTION_NAME = "Benjamin's publications"
ZOTERO_STORAGE = Path.home() / "Zotero" / "storage"


def main() -> None:
    zot = zotero.Zotero(library_id="0", library_type="user", local=True)
    coll = next(c for c in zot.collections() if c["data"]["name"] == COLLECTION_NAME)

    items = zot.collection_items(coll["key"], limit=10)
    non_attach = [
        it for it in items
        if it.get("data", {}).get("itemType") not in ("attachment", "note")
    ]

    for it in non_attach[:10]:
        data = it["data"]
        print("=" * 70)
        print(f"Titel: {data.get('title', '')[:80]}")
        print(f"itemType: {data.get('itemType')}")
        print(f"key: {it['key']}")

        try:
            children = zot.children(it["key"])
        except Exception as e:
            print(f"  children() schlug fehl: {e}")
            continue

        if not children:
            print("  (keine Children)")
            continue

        for c in children:
            cdata = c.get("data", {})
            print(f"  child key={c['key']}")
            print(f"    itemType:      {cdata.get('itemType')}")
            print(f"    contentType:   {cdata.get('contentType')}")
            print(f"    linkMode:      {cdata.get('linkMode')}")
            print(f"    filename:      {cdata.get('filename')}")
            print(f"    path:          {cdata.get('path')}")
            print(f"    url:           {cdata.get('url', '')[:80]}")

            # Storage-Ordner prüfen
            folder = ZOTERO_STORAGE / c['key']
            if folder.is_dir():
                files = list(folder.iterdir())
                print(f"    storage dir:   {folder} — {len(files)} Dateien")
                for f in files[:5]:
                    print(f"                   · {f.name}")
            else:
                print(f"    storage dir:   FEHLT ({folder})")


if __name__ == "__main__":
    main()
