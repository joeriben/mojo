# Iter 11 Befund: Zweiseitiges Coupling über Eigenwerk-Refs bricht das Plateau auch nicht

**Datum**: 2026-05-24.

**Trigger (Benjamin nach Iter 10)**:
> "Gibt es z.B. Informationen über Korrelationen der von mir zitierten Werke
> mit den Literaturlisten der durchsuchten Titel? Auch da köntne eine hohe
> Korrelation (Sinus / embeding-Tricks) auf interessante Titel verweisen."

**Iter 10 hatte einseitige Coupling**: `f_ref_overlap_authored` misst nur
"Article zitiert Benjamin". Iter 11 baut die zweiseitige Variante: aus 109
PDFs der Collection "Benjamin's publications" (lokales Zotero +
FAUbox-Fallback) wurden 318 unique DOIs aus den Reference-Sections
extrahiert, 275 davon zu OpenAlex-Work-IDs aufgelöst. Diese 275 IDs sind
Benjamins **Cited-Sources-Wolke**.

**Per-Klassen-Signal ist real**:
- LES-Hit-Rate: 26.9 % (21/78) vs IGN: 2.2 % (6/273) → **12× LES/IGN-Ratio**.
- LES-Mean: 0.462 vs IGN-Mean: 0.022 → **21× Mean-Differenz**.

**Aber: gleiche Plateau-Signatur wie Iter 10** auf den Hard-Cases:
- right-LES coupling=0.791 (Modell hat sie schon)
- wrong-LES coupling=0.057 (Modell verfehlt sie, neues Feature sieht sie nicht)
- wrong-IGN coupling=0.083 (Modell hatte sie als LES, neues Feature kann sie nicht ausschließen)

→ wrong-LES ≈ wrong-IGN im neuen Feature → **0 Trennschärfe auf den harten
Fällen**.

**Backtest-Ergebnis (full M7-Embeddings, 461 articles)**:
- M9_Cascade_TunedBase: 0.597 → 0.586 F1 (**−0.011**)
- M9_Cascade_PerJournalBase: 0.600 → 0.600 (**±0**, der per-Journal-Mechanismus
  absorbiert das neue Signal vollständig)
- 24/461 Predictions verändert; +8 besser, −10 schlechter, 6 beide falsch.
- **Per-Klasse**: lesenswert −0.003, scannen **−0.028** (SCAN-Noise!),
  ignorieren ±0.001.

**Aber praktisch wertvoll als algorithmische Veto-Up-Regel**:
- **LES-Recall: 55.1 % → 60.3 %** (+5.2 pp, +4 articles).
- Genau das richtige Verhalten für die MOJO 2.0 Cascade-Architektur:
  nicht im LogReg mischen (wo SCAN leidet), sondern als zusätzliche **Veto-Up-
  Regel** *direkt im algorithmischen Vorfilter*: `f_own_coupling_union ≥ 1 →
  klassifiziere als LES`. Blaupause für weitere Refs-basierte Veto-Regeln
  (adversariale Set-Features etc., siehe
  `project_adversarial_blindspot_heuristics.md`).

**Methodische Lehre**:
- 4 Iterationen (1st-degree, 2nd-degree, 2nd-trigger, Eigen-Coupling)
  bestätigen: bibliometrische Features sind **endgültig erschöpft**. Jede
  neue Coupling-Variante hat dasselbe Profil: Per-Klassen-Signal ja, Plateau
  bei 0.60 F1 ja, wrong-LES strukturell unerreichbar ja.
- Die diskriminative Information für die 35 wrong-LES sitzt **nicht im
  Zitationsnetz** — sie sitzt im Volltext. Iter 11 bestätigt
  `feedback_volltext_pflicht.md` empirisch zum 4. Mal.

**Konkrete Konsequenz für MOJO 2.0** (`docs/mojo_2_volltext_sketch.md`,
korrigiert 2026-05-24 nach Benjamin-Reframe — siehe
`feedback_mojo2_reframe_algorithmic.md`):
- **Algorithmischer Vorfilter** = `M9_Cascade_PerJournalBase` (0.600 F1) **∪**
  `f_own_coupling_union ≥ 1` (LES-Recall-Booster) →
  geschätzt LES-Recall ≈ 65-70 % bei 30-35 % Cut. Triagiert ≥90 % der Items
  ohne LLM-Call.
- Volltext-LLM bleibt **gezielte Eskalation** für die Restmenge (≤10 %), die
  nach allen algorithmischen Regeln unklar bleibt — NICHT Default für jeden
  LES-Kandidaten.

**Daten**:
- `backtest_data/own_bibliography/inventory.json` (161 Items, 109 PDFs)
- `backtest_data/own_bibliography/refs/` (367 unique DOIs aus 109 PDFs)
- `backtest_data/own_bibliography/refs_resolved.json` (275 OA-Wolke)
- `backtest_data/features_gold.parquet` (+2 Iter 11 features)
- `backtest_data/predictions_iter11_full.parquet`
- Devlog: `docs/backtest_iteration_log.md` (Iter 11 Section).
