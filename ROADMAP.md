# ROADMAP

## ✓ Erledigt
- [x] OpenAlex-Pagination (cursor-based paging)
- [x] Journal-Coverage-Analyse (welche Journals werden zitiert aber nicht getrackt?)
- [x] Scout (Watchlist-Evaluation via Haiku)
- [x] Rename journal-bot → mojo
- [x] Diskursraum-Management (CRUD, Profiling, Discovery, diskursraeume.json)
- [x] Multi-Linsen-Scout (3× Haiku + Opus-Synthese, Positionalitäts-Report)
- [x] Namensfindung → MOJO (Monitoring Journals)

## Nächste Schritte — UI / Workflow

### Journal-Aufnahme-Workflow
Aktuell: Scout empfiehlt "aufnehmen" → manuell in settings.py eintragen.
Gebraucht: Interaktiver Flow nach Scout-Lauf.
- [ ] `mojo scout --interactive`: Nach Evaluation Journal direkt aufnehmen (ISSN, Typ, Cluster)
- [ ] Oder: `mojo journal add <name>` mit ISSN-Autodetection + Cluster-Vorschlag aus Scout
- [ ] Sonderfälle: zkmb.de, e-flux (Scraper nötig, nicht via OpenAlex)

### Obsidian / Ausgabe
- [ ] Obsidian-Output überdenken (Benjamin findet Obsidian "nerdig")
- [ ] Alternative: einfache HTML-Reports? Zotero-Writeback? E-Mail-Digest?

## Phase 5b — Journals erweitern
- [ ] Journals aus docs/journal_watchlist_full.md via Scout prüfen (voller Lauf)
- [ ] Priorität WICHTIG: Studies in Art Education, IJADE, Review of Education/Pedagogy/Cultural Studies, BJET, Environmental Education Research, Ethics and Education
- [ ] ZfPäd, ZfM, VjwP aufnehmen (Scout sagt: aufnehmen/beobachten)

## Phase 5c — Historical Backfill
- [ ] Erst NACH Phase 5b (sonst unvollständiger Backfill)
- [ ] OpenAlex-Window auf 3 Jahre erweitern
- [ ] Crossref-ISSN-Suche als Alternative für Journals ohne OpenAlex-Coverage

## Qualitätsverbesserungen
- [ ] Biblio: Autor-Fallback für Sammelbände
- [ ] Biblio: DOI-Validierung, Dedup-Verbesserung
- [ ] Summarize: Qualitätsprüfung der 53 Summaries (stichprobenartig)
- [ ] Agent: Feedback-Loop (Digest-Einträge als nützlich/daneben markieren → DB)

## Diskursraum-Weiterentwicklung
- [ ] Positionalitäts-Report auf bereits getrackte Journals anwenden (nicht nur Kandidaten)
- [ ] `mojo diskurs profile --deep` (Haiku-Interpretation des Datenprofils)
- [ ] Testfall "Kulturelle Bildung / Arts Education" durchspielen

## Infrastruktur
- [ ] launchd-Setup für wöchentliche Ausführung
- [ ] Token-Logging in DB (pro Call: model, tokens_in, tokens_out, cost, timestamp)
- [ ] Kosten-Budget-Check (optional)

## Architektur (bei Bedarf)
- [ ] Delegation-first: Haiku als Vorsortierung, Opus nur für Kandidaten — relevant bei >50 Artikeln/Woche
- [ ] Anthropic Batch API (50% Rabatt) für wöchentliche Batch-Digest-Läufe
