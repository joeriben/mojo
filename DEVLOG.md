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

---

## Session 2026-04-10 — Diskursraum-Management + Multi-Linsen-Scout

### Phase 0: Rename journal-bot → mojo
- Alle "journal-bot"-Strings konsistent zu "mojo" umbenannt
- API-Key verschoben: `~/.config/journal-bot/` → `~/.config/mojo/`
- launchd-plist umbenannt + Pfade korrigiert

### Phase 1–4: Diskursraum-Management
Diskursräume von statischen Python-Konstanten zu editierbarer JSON-Datendatei migriert (`diskursraeume.json`).

1. **Storage + CRUD** — `journal_bot/diskurs.py`: add/rename/remove/assign/unassign
   - `settings.py` lädt aus JSON mit Fallback auf Hardcoded-Defaults
   - Keine Consumer-Module geändert (trends, biblio, coverage arbeiten unverändert)

2. **Profiling** — `mojo diskurs profile <key>` (kein LLM, null Kosten)
   - OpenAlex-Concepts/Topics-Aggregation, Zeitverlauf, Key-Term-Overlap mit summaries.json
   - Cross-Cluster-Overlap, Agent-Verdict-Verteilung

3. **Discovery** — `mojo diskurs suggest` + `mojo diskurs crosscut`
   - Querschnitt-Konzepte über alle Räume (kein LLM)
   - LLM-gestützte Vorschläge für neue/geänderte Diskursräume (Haiku)

4. **Scout-Integration** — SCOUT_TOOL dynamisch aus DISCOURSE_SPACES.keys()

### Multi-Linsen-Scout (Kernfeature)
Fundamentaler Umbau der Journal-Evaluation. Monoperspektivisch → adversarial:

**Problem:** Scout bewertete ZfPäd als "marginal" — technisch korrekt (wenige thematische Treffer), aber falsch (ZfPäd ist Kernorgan der Allgemeinen Pädagogik).

**Lösung: 3 Haiku-Linsen + Opus-Synthese**
- **Linse A (Thematisch):** Wie bisher — thematische Überlappung mit Forschungsthemen
- **Linse B (Disziplinäre Beheimatungen):** 5 Verortungen (Allg. Päd., Posthumanismus/STS, Medienbildung, Medienwiss., Kulturwiss./Ästhetik) — "Ist dieses Journal ein Publikationsort einer meiner Communities?"
- **Linse C (Latente Relevanz):** Periphere Diskurse die im Blickfeld bleiben sollten (mit Filter: kein Eyetracking, aber ANT-Historiografie ja)
- **Opus-Synthese:** Kartiert die Spannungen zwischen den Linsen, empfiehlt aufnehmen/beobachten/nicht_aufnehmen

**Ergebnis:** ZfPäd jetzt "aufnehmen" (A: mittel, B: zentral, C: mittel). Opus: "Als Kernorgan der Allgemeinen Pädagogik unverzichtbar [...] weniger wegen erwartbarer Volltreffer als wegen der diskursiven Seismografie."

**Nebeneffekt:** Der Scout-Output ist zugleich ein Positionalitäts-Report — die Spannungen zwischen den Linsen sind selbst informativ über Benjamins akademische Verortung.

### Schlüssel-Designentscheidungen
8. Diskursräume als Forschungsdaten (JSON) statt Code-Konstanten
9. Multi-Linsen-Evaluation statt Prompt-Inflation für mehrdimensionale Relevanz
10. Adversariale Perspektiven + Synthese statt Aggregation/Mittelung
11. Beheimatungen ≠ Diskursräume (intellektuelle Positionierungen vs. journal-orientierte Cluster)

### Kosten der Session
- Diskursraum-Suggest-Test: ~$0.10
- Scout-Testlauf (2 Journals, 3 Linsen + Opus): $0.13
- **Gesamt: ~$0.25**

---

## Session 2026-04-10b — Scout-Volllauf, Journal-Aufnahme, Workflow-Scripts

### Testfall "Kulturelle Bildung" (Task 3)
Diskursraum `aesthetische_kulturelle_bildung` war dünn besetzt (3 Journals, 77 Artikel). Workflow:
1. `mojo diskurs profile aesthetische_kulturelle_bildung` → Top-Konzepte: Humanities, Art, Philosophy, aber wenig Spezifisches
2. `mojo diskurs crosscut` → Art (42.4) und Aesthetics (27.7) als Querschnitt-Konzepte identifiziert
3. `mojo diskurs suggest` → Haiku schlägt u.a. "postdigitale_aesthetik" als neuen Raum vor ($0.01)
4. Scout-Volllauf hat **Studies in Art Education** und **Journal of Aesthetics and Culture** als Kernzugänge empfohlen
5. Raum hat jetzt 6 Journals (+ REPCS, SAE, JAC)

