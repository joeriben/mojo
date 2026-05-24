# Backtest: Algorithmische Triage vs. LLM-Agent

_Run: 2026-05-24T08:37:22.259509+00:00 | n=461 | seed=42 | Laufzeit 89.2s_

## TL;DR

| # | Methode | Agreement | Macro-F1 | Top-5%-Prec | Missed-Recall |
|---|---|---:|---:|---:|---:|
| — | **Agent (Opus 4.6, Baseline)** | 71.6% | 0.679 | n/a | n/a |
| 1 | M9_Cascade_PerJournalBase | 66.4% | 0.603 | 82.6% | 14/28 = 50% |
| 2 | M9_Cascade_TunedBase | 66.4% | 0.600 | 82.6% | 8/28 = 29% |
| 3 | M8_LogReg_TunedProba_PerJournal | 65.9% | 0.598 | 82.6% | 14/28 = 50% |
| 4 | M8_LogReg_TunedProba | 65.9% | 0.595 | 82.6% | 8/28 = 29% |
| 5 | M8_LogReg_TunedProba_AIandSocAdjust | 65.1% | 0.586 | 82.6% | 7/28 = 25% |
| 6 | M9_Cascade | 62.9% | 0.581 | 82.6% | 17/28 = 61% |
| 7 | M8_LogReg | 62.5% | 0.577 | 82.6% | 17/28 = 61% |
| 8 | M8_RF | 66.4% | 0.561 | 87.0% | 6/28 = 21% |
| 9 | M9_Cascade_PerJournalCVBase | 61.8% | 0.551 | 82.6% | 11/28 = 39% |
| 10 | M8_LogReg_TunedProba_PerJournalCV | 61.2% | 0.544 | 82.6% | 11/28 = 39% |
| 11 | M8_Ensemble | 64.0% | 0.535 | 87.0% | 6/28 = 21% |
| 12 | M8_LGBM | 62.9% | 0.531 | 69.6% | 7/28 = 25% |
| 13 | M8_GBM | 62.9% | 0.522 | 69.6% | 4/28 = 14% |
| 14 | M7_EmbeddingSimilarity | 51.4% | 0.465 | 65.2% | 16/28 = 57% |
| 15 | M10_ConceptVector | 51.0% | 0.437 | 30.4% | 6/28 = 21% |
| 16 | M4_TopicConceptJaccard | 52.1% | 0.433 | 26.1% | 6/28 = 21% |
| 17 | M5_RefOverlapTrigger | 55.5% | 0.415 | 47.8% | 3/28 = 11% |
| 18 | M6_TfidfSimilarity | 49.5% | 0.380 | 13.0% | 6/28 = 21% |
| 19 | M3_CitationOrTrigger | 62.3% | 0.360 | 87.0% | 0/28 = 0% |
| 20 | M2_TriggerAuthor | 59.7% | 0.265 | 21.7% | 0/28 = 0% |
| 21 | M1_CitationHit | 27.3% | 0.256 | 82.6% | 1/28 = 4% |

**Bestes Verfahren**: M9_Cascade_PerJournalBase mit Macro-F1 0.603 (-0.076 vs. Agent) und Agreement 66.4% (-5.2 pp).

## Setup

- Gold-Set: **461** Artikel mit user_verdict
- Klassen (nach Kollaps pflichtlektuere→lesenswert): {'ignorieren': 273, 'scannen': 109, 'lesenswert': 79}
- Agent-Baseline: Opus 4.6 (pre 2026-05-24), Agreement 71.6%
- Cross-Validation: 5-fold StratifiedKFold (für M8, Schwellen-Tuning auf voller Tabelle)
- Methodische Disziplin: non-LLM-Daten only (siehe docs/context/project_backtest_algorithmic_heuristics.md)

## Agent-Baseline (zum Vergleich)

### Agent (Opus 4.6)

- **Agreement vs. User**: 71.6%
- **Macro-F1** (3 Klassen): 0.679
- **Top-5%-Precision (LESENSWERT)**: 78.3%
- **Recall der 28 vom Agent verpassten LESENSWERT**: 0/0 = 0.0%

| Klasse | P | R | F1 | n |
|---|---:|---:|---:|---:|
| ignorieren | 0.843 | 0.784 | 0.812 | 273 |
| scannen | 0.461 | 0.596 | 0.520 | 109 |
| lesenswert | 0.773 | 0.646 | 0.703 | 79 |

**Konfusion (Agent vs. User):**

