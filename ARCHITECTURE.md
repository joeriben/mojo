# ARCHITECTURE.md — MOJO System Architecture

## Was ist MOJO?

Ein persönlicher Forschungsassistent, der wöchentlich wissenschaftliche Zeitschriften sichtet, jeden Beitrag gegen das publizierte Werk des Nutzers bewertet, und strukturierte Ergebnisse in einer Datenbank ablegt. Gebaut für Benjamin Jörissen (FAU Erlangen-Nürnberg), generalisierbar für andere Forscher*innen.

## Drei Phasen

```
1. INGEST          2. DIGEST              3. REVIEW            4. EXPLORE (geplant)
Zotero → corpus    fetch → screen →       UI: confirm/override Upload Stub →
Haiku → summaries  agent → store          Vertiefen, Export    Retrieval gegen DB
(einmalig)         (wöchentlich)          Zotero, Obsidian     (on demand)
```

---

## Phase 1: Ingest (einmalig + bei Änderung)

### Corpus-Aufbau
```
Zotero-Collection "Benjamin's publications"
        ↓ pyzotero (lokale API)
    corpus.py
        ↓
    corpus.json
    ├── publications[]     — 74 Pubs, 53 mit Volltext (PDF-Extraktion)
    └── authored_all[]     — 160 Pubs (alle Jahre, für Citation-Tracking)
```

### Summaries
```
    corpus.json
        ↓ Haiku 4.5 + Tool-Use ($1.64 einmalig)
    summarize.py
        ↓
    summaries.json
    └── summaries{}        — 53 faktische Kurzprofile
        ├── summary_de     — Was der Text behandelt (keine Interpretation)
        ├── key_terms[]    — 490 Begriffe
        ├── named_thinkers[] — 328 Denker*innen
        └── methods[]
```

**Design-Prinzip**: Summaries sind ein Suchindex, keine Interpretation. Der Agent liest Volltexte live via `read_publication()` wenn er Bezüge verifizieren will.

---

## Phase 2: Digest (wöchentlich)

### Datenfluss

```
28 Journals (journals.json, Tier A/B/C)
        ↓ OpenAlex ISSN-Fetcher / RSS / OJS
    fetch.py + enrichment.py
        ↓ OpenAlex Concepts/Topics + Crossref Refs
    articles.db (17.465+ Artikel)
        ↓
    ┌─────────────────────────────────────────────┐
    │ Phase 0: Vorfilter (null LLM-Kosten)        │
    │  · Junk-Filter (Corrections, Issue Info)     │
    │  · Citation Auto-Pass (→ A-Tier)             │
    │  · Trigger-Autoren Auto-Pass (→ A-Tier)      │
    └─────────────────────────────────────────────┘
        ↓
    ┌─────────────────────────────────────────────┐
    │ Phase 1: DeepSeek Batch-Screening            │
    │  · 40k System-Prompt (gecacht)               │
    │  · Batches à 25 Artikel                      │
    │  · Output: weitergeben|ignorieren pro Artikel │
    │  · ~$0.0005/Artikel                          │
    │  · Filtert ~40% Rauschen                     │
    └─────────────────────────────────────────────┘
        ↓                          ↓
    weitergeben                ignorieren
    (nach Tier aufteilen)      (in DB markieren,
        ↓                      Titel zur User-Sichtung)
    ┌──────────┬──────────┐
    │ A-Tier   │ B-Tier   │  C-Tier: kein Agent
    │ mit Tools│ ohne Tools│
    └──────────┴──────────┘
        ↓
    ┌─────────────────────────────────────────────┐
    │ Phase 2: Agent (DeepSeek V3.2 default)       │
    │                                              │
    │  A-Tier:                                     │
    │   · 40k System-Prompt + Enrichment + Refs    │
    │   · Tools: read_publication, submit_digest   │
    │   · 2-6 Iterationen, Volltext-Verifikation   │
    │   · ~$0.06/Artikel                           │
    │                                              │
    │  B-Tier:                                     │
    │   · 40k System-Prompt + Enrichment           │
    │   · Tool: nur submit_digest_entry            │
    │   · 1 Iteration, aus Summaries inferiert     │
    │   · ~$0.009/Artikel                          │
    └─────────────────────────────────────────────┘
        ↓
    articles.db
    ├── agent_verdict      — pflichtlektuere|lesenswert|scannen|ignorieren
    ├── agent_entry_json   — Kernthese, Bezüge, Bemerkenswert, Verdict
    ├── citation_hits_json — Gefundene Zitationen von Benjamins Werk
    └── cost_usd, tokens_* — Kostentracking
```

### Tier-System