### Scout-Volllauf (Task 1)
Erster Lauf: 50 Journals evaluiert, aber **Opus-Synthese konnte nur 14/50 zuordnen** — `max_tokens=4000` war zu niedrig. Drei Bugs gefixt:
- `max_tokens` 4000 → 16000 (Opus brauchte ~14k Output-Tokens für 49 Journals)
- Watchlist-Deduplizierung (Studies in Art Education stand 2x in der Watchlist)
- Fuzzy-Matching verbessert: normalisierte Namen + Word-Overlap-Score (≥60%) statt einfachem Substring-Match

Zweiter Lauf: **49/49 Journals zugeordnet**, $2.53. Ergebnis:
- **8 aufnehmen**: ZfPäd, Ethics and Education, REPCS, Studies in Art Education, BJET, Journal of Aesthetics and Culture, Big Data and Society, Science Technology and Human Values
- **22 beobachten**: u.a. Vierteljahresschrift, IJADE, Arts & Humanities in HE, ZQF, FQS, Kulturwiss. Zeitschrift, Zf. Ästhetik, Zf. Kulturphilosophie, Sound Studies, diverse Kunstgenre-Journals
- **19 nicht aufnehmen**: Bildung und Erziehung, Educational Research, Oxford Review, Contemporary EdTech, Frontiers AI, u.a.
- **25 übersprungen**: 11× ISSN nicht aufgelöst, 9× keine Artikel, 2× nicht in OpenAlex, 3× sonstige

Benjamin: "Sowohl die Zuordnungen als auch die differenzierten Begründungen übertreffen meine Erwartungen. Der Ansatz funktioniert zu 100%."

### Journal-Aufnahme-Workflow (Task 2)
- **journals.json** als Daten-Datei extrahiert (statt Hardcoded-Liste in settings.py). Agent-editierbar.
- **`mojo journal add/list/remove`** CLI-Befehle gebaut (journal_bot/journals.py)
- 8 Journals aufgenommen, Cluster in diskursraeume.json zugeordnet, Watchlist mit ✓ aktualisiert
- `mojo fetch` → 600 neue Artikel im Store (gesamt jetzt ~1.800)

### Scout-UX-Verbesserungen
- Skip-Gründe im Terminal gruppiert (ISSN / keine Artikel / nicht indexiert)
- "Bereits getrackt"-Sektion im Output → vollständige Watchlist-Bilanz, nichts kann "verschwinden"

### Workflow-Scripts für autonomen Agenten
MOJO wird als Open-Source-Plattform veröffentlicht. Ein Claude-Agent innerhalb der Plattform soll die Workflows autonom steuern. Dokumentation unter `docs/workflows/`:
1. **01_journal_evaluation.md** — Watchlist → Scout → Aufnahme
2. **02_diskursraum_pflege.md** — Profile → Crosscut → Suggest → CRUD
3. **03_woechentlicher_digest.md** — Fetch → Agent-Bewertung → Obsidian
4. **04_trend_analyse.md** — LLM-Trends + Biblio pro Diskursraum
5. **README.md** — Index mit Abhängigkeiten, Datendateien, CLI-Referenz

### Schlüssel-Designentscheidungen
12. journals.json als Daten-Datei statt Python-Code (Agent soll JSON editieren, nicht Python)
13. Scout-Output als vollständige Watchlist-Bilanz (jedes Journal taucht in genau einer Sektion auf)
14. Workflow-Scripts als Runbooks für autonome Agenten (nicht für menschliche Entwickler)

### Kosten der Session
- Scout-Volllauf 1 (fehlerhaft): $2.04
- Scout-Volllauf 2 (gefixt): $2.53
- Diskursraum-Suggest: $0.01
- **Gesamt: ~$4.60**

### Phase 5c: Historical Backfill
- `mojo fetch --since YYYY` eingebaut: OpenAlex-Window durch festes Startjahr ersetzbar
- RSS/OJS-Journals (ZfE, MedienPaed) automatisch via OpenAlex-Backfill wenn `--since` und ISSN vorhanden
- `journals.json` um optionales `issn`-Feld erweitert (ZfE: 1862-5215, MedienPaed: 1424-3636)
- Backfill seit 2016: **17.465 Artikel** im Store (vorher 1.224)
- Alle 28 Journals haben jetzt 10 Jahre Daten
- Kein einziger Enrichment-Fehler, 196 Artikel ohne DOI