| agent_verdict   |   ignorieren |   lesenswert |   scannen |   All |
|:----------------|-------------:|-------------:|----------:|------:|
| ignorieren      |          214 |            6 |        34 |   254 |
| lesenswert      |            5 |           51 |        10 |    66 |
| scannen         |           54 |           22 |        65 |   141 |
| All             |          273 |           79 |       109 |   461 |

## Methoden-Detail

### M9_Cascade_PerJournalBase

- **Agreement vs. User**: 66.4%
- **Macro-F1** (3 Klassen): 0.603
- **Top-5%-Precision (LESENSWERT)**: 82.6%
- **Recall der 28 vom Agent verpassten LESENSWERT**: 14/28 = 50.0%

| Klasse | P | R | F1 | n |
|---|---:|---:|---:|---:|
| ignorieren | 0.823 | 0.747 | 0.783 | 273 |
| scannen | 0.468 | 0.468 | 0.468 | 109 |
| lesenswert | 0.490 | 0.646 | 0.557 | 79 |

**Konfusion:**

| row_0      |   ignorieren |   lesenswert |   scannen |   All |
|:-----------|-------------:|-------------:|----------:|------:|
| ignorieren |          204 |           10 |        34 |   248 |
| lesenswert |           29 |           51 |        24 |   104 |
| scannen    |           40 |           18 |        51 |   109 |
| All        |          273 |           79 |       109 |   461 |

### M9_Cascade_TunedBase

- **Agreement vs. User**: 66.4%
- **Macro-F1** (3 Klassen): 0.600
- **Top-5%-Precision (LESENSWERT)**: 82.6%
- **Recall der 28 vom Agent verpassten LESENSWERT**: 8/28 = 28.6%

| Klasse | P | R | F1 | n |
|---|---:|---:|---:|---:|
| ignorieren | 0.799 | 0.773 | 0.786 | 273 |
| scannen | 0.415 | 0.468 | 0.440 | 109 |
| lesenswert | 0.595 | 0.557 | 0.575 | 79 |

**Konfusion:**

| row_0      |   ignorieren |   lesenswert |   scannen |   All |
|:-----------|-------------:|-------------:|----------:|------:|
| ignorieren |          211 |           13 |        40 |   264 |
| lesenswert |           12 |           44 |        18 |    74 |
| scannen    |           50 |           22 |        51 |   123 |
| All        |          273 |           79 |       109 |   461 |

### M8_LogReg_TunedProba_PerJournal

- **Agreement vs. User**: 65.9%
- **Macro-F1** (3 Klassen): 0.598
- **Top-5%-Precision (LESENSWERT)**: 82.6%
- **Recall der 28 vom Agent verpassten LESENSWERT**: 14/28 = 50.0%

| Klasse | P | R | F1 | n |
|---|---:|---:|---:|---:|
| ignorieren | 0.822 | 0.744 | 0.781 | 273 |
| scannen | 0.456 | 0.477 | 0.466 | 109 |
| lesenswert | 0.490 | 0.620 | 0.547 | 79 |

**Konfusion:**

| row_0      |   ignorieren |   lesenswert |   scannen |   All |
|:-----------|-------------:|-------------:|----------:|------:|
| ignorieren |          203 |           10 |        34 |   247 |
| lesenswert |           28 |           49 |        23 |   100 |
| scannen    |           42 |           20 |        52 |   114 |
| All        |          273 |           79 |       109 |   461 |

### M8_LogReg_TunedProba

- **Agreement vs. User**: 65.9%
- **Macro-F1** (3 Klassen): 0.595
- **Top-5%-Precision (LESENSWERT)**: 82.6%
- **Recall der 28 vom Agent verpassten LESENSWERT**: 8/28 = 28.6%

| Klasse | P | R | F1 | n |
|---|---:|---:|---:|---:|
| ignorieren | 0.798 | 0.769 | 0.784 | 273 |
| scannen | 0.406 | 0.477 | 0.439 | 109 |
| lesenswert | 0.600 | 0.532 | 0.564 | 79 |

**Konfusion:**

| row_0      |   ignorieren |   lesenswert |   scannen |   All |
|:-----------|-------------:|-------------:|----------:|------:|
| ignorieren |          210 |           13 |        40 |   263 |
| lesenswert |           11 |           42 |        17 |    70 |
| scannen    |           52 |           24 |        52 |   128 |
| All        |          273 |           79 |       109 |   461 |

### M8_LogReg_TunedProba_AIandSocAdjust

