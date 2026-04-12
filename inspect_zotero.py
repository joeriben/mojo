"""Einmaliger Prüfbefehl gegen die lokale Zotero-API.
Liest die konfigurierte Zotero-Collection (oder einen per Arg übergebenen Namen),
zeigt Größe/PDF-Abdeckung/Volltext-Volumen — macht KEINE Änderung, kein LLM-Call.

    .venv/bin/python inspect_zotero.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from pyzotero import zotero

try:
    import pypdf
except ImportError:
    pypdf = None

from journal_bot.settings import ZOTERO_COLLECTION, ZOTERO_STORAGE as _ZOTERO_STORAGE

COLLECTION_NAME = sys.argv[1] if len(sys.argv) > 1 else ZOTERO_COLLECTION
ZOTERO_STORAGE = _ZOTERO_STORAGE


def main() -> int:
    print(f"Prüfe Zotero-Collection: {COLLECTION_NAME!r}")
    print(f"Zotero-Storage:          {ZOTERO_STORAGE}")
    print()

    try:
        zot = zotero.Zotero(library_id="0", library_type="user", local=True)
    except Exception as e:
        print(f"❌ Konnte Zotero-API nicht erreichen: {e}")
        print("   Läuft Zotero im Hintergrund? (muss laufen, damit 127.0.0.1:23119 antwortet)")
        return 1

    try:
        collections = zot.collections()
    except Exception as e:
        print(f"❌ collections() schlug fehl: {e}")
        return 1

    match = next(
        (c for c in collections if c["data"]["name"] == COLLECTION_NAME),
        None,
    )
    if not match:
        print(f"❌ Collection {COLLECTION_NAME!r} nicht gefunden.")
        print("   Verfügbare Collections (erste 20):")
        for c in collections[:20]:
            print(f"   · {c['data']['name']}")
        return 1

    coll_key = match["key"]
    print(f"✓ Collection gefunden: key={coll_key}")

    items = zot.everything(zot.collection_items(coll_key))
    non_attach = [
        it for it in items
        if it.get("data", {}).get("itemType") not in ("attachment", "note")
    ]
    print(f"✓ {len(non_attach)} Publikationen in der Collection "
          f"(+ {len(items) - len(non_attach)} Anhänge/Notizen)")
    print()

    # PDF-Coverage
    pdf_count = 0
    full_text_chars = 0
    missing_pdf = []
    no_abstract = 0
    year_hist: dict[str, int] = {}

    for it in non_attach:
        data = it["data"]
        title = data.get("title", "(kein Titel)")
        year = (data.get("date", "") or "")[:4]
        if year:
            year_hist[year] = year_hist.get(year, 0) + 1
        if not data.get("abstractNote"):
            no_abstract += 1

        # Kind-Attachments holen
        try:
            children = zot.children(it["key"])
        except Exception:
            children = []
        pdf_attachments = [
            c for c in children
            if c.get("data", {}).get("contentType") == "application/pdf"
        ]
        if not pdf_attachments:
            missing_pdf.append(title[:80])
            continue

        att_key = pdf_attachments[0]["key"]
        att_folder = ZOTERO_STORAGE / att_key
        pdfs = list(att_folder.glob("*.pdf")) if att_folder.is_dir() else []
        if not pdfs:
            missing_pdf.append(title[:80] + "  (Attachment vorhanden, Datei fehlt)")
            continue

        pdf_count += 1
        if pypdf:
            try:
                reader = pypdf.PdfReader(str(pdfs[0]))
                text = "\n".join(p.extract_text() or "" for p in reader.pages)
                full_text_chars += len(text)
            except Exception:
                pass

    print("=== Übersicht ===")
    print(f"Publikationen gesamt:          {len(non_attach)}")
    print(f"  davon mit extrahierbarer PDF:{pdf_count}")
    print(f"  davon ohne PDF-Datei:        {len(missing_pdf)}")
    print(f"  davon ohne Zotero-Abstract:  {no_abstract}")
    if pdf_count and pypdf:
        avg = full_text_chars / pdf_count
        print(f"Volltext-Volumen (Zeichen):    {full_text_chars:,}")
        print(f"Ø Zeichen pro Publikation:     {avg:,.0f}")
        # grobe Token-Schätzung
        print(f"Volltext grob in Tokens (÷4):  ~{full_text_chars // 4:,}")
    print()

    if year_hist:
        print("=== Jahrgänge ===")
        for y in sorted(year_hist.keys()):
            print(f"  {y or '?'}: {'█' * year_hist[y]} {year_hist[y]}")
        print()

    if missing_pdf:
        print(f"=== Einträge ohne PDF ({len(missing_pdf)}) ===")
        for t in missing_pdf[:15]:
            print(f"  · {t}")
        if len(missing_pdf) > 15:
            print(f"  … und {len(missing_pdf) - 15} weitere")

    return 0


if __name__ == "__main__":
    sys.exit(main())