### Kosten der Session (korrigiert)
- Scout-Volllauf 1 (fehlerhaft): $2.04
- Scout-Volllauf 2 (gefixt): $2.53
- Diskursraum-Suggest: $0.01
- Backfill: $0 (nur OpenAlex + Crossref API)
- **Gesamt: ~$4.60**

### Commits dieser Session
```
e571764 feat: Journal-Aufnahme-Workflow + Scout-Bugfixes
ec212ac docs: Workflow-Scripts für autonomen Agenten (4 Workflows + Index)
bac1f28 docs: DEVLOG aktualisieren
5b32ba5 feat: Historical Backfill via `mojo fetch --since YYYY`
4227aa0 feat: Backfill für RSS/OJS-Journals via OpenAlex
```

---

## Session 2026-04-11 — Erster Digest-Lauf (gescheitert)

### Aufgabe
Erster Digest-Lauf über die 8 neu aufgenommenen Journals (Handover-Punkt 1).

### Ergebnis: $13.42 für 83 Artikel, 0 lesenswert

**83 Artikel verarbeitet**, alle aus dem Jahr 2016 (Backfill-Artefakt):
- 66× ignorieren, 17× scannen, 0× lesenswert, 0× pflichtlektuere
- 40 aus Science, Technology, and Human Values ($6.71)
- 25 aus Big Data & Society ($5.39)
- je 3 aus den übrigen 6 Journals ($1.32)

**Warum nur 2016er Artikel?** Parallele Session hat `mojo fetch --since 2016` laufen lassen → 17.465 Artikel im Store. `ORDER BY fetched_at DESC` liefert Backfill-Artikel zuerst.

### Was gebaut wurde

1. **Haiku-Triage** (`agent.py`, Funktion `triage_article`, Zeile ~260–328)
   - Vorfilter: Haiku ($0.001) entscheidet ob Opus ($0.05–0.45) nötig ist
   - Integriert in `digest.py` (`process_article`): bei Triage-"ignorieren" kein Opus-Call
   - Filtert nur 14% (12/83) — muss überarbeitet werden

2. **SQL-Filter-Fix** (`store.py`, Zeile 235)
   - Fehlende Klammern in WHERE: `(agent_processed_at IS NULL OR agent_processed_at = '')`
   - Funktioniert

3. **render_markdown-Absicherung** (`agent.py`, `render_markdown`)
   - `isinstance(h, dict)`-Filter für citation_hits + Guard gegen doppelt-encodiertes JSON
   - Funktioniert

4. **CLI-Ausgabe** (`cli.py`)
   - Volle Journalnamen statt Shortcodes, Triage-Status sichtbar
   - Funktioniert

5. **Triage JSON-Parser** (`agent.py`, Zeile ~306–325)
   - Drei Iterationen, aktuell: `raw.find("{")` bis `raw.rfind("}")`
   - ~50% Parse-Fehler im letzten Batch, Fallback "relevant" macht Triage wirkungslos

### 69 Obsidian-Dateien
Geschrieben nach `/Users/joerissen/Documents/Obsidian Vault/research/mojo/`. Format: Verdict, Kernthese, Bezüge, Bemerkenswert, Kosten-Footer.

### Kosten der Session
- Digest-Batches (5×): $13.42
- Davon durch Triage gespart: ~$0.20
- **Gesamt: ~$13.42**

### Offene Probleme
1. **Triage filtert zu wenig** (14% statt ~50–70%)
2. **Nur 2016er Artikel verarbeitet** (Sortierung nach `fetched_at`, kein `--year`-Flag)
3. **Triage-Parser instabil** (~50% Parse-Fehler → Fallback auf Opus)
4. **Kosten/Nutzen** ($13.42 für 0 lesenswerte Artikel)

---

## Session 2026-04-11b — Triage-Architektur neu gedacht

### Ausgangslage
Haiku-Triage aus Session 2026-04-11 war strukturell blind (14% Filterrate, kein Zugriff auf Enrichment-Daten oder Benjamins Publikationsindex). Aufgabe: Triage-Architektur grundlegend überdenken.

### Analyse: Warum Haiku versagt
1. **Haiku bekommt**: generische Stichpunkte + Titel + Abstract (500 Tokens)
2. **Opus bekommt**: 53 Publikationsprofile + OpenAlex + Refs + Citations (40k+ Tokens)
3. **Schlussfolgerung**: Die Unterscheidung "STS-Artikel relevant für Benjamin" vs. "STS-Artikel irrelevant" braucht Kenntnis seiner spezifischen Positionen — kein billiger Trick