- **Agreement vs. User**: 65.1%
- **Macro-F1** (3 Klassen): 0.586
- **Top-5%-Precision (LESENSWERT)**: 82.6%
- **Recall der 28 vom Agent verpassten LESENSWERT**: 7/28 = 25.0%

| Klasse | P | R | F1 | n |
|---|---:|---:|---:|---:|
| ignorieren | 0.797 | 0.762 | 0.779 | 273 |
| scannen | 0.391 | 0.477 | 0.430 | 109 |
| lesenswert | 0.597 | 0.506 | 0.548 | 79 |

**Konfusion:**

| row_0      |   ignorieren |   lesenswert |   scannen |   All |
|:-----------|-------------:|-------------:|----------:|------:|
| ignorieren |          208 |           12 |        41 |   261 |
| lesenswert |           11 |           40 |        16 |    67 |
| scannen    |           54 |           27 |        52 |   133 |
| All        |          273 |           79 |       109 |   461 |

### M9_Cascade

- **Agreement vs. User**: 62.9%
- **Macro-F1** (3 Klassen): 0.581
- **Top-5%-Precision (LESENSWERT)**: 82.6%
- **Recall der 28 vom Agent verpassten LESENSWERT**: 17/28 = 60.7%

| Klasse | P | R | F1 | n |
|---|---:|---:|---:|---:|
| ignorieren | 0.823 | 0.681 | 0.745 | 273 |
| scannen | 0.407 | 0.459 | 0.431 | 109 |
| lesenswert | 0.482 | 0.684 | 0.565 | 79 |

**Konfusion:**

| row_0      |   ignorieren |   lesenswert |   scannen |   All |
|:-----------|-------------:|-------------:|----------:|------:|
| ignorieren |          186 |            9 |        31 |   226 |
| lesenswert |           30 |           54 |        28 |   112 |
| scannen    |           57 |           16 |        50 |   123 |
| All        |          273 |           79 |       109 |   461 |

### M8_LogReg

- **Agreement vs. User**: 62.5%
- **Macro-F1** (3 Klassen): 0.577
- **Top-5%-Precision (LESENSWERT)**: 82.6%
- **Recall der 28 vom Agent verpassten LESENSWERT**: 17/28 = 60.7%

| Klasse | P | R | F1 | n |
|---|---:|---:|---:|---:|
| ignorieren | 0.822 | 0.678 | 0.743 | 273 |
| scannen | 0.398 | 0.468 | 0.430 | 109 |
| lesenswert | 0.481 | 0.658 | 0.556 | 79 |

_5-fold CV Macro-F1: 0.575 ± 0.045_
_n_features: 40_

**Konfusion:**

| row_0      |   ignorieren |   lesenswert |   scannen |   All |
|:-----------|-------------:|-------------:|----------:|------:|
| ignorieren |          185 |            9 |        31 |   225 |
| lesenswert |           29 |           52 |        27 |   108 |
| scannen    |           59 |           18 |        51 |   128 |
| All        |          273 |           79 |       109 |   461 |

### M8_RF

- **Agreement vs. User**: 66.4%
- **Macro-F1** (3 Klassen): 0.561
- **Top-5%-Precision (LESENSWERT)**: 87.0%
- **Recall der 28 vom Agent verpassten LESENSWERT**: 6/28 = 21.4%

| Klasse | P | R | F1 | n |
|---|---:|---:|---:|---:|
| ignorieren | 0.723 | 0.861 | 0.786 | 273 |
| scannen | 0.453 | 0.312 | 0.370 | 109 |
| lesenswert | 0.607 | 0.468 | 0.529 | 79 |

_5-fold CV Macro-F1: 0.555 ± 0.059_
_n_features: 40_

**Konfusion:**

| row_0      |   ignorieren |   lesenswert |   scannen |   All |
|:-----------|-------------:|-------------:|----------:|------:|
| ignorieren |          235 |           31 |        59 |   325 |
| lesenswert |            8 |           37 |        16 |    61 |
| scannen    |           30 |           11 |        34 |    75 |
| All        |          273 |           79 |       109 |   461 |

### M9_Cascade_PerJournalCVBase

- **Agreement vs. User**: 61.8%
- **Macro-F1** (3 Klassen): 0.551
- **Top-5%-Precision (LESENSWERT)**: 82.6%
- **Recall der 28 vom Agent verpassten LESENSWERT**: 11/28 = 39.3%

