# Iter 14 — reiche Summary-Sim ins volle 3-Klassen-Modell

## Anforderung
Iter 13: rich-Sim ist der bessere *Ranking*-Hebel (blind-AUC 0.632 vs 0.517). Überträgt sich das auf
die **harte 3-Klassen-Triage** (macro-F1 / LES-Recall)? Gegen Leiste: Boden 0.544/0.589, own+content 0.514.

## Messung (`iter_14_full_model_rich.py`, OOF LogReg balanced)
| Modell | macro-F1 | keep-F1 | LES-Rec |
|---|---|---|---|
| **GESAMT** own+content (Basis) | 0.514 | 0.605 | 0.532 |
| own+content+rich | 0.493 | 0.613 | 0.456 |
| own+rich (ohne M7) | 0.473 | 0.554 | 0.278 |
| own+global+rich | 0.494 | 0.629 | 0.380 |
| nur rich+global | 0.448 | 0.616 | 0.582 |
| **SCREENING** own+content (Basis) | 0.444 | 0.384 | 0.500 |
| own+content+rich | 0.427 | 0.333 | 0.375 |
| own+rich / own+global+rich | 0.364/0.367 | 0.394/0.382 | **0.000** |

## Harte Kritik
- **Der AUC-Gewinn überträgt sich NICHT auf die Entscheidung (P6, P15 — der ehrliche Hauptbefund):**
  own+content 0.514 → +rich **0.493**. Auf dem blinden Strom fällt LES-Recall der rich-lastigen Modelle
  auf **0.000**. Wer aus Iter 13 „rich-Sim hebt die Triage" gelesen hätte, ist hier widerlegt. Ranking
  (AUC) ≠ harte 3-Klassen-Entscheidung — das ist die klassische Lücke, und ich dokumentiere sie statt
  sie wegzudefinieren.
- **Warum — und es ist mein Konstruktionsfehler, nicht der des Signals:** Iter 13 hatte selbst gemessen
  `mean(rich,global)` (0.728) **>** `LogReg(rich,global)` (0.722). Hier füttere ich LogReg beide Achsen
  *roh* — also genau den in Iter 13 als unterlegen erwiesenen Kombinierer. Zusätzlich enthält `content`
  schon score_M7, sodass rich+M7 korrelierte Features sind, die die balancierte LogReg auf der winzigen
  LES-Klasse (n=79/8) destabilisieren. Der Test ist also nicht „rich nützt nichts", sondern „rich als
  rohes LogReg-Feature neben M7 nützt nichts".
- **Was der Befund klärt (P16):** das System hat **zwei verschiedene Aufgaben** mit verschiedenen
  Gütemaßen — (a) **Ranking** für Digest-Sortierung / Vorfilter (da hilft rich, Iter 13), (b) **harte
  3-Klassen-Zuweisung** (da hilft rich als rohes Feature nicht). Diese Trennung ist selbst ein Ergebnis:
  die Wahl des Gütemaßes entscheidet, ob der reiche Œuvre-Sim ein Hebel ist.
- **Nicht überdreht (P4):** ich habe NICHT durch Feature-Stapeln eine bessere Zahl erzwungen. Die
  einzige Stelle, wo rich+global die Basis schlägt, ist keep-F1 (0.629 vs 0.605, own+global+rich) und
  LES-Recall auf der breiten Menge (0.582, nur rich+global) — beides keep-*Ranking*-nahe Maße, konsistent
  mit Iter 13. macro-F1 (mit scannen/ignorieren-Grenze) profitiert nicht.

## → nächste Iteration
Iter 15: den in Iter 13 als bester erwiesenen Kombinierer **`mean(rich,global)` als EIN engineertes
content-Feature** ins 3-Klassen-Modell geben (statt beide roh) — testet, ob die Entscheidungs-Lücke am
Kombinierer lag oder strukturell ist. Falls weiter kein macro-F1-Gewinn: System explizit als **Ranker**
(keep-Wahrscheinlichkeit für Digest/Vorfilter) statt als 3-Klassen-Entscheider re-framen und dort die
rich-Achse verankern.