### Benchmark: Deterministische Signale (null LLM-Kosten)
Vier Signale getestet (`journal_bot/signals.py`):
- **a) Zitiert Benjamin**: citation_tracker gegen authored_all (160 Pubs) — 0 Hits (2016er Artikel zitieren kein 2018+-Werk)
- **b) Named-Thinker-Overlap**: 328 Nachnamen aus summaries.json — 94% Recall, aber **73% False Positives** (generische Namen: "may", "law", "harvey" matchen überall in STS-Journals)
- **c) Zotero-Bibliothek-Overlap**: 8008 Items exportiert, Title-Word-Matching gegen crossref_refs — bessere Precision, aber nur **47% Recall**
- **d) Keywords im Titel**: 537 key_terms aus summaries.json — zu wenig Treffer in beiden Gruppen

**Fazit**: Deterministische Signale können "STS-Artikel relevant" nicht von "STS-Artikel irrelevant" unterscheiden. Als standalone-Filter unbrauchbar — taugen nur als Enrichment-Input.

### Benchmark: LLM-Batch-Screening (gecachter System-Prompt)
Idee: Dasselbe 40k-Token-Publikationsindex wie Opus, aber Batch-Input (20 Artikel pro Call) und minimaler Output (1 Zeile pro Artikel). Getestet auf den 83 bereits bewerteten Artikeln:

| Modell | Recall | Filter-Rate | Kosten | Verpasst |
|--------|--------|-------------|--------|----------|
| **Sonnet 4.6** | 65% | 82% | $0.33 | 6/17 scannen |
| **DeepSeek V3.2** | 94% | 39% | $0.04 | 1/17 scannen |

DeepSeek V3.2 gewählt: 8× billiger als Sonnet, fast perfekter Recall (1 verpasst), akzeptable Filterrate. Aussortierte Titel werden dem User zur Schnellsichtung angezeigt.

### Pipeline-Umbau

**Neue Architektur**: `mojo digest --next N --since 2025`
1. **DeepSeek Batch-Screening** (~$0.008/Batch à 25 Artikel, filtert ~40% Rauschen)
2. **Opus Deep Analysis** nur für durchgelassene Artikel
3. **Opus Short-Circuit**: Sofort-Entscheidung bei offensichtlichem "ignorieren" (1 Iteration, kein read_publication)

**Weitere Fixes:**
- `find_unprocessed` sortiert jetzt `year DESC` statt `fetched_at DESC`
- `--since` Flag: `mojo digest --next 50 --since 2025`
- `--no-screen` Flag: DeepSeek-Vorfilter überspringen
- Enrichment aus Store wiederverwendet statt doppeltem Crossref/OpenAlex-Call

### Erster erfolgreicher Digest-Lauf (2026er MedienPädagogik)
20 Artikel, davon 8 im Screening aussortiert, 12 durch Opus:
- 6× scannen (u.a. "Dream Machine" — zitiert Benjamin!, "Hegemoniekritik lehren" — substanzieller Kontrast zu Rancière-Ansatz)
- 3× ignorieren (Short-Circuit: $0.055–0.069 statt vorher $0.117)
- **Gesamt: $3.19** (vs. geschätzt ~$3.98 ohne Screening/Short-Circuit)

### Schlüssel-Designentscheidungen
15. Triage braucht Benjamins Publikationsindex — kein billiger Shortcut möglich
16. DeepSeek V3.2 statt Sonnet/Haiku für Screening (Recall > Filter-Rate > Kosten)
17. Short-Circuit im Opus-Prompt statt separatem Triage-Step (halbiert "ignorieren"-Kosten)
18. Aussortierte Titel werden angezeigt — User-Sichtung als Sicherheitsnetz
19. Deterministische Signale nicht in Pipeline integriert (zu wenig Trennschärfe)

### Kosten der Session
- Sonnet-Benchmark: $0.33
- DeepSeek-Benchmark: $0.04
- Digest-Testlauf (20 Artikel): $3.19
- **Gesamt: ~$3.60** (davon ~$0 für deterministischen Benchmark)

### Kosten-Strategie: A/B/C-Tier-System

Flat Opus über alle 2.954 Artikel (2025+): ~$266 — zu teuer. Stattdessen differenzierter Analyseaufwand je nach Journal-Nähe zu Benjamins Forschung:

| Tier | Verfahren | Journals | Artikel | Kosten |
|------|-----------|----------|---------|--------|
| **A** | DeepSeek-Screen → Opus | 7 (MedienPaed, ZfPäd, ZfE, PDSE, DCS, SAE, JAE) | 524 | ~$47 |
| **B** | DeepSeek mit Pub-Index, kein Opus | 13 (merz, BDS, EPT, BJET, etc.) | 1.231 | ~$5 |
| **C** | Nur Citation-Tracker + Keywords | 6 (AIandSoc, JRTE, LMT, etc.) | 1.199 | ~$0.23 |
| Auto | Escalation zu Opus | Citation-Hits + Trigger-Autoren | ~18 | ~$4.50 |
| | | **Gesamt** | **2.954** | **~$57** |

**Escalation-Signale** (null LLM-Kosten, auto-pass zu Opus):
- **Zitiert Benjamin**: 11 Artikel in 2025+ (citation_tracker gegen authored_all)
- **Trigger-Autoren**: 9 Artikel (MacGilchrist 6×, Jarke 1×, Wendy Chun 1×, + Überlappung)
- **User-Click**: Manuell aus dem UI (jeder B/C-Eintrag kann zu Opus eskaliert werden)

### Output-Design: Sortierung nach Verdict, volle Daten immer verfügbar

Opus-Output (`agent_entry_json`) wird vollständig in DB gespeichert — immer. Auch "scannen"-Einträge haben oft substanzielle Argumentationen (z.B. Rancière-Kontrast bei "Hegemoniekritik lehren"). Im UI:
- **pflichtlektüre/lesenswert**: Prominent, voller Report, 1-Click Zotero
- **scannen**: Voller Report verfügbar, Sortierung nach Diskursraum
- **ignorieren**: Titelliste, aufklappbar bei Bedarf
- Jeder Eintrag eskalierbar (B/C → Opus, oder Zotero-Aufnahme)

### Modell-Benchmark: Full Agent Run (gleicher Artikel, gleiche Tools)

6 Modelle mit identischer Pipeline getestet (System-Prompt + read_publication + submit_digest_entry) auf dem Artikel "Hegemoniekritik lehren" (Opus-Referenz: scannen):

| Modell | Verdict | read_pub | Bezüge | Kosten | Zeit | Status |
|--------|---------|----------|--------|--------|------|--------|
| **Opus 4.6** | scannen | 4× | 2 verifiziert | $0.444 | ~60s | Referenz |
| **DeepSeek V3.2** | lesenswert | 5× | 3 verifiziert | $0.063 | 35s | Exzellent, 7× billiger |
| **Qwen 3.6 Plus** | scannen | 7× | 2 (JSON-Bug) | ~$0.04 | 100s | Gut, Bezüge-Format instabil |
| **Kimi K2.5** | scannen | 6× | 3 (Text fehlt) | $0.108 | 32s | Fast, Bezüge-Inhalt leer |
| GLM 5.1 | (kein Output) | 7× | — | $0.150 | 53s | Scheitert am Tool-Protokoll |
| MiniMax M2.7 | ignorieren | 0× | — | $0.018 | 19s | Falsches Verdict |

**DeepSeek V3.2 als A-Tier-Default**: Korrektes Verdict, 3 Bezüge mit Volltextbelegen, folgt dem Prompt sauber, **7× billiger als Opus**. Projizierte Kosten 2025+-Run: ~$15–20 statt $57 (Opus) oder $266 (flat).

**UI-Modellauswahl**: DeepSeek (Default), Opus (Premium), Sonnet (Mittelweg, noch zu benchmarken). Qwen zurückgestellt bis JSON-Bug gelöst.

### Schlüssel-Designentscheidungen (Fortsetzung)
20. A/B/C-Tier-System statt flat Opus (73% Kostenreduktion)
21. merz ist B-Tier (hohes Volumen, überwiegend Praxisbeiträge)
22. Trigger-Autoren als kostenloser Escalation-Trigger neben Citation-Hits
23. Output proportional zum Verdict — Opus-Daten immer vollständig in DB, Anzeige gefiltert
24. articles.db als Forschungsdatenbank, nicht Markdown-Halde — perspektivisch "Missed References"-Detektor für eigene Textentwürfe
25. Obsidian als Output-Format verworfen — Web-UI mit DB-Backend
26. DeepSeek V3.2 als Default-Modell statt Opus (7× billiger, vergleichbare Qualität mit Tools)

### Implementierung: Tier-System + Quick Wins + Modellwechsel

Alles aus dem Handover der vorigen Phase in Code umgesetzt:

1. **Tier-System** — `journals.json` v3 mit `tier`-Feld (A/B/C), `settings.py` lädt `JournalConfig.tier`, `cli.py` splittet Artikel nach Tier und wählt Verfahren automatisch
2. **B-Tier Agent ohne Tools** — `allow_read=False` in `run_agent()` entfernt `read_publication` aus der Tool-Liste. B-Tier bekommt nur `submit_digest_entry`. Bug gefunden und gefixt: DeepSeek rief `read_publication` auf bei `max_iterations=1` → 41/52 Fehler in erster Tranche
3. **Citation Auto-Pass + Trigger-Autoren** — Vorab-Scan vor Screening, Treffer → direkt A-Tier
4. **Müll-Filter** — "Issue Information", "Correction", "Erratum" per Titel-Regex entfernt
5. **DeepSeek V3.2 als Default-Modell** — `--model` Flag, Default `deepseek/deepseek-v3.2`
6. **ARCHITECTURE.md** — Vollständige Systemarchitektur-Dokumentation
7. **Workflow-Docs aktualisiert** — 03_woechentlicher_digest.md komplett neu, README aktualisiert

### 2025+-Run (läuft)

Erste 99 Artikel verarbeitet (vor Session-Absturz):
- 49× ignorieren ($0.70), 44× scannen ($3.65), 6× lesenswert ($0.05)
- Durchschnittskosten: **$0.044/Artikel** (besser als projiziert)
- Run wird mit ~2.867 verbleibenden Artikeln fortgesetzt

### Kosten der Session (bisherig)
- Benchmarks (Sonnet, DeepSeek, deterministisch): ~$0.40
- Modell-Benchmark (6 Modelle, Full Agent): ~$0.90
- Testläufe (20 + 100 Artikel): ~$3.75
- 2025+-Run erste Tranche (99 Artikel): ~$4.40
- **Gesamt bisherig: ~$9.45**

---

## Session 2026-04-12 — Zweiphasige Architektur, Prompt-Kalibrierung, 2025+-Run

### Kernproblem der vorigen Session
Die "Lösung" `allow_read=False` für alle Batch-Artikel war epistemisch falsch: Sie verwischte die Unterscheidung, WANN und WARUM Benjamins Publikationen zur Analyse herangezogen werden. Summaries sind ein Suchindex (was behandelt der Text?), Volltexte liefern Argumente (was wird vertreten?). Ohne Volltext keine echten bezuege — aber Volltext für alle ist zu teuer.

### Zweiphasige Agent-Architektur (Assessment → Verification)

**Phase 1 — Assessment** (DeepSeek, ~$0.009/Artikel):
Agent arbeitet nur mit dem Suchindex. Drei Ausgänge:
- Irrelevant → sofort ignorieren
- Thematisch nah ohne konkreten Argumenttransfer → scannen (kein read_publication)
- Spezifische Hypothese über Verbindung → candidate_reads (pub_id + search_term + Hypothese)

**Phase 2 — Verification** (DeepSeek, ~$0.05/Artikel, nur wenn candidate_reads ≠ []):
Agent liest gezielt die identifizierten Publikationen, verifiziert/falsifiziert Hypothesen.

Implementiert in `agent.py`: `assess_then_verify()` orchestriert beide Phasen, `run_agent()` erhält `system_outro` und `extra_user_content` Parameter.

### Drei Iterationen der Prompt-Kalibrierung

**Iteration 1: Deutsche Prompts, keine Kalibrierung**
- 558 Artikel, **18% lesenswert** — untragbar
- DeepSeek markierte jede thematische Parallele als lesenswert
- Verification-Rate: 37%

**Iteration 2: Englische Prompts + Opus-kalibrierte Verdict-Schwellen**
- Alle Prompts auf Englisch umgeschrieben (DeepSeek optimiert für EN/CN)
- Verdict-Kalibrierung aus 83 Opus-verarbeiteten Artikeln:
  - geteilte Referenzrahmen allein = ignorieren
  - Hintergrundliteratur ohne Argumenttransfer = scannen
  - "parallelisiert" allein reicht NICHT für lesenswert
  - lesenswert NUR bei erweitert/widerspricht/importiert
- Ergebnis: lesenswert runter, aber **Verification-Rate 70%** — Assessment zu großzügig bei candidate_reads

**Iteration 3: Geschärfte Assessment-Schwelle**
- candidate_reads nur noch bei konkretem Argumenttransfer, nicht thematischer Nähe
- Explizite Beispiele im Prompt (was rechtfertigt candidates, was nicht)
- Maximum 2 statt 3 candidates
- **Verification-Rate: 5%**, lesenswert: 0.4%

### No-Abstract-Filter

43% der 2025+-Artikel (1.284) haben kein Abstract. LLM-Bewertung auf Basis eines Titels allein ist Geldverschwendung.