| Klasse | P | R | F1 | n |
|---|---:|---:|---:|---:|
| ignorieren | 0.791 | 0.722 | 0.755 | 273 |
| scannen | 0.362 | 0.385 | 0.373 | 109 |
| lesenswert | 0.479 | 0.582 | 0.526 | 79 |

**Konfusion:**

| row_0      |   ignorieren |   lesenswert |   scannen |   All |
|:-----------|-------------:|-------------:|----------:|------:|
| ignorieren |          197 |           11 |        41 |   249 |
| lesenswert |           24 |           46 |        26 |    96 |
| scannen    |           52 |           22 |        42 |   116 |
| All        |          273 |           79 |       109 |   461 |

### M8_LogReg_TunedProba_PerJournalCV

- **Agreement vs. User**: 61.2%
- **Macro-F1** (3 Klassen): 0.544
- **Top-5%-Precision (LESENSWERT)**: 82.6%
- **Recall der 28 vom Agent verpassten LESENSWERT**: 11/28 = 39.3%

| Klasse | P | R | F1 | n |
|---|---:|---:|---:|---:|
| ignorieren | 0.790 | 0.718 | 0.752 | 273 |
| scannen | 0.352 | 0.394 | 0.372 | 109 |
| lesenswert | 0.473 | 0.544 | 0.506 | 79 |

**Konfusion:**

| row_0      |   ignorieren |   lesenswert |   scannen |   All |
|:-----------|-------------:|-------------:|----------:|------:|
| ignorieren |          196 |           11 |        41 |   248 |
| lesenswert |           23 |           43 |        25 |    91 |
| scannen    |           54 |           25 |        43 |   122 |
| All        |          273 |           79 |       109 |   461 |

### M8_Ensemble

- **Agreement vs. User**: 64.0%
- **Macro-F1** (3 Klassen): 0.535
- **Top-5%-Precision (LESENSWERT)**: 87.0%
- **Recall der 28 vom Agent verpassten LESENSWERT**: 6/28 = 21.4%

| Klasse | P | R | F1 | n |
|---|---:|---:|---:|---:|
| ignorieren | 0.739 | 0.828 | 0.781 | 273 |
| scannen | 0.391 | 0.312 | 0.347 | 109 |
| lesenswert | 0.515 | 0.443 | 0.476 | 79 |

_5-fold CV Macro-F1: 0.000 ± 0.000_
_n_features: 40_

**Konfusion:**

| row_0      |   ignorieren |   lesenswert |   scannen |   All |
|:-----------|-------------:|-------------:|----------:|------:|
| ignorieren |          226 |           25 |        55 |   306 |
| lesenswert |           13 |           35 |        20 |    68 |
| scannen    |           34 |           19 |        34 |    87 |
| All        |          273 |           79 |       109 |   461 |

### M8_LGBM

- **Agreement vs. User**: 62.9%
- **Macro-F1** (3 Klassen): 0.531
- **Top-5%-Precision (LESENSWERT)**: 69.6%
- **Recall der 28 vom Agent verpassten LESENSWERT**: 7/28 = 25.0%

| Klasse | P | R | F1 | n |
|---|---:|---:|---:|---:|
| ignorieren | 0.728 | 0.806 | 0.765 | 273 |
| scannen | 0.375 | 0.303 | 0.335 | 109 |
| lesenswert | 0.521 | 0.468 | 0.493 | 79 |

_5-fold CV Macro-F1: 0.532 ± 0.057_
_n_features: 40_

**Konfusion:**

| row_0      |   ignorieren |   lesenswert |   scannen |   All |
|:-----------|-------------:|-------------:|----------:|------:|
| ignorieren |          220 |           27 |        55 |   302 |
| lesenswert |           13 |           37 |        21 |    71 |
| scannen    |           40 |           15 |        33 |    88 |
| All        |          273 |           79 |       109 |   461 |

### M8_GBM

- **Agreement vs. User**: 62.9%
- **Macro-F1** (3 Klassen): 0.522
- **Top-5%-Precision (LESENSWERT)**: 69.6%
- **Recall der 28 vom Agent verpassten LESENSWERT**: 4/28 = 14.3%

| Klasse | P | R | F1 | n |
|---|---:|---:|---:|---:|
| ignorieren | 0.731 | 0.824 | 0.775 | 273 |
| scannen | 0.344 | 0.284 | 0.312 | 109 |
| lesenswert | 0.540 | 0.430 | 0.479 | 79 |

_5-fold CV Macro-F1: 0.522 ± 0.054_
_n_features: 40_

**Konfusion:**