| Tier | Journals | Verfahren | Kosten/Artikel |
|------|----------|-----------|----------------|
| **A** | 8 (ZfE, MedienPaed, PDSE, ZfPaed, DCS, DCE, SAE, JAE) | Agent mit `read_publication` | ~$0.06 |
| **B** | 14 (merz, BDS, BJET, EPT, EduTheory, Discourse, ...) | Agent ohne Tools | ~$0.009 |
| **C** | 6 (AIandSoc, JRTE, LMT, JEE, PCS, DIME) | Nur Screening | ~$0.0005 |

Escalation-Signale (immer → A-Tier, null Kosten):
- Artikel zitiert Benjamin (citation_tracker gegen authored_all)
- Trigger-Autoren (MacGilchrist, Jarke, Wendy Chun)

Modellwahl: DeepSeek V3.2 (Default), Opus 4.6 (Premium), Sonnet 4.6 (Mittelweg) — per `--model` Flag.

---

## Datenmodell

### articles.db (SQLite, Source of Truth)

```sql
articles (
    -- Metadaten (Fetch-Zeit)
    id, journal_short, journal_full, title, authors_json,
    abstract, doi, url, year, published, fetched_at,

    -- Enrichment (Fetch-Zeit, OpenAlex + Crossref)
    openalex_id, openalex_abstract, openalex_concepts,
    openalex_topics, openalex_refs, crossref_refs,
    enrichment_status,

    -- Agent (Digest-Zeit)
    agent_processed_at, agent_verdict, agent_entry_json,
    citation_hits_json,
    tokens_in, tokens_out, tokens_cached_read, tokens_cache_write,
    cost_usd, iterations,

    -- User Review
    user_verdict,       -- NULL = agrees with agent
    user_memo,          -- Freitext-Begründung
    user_verdict_at,

    -- Workflow
    archived_at,        -- aus Digest ausgeblendet
    zotero_key          -- Zotero item key nach Export
)
```

### Konfigurationsdateien (JSON, Agent-editierbar)

| Datei | Inhalt | Version |
|-------|--------|---------|
| `journals.json` | 28 Journals mit name, short, type, url, issn, tier | v3 |
| `diskursraeume.json` | 7 Diskursräume + Journal-Cluster-Zuordnung | v1 |
| `corpus.json` | Benjamins Publikationen + Volltexte | — |
| `summaries.json` | Haiku-Kurzprofile (Suchindex) | — |
| `zotero_library.json` | 8008 Items aus Zotero-Gesamtbibliothek | — |

---

## Module

### Kern-Pipeline

| Modul | Funktion | LLM? |
|-------|----------|------|
| `fetch.py` | RSS/OJS/OpenAlex → articles.db | Nein |
| `enrichment.py` | OpenAlex Concepts/Topics + Crossref Refs | Nein |
| `citation_tracker.py` | Findet Jörissen-Zitate in Referenzlisten | Nein |
| `agent.py` | System-Prompt + Tool-Loop + Batch-Screening | Ja |
| `digest.py` | Orchestriert Agent-Lauf, schreibt in Store | Ja |
| `store.py` | SQLite CRUD, find_unprocessed, update_agent_result | Nein |
| `cli.py` | Argparse CLI, Tier-Logik, Vorfilter | Nein |

### Analyse

| Modul | Funktion | LLM? |
|-------|----------|------|
| `trends.py` | LLM-Trendanalyse pro Diskursraum | Ja |
| `biblio.py` | Bibliometrische Zitationsanalyse (kein LLM) | Nein |
| `diskurs.py` | Diskursraum-CRUD, Profile, Suggest, Crosscut | Teilweise |
| `scout.py` | Multi-Linsen-Journal-Evaluation (Haiku + Opus) | Ja |
| `journal_coverage.py` | Welche Journals werden zitiert aber nicht getrackt? | Nein |
| `signals.py` | Deterministisch: Zotero-Overlap, Keywords, Citations | Nein |

### Infrastruktur

| Modul | Funktion |
|-------|----------|
| `settings.py` | Konstanten, JournalConfig, Diskursraum-Loading |
| `llm_client.py` | OpenRouter-Client mit Key-Flow |
| `corpus.py` | Zotero-Ingest → corpus.json |
| `summarize.py` | Haiku-Summaries → summaries.json |
| `journals.py` | Journal add/remove/list CLI |
| `output.py` | Markdown-Rendering (Legacy, wird durch Web-UI ersetzt) |
| `state.py` | Legacy seen.db (wird nicht mehr genutzt) |
| `zotero_export.py` | Export → Zotero via Connector-API |
| `obsidian_export.py` | Export → Obsidian Markdown mit Frontmatter |

### Web-UI

| Modul | Funktion |
|-------|----------|
| `web/app.py` | Flask-App, alle Routes + HTMX-Endpoints |
| `web/templates/` | Jinja2-Templates (Digest, Artikel, Diskurs, Review, Overrides, Suche) |

