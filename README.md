# MOJO — Monitoring Journals

**UCDCAE AI Lab: MOJO** — *Periodic discourse monitoring, analysis, and scholarly positioning.*

## Problem

Academic researchers — especially in theory-heavy and highly transdisciplinary fields like Allgemeine Pädagogik, Cultural/Aesthetic Education, and Postdigital Studies — face a persistent problem: the volume of new publications across 20+ relevant journals exceeds what can be manually sighted. This task requires deep domain knowledge and substantial time. Neither generic alerting services (Google Scholar alerts) nor simple keyword filters provide the depth of engagement needed for substantive academic sighting (*Sichtung*).

## Goals

1. **Per-article digest entries** that go beyond "relevant because keyword X" — each entry positions a new publication against the researcher's own published work, identifies specific tensions/extensions/parallels, and flags methodologically or phenomenologically noteworthy moves even when direct topical relevance is low.

2. **Citation tracking**: automatic detection when new publications cite the researcher's own work — the strongest relevance signal.

3. **Discourse-level trend analysis** per curated *Diskursraum* (discourse space): thematic consolidation, divergence, emerging methods, absences. Both LLM-based (thematic) and bibliometric (citation-frequency, non-LLM).

4. **Minimal operational overhead**: weekly `fetch` (free, no LLM) + periodic `digest` and `trends` runs. No complex config files, no server infrastructure, runs on a Mac via launchd.

## Core Design Decisions

### Agent Architecture (3-layer)
- **Haiku summaries** (factual, non-interpretive, ~120 words each) of the researcher's own publications serve as a **search index** — always in the agent's context. No interpretation baked in; the summaries tell the agent WHAT each paper discusses, not what it MEANS.
- **Opus agent with tool-use** does the actual interpretive work LIVE: reads the new article + enrichment data, selects 2–5 own publications from the index, reads their FULL TEXT via `read_publication()` tool, then produces a grounded digest entry. The agent cites only what it has actually read.
- **Prompt caching** (Anthropic ephemeral cache via OpenRouter) reduces repeated input costs across multi-iteration agent runs and batch processing.

### Three Categories of Relevance
1. **Bezüge** (substantive connections): explicit links to the researcher's own arguments, grounded in full-text reading. Relation types: *erweitert, widerspricht, parallelisiert, importiert, tangential*.
2. **Bemerkenswert** (second-order observations): methodological or phenomenological moves worth knowing about even when direct topical overlap is low — e.g., "someone applies Foucaultian discourse analysis with distributional semantics tools".
3. **Citation hits**: new publications that cite the researcher's own work, detected via DOI matching and author-name heuristics against the full publication list.

### Discourse Spaces (*Diskursräume*)
Journals are grouped into curated discourse spaces (e.g., *digitale_kultur*, *bildungstheorie*, *medienpaed*, *resilienz*). A journal can belong to multiple spaces. Trend analysis runs PER discourse space, not across all journals — mixing ZfE (empirical educational research) with e-flux (art theory) produces noise, not insight.

### Fetcher Architecture
- **RSS/OJS** for latency-free feeds (ZfE, MedienPaed)
- **OpenAlex ISSN-based** for everything else — one API, all publishers, enrichment included. Covers Taylor & Francis, Springer, Wiley, Sage, smaller publishers. Indexing lag ~1–4 weeks, acceptable for weekly sighting.
- **Manual scrapers** (future) for non-indexed sources: e-flux Journal, zkmb.de.

### Bibliometric Analysis (non-LLM)
Citation-frequency ranking from Crossref reference lists: which works are most cited across a discourse space? Sorted by **unique citing authors** (not raw citation count) to control for prolific self-citers. Trend labels only when statistical basis exists (≥3 citing years, ≥5 total citations).

### Store
`articles.db` (SQLite) is the format-agnostic source of truth. Obsidian markdown and potential Zotero writeback are rendering layers, not storage.

## Technology Stack

- **Python 3.10+**, plain venv (no framework dependencies)
- **OpenRouter** as LLM gateway (OpenAI-compatible API, supports Claude tool-use + prompt caching)
- **Claude Haiku 4.5** for corpus summarization
- **Claude Opus 4.6** for agent reasoning + trend analysis
- **OpenAlex API** (free, polite pool) for journal fetching + enrichment
- **Crossref API** (free) for reference lists + citation tracking
- **SQLite** for article store + dedup state
- **pyzotero** (local HTTP API) for Zotero corpus ingest
- **pypdf** for PDF text extraction
- **feedparser** for RSS/OJS feeds

## CLI Commands

```
mojo ingest      # Zotero → corpus.json (one-time, no LLM)
mojo summarize   # corpus → summaries.json (one-time, ~$2 Haiku)
mojo fetch       # Feeds → articles.db (weekly, no LLM)
mojo digest      # Agent run: --doi X or --next N (per article ~$0.50-$1)
mojo trends      # LLM discourse analysis: --cluster NAME (~$0.20)
mojo biblio      # Citation-frequency analysis: --cluster NAME (free)
mojo stats       # Store statistics
```

## Project Status

Working prototype. Core pipeline (ingest → summarize → fetch → digest → trends → biblio) is functional end-to-end. 20 journals configured, 624 articles in store. See ROADMAP.md for open items.

## Setup

See the step-by-step in DEVLOG.md (Session 2026-04-09/10).
