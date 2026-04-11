# MOJO Workflow-Scripts

Dokumentation der Kern-Workflows für den autonomen Claude-Agenten innerhalb der MOJO-Plattform. Jedes Workflow-Script beschreibt: Trigger, Voraussetzungen, Schrittfolge, Entscheidungspunkte, erwartete Outputs und Kosten.

## Workflows

| # | Workflow | Frequenz | LLM-Kosten | Beschreibung |
|---|----------|----------|------------|--------------|
| 01 | [Journal-Evaluation](01_journal_evaluation.md) | halbjährlich | ~$3 | Watchlist → Scout → Aufnahme + Tier-Zuordnung |
| 02 | [Diskursraum-Pflege](02_diskursraum_pflege.md) | quartalsweise | ~$0.01 | Profile → Crosscut → Suggest → CRUD |
| 03 | [Wöchentlicher Digest](03_woechentlicher_digest.md) | wöchentlich | ~$1.75 | Fetch → Screening → Tier-Agent → DB |
| 04 | [Trend-Analyse](04_trend_analyse.md) | quartalsweise | ~$1.50 | LLM-Trends + Biblio pro Diskursraum |

## Abhängigkeiten

```
01 Journal-Evaluation (+ Tier-Zuordnung A/B/C)
 └→ 02 Diskursraum-Pflege (neue Journals brauchen Cluster)
      └→ 03 Wöchentlicher Digest (regelmäßig)
           └→ 04 Trend-Analyse (wenn genug Daten)
```

## Datendateien

| Datei | Beschreibung | Editiert durch |
|-------|-------------|----------------|
| `journals.json` (v3) | Journal-Registry (Name, Short, ISSN, Typ, **Tier**) | Workflow 01, `mojo journal` |
| `diskursraeume.json` | Diskursraum-Definitionen + Journal-Cluster | Workflow 02, `mojo diskurs` |
| `articles.db` | Alle Artikel (Metadaten, Enrichment, Verdicts, Kosten) | Workflow 03, `mojo fetch/digest` |
| `summaries.json` | Haiku-Summaries als Suchindex (53 Pubs) | `mojo summarize` (einmalig) |
| `corpus.json` | Volltext-Publikationen (74 Pubs, 53 mit Volltext) | `mojo ingest` (einmalig) |
| `zotero_library.json` | Zotero-Gesamtbibliothek (8008 Items) | `corpus.py` Export |
| `docs/journal_watchlist_full.md` | Watchlist aller Kandidaten-Journals | manuell + Workflow 01 |

## CLI-Referenz

```
# --- Digest-Pipeline ---
mojo fetch                              # Artikel holen (kein LLM)
mojo fetch --since 2020                 # Backfill ab Jahr
mojo digest --next N --since 2025       # Tier-differenzierter Agent-Lauf (DeepSeek)
mojo digest --next N --model anthropic/claude-opus-4.6   # mit Opus
mojo digest --doi 10.xxx --journal "X"  # Ad-hoc einzelner Artikel
mojo digest --no-screen                 # Screening überspringen

# --- Analyse ---
mojo trends --cluster KEY               # LLM-Trendanalyse (Opus)
mojo biblio --cluster KEY               # Bibliometrie (kein LLM)
mojo coverage --cluster KEY             # Journal-Zitations-Coverage

# --- Journal-Management ---
mojo scout                              # Journal-Evaluation (Haiku + Opus)
mojo journal list|add|remove            # Journal-Registry

# --- Diskursräume ---
mojo diskurs list|profile|suggest       # Diskursraum-Management
mojo diskurs crosscut                   # Querschnitt-Konzepte (kein LLM)
mojo diskurs add|rename|remove          # Diskursraum-CRUD
mojo diskurs assign|unassign            # Journal-Cluster-Zuordnung

# --- Sonstiges ---
mojo stats                              # Store-Statistik
mojo ingest                             # Zotero → corpus.json (einmalig)
mojo summarize                          # Haiku-Summaries (einmalig)
```

## Architektur

Siehe [ARCHITECTURE.md](../../ARCHITECTURE.md) für die vollständige Systemarchitektur.
