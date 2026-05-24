# MOJO — Handover (2026-05-24)

---

## §0 Pflicht-Vorlektüre

Lies **vor** diesem Handover das dauerhafte Orientierungsdokument:
**[`docs/mojo_2_grundorientierung.md`](docs/mojo_2_grundorientierung.md)**.
Es beschreibt was MOJO 1.x ist (Plattform), wo der algorithmische Backtest
steht (Plateau bei 0.60 F1), was MOJO 2.0 ist und nicht ist (drei
Verschärfungen) und — zentral — dass **MOJO 1.x code-seitig erhalten und
API-kompatibel bleibt**, auch wenn Funktionen schlafen
([Festlegung 2026-05-24, §4](docs/mojo_2_grundorientierung.md)). Dieser Handover
beschreibt den nächsten konkreten Schritt, das Dokument den Rahmen.

---

## Worum es wirklich geht (lies das zuerst, sonst läufst du in die falsche Richtung)

MOJO 2.0 ist **keine Volltext-LLM-Architektur**. Es ist die Weiterentwicklung
der bestehenden algorithmischen Cascade-Triage durch eine **produktive,
wachsende Refs-Pipeline**. LLM-Volltext-Calls bleiben die teure Ausnahme an
einzelnen, vorab durch Algorithmus selektierten Items — nicht der Default.

**Drei Korrekturen gegenüber älteren Sketches** (waren falsch fokussiert):

1. „Adversariale Heuristiken" = **algorithmische Set-Operationen** über
   Refs-/Autor-/Topic-Mengen, die als Veto-Up/Veto-Down direkt in die Cascade
   einfließen. NICHT: LLM-Prompts mit „adversarialem Anker".
2. Refs-Extraktion aus PDFs ist **algorithmisch** (Header-Erkennung,
   Citation-Splitting, DOI-/Autor-/Jahr-Parsing, Disambiguation). NICHT: LLM
   liest den Volltext.
3. Ground-Truth ist **multi-source und wachsend** (Zotero-Collection plus
   beliebige User-Ordner, additiv-idempotent re-importierbar). NICHT: ein
   einmaliger 109-PDF-Snapshot wie in den Iter-11-Backtest-Scripts.

Der Hebel für bessere Triage liegt in: mehr/besseren eigenen Refs-Daten →
schärfere Set-Operationen → mehr Veto-Up/Veto-Down-Regeln auf die Cascade.
LLM-Volltext nur dort, wo die Cascade nach allen Regeln noch unklar ist.

---

## §1 START HIER — eine Aufgabe

**Hebe die Refs-Pipeline aus dem Backtest-Track in `journal_bot/` als
produktives, multi-source, additiv-inkrementelles Modul** —
`journal_bot/own_refs.py`.

### Worum es geht (zwei Sätze)

MOJO triagiert wöchentlich ~300 Artikel gegen Benjamins publiziertes Werk.
Bisher kennt der Produktiv-Code dieses Werk nur als Volltext-Index (`corpus.json`
aus Zotero); die Refs/Literaturverzeichnisse darin sind unausgewertet, obwohl
Backtest gezeigt hat: Refs-Overlap zwischen Kandidat und Benjamins
Cited-Sources-Wolke ist das stärkste verbleibende algorithmische Signal
(12× LES/IGN-Ratio, +5.2 pp LES-Recall als Veto-Up-Regel). Dieses Signal muss
raus aus dem Backtest-Track und in den Produktiv-Code, als wachsende Datenbasis.

### Ist-Zustand

| Ort | Was es leistet | Limitierung |
|---|---|---|
| `journal_bot/corpus.py` | Zotero-Collection → PDF-Volltext → `corpus.json` (pyzotero local API, `zot.children()` → PDF-Resolver, pypdf-Extraktion, `authored_all`-Schema) | Single-Source (nur eine Zotero-Collection), **überschreibt** `corpus.json` bei jedem Lauf, **keine** Refs-Extraktion |
| `scripts/iter11_extract_own_refs.py` | PDF → Refs-Sektion → DOIs/Free-Text-Cites (pdftotext -layout, Header-Regex, Citation-Splitting, `cut_post_refs_garbage`) | Wegwerf-Snapshot auf 109 PDFs, nicht produktiv eingebunden — **Logik portierbar** |
| `scripts/iter11_resolve_refs_to_openalex.py` | DOI → OpenAlex-Work-ID + `publication_year` (Batch-25, Polite-Pool, File-Cache `.enrichment_cache/iter11_oa_doi/<sha1>.json`) | Wegwerf-Snapshot — **Cache (318 Files) wiederverwendbar**, Logik portierbar |
| `scripts/iter11_inventory_own_bibliography.py` | Zotero-Items via SQLite-Snapshot + Fallback-PDF-Suche in FAUbox (Title-Token-Match-Score) | Wegwerf-Snapshot, parallel zu `corpus.py` — **Fallback-Score-Pattern für Folder-Source nutzbar** |
| `journal_bot/settings.py` | `ZOTERO_COLLECTION`, `ZOTERO_STORAGE`, `SINCE_YEAR` | Erweitern um Folder-Sources (Konfig in `profile.json`) |

