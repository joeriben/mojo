# Iter 36 — Seed-/Split-Stabilität (Anti-Overclaim-Absicherung)

## Anforderung
Phase E stützt sich auf Zahlen aus n=120/25 keep/8 LES. Wie stark streuen sie über CV-Seeds? Welche
Headline-Werte sind belastbar, welche Rauschen? 20 Seeds, zentrale Kennwerte.

## Messung (`iter_36_seed_stability.py`, 20 CV-Seeds)
| Kennwert | Mittel | Std | Min | Max | Spanne |
|---|---|---|---|---|---|
| rich blind-AUC | 0.632 | 0.000 | 0.632 | 0.632 | 0.000 |
| journal-prior blind-AUC | 0.678 | 0.014 | 0.648 | 0.700 | 0.052 |
| M-C blind-AUC | 0.658 | 0.011 | 0.635 | 0.683 | 0.048 |
| M-C LES-Recall@20 % | **0.550** | 0.073 | 0.375 | 0.625 | **0.250** |

## Harte Kritik — Korrektur eigener Headline-Zahlen (P15, P3, P4)
- **rich blind-AUC ist felsenfest (0.632 ± 0.000):** vorberechnet, fold-unabhängig. Diese Zahl trägt.
- **M-C blind-AUC: ehrlich ~0.658, NICHT 0.702.** Die in Iter 26 zitierte **0.702 war ein günstiger
  Seed** (seed 42). Über 20 Seeds liegt der Mittelwert bei 0.658 ± 0.011 (Spanne 0.635–0.683). Ich habe
  in Iter 26 den Glücks-Wert als Punktschätzung verkauft — das korrigiere ich hier: M-C blind-AUC ≈
  **0.66 ± 0.01**. Die *Richtung* (M-C > rich > M7) bleibt, der Spitzenwert war Rauschen.
- **M-C LES-Recall@20 %: ehrlich ~55 % ± 7 pp (Spanne 37.5–62.5 %), NICHT 62 %.** Die Iter-31-„62 %"
  liegt am **oberen Rand** der Streuung. Bei 8 LES und 24 gelesenen Artikeln ist das ein Wenig-Artikel-
  Maß — jede LES = 12,5 %, jede Verschiebung um 1 LES = 12,5 pp. Der ehrliche Wert ist „rund die Hälfte
  der Pflichtlektüre in den oberen 20 %, ± ein gutes Stück". Punktgenauigkeit wäre Hochstapelei.
- **journal-prior ~0.678 ± 0.014** (mixed-trainiert); die Iter-25-„0.711" war die screening-only-
  trainierte Einzelvariante — beide sagen „starkes Signal ~0.68–0.71", konsistent, aber die robuste
  Zahl ist 0.678.
- **Die generelle Lehre für die ganze Synthese (P15):** alle LES-bezogenen Prozente (8 Stück) tragen
  **±7–12 pp** Rauschen; die AUC-Werte ±0.01–0.05. Qualitative Aussagen (M-C ≫ M7; LLM ≫ M-C; alle LES
  in Pfad A; Bibliometrie-Veto blind wirkungslos) sind robust; **exakte Prozente sind es nicht**. Die
  Synthese-Doku muss Spannen führen, keine Punktwerte. Genau die Disziplin, deren Fehlen heute zum
  „0.603-Plateau"-Fehler führte (Iter 05).

## Konsequenz
Headline-Zahlen der Phase E werden auf Spannen umgestellt: M-C blind-AUC **0.66 ± 0.01**, LES-Recall@20 %
**≈50–60 %**, journal-prior **≈0.68–0.71**, rich **0.632** (exakt). Der finale Scorecard (Iter 40)
benutzt diese ehrlichen Spannen.

## → nächste Iteration
Iter 37: **Per-Verortung-Abdeckung** — bedient M-C alle 5 disziplinären Verortungen Benjamins gleich,
oder vernachlässigt es eine (z. B. ÄKB, deren keeper teils in 0-keeper-Journals sitzen, Iter 26)? Heuristische
Verortungs-Zuordnung der blind-keeper + Recall pro Verortung. Fairness-Check des Scouts über die Breite.