| row_0      |   ignorieren |   lesenswert |   scannen |   All |
|:-----------|-------------:|-------------:|----------:|------:|
| ignorieren |          225 |           22 |        61 |   308 |
| lesenswert |           12 |           34 |        17 |    63 |
| scannen    |           36 |           23 |        31 |    90 |
| All        |          273 |           79 |       109 |   461 |

### M7_EmbeddingSimilarity

_Tuned thresholds: scannen ≥ 0.589, lesenswert ≥ 0.625_

- **Agreement vs. User**: 51.4%
- **Macro-F1** (3 Klassen): 0.465
- **Top-5%-Precision (LESENSWERT)**: 65.2%
- **Recall der 28 vom Agent verpassten LESENSWERT**: 16/28 = 57.1%

| Klasse | P | R | F1 | n |
|---|---:|---:|---:|---:|
| ignorieren | 0.746 | 0.571 | 0.647 | 273 |
| scannen | 0.290 | 0.349 | 0.317 | 109 |
| lesenswert | 0.355 | 0.544 | 0.430 | 79 |

**Konfusion:**

| row_0      |   ignorieren |   lesenswert |   scannen |   All |
|:-----------|-------------:|-------------:|----------:|------:|
| ignorieren |          156 |           15 |        38 |   209 |
| lesenswert |           45 |           43 |        33 |   121 |
| scannen    |           72 |           21 |        38 |   131 |
| All        |          273 |           79 |       109 |   461 |

### M10_ConceptVector

_Tuned thresholds: scannen ≥ 0.062, lesenswert ≥ 0.175_

- **Agreement vs. User**: 51.0%
- **Macro-F1** (3 Klassen): 0.437
- **Top-5%-Precision (LESENSWERT)**: 30.4%
- **Recall der 28 vom Agent verpassten LESENSWERT**: 6/28 = 21.4%

| Klasse | P | R | F1 | n |
|---|---:|---:|---:|---:|
| ignorieren | 0.694 | 0.615 | 0.652 | 273 |
| scannen | 0.300 | 0.358 | 0.326 | 109 |
| lesenswert | 0.315 | 0.354 | 0.333 | 79 |

**Konfusion:**

| row_0      |   ignorieren |   lesenswert |   scannen |   All |
|:-----------|-------------:|-------------:|----------:|------:|
| ignorieren |          168 |           31 |        43 |   242 |
| lesenswert |           34 |           28 |        27 |    89 |
| scannen    |           71 |           20 |        39 |   130 |
| All        |          273 |           79 |       109 |   461 |

### M4_TopicConceptJaccard

_Tuned thresholds: scannen ≥ 0.054, lesenswert ≥ 0.077_

- **Agreement vs. User**: 52.1%
- **Macro-F1** (3 Klassen): 0.433
- **Top-5%-Precision (LESENSWERT)**: 26.1%
- **Recall der 28 vom Agent verpassten LESENSWERT**: 6/28 = 21.4%

| Klasse | P | R | F1 | n |
|---|---:|---:|---:|---:|
| ignorieren | 0.696 | 0.656 | 0.675 | 273 |
| scannen | 0.308 | 0.303 | 0.306 | 109 |
| lesenswert | 0.289 | 0.354 | 0.318 | 79 |

**Konfusion:**

| row_0      |   ignorieren |   lesenswert |   scannen |   All |
|:-----------|-------------:|-------------:|----------:|------:|
| ignorieren |          179 |           34 |        44 |   257 |
| lesenswert |           37 |           28 |        32 |    97 |
| scannen    |           57 |           17 |        33 |   107 |
| All        |          273 |           79 |       109 |   461 |

### M5_RefOverlapTrigger

_Tuned thresholds: scannen ≥ 0.693, lesenswert ≥ 1.946_

- **Agreement vs. User**: 55.5%
- **Macro-F1** (3 Klassen): 0.415
- **Top-5%-Precision (LESENSWERT)**: 47.8%
- **Recall der 28 vom Agent verpassten LESENSWERT**: 3/28 = 10.7%

| Klasse | P | R | F1 | n |
|---|---:|---:|---:|---:|
| ignorieren | 0.654 | 0.777 | 0.710 | 273 |
| scannen | 0.278 | 0.275 | 0.276 | 109 |
| lesenswert | 0.483 | 0.177 | 0.259 | 79 |

**Konfusion:**