---

## Agent-Architektur

### System-Prompt (~24k Tokens)

Enthält alle 53 Publikationsprofile (sortiert nach Jahr), plus:
- Zwei Arten von Relevanz (inhaltlich + Beobachtung 2. Ordnung)
- Short-Circuit-Instruktion (sofort `submit_digest_entry` bei offensichtlichem "ignorieren")
- Regeln für Bezüge (nur aus gelesenem Volltext zitieren)

### Tools

| Tool | A-Tier | B-Tier | Funktion |
|------|--------|--------|----------|
| `read_publication(pub_id, search_term)` | Ja | Nein | Lädt Benjamins Volltext (~16k Zeichen) |
| `submit_digest_entry(...)` | Ja | Ja | Strukturierter Digest-Eintrag |

### Prompt-Caching

System-Prompt wird via OpenRouter `cache_control: ephemeral` gecacht (5-Min-TTL). Bei Batch-Läufen liest jeder Call aus dem Cache statt 24k Tokens neu zu verarbeiten.

---

## Phase 3: Review (Web-UI)

### Stack
Flask + Jinja2 + HTMX. Kein JS-Framework, kein Build-Step. SQLite direkt. `mojo.localhost:5555` (eigener Hostname trennt Cookies & Passwort-Manager von anderen `localhost:*`-Apps; `*.localhost` löst per RFC 6761 ohne `/etc/hosts` auf 127.0.0.1 auf).

### Ansichten

| Route | Funktion |
|-------|----------|
| `/` | **Digest**: Lesenswert aufgeklappt, Zitiert-Dich, Scannen kompakt, Ignorieren zugeklappt. Filter: Jahr, Diskursraum, Journal, Verdict |
| `/article/<id>` | **Artikeldetail**: Verdict-Controls, Kernthese, Bezüge, Bemerkenswert, Meta-Footer, Aktionen |
| `/review` | **Review-Queue**: Unbestätigte Artikel (user_verdict IS NULL), sortiert nach Relevanz |
| `/overrides` | **Overrides**: Upgrades vs. Downgrades mit Memo → Input für Prompt-Optimierung |
| `/diskurs` | **Diskursräume**: Übersicht mit Verdict-Balken |
| `/diskurs/<key>` | **Diskursraum-Detail**: Journals, Analysen (Profil, Biblio, Trends) |
| `/search?q=` | **Suche**: Titel-Volltextsuche, max 100 Treffer |

### User-Verdict-System

```
effective_verdict = user_verdict ?? agent_verdict

Aktionen:
  OK       → user_verdict = agent_verdict (bestätigt, ✓ im Badge)
  Override → user_verdict = neues Verdict (altes durchgestrichen)
  Memo     → user_memo (Freitext, für spätere Revision/Prompt-Tuning)
  Reset    → user_verdict = NULL (zurück in Review-Queue)
```

### Vertiefen (On-Demand)

```
Shallow-Artikel (cost < $0.02 oder keine Bezüge)
        ↓ Button "Vertiefen" oder Auto bei Upgrade auf Lesenswert
    assess_then_verify (Opus, ~$0.05)
        ↓
    Neues agent_entry_json (altes als _previous gestasht)
```

### Export

| Aktion | Mechanismus | Ziel |
|--------|-------------|------|
| **→ Zotero** | Connector-API (`/connector/saveItems`), Item + Child-Note | Collection "mojo" |
| **→ Obsidian** | Markdown + YAML-Frontmatter | `DIGEST_DIR/<verdict>/slug.md` |
| **Archivieren** | Toggle `archived_at` | Artikel aus Digest ausblenden |

### Hover-Tooltips
Lazy-loaded per HTMX (`mouseenter once` → `/api/tooltip/<id>`). Zeigt Verdict-Begründung + Kernthese ohne Klick.

---

## Geplant (Phase 4)

### Dialogischer Research-Agent
- Stub/Entwurf hochladen → Frage stellen → Retrieval gegen DB
- "Missed References"-Detektor: welche relevanten Bezüge fehlen?
- Architektur-Vorlage: transact-qda

---

## Kostenstruktur

### Einmalig
- Haiku-Summaries: $1.64 (53 Publikationen)
- Scout-Volllauf: $2.53 (49 Journals)

### Pro Digest-Lauf (wöchentlich, ~50 neue Artikel)
- Screening: ~$0.03
- A-Tier Agent: ~$1.50 (25 Artikel × $0.06)
- B-Tier Agent: ~$0.23 (25 Artikel × $0.009)
- **Gesamt: ~$1.75/Woche**

### Großer Backfill-Run (2025+, einmalig)
- 2.954 Artikel: ~$16–32 je nach Trefferquote
