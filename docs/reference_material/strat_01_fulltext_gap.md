# Strategie 01 — Volltext-Lücke schließen (Beschaffung, nicht Extraktion)

> **Korrektur 2026-05-31 (zwei selbstverschuldete Fehler, von Benjamin aufgedeckt, gemessen behoben).**
> Eine frühere Fassung behauptete, „6 DOI-Lücken = großteils Benjamins eigene AI&Society-Artikel", und
> schloss, das VPN helfe nicht und Benjamin müsse die PDFs manuell im Browser laden. **Beides falsch.**
> Tatsächlich (gemessen, `/tmp/check.py`, `/tmp/phantom.py`, `/tmp/zcheck.py`):
> - Die 5 `10.1007/s00146-…`-Einträge (AI&Society) waren **leere Phantom-Stubs** — kein Titel, keine
>   Autoren, kein Jahr, `fulltext_chars=0` — und Benjamin hat **keine** Publikationen in AI&Society.
> - Sie standen als **5 titellose DOI-Einträge** in der Zotero-Collection `QM7TZT44` („Benjamin's
>   publications"). Der additiv-idempotente Build hat sie korrekt eingelesen → 5 leere Werk-Records.
> - **Fix:** Build härtet jetzt am Schreib-Choke-point (`_ingest_item`): Items **ohne Titel UND ohne PDF**
>   erzeugen keinen Record mehr und ein bereits eingebauter Leer-Stub wird self-healing entfernt
>   (`store.delete_publication`, Stat `items_skipped_empty`, Tests in `tests/test_own_refs.py`). Die 5
>   Alt-Stubs sind aus `own_refs.db` purged → **161 → 156 Pubs, 0 titellos, 156/156 mit „Jörissen"**.
> - **VPN:** ist systemweit (ganzer PC), nicht „für Zotero". Die „Client Challenge"-Wand war
>   Bot-Erkennung auf einen naiven `urllib`-Client (Client-Verhalten), kein Zugangs-/VPN-Problem. Das
>   Fetchen läuft ohnehin über die bestehende Pipeline (Zotero-Connector + OA/Unpaywall), die vom
>   institutionellen Zugang profitiert — kein manueller Browser-Download nötig.

## Ist-Zustand (gemessen am bereinigten Korpus, `/tmp/gap.py`)
- Volltext-Lücke: **66/156 (42 %)** — überwiegend **pre-2018** (48/66) Bildungstheorie/Medien-Fundament.
- Item-Typen der Lücke: **39 bookSection, 15 journalArticle, 11 book, 1 magazineArticle**.
- **Nur 1/66 hat eine DOI:** `10.1515/para-2024-0043` („Digital-kulturelle Praktiken als immaterielles
  kulturelles Erbe", Klepacki/**Jörissen**/Pino, De Gruyter) — sein realer Ko-Autoren-Artikel, noch ohne
  Volltext. Die übrigen 65 haben **keine DOI** (alte Buchkapitel/Bücher).
- Grund der Lücke: in Zotero hängt für diese Items schlicht **kein PDF** (`no_pdf_attachment`). Zotero hat
  insgesamt ~8 346 PDF-Attachments — aber für genau diese 66 keines.

## Strategie v1
Volltexte der Lücken aus Zotero-PDFs nachextrahieren (pdftotext/pdfplumber).

## Adversariale Kritik (v1)
**v1 ist an der gemessenen Realität vorbei.** Die PDFs existieren in Zotero **nicht** — es gibt nichts zu
extrahieren. „Extraktion verbessern" löst ein Problem, das nicht das Problem ist. Außerdem: alte
Buchkapitel (39 bookSection, 11 book) sind oft nur in Print/als Scan verfügbar → selbst beschaffte PDFs
wären OCR-bedürftig.

## Strategie v2 (Beschaffung über die bestehende Pipeline + ehrliche Grenze)
1. **DOI-Lücke (n=1, De Gruyter):** OA-Fetch (Unpaywall/OpenAlex-OA-URL) bzw. Zotero „Find Available PDF" —
   läuft über die normale Pipeline und profitiert vom systemweiten VPN/institutionellen Zugang. Kein
   `urllib`-Direktabruf auf Publisher-PDF-URLs (Bot-Wand), sondern die robusten OA-Routen.
2. **Metadaten/Refs-Backfill für die 65 ohne DOI**, wo ein OA-Record per Titel-Suche existiert — liefert
   wenigstens Referenzen/Abstract, auch ohne Volltext (OpenAlex/Crossref, kostenlos, idempotent).
3. **Restmenge = pre-2018-Print-only-Buchkapitel:** die hochwertigen Fundament-Werke, die nur Benjamin als
   Datei/Scan hat, als PDF-Attachment in die Zotero-Collection „Benjamin's publications" (`QM7TZT44`)
   hängen. Danach Re-Build idempotent (`mojo refs build`). Das ist die *einzige* echte „Datei
   bereitstellen"-Komponente — **niedrige Priorität, nicht blockierend.**

**Priorisierung (R5):** nicht alle 66 gleich — zuerst die pre-2018-Werke mit höchstem Erdungswert
(viel-zitiert / discourse-zentral). Kein Browser-Download „eigener AI&Society-Artikel" — die gab es nie.

## Erwarteter Effekt & Messbarkeit (R2)
Volltext-Coverage 58 % → geringfügig höher (DOI-/OA-Fetch) bzw. deutlich höher nur mit Benjamins
pre-2018-Attachments. Validierung **nicht** an der Coverage-Zahl, sondern nachgelagert in Phase 2: hebt das
pre-2018-Fundament im `rich_sim` die Iter-47-Hard-Cases (Barad/Whitehead-Verwandtschaft)? — dort messen,
nicht hier behaupten.

## → Benjamin-Aufgabe?
**Optional, niedrig, nicht blockierend.** Zwei Dinge, beide informativ statt aufschiebend:
1. **Hygiene (optional):** Die 5 titellosen AI&Society-DOIs (itemIDs 43704–43708) liegen in deiner
   Collection `QM7TZT44`. Code-seitig sind sie jetzt neutralisiert (Build ignoriert sie); du *kannst* sie
   aus „Benjamin's publications" entfernen, weil sie nicht deine sind — nötig ist es nicht mehr.
2. **Fundament (optional, hoher Erdungswert):** pre-2018-Buchkapitel ohne DOI/PDF, die nur du als Datei
   hast, als Zotero-Attachment hängen → Re-Build zieht sie automatisch.

Der frühere „du musst deine eigenen Paper im Browser laden"-Trigger **entfällt** — er beruhte auf der
falschen AI&Society-Annahme.

## → nächste
Strat 02: Refs-Auflösung — der größere Hebel (12 % → ?), und er hängt **nicht** an fehlenden Volltexten,
weil `ref_text` für die unaufgelösten Refs bereits vorliegt.
