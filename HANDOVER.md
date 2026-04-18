# MOJO — Übergabe-Dokumentation

Dieses Dokument fasst den Projektzustand und die relevanten Arbeitskontexte zusammen, damit die Arbeit an MOJO mit einem anderen Coding-Assistenten (GPT Codex o.ä.) fortgesetzt werden kann.

Stand: 2026-04-15

---

## 1. Projekt in Kürze

**Zweck:** Persönlicher Forschungsassistent für Benjamin Jörissen (FAU Erlangen-Nürnberg, Allgemeine Pädagogik / ästhetische & kulturelle Bildung). Wöchentliche Sichtung von ~20 Journals, Bewertung jedes Beitrags gegen Benjamins publiziertes Werk (160 Publikationen), strukturierte Digest-Einträge + Trend-Analysen.

**Aktueller Stand:**
- 17.601 Artikel in DB, 15.929 davon Agent-verarbeitet
- 53 Opus-Summaries von Benjamins Publikationen als Suchindex
- 5 aktive Forschungsprojekte in `projects.json`
- Gesamtkosten DB: $47.04

**Technik-Stack:**
- Python 3.10
- OpenRouter-API (Claude Opus 4.6 für Agent, DeepSeek v3.2 für Screening, Haiku für Triage-on-no-abstract)
- SQLite (articles.db)
- Flask + HTMX (Web-UI, Port 5555)
- OpenAlex + Crossref (Enrichment)

---

## 2. Architektur-Überblick

### Retrieval-Pipeline (`journal_bot/fetch.py`)

1. **Fetcher** je nach Journal-Typ: RSS / OJS / HTML / OpenAlex / DCE / Custom
2. **Enrichment** pro DOI: OpenAlex (Abstract, Concepts, Topics, Refs) + Crossref (vollständige Referenzliste)
3. **Persistierung** in `articles.db`

### Triage-Pipeline (mehrstufig, kostenoptimiert)

```
Artikel aus articles.db (unverarbeitet)
  │
  ├── Phase 0: Vorfilter (kein LLM)
  │   - Junk-Filter (Editorials, Corrections)
  │   - Kein-Abstract-Filter + Catchword-Match
  │   - Citation Auto-Pass (zitiert Benjamin)
  │   - Trigger-Autoren (MacGilchrist, Jarke, Chun)
  │
  ├── Phase 1: Batch-Screening (DeepSeek v3.2, 25er-Batches)
  │   - System-Prompt: alle 53 Summaries + triage_topics (cached)
  │   - Verdict: weitergeben | ignorieren
  │
  ├── Tier-Split
  │   - C-Tier → verdict="scannen", Ende
  │   - A/B-Tier → Phase 3
  │
  └── Phase 3: Assess-then-Verify (Opus 4.6)
      - Assessment (kein Volltext): Verdict + optionale candidate_reads
      - Verification (nur bei candidate_reads): read_publication() auf
        Benjamins Volltexten, finale bezuege
```

### Zentrale Dateien

| Datei | Zweck |
|-------|-------|
| `journal_bot/settings.py` | Konstanten, Profilladen, Diskursraum-Registry |
| `journal_bot/fetch.py` | Retrieval-Runner |
| `journal_bot/fetchers/` | Fetcher-Implementierungen |
| `journal_bot/enrichment.py` | OpenAlex + Crossref API-Wrapper |
| `journal_bot/agent.py` | Opus-Agent (run_agent, batch_screen, assess_then_verify) |
| `journal_bot/citation_tracker.py` | Citation-Matching mit Vornamen-Disambiguation |
| `journal_bot/summarize.py` | Opus-Summaries aus Zotero-Korpus |
| `journal_bot/store.py` | SQLite-Wrapper |
| `journal_bot/digest.py` | process_article, render_markdown |
| `journal_bot/scout.py` | Multi-Linsen Journal-Evaluation |
| `journal_bot/trends.py` | Diskursraum-basierte Trend-Analyse |
| `journal_bot/cli.py` | Haupt-Entry (digest, fetch, summarize, etc.) |
| `journal_bot/web/app.py` | Flask-App |
| `journal_bot/web/templates/` | Jinja-Templates |

### Konfigurationsdateien (Projekt-Root)