### Soll-Zustand: Multi-Source-Modell

Quellen sind gleichberechtigt und ergänzen sich:

```
sources (in profile.json konfigurierbar, beliebig viele):
  - zotero:<collection_key>            # heute: QM7TZT44 ("Benjamin's publications")
  - folder:<absolute_path>             # z.B. /Users/joerissen/FAUbox/01_Projekte

for source in sources:
    for item in source.discover():           # Metadaten + PDF-Pfad
        canonical_id = resolve_identity(item)  # DOI primary, fallback Hash
        upsert(store, canonical_id, item)    # additiv, idempotent
```

**Identitäts-Auflösung** (Dedup über Quellen):
- Primary: normalisierter DOI
- Fallback: Hash aus `normalize(title) + year + normalize(first_author_lastname)`
- Bei Konflikt: erste vollständige Quelle gewinnt, weitere als `source_refs[]`
  angefügt

**Additiv-inkrementell heißt**: jeder Re-Run einer Quelle ist no-op für bereits
eingelesene Items; nur neue oder geänderte Items werden verarbeitet. Quellen
können in beliebiger Reihenfolge laufen und beliebig oft.

### Pipeline-Stufen pro Publikation

```
Item discovered (Zotero-API ODER Filesystem-Heuristik)
  → canonical_id resolved
  → PDF-Pfad resolved (Zotero-Storage ODER absoluter Pfad ODER None)
  → pdftotext -layout, Cache in <data>/text/<canonical_id>.txt
  → Refs-Sektion extrahiert (Header-Regex aus iter11_extract_own_refs)
  → DOIs + Free-Text-Citations extrahiert
  → DOIs → OpenAlex aufgelöst (bestehenden iter11-Cache wiederverwenden)
  → Optional Phase 2: Non-DOI-Citations → OpenAlex-search (Autor+Jahr+Titel)
  → Persistiert in Store
```

Jede Stufe ist idempotent. Failures pro Stufe werden im Item vermerkt
(`extraction_notes`), nicht propagiert.

### Persistenz-Entscheidung

**Empfehlung: SQLite** in `own_refs.db` neben `articles.db`. Begründung:
- Additiv-inkrementell ist mit SQL trivial (UPSERT), mit JSON-Datei umständlich
- Inverser Refs-Index (welche eigenen Pubs zitieren Ref X?) ist Query, nicht
  Rebuild
- Skaliert wenn die Quellen wachsen (heute 161 Items, kann 500+ werden)
- Cache-Lookups auf DOI-Auflösung bleiben File-basiert (bestehende Konvention)

Schema-Vorschlag (indikativ, nicht final):

```sql
CREATE TABLE publications (
  canonical_id TEXT PRIMARY KEY,
  doi TEXT, title TEXT, year INTEGER, item_type TEXT, venue TEXT,
  authors_json TEXT,                -- list as JSON
  discourse_json TEXT,              -- multi-label list as JSON (aus discourse_classification.json)
  fulltext_path TEXT, fulltext_chars INTEGER, fulltext_extracted_at TEXT,
  refs_extracted_at TEXT, refs_header_label TEXT,
  notes_json TEXT                   -- extraction_notes
);
CREATE TABLE source_refs (          -- many-to-one, Source-Provenienz
  canonical_id TEXT, source_type TEXT, source_key TEXT, imported_at TEXT,
  PRIMARY KEY (canonical_id, source_type, source_key)
);
CREATE TABLE pub_refs (             -- refs OUT of a publication
  canonical_id TEXT, ref_doi TEXT, ref_oa_id TEXT, ref_year INTEGER,
  PRIMARY KEY (canonical_id, ref_doi)
);
CREATE INDEX idx_pub_refs_oa ON pub_refs(ref_oa_id);   -- inverse queries
```

JSON-Export (`own_refs_index.json` analog zur HANDOVER-v1-Skizze) als
optionales `--export`-Flag, falls Backtest- oder UI-Konsumenten das brauchen —
nicht primärer Output.

