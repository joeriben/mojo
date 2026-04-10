# CLAUDE.md — Projektkontext für Claude Code Sessions

## Was ist dieses Projekt?
Ein persönlicher Forschungsassistent für Benjamin Jörissen (FAU Erlangen-Nürnberg, Allgemeine Pädagogik / ästhetische & kulturelle Bildung). Der Bot sichtet wöchentlich wissenschaftliche Zeitschriften, bewertet jeden Beitrag gegen Benjamins publiziertes Werk, und produziert Digest-Einträge + Trend-Analysen.

## Architektur-Kern
- Haiku-Summaries der eigenen Publikationen als Suchindex (summaries.json, ~40k tokens)
- Opus-Agent mit Tool-Use (read_publication, submit_digest_entry) für Live-Interpretation
- OpenAlex ISSN-Fetcher für 20 Journals, Crossref für Referenzlisten
- Citation-Tracker gegen authored_all (160 Publikationen, alle Jahre)
- Prompt-Caching via OpenRouter (cache_control ephemeral)
- Diskursraum-basierte Trend-Analyse (LLM + bibliometrisch)

## Wichtige Pfade
- Zotero-Daten: `/Users/joerissen/FAUbox/Zotero` (NICHT ~/Zotero)
- Zotero-Collection: "Benjamin's publications" (key QM7TZT44)
- Obsidian-Vault: `/Users/joerissen/Documents/Obsidian Vault/research/mojo/`
- API-Key: `~/.config/mojo/openrouter_key` (chmod 600)
- Store: `articles.db` im Projektordner
- Corpus: `corpus.json` + `summaries.json` im Projektordner

## Konventionen
- Deutsch im User-Facing-Output (Digest, Trends, CLI-Meldungen)
- Englisch im Code (Variablen, Docstrings, Kommentare)
- Keine Config-Dateien: Konstanten in settings.py, Override per CLI-Flag
- Kein Over-Engineering: einfachste Lösung zuerst, komplexer nur bei Bedarf
- Kosten transparent: jeder LLM-Call wird in der Ausgabe mit Tokens + $ geloggt

## Was NICHT tun
- Keine .env-Dateien vorschreiben (User kennt das Konzept nicht / will es nicht)
- Keine Zotero-Collections manuell anlegen lassen
- Keine Multi-Step-Setup-Anleitungen (Bot fragt interaktiv, wenn was fehlt)
- Keine Trend-Analyse über ALLE Journals gleichzeitig (→ Diskursräume!)
- Keine Trend-Labels bei <3 Zitationsjahren oder <5 Gesamtzitationen
- Keine "theoretische Verortung" in Haiku-Summaries (das ist Interpretation, nicht Zusammenfassung)

## Diskursräume (in settings.py definiert)
deutsche, erziehungswiss, digitale_kultur, medienpaed, bildungstheorie,
aesthetische_kulturelle_bildung, resilienz

## Offene Sonderfälle
- zkmb.de (nicht in OpenAlex, Scraper nötig)
- e-flux Journal (nicht in OpenAlex, Scraper nötig, stabile /journal/<nr>/ Struktur)
- Vollständige Journal-Watchlist: docs/journal_watchlist_full.md