Flow (vor Screening, quer zu A/B/C-Tiers):
1. Catchword-Match auf Titel (~500 Terms aus summaries.json key_terms + named_thinkers + englische Äquivalente)
2. Kein Match (78%) → sofort ignorieren ($0)
3. Match (22%) → Haiku-Triage nur mit Forschungsprofil (kein Publikationsindex) → scannen oder ignorieren (~$0.0001/Artikel)

### Researcher-Profil extrahiert

Alle Prompts parametrisiert über `settings.py`:
- `RESEARCHER_NAME`, `RESEARCHER_INSTITUTION`, `RESEARCHER_AREAS`, `RESEARCHER_TRIAGE_TOPICS`
- Kein hardcodierter "Benjamin" mehr in agent.py

### Persistence-Fix

Screening-ignorieren und C-Tier-Pass-Through wurden nicht in die DB geschrieben → 1.048 Artikel in Limbo. Gefixt: alle Pfade schreiben jetzt Verdicts in articles.db.

### 2025+-Run abgeschlossen

| Metrik | Wert |
|--------|------|
| Artikel verarbeitet | 2.935 / 2.966 |
| Kosten | **$8.30** |
| Ø Kosten/Artikel | $0.0028 |
| ignorieren | 1.953 (66.5%) |
| scannen | 975 (33.2%) |
| lesenswert | 7 (0.2%) |
| Verification-Rate | 5% der Agent-Artikel |

Vergleich mit früheren Runs:
| Run | Kosten | lesenswert | Ø/Artikel |
|-----|--------|-----------|-----------|
| Flat Opus (83 Art., 2016) | $13.42 | 0% | $0.162 |
| DeepSeek dt. Prompts (558) | ~$13.74 | 18% | $0.025 |
| **Assess→Verify EN (2.935)** | **$8.30** | **0.2%** | **$0.003** |

### Baselines gesichert
- `baseline_99_old_pipeline.json` — alte Pipeline (flat, kein assess/verify)
- `baseline_558_german_prompts.json` — deutsche Prompts, 18% lesenswert

### Commits dieser Session
```
5436cb0 feat: zweiphasige Agent-Architektur (Assessment → Verification)
d6a9cb8 fix: English prompts + Opus-calibrated verdict thresholds for DeepSeek
9d38109 fix: sharpen assessment-phase candidate_reads threshold
18927fb feat: title-only screening for articles without abstract
f25d174 fix: persist screening-ignorieren and C-tier verdicts to DB
dfe2fba docs: UI-Entwurf — Flask/HTMX-Prototyp, drei Ansichten
```

---

---

## Session 2026-04-12b — Web-UI + Runs 2024/2026

### Gebaut

1. **Web-UI Prototyp** (Flask + Jinja2 + HTMX, Port 5555)
   - **Digest-Ansicht**: Lesenswert aufgeklappt, Zitiert-Dich-Sektion, Scannen kompakt, Ignorieren zugeklappt. Filter: Jahr, Diskursraum, Journal, Verdict. Default: aktuelles Jahr.
   - **Artikeldetail**: Verdict + Begründung, Kernthese, Bezüge, Bemerkenswert, Methodisch/Theoretisch, Meta-Footer.
   - **Diskursraum-Ansicht**: Übersicht mit Verdict-Balken, Detail mit Journals, Analyse-Buttons.
   - **Suche**: Titel-Volltextsuche in der Navbar.

2. **User-Verdict-System**
   - Confirm (OK) / Override (→ Lesenswert, → Scannen, → Ignorieren) per HTMX
   - Memo-Feld für Begründung
   - DB: `user_verdict`, `user_memo`, `user_verdict_at` (Auto-Migration)
   - `effective_verdict` Property (User > Agent)
   - **Review-Queue** (`/review`): nur unbestätigte Artikel
   - **Overrides-Ansicht** (`/overrides`): Upgrades vs. Downgrades für Prompt-Optimierung

3. **Hover-Tooltips**: Lazy-loaded per HTMX (`mouseenter once`), zeigt Verdict-Begründung + Kernthese.

4. **Vertiefen-Button**: Löst `assess_then_verify` aus für Shallow-Artikel. Automatisch bei Upgrade auf Lesenswert. Vorherige Analyse als `_previous` gestasht (aufklappbar zum Vergleich).

5. **Zotero-Export**: Via Connector-API (`/connector/saveItems`), Item + eingebettete Child-Note in Collection "mojo". Prüft ob Zotero läuft, ob Collection existiert.

6. **Obsidian-Export**: Markdown mit YAML-Frontmatter, sortiert nach Verdict-Ordner. Einzelartikel-Button.

