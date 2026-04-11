# Workflow: Wöchentlicher Digest

## Zweck
Neue Artikel aus allen getrackten Journals holen, nach Tier differenziert bewerten, Ergebnisse in `articles.db` speichern.

## Trigger
- Wöchentlich (via launchd oder manuell)
- Ad-hoc bei konkretem Interesse an einem Artikel

## Voraussetzungen
- `journals.json` mit Tier-Zuordnung (A/B/C)
- `summaries.json` existiert (Haiku-Summaries als Suchindex)
- `corpus.json` existiert (Volltext-Zugriff für A-Tier)
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

### 2. Digest-Lauf (Batch)
```bash
# Standard: aktuelle Artikel, DeepSeek als Agent
mojo digest --next 50 --since 2025

# Nur A-Tier-Journals
mojo digest --next 50 --since 2025 --journals ZfE,MedienPaed,PDSE

# Ad-hoc: einzelner Artikel per DOI
mojo digest --doi 10.1234/example --journal "Journal Name"

# Mit Opus statt DeepSeek (Premium)
mojo digest --next 50 --since 2025 --model anthropic/claude-opus-4.6

# Screening überspringen (alle direkt zum Agent)
mojo digest --next 50 --no-screen
```

### Was die Pipeline intern tut

```
Phase 0: Vorfilter (null Kosten)
  · Junk entfernen (Corrections, Issue Info, Errata)
  · Citation Auto-Pass: Artikel die Benjamin zitieren → direkt A-Tier
  · Trigger-Autoren Auto-Pass: MacGilchrist, Jarke, Chun → direkt A-Tier

Phase 1: DeepSeek Batch-Screening (~$0.0005/Artikel)
  · 40k System-Prompt (Benjamins Pub-Index, gecacht)
  · Batches à 25 Artikel: weitergeben|ignorieren
  · Aussortierte Titel werden angezeigt (User-Sichtung)
  · Filtert ~40% Rauschen

Phase 2: Agent-Analyse (differenziert nach Tier)
  A-Tier: DeepSeek mit Tools ($0.06/Artikel)
    · read_publication + submit_digest_entry
    · 2-6 Iterationen, Volltext-Verifikation
    · Verifizierte Bezüge mit Textbelegen

  B-Tier: DeepSeek ohne Tools ($0.009/Artikel)
    · Nur submit_digest_entry (kein read_publication)
    · 1 Iteration, Einschätzung aus Summaries
    · Kernthese + Verdict, Bezüge aus Pub-Index inferiert

  C-Tier: Kein Agent
    · Nur das Screening-Ergebnis
    · Escalation bei Citation-Hits oder Trigger-Autoren
```

### 3. Ergebnis prüfen
```bash
mojo stats
```

### 4. Ergebnisse sichten

Alle Ergebnisse in `articles.db`:
- `agent_verdict`: pflichtlektuere | lesenswert | scannen | ignorieren
- `agent_entry_json`: Kernthese, Bezüge, Bemerkenswert, Verdict-Begründung
- `citation_hits_json`: Gefundene Zitationen von Benjamins Werk
- `cost_usd`: Tatsächliche Kosten pro Artikel

Perspektivisch: Web-UI mit strukturierter Ablage, Zotero-1-Click, Escalation-Button.

## Tier-System

| Tier | Journals | Verfahren | Kosten/Artikel |
|------|----------|-----------|----------------|
| **A** | ZfE, MedienPaed, PDSE, ZfPaed, DCS, DCE, SAE, JAE | Agent mit read_publication | ~$0.06 |
| **B** | merz, BDS, BJET, EPT, EduTheory, Discourse, EERJ, STHV, ... | Agent ohne Tools | ~$0.009 |
| **C** | AIandSoc, JRTE, LMT, JEE, PCS, DIME | Nur Screening | ~$0.0005 |

Tier-Zuordnung in `journals.json` (Feld `tier`). Änderbar per Editor oder zukünftig per Agent-Vorschlag.

## Escalation-Signale (null LLM-Kosten, immer → A-Tier)
- **Zitiert Benjamin**: citation_tracker gegen authored_all (160 Pubs)
- **Trigger-Autoren**: MacGilchrist, Jarke, Wendy Chun (erweiterbar)

## Modellwahl
- **DeepSeek V3.2** (Default): $0.06/Artikel A-Tier, bestes Preis/Leistungs-Verhältnis
- **Opus 4.6** (Premium): $0.44/Artikel, höchste Qualität bei verifizierten Bezügen
- **Sonnet 4.6** (Mittelweg): noch zu benchmarken

## Kosten
- Wöchentlich (~50 neue Artikel): ~$1.75
- Großer Backfill-Run (2.954 Artikel, 2025+): ~$16–32