| Datei | Zweck |
|-------|-------|
| `profile.json` | Forscher-Profil (Name, Institution, Areas, Triage-Topics, Modelle) |
| `projects.json` | **NEU** — Aktive Forschungsprojekte mit relevance_shifts |
| `journals.json` | Journal-Watchlist (Name, ISSN, Typ, Tier, Diskursräume) |
| `diskursraeume.json` | Diskursraum-Definitionen |
| `corpus.json` | Zotero-Import (Benjamins Publikationen + Volltexte) |
| `summaries.json` | Opus-Summaries der Publikationen |
| `articles.db` | SQLite-DB aller gefetchten Artikel + Verdicts |

API-Keys liegen in `~/.config/mojo/openrouter_key` und `~/.config/mojo/s2_api_key` (chmod 600).

---

## 3. Heutige Arbeit (2026-04-15)

### Validierte & committete Änderungen

1. **Opus-Summaries** (Commit `76afb4c`): Haiku-Summaries durch Opus ersetzt. Qualität signifikant besser (vollständigere key_terms, named_thinkers, cases_examples). Kosten einmalig ~$18. Backup der Haiku-Summaries in `summaries_haiku_backup.json`.

2. **Dark Mode Toggle** (im Commit `76afb4c`): Tag/Nacht-Umschalter in der Nav, CSS-Variablen für alle Themes, localStorage-Persistenz, System-Preference-Fallback.

3. **Profile wiederhergestellt**: `profile.json` enthielt Testdaten (`"areas": "test"`), wurde mit echten Beheimatungen und englischen Triage-Topics neu gefüllt. (User hat das manuell noch verfeinert.)

4. **Projekte-Tab in Setup-UI** (Commit `68dff1a`): Neue Datenebene `projects.json` mit 5 aktiven Projekten (Cultural Resilience, MetaKuBi, AI4ArtsEd, ComeArts, DiäS-KuBi). UI mit CRUD-Operationen. Felder: key, name, status, funder, period, description, relevance_shifts, connected_publications.

5. **Cache-Safety-Checks** (Commit `42900e8`): `agent.py` prüft Cache-Hit-Rate ab dem 2. Batch in `batch_screen()` (`CacheNotHitError` bei <50%). `cli.py cmd_digest()` prüft Kosten pro Artikel nach den ersten 3 Artikeln und bricht bei >$0.15/Artikel ab.

### Rückgängig gemacht (Commit `37081ca` revert von `b7fc098`)

**Prompt-Redesign mit Projekten**: Ein Versuch, `projects.json` als Block `ACTIVE RESEARCH PROJECTS` in den System-Prompt einzuspeisen und die Verdict-Kalibrierung umzuschreiben (von "concrete resource transfer" zu "Anregungspotenzial"). Im gezielten Einzeltest validiert (Ethics&Education → lesenswert mit candidate_reads), **aber vor Batch-Test revertiert** wegen Kosten-Vorfall.

### Der $43-Vorfall

Ich habe ein Test-Script (`test_new_prompt.py`, inzwischen gelöscht) geschrieben, das 100 Artikel durch den neuen Prompt laufen lassen sollte. Geplante Kosten: ~$1. Tatsächliche Kosten: $43, weil der Prompt-Cache nicht gegriffen hat. Jeder der 100 Calls hat die vollen ~28k System-Prompt-Tokens bezahlt.

Mögliche Ursachen (nicht abschließend geklärt):
- Cache-Key-Invalidierung durch parallele Calls zu schnell hintereinander
- OpenRouter-seitiges Cache-Verhalten anders als erwartet
- Prompt-Änderung gegenüber vorher gecachten Varianten

Als Reaktion:
- Prompt-Redesign revertiert
- Safety-Checks eingebaut (siehe oben)
- Mit 5-Artikel-Test über `cli.py digest` verifiziert dass die Produktions-Pipeline korrekt funktioniert ($0.018/Artikel, Cache-Hit sichtbar)

---

## 4. Wo wir vor dem Vorfall standen: Projekt-Integration in die Suche

Der eigentliche inhaltliche Strang, der unterbrochen wurde:

### Problemanalyse aus 127 User-Overrides

- **28 Upgrades** (Agent zu konservativ), v.a. in drei Clustern:
  - Kulturelle Resilienz / Planetary (6): Artikel über ecological grief, Anthropozän, Futurability — Agent verpasst die strukturelle Verbindung weil "Resilienz" nicht im Text steht
  - AI4ArtsEd / Generative AI (8): AI-Artikel mit Bezug zu Subjektivation/Macht/Kultur — Agent erkennt Projektbezug nicht
  - Relationale Bildungstheorie (3): Posthumanismus, ensemble cognition — bildungstheoretische Brücke fehlt
