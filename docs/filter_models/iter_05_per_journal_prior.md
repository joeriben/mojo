# Iter 05 — Per-Journal-Prior & ein Leak in der „Algo-Bar"

## Anforderung
Drei Lerner stranden bei ~0.51, M9_PerJournalBase=0.603. Hypothese: die Journal-Basisrate ist
der +0.09-Hebel. Streng out-of-fold testen (P3/P5).

## Messung (`iter_05_per_journal_prior.py`, 5-fold, Prior NUR aus Train-Fold)
| Modell | f1_3cls | f1_keep | LES-Rec |
|---|---|---|---|
| Per-Journal-Prior allein | 0.362 | 0.294 | 0.177 |
| Prior × LogReg(own+content) | 0.490 | 0.485 | 0.392 |
| *LogReg own+content (Iter 03)* | *0.514* | *0.605* | *0.532* |

Der ehrliche Prior-Blend (0.49) **unterbietet** die schlichte LogReg (0.514). Verdacht: die Bar nutzt
in-sample-Journalraten. Gegenprobe an den dokumentierten Cascade-Varianten:

| Cascade-Variante | f1_3cls | |
|---|---|---|
| M9_Cascade | 0.574 | |
| M9_Cascade_TunedBase | 0.589 | |
| **M9_Cascade_PerJournalBase** | **0.603** | ← in-sample-Journalraten (optimistisch) |
| **M9_Cascade_PerJournalCVBase** | **0.544** | ← ehrlich out-of-fold |

## Harte Kritik
- **Korrektur einer dokumentierten Zahl (P5/P15):** Die „Algo-Bar 0.603"/„Plateau 0.607" (Memory)
  ist **um ~0.06 durch in-sample-Per-Journal-Leak inflationiert**. Der **ehrliche Algo-Boden ist 0.544**
  (PerJournalCVBase) bzw. 0.589 (TunedBase ohne Journal-Trick). Alle folgenden Iterationen vergleichen
  gegen **0.544/0.589**, nicht 0.603.
- **Folge:** meine schlichte LogReg own+content (0.514, ehrlich CV) ist **nahe** am ehrlichen Boden,
  nicht 0.09 darunter. Der vermeintlich große Abstand war ein Mess-Artefakt.
- **Per-Journal hilft ehrlich wenig:** out-of-fold ~+0.03 (0.514→0.544 in der Cascade), nicht +0.09.
  Journals sind keine starken Prädiktoren, sobald man nicht aus der eigenen Test-Verteilung abschreibt.
- **Eigener Fehler vermieden:** Hätte ich den Prior in-sample gerechnet, hätte ich 0.60 „erreicht" und
  mich selbst getäuscht — genau der Fehlertyp von heute. Strikt-OOF (P5) hat es aufgedeckt.
- **Schwäche:** mein Blend (Prior × Proba) ist naiv; eine gelernte Gewichtung (Stacking) wäre fairer.
  Aber selbst optimal kann der Prior nicht mehr Information liefern als die 0.544-Cascade zeigt.

## → nächste Iteration
Iter 06: ehrliche Vergleichsleiste fixieren (Boden 0.544/0.589, Decke 0.679) und die **Selection-Bias-/
Blind-Screening-Frage** angehen — wie viel der LES-Performance hängt an intentional-positiven Quellen?
