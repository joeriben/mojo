# DEVLOG

## Session 2026-04-09/10 — Initiale Entwicklung

### Gebaut
1. **Corpus-Ingest** aus Zotero-Collection "Benjamin's publications" via lokaler HTTP-API
   - 74 Publikationen ab 2018, 53 mit extrahiertem PDF-Volltext (~967k Tokens)
   - 160 Publikationen gesamt in authored_all (alle Jahre, für Citation-Tracking)
   - Zotero-Datenpfad: `/Users/joerissen/FAUbox/Zotero` (nicht der Default)

2. **Haiku-Summaries** (summaries.json)
   - 53 Publikationen faktisch summarisiert via Claude Haiku 4.5, Tool-Use für JSON-Stabilität
   - Rein deskriptiv: summary_de, key_terms, named_thinkers, methods, cases_examples
   - Kosten: $1.64, ~11 Minuten

3. **Agent-Loop** (Opus 4.6 via OpenRouter)
   - System-Prompt mit allen 53 Summaries als Suchindex (~23k Tokens)
   - Tools: read_publication(pub_id, search_term), submit_digest_entry(...)
   - Prompt-Caching (cache_control ephemeral): Iter 1 schreibt ~33k Tokens, Iter 2+ lesen aus Cache
   - Drei Testläufe:
     - ZfE "Topoi" (neg. Fall): korrekt als IGNORIEREN→SCANNEN bewertet, keine Pseudo-Anschlüsse
     - ZfE "Topoi" v2 (mit bemerkenswert): Foucault+Netzwerkanalyse-Befund korrekt als bemerkenswert erkannt
     - PDSE "Critical GenAI Literacy" (pos. Fall): 4 substanzielle Bezüge mit Volltext-Rückgriff, korrekt SCANNEN

4. **Citation-Tracker**
   - Matching: DOI-exact → Autor+Jahr+Titel-Disambiguierung → Autor-only (Fallback)
   - Gegen authored_all (160 Publikationen, alle Jahre)
   - Null-Fall-verifiziert, Positiv-Fall mit synthetischen Refs verifiziert
   - Wird vor dem Agent-Call in den User-Content injiziert als stärkstes Relevanzsignal

5. **Store** (articles.db, SQLite)
   - Format-agnostische Source of Truth für alle gefetchten + enriched + agent-verarbeiteten Artikel
   - Schema: Metadaten, OpenAlex-Enrichment, Crossref-Refs, Agent-Verdict, Citation-Hits, Kosten

6. **fetch-Kommando** (keine LLM-Kosten)
   - RSS/OJS für ZfE + MedienPaed (latenzfrei)
   - OpenAlex ISSN-Fetcher für 18 weitere Journals (eine API für alle Verlage)
   - 624 Artikel im Store nach initialem Fetch

7. **Trend-Analyse** (LLM-basiert, cluster-scoped)
   - Diskursraum-Konzept: 7 Cluster, Multi-Membership, trends --cluster NAME
   - Erster Lauf auf digitale_kultur (56 Artikel, $0.19): 4 konsolidierende Diskurse, 2 Spannungen, methodische Beobachtungen, Absenzen
   - Schlüsselbefund: "Ästhetische Bildung und kulturelle Bildung sind im Diskursraum Digitale Kultur praktisch absent"

8. **Bibliometrische Analyse** (kein LLM, null Kosten)
   - Crossref-Referenzlisten aggregiert, Erstautor+Titel normalisiert
   - Sortierung nach unique_citing_authors (nicht Roh-Zitationszahl)
   - Trend-Labels nur bei ≥3 Zitationsjahren UND ≥5 Gesamtzitationen
   - Schlüsselbefund: Barad "Meeting the Universe Halfway" ist der stärkste Aufsteiger (11 unique citers, 1:1-Ratio)

### Kosten der Session
- Haiku-Summaries: $1.64
- Agent-Testläufe (3×): ~$4.00
- Trend-Analysen (2×): ~$0.40
- Modell-Tests + Probes: ~$1.50
- **Gesamt: ~$7.50**

### Schlüssel-Designentscheidungen (chronologisch)
1. Haiku für Zusammenfassung, Opus für Interpretation — nicht umgekehrt
2. Summaries sind ein Suchindex, keine Interpretation — Agent liest Volltext live
3. "bemerkenswert" als eigenständige Relevanz-Kategorie neben "bezuege"
4. Diskursräume statt Journal-Gesamtanalyse
5. Unique-Citers statt Roh-Zitationszahl für bibliometrische Robustheit
6. OpenAlex ISSN-Fetcher statt pro-Verlag-Scraper (skaliert)
7. Prompt-Caching über OpenRouter (70–80% Ersparnis bei Batch-Läufen)
