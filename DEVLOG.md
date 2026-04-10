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

### Commits dieser Session
```
e571764 feat: Journal-Aufnahme-Workflow + Scout-Bugfixes
ec212ac docs: Workflow-Scripts für autonomen Agenten (4 Workflows + Index)
```

---

## Handover für nächste Session

### Was steht
- **28 Journals** aktiv getrackt (20 original + 8 neu), ~1.800 Artikel in articles.db
- **Diskursraum `aesthetische_kulturelle_bildung`** hat jetzt 6 Journals (vorher 3)
- **Scout** funktioniert fehlerfrei über die gesamte Watchlist (49 Journals, $2.53)
- **`mojo journal add/list/remove`** CLI steht
- **4 Workflow-Scripts** dokumentiert unter `docs/workflows/`
- **journals.json** als Agent-editierbare Datenquelle für Journal-Konfiguration

### Was als nächstes zu tun ist

**1. Erster Digest-Lauf über die neuen Journals**
```bash
mojo digest --next 20 --journals ZfPaed,EthicsEd,SAE,JAC
```
Die 8 neuen Journals haben ~200 unverarbeitete Artikel. Agent-Bewertung mit Opus testen, Ergebnisse prüfen.

**2. Trend-Analyse für aesthetische_kulturelle_bildung**
```bash
mojo trends --cluster aesthetische_kulturelle_bildung
mojo biblio --cluster aesthetische_kulturelle_bildung
```
Der Raum hat jetzt genug Substanz (6 Journals). Erste LLM-Trendanalyse + bibliometrische Analyse.

**3. Watchlist-✓ automatisieren**
Aktuell muss man nach `mojo journal add` die Watchlist manuell editieren. Könnte `journal add` automatisch das ✓ setzen.

**4. Open-Source-Vorbereitung**
- Pfade abstrahieren (aktuell Hardcoded: Zotero-Pfad, Obsidian-Vault)
- API-Key-Management generalisieren
- README für externe Nutzer

### Bekannte Einschränkungen
- **25 Journals übersprungen** beim Scout (11× ISSN, 9× keine Artikel, 2× nicht in OpenAlex). Für wichtige Journals (zkmb.de, e-flux) sind Scraper nötig.
- **`mojo diskurs suggest`** live getestet ($0.01) — Vorschläge sind plausibel aber noch nicht umgesetzt.
- **Vierteljahresschrift** auf "beobachten" — als Testfall für späteres UI vorgemerkt.
- **Digest** noch nicht auf den 8 neuen Journals gelaufen — Verdicts stehen aus.
