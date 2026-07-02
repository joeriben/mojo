# Iter 41 — Temporal-Holdout: Drift oder Selection-Bias?

## Anforderung
Validitätsfrage (P3): driftet Benjamins Relevanz-Signatur über die Zeit so, dass ein auf Vergangenheit
kalibriertes Modell die Gegenwart schlechter trifft? Naiver Ansatz: train auf älteren, test auf neueren
Artikeln. ZUERST aber der Konfundierungs-Check — ist `year` im Gold überhaupt ein valider Zeit-Achsen-
Proxy, oder steckt Selection-Bias darin?

## Messung (`iter_41_temporal_holdout.py`)
**(1) Konfundierung year ↔ selection_mode:**
| Periode | n | keep-rate | screening-Anteil |
|---|---|---|---|
| 2020–2025 (Backfill) | 68 | **0.87** | 9 % |
| 2026 (Strom) | 393 | **0.33** | 29 % |

**(2) Intra-2026-Drift, blinder Strom (screening), Monats-Split:**
| Periode | n | keep | LES | rich-sim keep-AUC | Δ rich-sim (keep−nonkeep) |
|---|---|---|---|---|---|
| früh (Jan+Feb) | 64 | 13 | 3 | **0.638** | +0.062 |
| spät (Mär+Apr) | 44 | 6 | 0 | **0.632** | +0.035 |

## Harte Kritik
- **Der Cross-Year-Split ist methodisch unzulässig — und das ist der Hauptbefund (P3, P15):** `year`
  ist im Gold fast ein selection_mode-Proxy. Die alten Artikel (2020–2025) sind zu 91 % intentional-
  positiver Backfill (keep-rate 0.87), die 2026er der blinde Strom (keep-rate 0.33). Ein train-alt/
  test-neu-Modell lernte „alles ist Treffer" und bräche auf dem Strom ein — es misst **Selektion, nicht
  Drift**. Ehrlich verworfen, statt eine bedeutungslose Zahl zu produzieren. Das validiert *rückwirkend*,
  warum die ganze Serie screening-only / selection_mode-bewusst gemessen hat statt mit naiven Splits.
- **Auf dem validen Intra-Strom-Probe: kein Drift detektiert, aber unterbesetzt (P15, P6):** rich-sim
  trennt früh wie spät praktisch gleich (AUC 0.638 vs 0.632). Die Signaltrennung schrumpft nominell
  (+0.062 → +0.035), aber die Spät-Periode hat **0 LES und nur 6 keeper bei n=44** — das ist Rauschen,
  kein Trend. Korrekte Aussage: *„über ein Quartal 2026 ist rich-sim stabil; Drift über längere
  Zeiträume ist mit diesem Gold nicht prüfbar."* Kein „stabil bewiesen", nur „kein Drift sichtbar bei
  schwacher Teststärke".
- **Konsequenz für den Betrieb (P6):** weil das Eigenwerk-Korpus (summaries.json) die Referenz ist und
  sich Benjamins Werk *langsam* fortschreibt, ist der erwartbare Drift gering und durch periodisches
  Neu-Einbetten der Summaries (bei neuen Publikationen) trivial behebbar. Drift ist hier ein
  **Wartungs-, kein Architektur-Problem** — die M-E-Spezifikation braucht nur einen „Summaries
  aktualisieren → rich_sim neu cachen"-Hook, keine Online-Adaptation.
- **Selbstkritik am eigenen Test (P3):** der Monats-Split hat keine echte Train→Test-Trennung gebraucht,
  weil AUC ein Rangmaß ist (schwellen-/trainingsfrei). Das ist legitim für eine *Stabilitäts*-Frage, aber
  es ist kein vollwertiger Generalisierungstest — für den fehlen schlicht die Daten (zu wenige LES je
  Monat). Nicht überverkauft.

## → nächste Iteration
Iter 42: **Feature-Ablation** (drop-one-out auf M-C: rich_sim / Journal-Prior / Biblio-Veto). Quantifiziert,
welches Signal die M-C-Trennschärfe wirklich trägt — als belastbare Grundlage für die finale M-E-Spezifikation
(welche Komponenten sind essenziell, welche schmückend). Knüpft an Iter 40 (rich-sim trägt 96 %) an.
