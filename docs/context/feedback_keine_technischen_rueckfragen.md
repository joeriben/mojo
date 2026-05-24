# Keine technischen Rückfragen an Benjamin

**Datum**: 2026-05-24 (Reaktion Benjamins auf einen 4-Optionen-Fragenblock zu
Schema-Detail, Pattern-Pfad, Default-Verhalten, Test-Strategie)

## Festlegung

> „Ich habe mit dieser technischen Ebene wirklich NICHTS zu tun. Ich definiere
> Ziele. Wenn Du MICH fragen musst hast Du zu wenig nachgedacht."
> — Benjamin Jörissen, 2026-05-24

Technische Detail-Entscheidungen (Schema, API-Form, Test-Strategie, Library-
Wahl, Default-Verhalten, Datei-/Modul-Layout, Migrations-Granularität,
Pfad-Konvention, Cache-Strategie, Performance-Trade-off) sind **Aufgabe des
Coding-Assistenten**. Rückfragen an Benjamin dazu zeigen, dass der Assistent
zu wenig nachgedacht hat.

## Wann doch eine Rückfrage erlaubt ist

- Ziel- oder Scope-Konflikte (baust du Modul X oder Modul Y?)
- Inhaltliche Forschungsfragen (welche Diskursräume haben Vorrang, ist diese
  Heuristik kohärent zu deiner Werklogik?)
- Strategische/ethische Entscheidungen (Open-Source-Release jetzt? Welcher
  Nutzerkreis?)
- Wenn Benjamin selbst Optionen anbietet und um Auswahl bittet

## Wie das anzuwenden ist

- Bei technischer Unsicherheit: selbst entscheiden, Entscheidung in 1 Satz
  mit Trade-off-Stichwort begründen, weiter. Beispiel:
  „Tests als Systemverhalten-Tests (Idempotenz, Dedup, Re-Ingest); PDF-Round-
  Trip durch ein CLI-Smoke-Tool ersetzt (`mojo refs validate <pdf>`), weil
  echte PDFs aussagekräftiger sind als synthetische Mocks."
- Bei wirklicher Ziel-Unsicherheit: kurz formulieren *was* unklar ist (das
  Ziel, nicht die Implementierung), und nur dann eine Rückfrage stellen.
- Falsch wäre: „SQLite oder JSON? On-the-fly-PDF oder Repo-Fixture?
  Klassifikation jetzt oder später?" — alles drei sind technische Details.

## Konsequenz für meinen Sketch zu `mojo refs`

Die fünf Fragen aus dem Sketch waren überwiegend technische Details. Ab jetzt
entscheide ich:
- Discourse-Klassifikation: drin (Patterns kosten nichts, ermöglichen
  diskursraum-spezifische Vetos).
- Pattern-Datei: nach `journal_bot/data/discourse_patterns.json` ziehen
  (Open-Source-tauglich, einmaliger Cut billiger als spätere Migration).
- Default ohne konfigurierte Quellen: Abbruch mit klarer Anweisung (verhindert
  stille Leerläufe).
- Tests: Akzeptanz-Tests 1–3 (Systemverhalten) + CLI-Tool `mojo refs validate
  <pdf>` als manueller Smoke-Test (kein synthetisches Round-Trip-PDF — echte
  PDFs sind aussagekräftiger).
- Modul-Layout: Package `journal_bot/own_refs/` mit Submodulen statt single
  file (HANDOVER nennt `own_refs.py`, aber die Komplexität rechtfertigt
  Submodule; Public-API über `__init__.py` macht das von außen identisch).

## Verwandte Memories

- [feedback_keine_rueckfragen.md](feedback_keine_rueckfragen.md) — allgemeiner:
  nicht fragen wenn der Schritt offensichtlich ist. Diese Festlegung ist
  Verschärfung für den *technischen* Bereich.
