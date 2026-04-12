# MOJO Interface — Entwurf (2026-04-12)

## Stack
Flask + Jinja2 + HTMX. Kein JS-Framework, kein Build-Step. SQLite direkt. Lokal auf `localhost:5000`.

## Drei Ansichten

### 1. Digest (Hauptansicht)

- **Lesenswert** oben, aufgeklappt, volle Details, Aktionsbuttons
- **Zitiert dich** als eigene Sektion (Citation-Hits), quer zu Verdicts
- **Scannen** kompakt, 1 Zeile pro Artikel, aufklappbar per [+]
- **Ignorieren** zugeklappt, nur Zahl, auf Klick Titelliste

Filter: Jahr, Diskursraum, Journal, Verdict
Sortierung: Datum, Verdict, Journal

### 2. Artikeldetail

- Verdict + Begründung
- Kernthese
- Bezüge (mit pub_kurz, relation, bezug-Text)
- Bemerkenswert
- Methodisch/Theoretisch
- Meta-Footer (Iterationen, Reads, Kosten)
- Aktionen: Vertiefen, Zotero, DOI

### 3. Diskursraum-Ansicht

- Journals + Artikelzahlen
- Verdict-Verteilung
- Lesenswert aufgeklappt, Scannen mit Bemerkenswert priorisiert
- Trend-Analyse und Bibliometrie startbar

## Aktionen

| Button | Was passiert |
|---|---|
| **Vertiefen** | Opus assess_then_verify mit allow_read=True. HTMX-Update. |
| **→ Zotero** | pyzotero: Artikel in mojo-Collection, Opus-Kommentar als Notiz. |
| **DOI** | Öffnet DOI-URL im Browser. |
| **Trend-Analyse** | mojo trends --cluster X im Hintergrund, Ergebnis in Ansicht. |

## Nicht im Prototyp

- Dialogischer Research-Agent (Phase 2)
- Diskursraum/Journal-CRUD (bleibt CLI)
- User-Auth (lokal, single-user)
