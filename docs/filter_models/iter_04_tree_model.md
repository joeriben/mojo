# Iter 04 — Baummodell (HistGradientBoosting, CV)

## Anforderung
Iter-03-Kritik: LogReg linear, verpasst Interaktionen. Hypothese: ein Baummodell fängt sie und
schlägt 0.514. Test unter gleicher CV.

## Messung (`iter_04_tree_model.py`, 5-fold OOF, kostensensitive sample_weights)
| Feature-Menge | f1_3cls | f1_keep | LES-Rec | keepPrec |
|---|---|---|---|---|
| own+content (8) | 0.475 | 0.556 | 0.354 | 0.577 |
| ALL numeric+content | 0.514 | 0.584 | 0.494 | 0.589 |
| *Referenz LogReg own+content* | *0.514* | *0.605* | *0.532* | *0.547* |

## Harte Kritik
- **Hypothese widerlegt (P6/P15):** HistGBM auf own+content (0.475) ist **schlechter** als LogReg
  (0.514). Bei n=461 und schwachem, verrauschtem Signal überanpasst Gradient Boosting; lineare
  Regularisierung gewinnt. Kein Trick versteckt sich in den Interaktionen.
- **Spiegelbild zu Iter 03:** Für Bäume ist ALL ≥ own+content (0.514 vs 0.475) — Bäume werden von
  Zusatzfeatures weniger geschädigt als LogReg, aber gewinnen dadurch nichts über die 0.514-Linie.
- **Bestätigt die Richtung:** Der Weg zur Algo-Bar (0.603) führt **nicht** über einen stärkeren Lerner.
  Drei verschiedene Lerner (LogReg, HistGBM, und die dokumentierten M8_GBM=0.513/M8_RF) landen alle
  bei ~0.51. Die ~0.09 zur Bar müssen aus **Struktur** kommen: Per-Journal-Basisrate + Cascade.
- **Schwäche des eigenen Tests:** `max_depth=3`/`min_samples_leaf=20` ist bewusst flach gegen Overfit;
  ein tieferes Modell wäre auf 461 Items noch unzuverlässiger. CV-OOF schützt vor Selbsttäuschung (P5).

## → nächste Iteration
Iter 05: **Per-Journal-Basisrate als Prior** — der strukturelle Hebel, der M9_PerJournalBase von
0.51 auf 0.603 trägt. Re-derivieren und messen, ob er reproduziert.