| row_0      |   ignorieren |   lesenswert |   scannen |   All |
|:-----------|-------------:|-------------:|----------:|------:|
| ignorieren |          212 |           40 |        72 |   324 |
| lesenswert |            8 |           14 |         7 |    29 |
| scannen    |           53 |           25 |        30 |   108 |
| All        |          273 |           79 |       109 |   461 |

### M6_TfidfSimilarity

_Tuned thresholds: scannen ≥ 0.153, lesenswert ≥ 0.171_

- **Agreement vs. User**: 49.5%
- **Macro-F1** (3 Klassen): 0.380
- **Top-5%-Precision (LESENSWERT)**: 13.0%
- **Recall der 28 vom Agent verpassten LESENSWERT**: 6/28 = 21.4%

| Klasse | P | R | F1 | n |
|---|---:|---:|---:|---:|
| ignorieren | 0.625 | 0.667 | 0.645 | 273 |
| scannen | 0.330 | 0.294 | 0.311 | 109 |
| lesenswert | 0.192 | 0.177 | 0.184 | 79 |

**Konfusion:**

| row_0      |   ignorieren |   lesenswert |   scannen |   All |
|:-----------|-------------:|-------------:|----------:|------:|
| ignorieren |          182 |           52 |        57 |   291 |
| lesenswert |           39 |           14 |        20 |    73 |
| scannen    |           52 |           13 |        32 |    97 |
| All        |          273 |           79 |       109 |   461 |

### M3_CitationOrTrigger

_Tuned thresholds: scannen ≥ 1.000, lesenswert ≥ 1.000_

- **Agreement vs. User**: 62.3%
- **Macro-F1** (3 Klassen): 0.360
- **Top-5%-Precision (LESENSWERT)**: 87.0%
- **Recall der 28 vom Agent verpassten LESENSWERT**: 0/28 = 0.0%

| Klasse | P | R | F1 | n |
|---|---:|---:|---:|---:|
| ignorieren | 0.622 | 0.996 | 0.766 | 273 |
| scannen | 0.000 | 0.000 | 0.000 | 109 |
| lesenswert | 0.882 | 0.190 | 0.312 | 79 |

**Konfusion:**

| row_0      |   ignorieren |   lesenswert |   scannen |   All |
|:-----------|-------------:|-------------:|----------:|------:|
| ignorieren |          272 |           58 |       107 |   437 |
| lesenswert |            0 |           15 |         2 |    17 |
| scannen    |            1 |            6 |         0 |     7 |
| All        |          273 |           79 |       109 |   461 |

### M2_TriggerAuthor

_Tuned thresholds: scannen ≥ 0.500, lesenswert ≥ 0.500_

- **Agreement vs. User**: 59.7%
- **Macro-F1** (3 Klassen): 0.265
- **Top-5%-Precision (LESENSWERT)**: 21.7%
- **Recall der 28 vom Agent verpassten LESENSWERT**: 0/28 = 0.0%

| Klasse | P | R | F1 | n |
|---|---:|---:|---:|---:|
| ignorieren | 0.595 | 1.000 | 0.746 | 273 |
| scannen | 0.000 | 0.000 | 0.000 | 109 |
| lesenswert | 1.000 | 0.025 | 0.049 | 79 |

**Konfusion:**

| row_0      |   ignorieren |   lesenswert |   scannen |   All |
|:-----------|-------------:|-------------:|----------:|------:|
| ignorieren |          273 |           77 |       109 |   459 |
| lesenswert |            0 |            2 |         0 |     2 |
| All        |          273 |           79 |       109 |   461 |

### M1_CitationHit

_Tuned thresholds: scannen ≥ 0.000, lesenswert ≥ 0.000_

- **Agreement vs. User**: 27.3%
- **Macro-F1** (3 Klassen): 0.256
- **Top-5%-Precision (LESENSWERT)**: 82.6%
- **Recall der 28 vom Agent verpassten LESENSWERT**: 1/28 = 3.6%

| Klasse | P | R | F1 | n |
|---|---:|---:|---:|---:|
| ignorieren | 0.000 | 0.000 | 0.000 | 273 |
| scannen | 0.244 | 0.982 | 0.391 | 109 |
| lesenswert | 0.864 | 0.241 | 0.376 | 79 |

**Konfusion:**

| row_0      |   ignorieren |   lesenswert |   scannen |   All |
|:-----------|-------------:|-------------:|----------:|------:|
| lesenswert |            1 |           19 |         2 |    22 |
| scannen    |          272 |           60 |       107 |   439 |
| All        |          273 |           79 |       109 |   461 |
