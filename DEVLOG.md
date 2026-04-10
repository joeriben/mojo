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

## Handover für nächste Session

### Was steht
- **Diskursraum-Management** ist vollständig: CRUD (`mojo diskurs list/add/rename/remove/assign/unassign`), datengetriebenes Profiling (`profile`), Discovery (`suggest`, `crosscut`). Alles getestet, committed.
- **Multi-Linsen-Scout** ist funktional: 3 Haiku-Linsen (Thematisch / Disziplinär / Latent) + Opus-Synthese. Getestet mit 2 Journals (ZfPäd, VjwP), produziert qualitativ gute Ergebnisse. Committed.
- **Rename** journal-bot → mojo ist überall durch. API-Key liegt unter `~/.config/mojo/`.

### Was als nächstes zu tun ist

**1. Scout-Volllauf über die gesamte Watchlist**
```bash
mojo scout
```
Ohne `--limit` läuft der Scout über alle Kandidaten in `docs/journal_watchlist_full.md`. Geschätzte Kosten: ~$1–2, Dauer: ~5–10 Minuten. Das Ergebnis zeigt für jedes Kandidaten-Journal die 3-Linsen-Bewertung + Opus-Synthese. Output liegt danach in `~/Documents/Obsidian Vault/research/mojo/trends/scout_<datum>.md`.

**2. Journal-Aufnahme-Workflow**
Aktuell gibt es keinen interaktiven Weg, ein vom Scout empfohlenes Journal in die Tracking-Liste aufzunehmen. Dafür braucht es ein Design:
- Option A: `mojo scout --interactive` (nach Evaluation direkt aufnehmen)
- Option B: `mojo journal add <name>` (separater Befehl, ISSN-Autodetection + Cluster-Vorschlag)
- In beiden Fällen: neues `JournalConfig` in `settings.py` eintragen (oder eigene journals.json?) + Cluster-Zuordnung in `diskursraeume.json`

**3. Testfall "Kulturelle Bildung / Arts Education"**
Noch nicht durchgespielt. Workflow wäre: `mojo diskurs profile aesthetische_kulturelle_bildung` → `mojo diskurs suggest` → ggf. neuen Diskursraum anlegen + Journals zuordnen + scouten.

### Bekannte Einschränkungen
- **3 Journals übersprungen** im Testlauf: "Critical Questions in Education" (keine Artikel), "On Education" (ISSN nicht aufgelöst), "IJEA" (keine Artikel). ISSN-Resolution und OpenAlex-Coverage könnten für einige Watchlist-Einträge scheitern → ggf. manuelle ISSN-Angabe in der Watchlist nötig.
- **Opus-Synthese matcht Journals per Name** (fuzzy). Bei sehr ähnlichen Journalnamen könnte die Zuordnung fehlschlagen → beobachten beim Volllauf.
- **settings.py enthält noch die Hardcoded-Defaults** für Diskursräume und Journal-Cluster. Die JSON-Datei hat Vorrang, aber die Hardcoded-Werte sind Fallback. Bei Diskrepanzen gewinnt die JSON.
- **`mojo diskurs suggest`** (LLM-gestützt) wurde noch nicht live getestet — nur `crosscut` (kein LLM) ist verifiziert.

### Commits dieser Session
```
321d81c feat: Diskursraum-Management + Rename journal-bot → mojo
75ad3a6 feat: Multi-Linsen-Scout (3× Haiku + Opus-Synthese)
```
