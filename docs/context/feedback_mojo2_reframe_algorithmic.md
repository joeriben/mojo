# MOJO 2.0 Reframe: algorithmisch, nicht LLM-zentriert

**Datum**: 2026-05-24 (nach HANDOVER-V2-Review)

**Trigger (Benjamin)**:
> "Ich habe vorhin in die falsche Richtung gedriftet, als ich Volltext-LLM und
> adversariale LLM-Prompts in den Vordergrund gestellt habe."

## Drei Korrekturen am MOJO-2.0-Verständnis

### 1. „Adversariale Heuristiken" = algorithmische Set-Operationen

NICHT: LLM-Prompts mit „adversarialem Anker am Volltext".
SONDERN: Set-Operationen über Refs-/Autor-/Topic-Mengen
(`article.refs ∩ (trigger_cited_refs \ benjamin_cited_refs)`), die als
Veto-Up/Veto-Down direkt in die Cascade einfließen — analog zur
`f_own_coupling_union`-Regel aus Iter 11.

### 2. Volltext-Verarbeitung ist algorithmisch, nicht LLM-basiert

PDF → Plain-Text → strukturierte Sektions-Erkennung (Refs/Bibliographie) via
Heuristiken (Header-Erkennung, Citation-Splitting, DOI-/Autor-/Jahr-Parsing,
Disambiguation). LLM liest den Text NICHT.

LLM-Volltext-Calls bleiben die teure Ausnahme an einzelnen, vorab durch
Algorithmus selektierten Items (Restmenge nach allen Cascade-Regeln, höchstens
5–10 % der Items) — NICHT der Default.

### 3. Ground-Truth-Quelle ist multi-source und wachsend

NICHT: einmaliger Snapshot von 109 PDFs aus einer Zotero-Collection.
SONDERN:
- Zotero-Collection als eine Quelle (heute QM7TZT44)
- Beliebig viele User-spezifizierte PDF-Ordner als weitere Quellen
- Re-Import additiv-idempotent, egal aus welcher Quelle
- → wachsender, deduplizierter Korpus

Re-Import muss inkrementell sein: zweiter Lauf ohne neue Quellen = 0
OpenAlex-Calls. Neuer PDF im Ordner → genau dessen Refs werden verarbeitet,
Rest aus Cache.

## Was das für den Arbeitsplan bedeutet

**Falsches Ziel** (frühere HANDOVER-Version):
- `scripts/build_benjamin_corpus.py` als neues Backtest-Artefakt mit Zeitindex

**Richtiges Ziel** (HANDOVER-Korrektur):
- Refs-Pipeline aus `scripts/iter11_extract_own_refs.py` +
  `iter11_resolve_refs_to_openalex.py` in `journal_bot/own_refs.py` als
  produktives, multi-source, additiv-inkrementelles Modul heben
- `own_refs_index.json` mit per-Publikation-Refs + per-Ref-Zeitindex als
  Nebenprodukt der produktiven Pipeline
- Daran docken neue Veto-Up/Veto-Down-Regeln auf die Cascade an

Der Hebel für bessere Triage liegt in: mehr/besseren eigenen Refs-Daten →
schärfere Set-Operationen → mehr algorithmische Filterregeln. NICHT in: mehr
LLM-Calls.

## Was bleibt richtig

- M9_Cascade-Plateau bei ~0.60 F1 ist Stand, nicht Endpunkt
- Iter-11-Veto-Up (`f_own_coupling_union ≥ 1` → LES, +5.2 pp Recall) ist die
  Blaupause, an die alle weiteren Veto-Regeln angedockt werden
- Adversariale Set-Features wie in `project_adversarial_blindspot_heuristics.md`
  beschrieben sind die richtigen Features — nur ihr **Integrationspunkt** war
  falsch dargestellt (Cascade, nicht LLM-Prompt)
- Volltext-LLM bleibt im Repertoire als gezielte Eskalation für Restmenge

## Verankerung

- HANDOVER.md (V3 vom 2026-05-24): „Worum es wirklich geht"-Section am Anfang
- `docs/mojo_2_volltext_sketch.md` §2.3 korrigiert (Set-Operationen statt
  LLM-Anker)
- `project_adversarial_blindspot_heuristics.md` (Memory + docs/context)
  korrigiert