### CLI-Oberfläche

```
mojo refs build [--source zotero:KEY] [--source folder:PATH] [--force-refresh]
mojo refs status                              # counts, coverage, last ingest per source
mojo refs sources add zotero KEY              # Persistente Quellen-Liste
mojo refs sources add folder /pfad
mojo refs sources list
mojo refs export json --out /pfad/own_refs_index.json
mojo refs report                              # Coverage pro Source × Jahr-Bucket
```

Eingliederung in `journal_bot/cli.py` analog zu `mojo digest`, `mojo fetch`,
`mojo scout`.

### Akzeptanzkriterien

1. **Multi-Source**: nimmt Zotero-Collections UND PDF-Ordner aus
   `profile.json`-Config oder via `--source`-Flag.
2. **Idempotent**: zweiter Lauf ohne neue Quellen → **0 OpenAlex-Calls**
   (alles aus Cache + persistiertem Index), 0 PDF-Re-Extraktionen.
3. **Inkrementell**: dritter Lauf mit *einem* neuen PDF im Ordner → genau die
   Refs dieses einen PDFs werden verarbeitet, der Rest aus Cache.
4. **Robuste Refs-Extraktion**: PDFs ohne DOI in Refs (pre-2010er) müssen
   *mindestens* erkannt und markiert werden; Phase-2-Auflösung über
   Autor+Jahr+Titel-Match gegen OpenAlex ist optional, aber dann ohne Trade-off
   bei späterem Re-Run.
5. **Robuste Identitäts-Auflösung**: dasselbe Item aus Zotero (via DOI) und
   aus einem User-Ordner (via Title-Hash) wird zu einer `canonical_id` mit
   zwei `source_refs`-Einträgen, NICHT zu zwei Items.
6. **`mojo refs report`**: zeigt Coverage-Bilanz pro Source × Jahr-Bucket
   (analog zu `feedback_korpus_aufarbeitung.md`-Tabellen).
7. **Tests in `tests/test_own_refs.py`** mindestens für:
   - Folder-Ingest-Idempotenz
   - Dedup über DOI bei Zotero+Folder mit demselben Item
   - Re-Ingest nach Hinzufügen eines neuen PDFs in einen bekannten Folder
   - Refs-Extraction-Round-Trip (kleines Test-PDF)
8. **Open Source**: keine Heredoc-Analyse während des Baus. Alle Logik im
   Modul.
9. **Keine LLM-Calls in der gesamten Pipeline.** Wenn doch geplant — STOP,
   falsches Modul.

### Smoke-Test

```bash
mojo refs build --source zotero:QM7TZT44                          # erster Lauf
mojo refs build --source zotero:QM7TZT44                          # 0 API-Calls
mojo refs build --source zotero:QM7TZT44 --source folder:/tmp/new # +N PDFs
mojo refs report
```

Erwartete Coverage nach Lauf 1 (basierend auf Iter-11-Snapshot):
161 Publikationen, 109 mit PDF, ≥275 unique OA-Refs (idealerweise mehr durch
spätere Non-DOI-Resolution).

---

## §2 Was DANACH kommt (in dieser Reihenfolge — NICHT vor §1)

1. **Cascade-Andockung der bestehenden Veto-Up-Regel**: die Iter-11-Erkenntnis
   (`f_own_coupling_union ≥ 1` → LES, +5.2 pp Recall) auf den **produktiven**
   Refs-Index umstellen statt auf den Snapshot. Implementierung in
   `journal_bot/signals.py` analog zur bestehenden Cascade-Logik.
2. **Adversariale Set-Features in der Cascade** (siehe `mojo_2_volltext_sketch.md`
   §2.3, korrigiert 2026-05-24):
   - `scripts/build_adversarial_sets.py` — vorberechnete Set-Differenzen
     (`cited_by_trigger \ cited_by_benjamin_per_year` etc.), wöchentlicher Cache
   - `f_adv_*` Features in `signals.py`
   - Validierung: treffen `f_adv_*` ≥ Schwelle die 35 wrong-LES überproportional?
   - Wenn ja: Veto-Up/Veto-Down-Regeln in der Cascade
3. **Bessere Refs-Extraktion bei schwierigen Layouts**: pdfplumber-Fallbacks,
   OCR für gescannte Texte, bessere Header-Erkennung. Nicht spekulativ —
   gezielt für die ~20 Publikationen, die heute „leer" rauskommen.
