# ROADMAP

## ✓ Erledigt
- [x] OpenAlex-Pagination (cursor-based paging)
- [x] Journal-Coverage-Analyse (welche Journals werden zitiert aber nicht getrackt?)
- [x] Scout (Watchlist-Evaluation via Haiku)
- [x] Rename journal-bot → mojo
- [x] Diskursraum-Management (CRUD, Profiling, Discovery, diskursraeume.json)
- [x] Multi-Linsen-Scout (3× Haiku + Opus-Synthese, Positionalitäts-Report)
- [x] Namensfindung → MOJO (Monitoring Journals)
- [x] Phase 5b: Scout-Volllauf (49 Journals), 8 aufgenommen (ZfPaed, EthicsEd, REPCS, SAE, BJET, JAC, BDS, STHV)
- [x] Phase 5c: Historical Backfill (`mojo fetch --since 2016`, 17.465 Artikel, 10 Jahre, alle 28 Journals)
- [x] Journal-Aufnahme-Workflow: journals.json + `mojo journal add/list/remove`
- [x] Testfall "Kulturelle Bildung" (aesthetische_kulturelle_bildung: 3→6 Journals)
- [x] Workflow-Scripts für autonomen Agenten (docs/workflows/)

## Nächste Schritte

### Erster Digest-Lauf
- [ ] `mojo digest --next 20` auf den neuen Journals testen
- [ ] Haiku-Triage verifizieren (filtert irrelevante Artikel vor Opus)
- [ ] Kosten und Qualität der Verdicts prüfen

### Trend-Analyse
- [ ] `mojo trends --cluster aesthetische_kulturelle_bildung` (jetzt 6 Journals, genug Substanz)
- [ ] `mojo biblio --cluster aesthetische_kulturelle_bildung` (10 Jahre Daten)
- [ ] Alle 7 Räume durchlaufen

### Open-Source-Vorbereitung
- [ ] Pfade abstrahieren (Zotero-Pfad, Obsidian-Vault → Konfigurierbar)
- [ ] API-Key-Management generalisieren
- [ ] README für externe Nutzer
- [ ] Watchlist-✓ automatisieren bei `mojo journal add`

### Obsidian / Ausgabe
- [ ] Obsidian-Output überdenken (Benjamin findet Obsidian "nerdig")
- [ ] Alternative: einfache HTML-Reports? Zotero-Writeback? E-Mail-Digest?

## Qualitätsverbesserungen
- [ ] Biblio: Autor-Fallback für Sammelbände
- [ ] Biblio: DOI-Validierung, Dedup-Verbesserung
- [ ] Summarize: Qualitätsprüfung der 53 Summaries (stichprobenartig)
- [ ] Agent: Feedback-Loop (Digest-Einträge als nützlich/daneben markieren → DB)

## Diskursraum-Weiterentwicklung
- [ ] Positionalitäts-Report auf bereits getrackte Journals anwenden (nicht nur Kandidaten)
- [ ] `mojo diskurs profile --deep` (Haiku-Interpretation des Datenprofils)

## Infrastruktur
- [ ] launchd-Setup für wöchentliche Ausführung
- [ ] Token-Logging in DB (pro Call: model, tokens_in, tokens_out, cost, timestamp)
- [ ] Kosten-Budget-Check (optional)
- [ ] Sonderfälle: zkmb.de, e-flux (Scraper nötig, nicht via OpenAlex)

## Architektur (bei Bedarf)
- [ ] Delegation-first: Haiku als Vorsortierung, Opus nur für Kandidaten — relevant bei >50 Artikeln/Woche
- [ ] Anthropic Batch API (50% Rabatt) für wöchentliche Batch-Digest-Läufe
