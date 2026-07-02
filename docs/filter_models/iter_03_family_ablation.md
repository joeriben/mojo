# Iter 03 — Feature-Familien-Ablation (CV)

## Anforderung
Iter 01/02: beide Achsen je mäßig. Welche Familie trägt unter sauberer CV den F1, und bringt
die Kombination etwas? Modell konstant (balanced LogReg), nur Feature-Menge variiert (P5).

## Messung (`iter_03_family_ablation.py`, 5-fold OOF)
| Familie | f1_3cls | f1_keep | LES-Rec | keepPrec |
|---|---|---|---|---|
| own (5) | 0.408 | 0.303 | 0.266 | 0.814 |
| trigger (8) | 0.409 | 0.469 | 0.228 | 0.568 |
| content (3) | **0.430** | 0.587 | 0.570 | 0.532 |
| **own+content (8)** | **0.514** | 0.605 | 0.532 | 0.547 |
| own+trigger (13) | 0.445 | 0.495 | 0.278 | 0.573 |
| ALL numeric+content | 0.511 | 0.643 | 0.494 | 0.576 |

## Harte Kritik
- **Anti-Feature-Bloat-Befund:** `own+content` (8 Features, 0.514) **schlägt** `ALL` (24 Features, 0.511).
  Die Trigger-/2nd-Trigger-Features sind unter CV **Rauschen**, das leicht schadet. Konsequenz für alle
  weiteren Iterationen: schlanke own+content-Basis, Trigger nur als gezielte Veto-up-Regel (Iter 01:
  Präzision 0.83–1.0), nicht im LogReg-Vektor.
- **Komplementarität bestätigt am Modell:** own (0.408) ⊕ content (0.430) → 0.514. Die Achsen addieren
  sich real, wie Iter 01/02 vermuten ließen.
- **Lücke zur Algo-Bar ehrlich verortet:** 0.514 (schlanke CV-LogReg) vs 0.603 (M9 PerJournalBase).
  Die ~0.09 stecken in **Per-Journal-Basisraten + Cascade-Struktur + Threshold-Tuning**, nicht in mehr
  Rohfeatures. Das ist der nächste Hebel — nicht „noch ein Feature".
- **Schwäche:** LogReg ist linear; Interaktionen (z. B. „hohe Sim NUR wenn Abstract vorhanden")
  bleiben ungenutzt → Iter 04 Baummodell. Und `class_weight=balanced` treibt keep-Recall künstlich;
  Kalibrierung+Threshold (Iter 05) ist sauberer als balanced.
- **Selbst-Check:** kein journal→Raum-Leak; aber `f_year_normalized`/`abstract_len` in ALL sind
  potenziell selektions-/venue-korreliert → in Phase D (Leakage-Audit) prüfen.

## → nächste Iteration
Iter 04: Baummodell (GBM/LGBM) auf own+content unter CV — fängt es die Interaktionen, die LogReg
verfehlt? Danach Iter 05: Per-Journal-Prior als der eigentliche Hebel zur Algo-Bar.
