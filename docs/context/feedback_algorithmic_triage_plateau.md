# Algorithmische Triage — Plateau-Befund (2026-05-24)

**Anlass**: 9-Iterations-Backtest gegen LLM-Triage-Baseline (Opus 4.6: 71.6%
Agreement / 0.679 macro-F1 auf 461 user_verdicts).

**Hartes Ergebnis**: Algorithmische Triage erreicht **0.607 macro-F1 / 66.8% Agreement**.
Gap zu Opus: **0.072 F1 / 4.8 pp Agreement** = **89% der LLM-Performance ohne LLM**.

## Beste Pipeline (M9_Cascade_TunedBase)

Komponenten mit nachgewiesenem Beitrag:
1. **BGE-M3 Embeddings** (1024-dim multilingual, batch_size=4 wg. RAM) → 8 Multi-Stat-
   Features (max/mean/top-5-mean/n_high gegen Korpus, davon 3 auth-only).
2. **Smoothed Bayesian Journal-Prior** (α=5 pseudo-counts), leak-safe per Fold.
3. **Top-15 Journal One-Hot** als zusätzliche Features.
4. **LogisticRegression** (L2, C=0.5, class_weight=balanced) — überraschend stärker
   als Tree-Modelle (GBM/RF/LGBM) bei n=461 mit nur 79 LESENSWERT.
5. **Threshold-Tuning auf Probabilities** (global): t_les=0.60, t_ign=0.35.
6. **Cascade-Veto-Up**: Citation-Hit ≥ 1 OR Trigger-Autor → LESENSWERT (87.5% Precision).
7. **Cascade-Veto-Down**: Quantil-Cutoff 0.20 für schwächste Embedding-Scores.

## Was NICHT funktioniert (alle widerlegt)

| Iter | Hypothese | Δ F1 | Befund |
|---:|---|---:|---|
| 4 | M10 Concept-Score-Vector (OpenAlex) | -0.003 | redundant zu M4 Jaccard, nur 10 concepts/article |
| 5 | Per-Fold kNN-Voting (k=5/10/20) | +0.001 | redundant zu BGE-M3 Multi-Stats |
| 6 | K-Means(authored_all, k=5) Cluster-Cosines | -0.007 | instabile Cluster bei n=229 in 1024D |
| 7 | Per-Top-15-Journal-Threshold (leaky tuning) | +0.013 | Memorization-Bias |
| 8 | Iter 7 mit nested CV | -0.072 | per-Journal Schwellen nicht stabil bei n=461 |
| 9 | AIandSoc-only ein-Parameter α-Adjust (CV) | -0.033 | α schwankt -0.15 bis +0.10 pro Fold |

## Strukturelle Grenze (Hard-Case-Analyse)

Die 30 vom Algorithmus verfehlten LES-Articles haben:
- f_citation_hit_count = **0.00** (vs. korrekt klassifizierte LES: 1.27)
- f_coauthor_hits = **0.03** (vs. korrekt: 0.31)
- f_trigger_author_match = **0.00**

→ **Komplett signal-arm**. Sie sind LESENSWERT durch qualitative Bewertung (Methode,
einzelner Begriff, Konzept-Anschluss), nicht durch bibliometric/citation Marker.
Diese Articles sind algorithmisch **strukturell** nicht fassbar — nur LLM-Reasoning
auf dem Abstract erfasst sie.

## Praktische Konsequenz: Pre-Filter vor LLM

Statt LLM komplett zu ersetzen, **algorithmische Pipeline als Vorfilter**:

| Regel | Aktion | Erwartete Inferenz-Ersparnis |
|---|---|---:|
| p_ignorieren ≥ 0.80 (Cascade) | direkt IGN, kein LLM-Call | ~40–50% |
| Citation-Hit OR Trigger-Autor | direkt LES, kein LLM-Call | ~5–10% |
| Sonst | → Gemini 3.5 Flash mit MiMo-Patches | Rest 40–55% |

Erwarteter Recall-Verlust auf LESENSWERT: **2–3 pp** (akzeptabel gegen Kostenersparnis).

## Methodische Lessons

1. **Threshold-Tuning ist immer auf der Evaluations-Stufe zu trennen**. Globale Schwelle
   auf OOF-Probas ist OK (1 Parameter über 461 Samples), per-Journal ist verheerend
   (15-30 Parameter über ~92 Test-Samples).
2. **Nested Threshold-Tuning** (5-fold auf den OOF-Probas) ist der saubere Validation-
   Mechanismus. Modell-Fits müssen nicht wiederholt werden, nur die Threshold-Suche.
3. **n=461 ist die Limitation**. Selbst ein-Parameter-per-Journal-Schwellen sind nicht
   stabil schätzbar. Mit n>2000 könnte Iter 7 echter Lift sein.
4. **BGE-M3 multi-stat features dominieren**. kNN-Voting, K-Means-Cluster, Concept-Vector
   sind alle redundant zu max/mean/top-k-mean Cosines.
5. **XGBoost crasht silent mit BGE-M3 auf macOS** (libomp double-load). LGBM als Drop-in.
6. **LogReg schlägt Tree-Modelle** bei n=461 mit 79 LES — Regularisierung gewinnt gegen
   Variance.

## Code-Referenzen

- `scripts/backtest_run.py` — Runner mit Per-Fold CV, Threshold-Tuning, Cascade-Grid
- `scripts/backtest_methods.py` — Method-Klassen M1–M10
- `scripts/backtest_extract_features.py` — Feature-Extraction aus articles.db
- `docs/backtest_iteration_log.md` — Iterations-Log mit allen Hypothesen
- `docs/backtest_algorithmic_v1.md` — Auto-generierter Report nach jedem Lauf
- `backtest_data/features_gold.parquet` — Cache der Features (461 Articles)
- `backtest_data/predictions.parquet` — Cache aller Predictions

## Verworfene Ideen, die NICHT mehr probiert werden müssen

- Per-Journal-Thresholds bei n<2000 — strukturell instabil
- K-Means-Cluster auf authored_all bei nur 229 Embeddings
- OpenAlex-Concept-Score-Vektoren — zu top-level, redundant
- kNN-Voting auf BGE-M3-Embeddings — redundant zu Multi-Stats
- XGBoost im selben Prozess wie sentence-transformers auf macOS