4. **Non-DOI-Resolution gegen OpenAlex** (für die ~70 % der pre-2010er Refs
   ohne DOI): Autor+Jahr+Titel-Levenshtein-Match gegen
   `https://api.openalex.org/works?search=...`. Hat das Potenzial, die
   `ref_frequency`-Wolke deutlich zu vergrößern.
5. **Volltext-LLM als Eskalations-Slot** (NICHT Default!): für Articles, die
   nach allen Cascade-Regeln (Vorfilter + own_coupling + adversarial veto) noch
   in der Unklar-Zone sind. Höchstens ~5–10 % der Items, manuell oder
   Wochen-Batch.

---

## §3 Was bereits existiert (Kontext — nicht erneut anfassen)

**Produktion (MOJO 1.x, stabil):**
- `mojo digest`, `mojo fetch`, `mojo scout`, `mojo trends`, `mojo cache-report`
- Opus 4.6 Assessment mit ~98 % Cache-Hit, $0.049/Artikel
- 17.601 Artikel in `articles.db`, 15.929 Agent-verarbeitet

**Backtest-Pipeline (vollständige Scripts in `scripts/`):**
- Feature-Extraktion + Runner: `backtest_extract_features.py`, `backtest_run.py`,
  `backtest_methods.py`
- Iter 10 Trigger-Coupling: `iter10_pull_trigger_bibliographies.py`,
  `iter10_build_trigger_network.py`, `iter10_add_trigger_features.py`
- Iter 11 Own-Coupling (Snapshot, **nicht produktiv**):
  `iter11_inventory_own_bibliography.py`, `iter11_extract_own_refs.py`,
  `iter11_resolve_refs_to_openalex.py`, `iter11_add_own_coupling_features.py`

**Backtest-Befund (Stand, nicht Endpunkt):**
- M9_Cascade_TunedBase = 0.600 F1, plateauft seit Iter 7 auf reinen Metadaten
- Hebel für die nächste Stufe = **bessere/wachsende Refs-Daten** und daraus
  abgeleitete algorithmische Filter, nicht mehr LogReg-Features

**Datenartefakte:**
- `corpus.json` (4 MB, 74 Pubs ab 2018 mit Volltext, 160 `authored_all`)
- `summaries.json` (53 Opus-Summaries als ~28k-Token-Suchindex)
- `backtest_data/own_bibliography/inventory.json` (161 Items)
- `backtest_data/own_bibliography/refs/*.json` (109 Refs-Extraktionen)
- `backtest_data/own_bibliography/refs_resolved.json` (275 OA-IDs, **flach**)
- `backtest_data/own_bibliography/discourse_classification.json` (V3-Patterns
  + Multi-Label-Output für alle 161 Items — **patterns_per_discourse-Key
  enthält die Regex-Patterns**, einlesbar ohne Re-Klassifikation)
- `.enrichment_cache/iter11_oa_doi/` (318 gecachte DOI→OA-Resolutions,
  wiederverwendbar)

**Architektur-Plan:** `docs/mojo_2_volltext_sketch.md` (am 2026-05-24
durchgängig korrigiert: §2.3 = adversariale Heuristiken als algorithmische
Set-Operationen für Cascade; §4 = Volltext-LLM nur als Eskalation für
≤10 % Restmenge; §5 = Coding-LLM nur als optionales Developer-Tool, nicht
Auto-Deployment; §6 = Migrations-Pfad algorithmisch-zuerst; §7 + TL;DR
entsprechend).

---

## §4 Open-Source-Schulden (parallel oder später, NICHT vor §1)

Vier Analyseschritte aus der 2026-05-24-Session sind nur als Heredoc-Pipes
gelaufen. Die Outputs liegen aber im Repo, die Daten sind voll reproduzierbar:

| Output existiert | Script fehlt | Aufwand |
|---|---|---|
| `discourse_classification.json` mit Patterns | `scripts/iter11e_classify_discourses.py` | 5 Min (Patterns sind im JSON) |
| `feedback_korpus_aufarbeitung.md` Tabellen | `scripts/iter11f_corpus_aufarbeitung_report.py` | trivial aus `inventory.json` + `refs/*.json` |
| `feedback_ground_truth_qualitaet.md` Tabellen | `scripts/iter11g_ground_truth_diagnosis.py` | trivial aus `articles.db` + `features_gold.parquet` + `predictions_iter11_full.parquet` |
| Veto-Up-Validierung im Sketch §2.1 | `scripts/iter11h_validate_veto_up.py` | trivial aus `features_gold.parquet` + `predictions_iter11_full.parquet` |