7. **Archivieren**: Toggle, blendet Artikel aus Digest aus. `?archived=1` zum Einblenden.

8. **Diskursraum-Analysen**: Drei HTMX-Buttons auf Diskursraum-Detail:
   - Diskurs-Profil (kostenlos, datengetrieben)
   - Bibliometrie (kostenlos, Zitationsanalyse)
   - Trend-Analyse (~$1–3, LLM-Call mit Bestätigungsdialog)

### Bugfixes
- `assess_then_verify`: Fallback auf Assessment-Entry wenn Verification ohne `submit_digest_entry` endet
- `cli.py`: `.get("entry") or {}` statt `.get("entry", {})` für None-Safety

### Runs
- **2026**: 708 Artikel, alle fertig (2 lesenswert, 236 scannen, 457 ignorieren, 13 Müll)
- **2025 offene**: 31 Artikel fertig (30 Müll/Corrections, 1 scannen)
- **2024**: 1802/1944 verarbeitet (läuft noch im Hintergrund)

### Commits dieser Session
```
5f6f83e feat: Web-UI Prototyp (Flask+HTMX) + fix verification fallback
b4d072e feat: User-Verdict-System (confirm/override/memo)
9920a98 feat: lazy-loaded hover tooltips + title_link macro
a45a39a feat: Zotero-Export, Obsidian-Export, Archivieren
ac16130 feat: Suche + Trend/Biblio/Profil in Diskursraum-UI
```

---

## Handover für nächste Session

### Was steht
- **28 Journals** aktiv getrackt, **17.465 Artikel** in articles.db
- **4.821 verarbeitet** (2016: 83, 2024: 1802, 2025: 2241, 2026: 695), 14 lesenswert, 1513 scannen
- **Web-UI** voll funktional: Digest, Artikeldetail, Diskursräume, Review-Queue, Overrides, Suche
- **User-Verdict-System**: Confirm/Override/Memo, effective_verdict, Overrides-Export
- **Export**: Zotero (Connector-API + Child-Note), Obsidian (Markdown + Frontmatter), Archivieren
- **Vertiefen**: On-demand Opus-Analyse, automatisch bei Upgrade auf Lesenswert
- **Diskursraum-Analysen**: Profil, Bibliometrie, Trend-Analyse in der UI
- **Gesamtkosten DB**: $27.50

### Was als nächstes zu tun ist

**1. 2024er-Run abschließen**
- 142 Artikel noch offen (1802/1944 fertig)
- Läuft im Hintergrund, ggf. Reste manuell nachschieben

**2. Review-Workflow testen**
- Lesenswert-Artikel in der UI durchgehen, OK/Override/Memo
- Erste Overrides sammeln → Prompt-Optimierung ableiten

**3. Trend-Analyse für aesthetische_kulturelle_bildung**
- Biblio (kostenlos) bereits gelaufen
- LLM-Trend-Analyse jetzt per UI-Button startbar

**4. Dialogischer Research-Agent** (Phase 3)
- Stub/Entwurf hochladen → Retrieval gegen DB → "Missed References"
- Architektur-Vorlage: transact-qda

**5. Open-Source-Vorbereitung**
- Pfade teilweise hardcoded (Zotero, Obsidian)
- Researcher-Profil bereits extrahiert (settings.py)
- Obsidian-Pfad als Setting (statt hardcoded DIGEST_DIR)

**6. UI-Polish**
- Obsidian-Mirror-All-Button (Settings-Seite mit Pfad-Konfiguration)
- Markdown-Rendering für Trend/Biblio-Ergebnisse (statt `<pre>`)

### Bekannte Einschränkungen
- **Trigger-Autoren-Matching** braucht Vollnamen (nicht nur Nachnamen)
- **Catchword-Liste** enthält einige XML-Artefakte aus summaries.json
- **`--since` filtert ≥, nicht =** — für year-only-Runs ggf. nachfiltern
- **Zotero-Export** braucht manuell angelegte Collection "mojo"
- **trends.run() / biblio.run()** geben teils Result-Dicts zurück, teils nicht — API-Endpoints brauchen ggf. Error-Handling-Anpassung

### Kosten dieser Session

| Posten | Kosten |
|--------|--------|
| Vorherige Sessions | ~$12.00 |
| 2024-Run (1802 Artikel, läuft) | ~$4.50 |
| 2026-Run (708 Artikel) | ~$0.06 |
| 2025-Nachverarbeitung | ~$0.06 |
| Vertiefungs-Tests | ~$0.50 |
| **DB-Gesamtkosten** | **$27.50** |