- **45 Downgrades** (Agent zu permissiv), v.a. bei AI & Society: "healthcare", "quantitativ", "Interview mit Praxisvertreter", "konfus", "Berufsbildung"

### Erkannter Kern

Der Agent kennt Benjamins **Publikationen** (über summaries.json), aber nicht:
- Aktive Projekte (AI4ArtsEd, KuBiMeta, De-Stock DFG-Antrag)
- Laufende theoretische Suchinteressen (Futurability, Affect, Rancière)
- Journal-spezifische Relevanz-Logiken

Benjamins Kernaussage: **Relevanz = Anregungspotenzial für Denken + Projekte**, NICHT "concrete resource transfer". Ein Artikel aus anderer Theorietradition zum selben Problemfeld ist POSITIV (produktive Reibung), nicht NEGATIV.

### Bereits erledigt

- `projects.json` als Datenstruktur mit 5 aktiven Projekten
- Projekte-Tab in Setup-UI für CRUD
- User hat die Inhalte verfeinert

### Noch offen (vor dem $43-Crash als nächster Schritt geplant)

1. **`projects.json` in den System-Prompt integrieren** (war in Commit `b7fc098`, revertiert):
   - Funktion `_build_projects_block()` die `ACTIVE RESEARCH PROJECTS`-Sektion formatiert
   - Einspeisung via `build_system_prompt()` in Screening UND Assessment
   - Verdict-Kalibrierung umschreiben: "Anregungspotenzial" statt "concrete resource transfer"
   - PROCEDURE um dritten Check erweitern: (a) Published work, (b) Active projects, (c) Discourse awareness
   - **Diff liegt in Git-History**: `git show b7fc098`

2. **Validierungs-Methodik**:
   - Vor einem Batch-Run immer 2-3 Einzelcalls testen und Kosten verifizieren
   - Gegen vorhandene Overrides validieren (würde der neue Prompt die 28 Upgrades korrekt hochstufen ohne die 45 Downgrades falsch zu labeln?)

3. **Tier-Optimierung** (siehe Memory `feedback_kosten_differenzierung.md`):
   - Aktuell 4.828 Artikel in Opus-Agent für $47
   - Journals mit 0 lesenswert-Treffern auf 400+ Artikel könnten nach C-Tier — aber User hat berechtigt eingewandt, dass das Modelling-Problem journal-spezifisch ist, nicht ein Journal-Qualitätsproblem

4. **Ongoing-Learning-Agent** (User-Anforderung): Ein separater Agent, der regelmäßig die User-Overrides analysiert, daraus Prompt-Meta-Regeln ableitet und die `relevance_shifts` der Projekte anpasst. "Wir brauchen gute Meta-Regeln für diesen Agent."

---

## 5. Kritische Feedback-Regeln (aus Memory)

Diese Regeln wurden im Laufe der Arbeit etabliert. Ein anderer Assistent sollte sie kennen:

### Kommunikation & Arbeitsweise
- **Keine Rückfragen wenn der nächste Schritt offensichtlich ist** — einfach machen
- **Keine optimistischen Projektionen auf Basis von Einzeltests** — vor Batch-Runs ≥20 Testartikel
- **Volle Journal-Namen im User-Output**, nicht die Shortcodes (ZfPaed → "Zeitschrift für Pädagogik")
- **Deutsch im User-Output, Englisch im Code** (Variablen, Docstrings)

### Kosten-Kontrolle
- **NIEMALS Batch-API-Tests blind starten** — erst 2-3 Einzelcalls mit Kostenverifikation, dann erst Batch mit User-Bestätigung
- **A/B/C-Tier-Strategie für Journals** — Opus ist zu teuer für alle

### Fachliche Regeln
- **Citation-Tracker: Vornamen-Initial prüfen** (nicht nur Nachnamen) — sonst False Positives bei Namesakes
- **Scout: disziplinäre ≠ thematische Relevanz** — ZfPäd kann disziplinär zentral sein bei wenig thematischer Überlappung
- **Trigger-Autoren** (Liste in `cli.py`): MacGilchrist, Jarke, Chun — Escalation unabhängig vom Tier. **NICHT**: Petar Jandrić (zu viel Output, zu wenig Trennschärfe)
- **Obsidian-Output ist UX-Problem** — Output-Format perspektivisch neu denken

---

## 6. Benjamins 5 disziplinäre Beheimatungen

Zentral für Scout-Evaluation und Prompt-Design:

1. **Allgemeine Pädagogik / Bildungstheorie** — institutionelle Heimat (Lehrstuhl FAU)
2. **Posthumanismus / STS / Resilienz** — Paradigmenwechsel zu relationaler Bildungstheorie
3. **Medienbildung / Medienpädagogik** — Kernfeld
4. **Pädagogische Medienforschung / Medienwissenschaft** — medienwissenschaftlich orientiert
5. **Kulturwissenschaft / Ästhetik** — kulturelle und ästhetische Bildung

Diese sind NICHT identisch mit den Diskursräumen in `settings.py`. Diskursräume sind journal-orientierte Cluster; Beheimatungen sind intellektuelle Positionierungen.

Die Spannung zwischen thematischer Passung und disziplinärer Beheimatung ist SELBST informativ ("Positionalitäts-Report").

---

## 7. Strategische Projektperspektiven

### MOJO wird Open Source
Workflows müssen als Scripts/Runbooks dokumentiert sein (nicht nur DEVLOG-Prosa), damit ein Agent *innerhalb* der Plattform die Tools autonom steuern kann.

### UI-Anforderungen (3 Kernfunktionen)
1. **Strukturierte Ablage** — Titel nach Diskursraum organisiert, nicht Markdown-Halde
2. **1-Click-Zotero-Aufnahme** pro Titel (pyzotero, bereits im Projekt)
3. **Dialogischer Research-Agent** — Rohtext/Stub → Retrieval aus dem Store. `transact-qda` als Referenzimplementierung

### Missed-References-Detektor
Die DB (17k Artikel + 160 Publikationen mit Bezügen) kann erkennen, wenn Benjamin in eigenen Textentwürfen einen relevanten Bezug übersieht.

---

## 8. Laufender Prozess-Status

- **Web-Server läuft** auf Port 5555 (PID 83806)
- **Keine Triage-Prozesse** aktiv
- **1.672 Artikel offen** (unverarbeitet in articles.db)
- **Uncommittete Änderungen**:
  - `profile.json` (User hat Triage-Topics verfeinert)
  - `projects.json` (User hat Descriptions und relevance_shifts verfeinert)
  - `journal_bot/web/templates/setup.html`, `base.html`, `summarize.py` (evtl. minor linter-changes)
  - Untracked: `baseline_558_german_prompts.json`, `baseline_99_old_pipeline.json`, `output/`

---

## 9. Empfohlener nächster Schritt (wenn Arbeit fortgesetzt wird)

1. **Git-Diff des revertierten Commits prüfen**: `git show b7fc098`
2. **Prompt-Änderungen selektiv wieder einführen**: `_build_projects_block()` und geänderte `ASSESSMENT_OUTRO` aus dem Diff übernehmen
3. **Offline zuerst**: `python3 scripts/analyze_overrides.py` laufen lassen, um die 28 Upgrades / 45 Downgrades reproduzierbar zu sehen
4. **Vor Batch-Lauf**: 2-3 Einzelartikel testen, Kosten verifizieren (Safety-Check im Code hilft jetzt)
5. **Validierung gegen die 28 Upgrades**: hätte der neue Prompt sie alle als lesenswert erkannt? Wie viele False Positives auf den 45 Downgrades?
5. **Erst bei Gelingen Batch-Lauf auf den 1.672 offenen Artikeln**

---

## 10. Bekannte Probleme / Offene Tickets

- **GitHub Issue #1**: Journal-Editor in Setup-UI (inzwischen teilweise gelöst — siehe Matrix-Tab mit "Journal hinzufügen")
- **Output-Format** (Obsidian): muss neu gedacht werden
- **Dialogischer Research-Agent**: noch nicht implementiert

---

## 11. Nicht vergessen

- **API-Key liegt in `~/.config/mojo/openrouter_key`** (chmod 600). Der Key sollte beim Wechsel der Dev-Umgebung NICHT in Git landen.
- **Zotero-Pfad**: `/Users/joerissen/FAUbox/Zotero` (nicht `~/Zotero`)
- **Zotero-Collection**: "Benjamin's publications" (key QM7TZT44)
- **Obsidian-Vault**: `/Users/joerissen/Documents/Obsidian Vault/research/mojo/` (falls Output-Format dort bleibt)
- **`AGENTS.md` ist jetzt der kanonische Assistenten-Kontext** im Projekt-Root. `CLAUDE.md` bleibt als Kompatibilitäts-Spiegel erhalten.