Diese Schulden blockieren §1 NICHT. Sie sollten aber vor MOJO-2.0-Launch
extrahiert werden, weil sonst die Validierungs-Pipeline nicht reproduzierbar
ist.

---

## §5 Anti-Drift-Regeln (vor dem Start lesen)

Diese Regeln existieren, weil frühere Sessions wiederholt vom algorithmischen
Pfad in LLM-Visionen abgedriftet sind. Wenn eine dieser Bedingungen eintritt:
**STOP**, lies §1 nochmal, korrigier den Kurs.

1. **Volltext-LLM ist Eskalation, nicht Default.** Wer mehr als 10 % der Items
   in einen LLM-Volltext-Call routet, hat die Architektur missverstanden.
2. **„Adversariale Heuristiken" sind algorithmische Set-Operationen**
   (z. B. `cand.refs ∩ (trigger_refs \ benjamin_refs)`), die als
   Veto-Up/Veto-Down-Regeln in die Cascade gehen. Keine LLM-Prompts.
3. **OpenAlex-Schema-Recherche ist nicht §1.** Die Resolution-Logik steht in
   `scripts/iter11_resolve_refs_to_openalex.py` fertig. Porten, nicht neu
   denken.
4. **Backtest-Artefakte sind nicht §1.** Code gehört nach `journal_bot/`, nicht
   `scripts/`. `benjamin_corpus.json` ist allenfalls `--export`-Nebenprodukt.
5. **Single-Source ist halb fertig.** Multi-source (Zotero + N Folders) ist
   konstitutiv für den Auftrag, nicht optional.
6. **Kosten-Disziplin**: pdftotext = gratis, OpenAlex Polite-Pool = gratis.
   Wenn $-Zeichen auftauchen, falscher Pfad.

---

## §6 Konventionen (Verletzung = Rollback)

- **Alle Analytics = Scripts in `scripts/` oder Module in `journal_bot/`.**
  Keine Heredoc-Pipes. Keine Einmal-Runs. MOJO ist Open Source.
- **Kostenkontrolle**: NIEMALS Batch-API-Tests ohne vorherige Einzelkosten-
  Verifikation. Erst 2–3 Calls → Kosten zeigen → Bestätigung → Batch.
- **Sprachregeln**: Deutsch im User-Output, Englisch im Code.
- **Volle Journal-Namen** im User-Output, nicht Shortcodes.
- **Pfade**: Zotero unter `/Users/joerissen/FAUbox/Zotero`, Collection
  „Benjamin's publications" (key `QM7TZT44`).
- **Trigger-Autoren**: MacGilchrist, Jarke, Chun (Wendy Hui Kyong Chun).
  Petar Jandrić explizit NICHT.
- **Keine Rückfragen** wenn der nächste Schritt offensichtlich ist. §1 ist
  offensichtlich.

---

## §7 Empfohlene erste Aktion in der neuen Session

1. Parallel lesen:
   - `journal_bot/corpus.py` (heutige Zotero-Anbindung)
   - `scripts/iter11_extract_own_refs.py` (Refs-Extraktions-Logik)
   - `scripts/iter11_resolve_refs_to_openalex.py` (DOI→OA-Cache-Pattern)
2. Skizze des Schemas (SQLite-Tabellen) + CLI-Interface vorlegen
3. **Erst nach Bestätigung Code schreiben**

Wenn du anfängst, mehr als 3 Memory-Files zu lesen, driftest du wahrscheinlich.
Die drei für §1 relevanten:
- `docs/context/feedback_mojo2_reframe_algorithmic.md`
- `docs/context/feedback_volltext_pflicht.md`
- `docs/context/feedback_keine_rueckfragen.md`

---

## §8 Querverweise

- `docs/mojo_2_volltext_sketch.md` — MOJO-2.0-Architektur, §2.3 korrigiert
- `docs/backtest_iteration_log.md` — Iter 1–11 Chronik (Stand, nicht Endpunkt)
- `docs/context/MEMORY.md` — Index aller Memory-Files
- `docs/context/feedback_ground_truth_qualitaet.md` — 35 wrong-LES, Hard-Cases
- `docs/context/feedback_korpus_aufarbeitung.md` — Korpus-Bilanz (161 Items)
- `docs/context/project_adversarial_blindspot_heuristics.md` — Adversariale
  Set-Features als Cascade-Erweiterung
- `journal_bot/corpus.py` — heutige Single-Source-Pipeline (Ausgangsbasis §1)
- `ARCHITECTURE.md` — Systemarchitektur MOJO 1.x
- `CLAUDE.md` / `AGENTS.md` — Coding-Assistent-Briefing
