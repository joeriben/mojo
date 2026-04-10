# ROADMAP

## Phase 5b — Journals erweitern (vor Backfill!)
- [ ] Journals aus docs/journal_watchlist_full.md schrittweise hinzufügen
  - Priorität WICHTIG: Studies in Art Education, IJADE, Review of Education/Pedagogy/Cultural Studies, BJET, Environmental Education Research, Ethics and Education, Oxford Review of Education, Big Data and Society, Arts and Humanities in Higher Education, Frontiers in AI
  - Sonderfälle (Scraper nötig): e-flux Journal, zkmb.de
- [ ] ZfPäd, ZfM, VjwP als HTML-Scraper oder via OpenAlex prüfen
- [ ] OpenAlex-Pagination einbauen (max_results-Deckel entfernen, cursor-based paging)

## Phase 5c — Historical Backfill
- [ ] Erst NACH Phase 5b (sonst unvollständiger Backfill)
- [ ] OpenAlex-Window auf 3 Jahre erweitern, Pagination nötig
- [ ] Crossref-ISSN-Suche als Alternative für Journals ohne OpenAlex-Coverage
- [ ] OJS-Archivseiten für MedienPaed historisch crawlen

## Qualitätsverbesserungen
- [ ] Biblio: Autor-Fallback für Sammelbände (leere Erst-Autoren bei Editionen)
- [ ] Biblio: DOI-Validierung in der Anzeige (abgeschnittene DOIs nicht als gültig darstellen)
- [ ] Biblio: Dedup-Verbesserung (DOI-basierte Normalisierung wenn DOI vorhanden)
- [ ] Biblio: Aggregation über mehrere Normalisierungsvarianten desselben Werks
- [ ] Summarize: Qualitätsprüfung der 53 Summaries (stichprobenartig, Benjamin)
- [ ] Agent: Feedback-Loop (Benjamin markiert Digest-Einträge als nützlich/daneben → persistent in DB)

## Ausgabe-Schichten
- [ ] Obsidian: ggf. durch anderes System ersetzen (Benjamin findet Obsidian "nerdig")
- [ ] Zotero-Writeback: Digest-Verdict + Kommentar als Note/Extra-Feld in "mojo digest"-Collection via pyzotero
- [ ] Markdown-Export: auch ohne Obsidian nutzbar als Dateiablage

## Infrastruktur
- [ ] launchd-Setup für wöchentliche Ausführung (fetch automatisch, digest ggf. manuell)
- [ ] Token-Logging in DB (pro Call: model, tokens_in, tokens_out, cost, timestamp)
- [ ] Kosten-Budget-Check (optional: monatliches Limit, Warnung bei Überschreitung)
- [ ] Git-Repo anlegen, .gitignore prüfen (corpus.json, summaries.json, articles.db, seen.db, .env, *.key)

## Architektur (bei Bedarf)
- [ ] Embedding-Retrieval über Summaries (sentence-transformers lokal) — nur wenn Corpus >200 Publikationen oder Agent-Qualität nachlässt
- [ ] Delegation-first-Pattern aus transact-qda: Haiku als Vorsortierung pro Artikel, Opus nur für Kandidaten mit positiver Haiku-Einschätzung — relevant bei >50 Artikeln/Woche
- [ ] Anthropic Batch API (50% Rabatt) für wöchentliche Batch-Digest-Läufe

## Namensfindung
- [ ] Projekt braucht einen Namen und ein Akronym — offen, bisherige Vorschläge waren zu generisch
