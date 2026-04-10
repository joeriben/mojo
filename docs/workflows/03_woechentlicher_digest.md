# Workflow: Wöchentlicher Digest

## Zweck
Neue Artikel aus allen getrackten Journals holen, gegen Benjamins Publikationen bewerten, und einen Digest für Obsidian produzieren.

## Trigger
- Wöchentlich (via launchd oder manuell)
- Ad-hoc bei konkretem Interesse an einem Artikel

## Voraussetzungen
- `journals.json` + `diskursraeume.json` konfiguriert
- `summaries.json` existiert (Haiku-Summaries als Suchindex)
- `corpus.json` existiert (Volltext-Zugriff für den Agenten)
- OpenRouter API-Key

## Schritte

### 1. Artikel fetchen
```bash
mojo fetch
```
- Keine LLM-Kosten
- Holt neue Artikel via RSS/OJS/OpenAlex
- Enrichment: DOI → OpenAlex-Metadaten + Crossref-Referenzlisten
- Output: Neue Einträge in `articles.db`

Prüfe im Output:
- Liefern alle Journals Artikel? (0 Einträge = mögliches Problem)
- Enrichment-Fehler?

### 2. Agent-Lauf (Batch)
```bash
# Nächste N unverarbeitete Artikel bewerten
mojo digest --next 20

# Optional: nur bestimmte Journals
mojo digest --next 10 --journals ZfE,PDSE,SAE

# Ad-hoc: einzelnen Artikel per DOI
mojo digest --doi 10.1234/example --journal "Journal Name"
```
- Kosten: ~$0.50–1.00 pro Artikel (Opus, mit Prompt-Caching ab Artikel 2)
- Der Agent hat Zugriff auf:
  - Alle 53 Haiku-Summaries als Suchindex (~23k Tokens)
  - `read_publication(pub_id, search_term)` für Volltext-Zugriff
  - `submit_digest_entry(...)` für strukturierte Bewertung
- Citation-Tracker läuft automatisch VOR dem Agent-Call

### 3. Ergebnis prüfen
```bash
mojo stats
```
Zeigt:
- Anzahl verarbeiteter Artikel
- Verdict-Verteilung (LESEN / SCANNEN / IGNORIEREN / bemerkenswert)
- Kosten

### 4. Digest in Obsidian
Output liegt automatisch unter:
`~/Documents/Obsidian Vault/research/mojo/digest_<datum>.md`

## Kostenmanagement
- Prompt-Caching: Erste Iteration schreibt ~33k Tokens in Cache, Folge-Iterationen lesen → 70–80% günstiger
- Batch-Größe: 20 Artikel pro Run ist ein guter Kompromiss
- Bei Budgetgrenzen: `--journals` Flag nutzen, um teure High-Volume-Journals (BJET, BDS) seltener zu verarbeiten

## Kosten
- Fetch: $0
- Digest (20 Artikel): ~$5–10 (abhängig von Volltext-Reads)
- Gesamtbudget wöchentlich: ~$10–15
