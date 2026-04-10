# MOJO Workflow-Scripts

Dokumentation der Kern-Workflows für den autonomen Claude-Agenten innerhalb der MOJO-Plattform. Jedes Workflow-Script beschreibt: Trigger, Voraussetzungen, Schrittfolge, Entscheidungspunkte, erwartete Outputs und Kosten.

## Workflows

| # | Workflow | Frequenz | LLM-Kosten | Beschreibung |
|---|----------|----------|------------|--------------|
| 01 | [Journal-Evaluation](01_journal_evaluation.md) | halbjährlich | ~$3 | Watchlist → Scout → Aufnahme |
| 02 | [Diskursraum-Pflege](02_diskursraum_pflege.md) | quartalsweise | ~$0.01 | Profile → Crosscut → Suggest → CRUD |
| 03 | [Wöchentlicher Digest](03_woechentlicher_digest.md) | wöchentlich | ~$10 | Fetch → Agent-Bewertung → Obsidian |
| 04 | [Trend-Analyse](04_trend_analyse.md) | quartalsweise | ~$1.50 | LLM-Trends + Biblio pro Diskursraum |

## Abhängigkeiten

```
01 Journal-Evaluation
 └→ 02 Diskursraum-Pflege (neue Journals brauchen Cluster)
      └→ 03 Wöchentlicher Digest (regelmäßig)
           └→ 04 Trend-Analyse (wenn genug Daten)
```

## Datendateien

| Datei | Beschreibung | Editiert durch |
|-------|-------------|----------------|
| `journals.json` | Journal-Registry (Name, Short, ISSN, Typ) | Workflow 01, `mojo journal` |
| `diskursraeume.json` | Diskursraum-Definitionen + Journal-Cluster | Workflow 02, `mojo diskurs` |
| `articles.db` | Alle Artikel (Metadaten, Verdicts, Kosten) | Workflow 03, `mojo fetch/digest` |
| `summaries.json` | Haiku-Summaries als Suchindex | `mojo summarize` (einmalig) |
| `corpus.json` | Volltext-Publikationen | `mojo ingest` (einmalig) |
| `docs/journal_watchlist_full.md` | Watchlist aller Kandidaten-Journals | manuell + Workflow 01 |

## CLI-Referenz

```
mojo fetch                          # Artikel holen (kein LLM)
mojo digest --next N                # Agent-Bewertung (Opus)
mojo scout                          # Journal-Evaluation (Haiku + Opus)
mojo trends --cluster KEY           # LLM-Trendanalyse (Opus)
mojo biblio --cluster KEY           # Bibliometrie (kein LLM)
mojo journal list|add|remove        # Journal-Registry
mojo diskurs list|profile|suggest   # Diskursraum-Management
mojo diskurs crosscut               # Querschnitt-Konzepte (kein LLM)
mojo diskurs add|rename|remove      # Diskursraum-CRUD
mojo diskurs assign|unassign        # Journal-Cluster-Zuordnung
mojo stats                          # Store-Statistik
mojo coverage --cluster KEY         # Journal-Zitations-Coverage
```
