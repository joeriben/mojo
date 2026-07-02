# Iter 48 — Kalibrierung: M-E-Score als Wahrscheinlichkeit?

## Anforderung
Die Confidence-Bänder (Iter 46) ruhten auf Perzentilen. Dürfen sie auf *kalibrierten* p-Schwellen ruhen?
Test: ECE (Expected Calibration Error) + Reliabilitätskurve, roh (M-C als p) vs. isotonisch out-of-fold
kalibriert (M-C → keep-Wahrscheinlichkeit). Seed-gemittelt, OOF (kein Leak, P3/P5).

## Messung (`iter_48_calibration.py`, alle Quellen, 5 Seeds, 10 Bins, OOF)
| Variante | ECE |
|---|---|
| roh (M-C als p) | 0.088 ± 0.005 |
| **isotonisch kalibriert** | **0.047 ± 0.002** |

Reliabilitätskurve (kalibriert): vorhergesagt → beobachtet
| p-Bin | n | Ø-p | beobachtet keep |
|---|---|---|---|
| 0.0–0.2 | 66 | 0.09 | 0.12 |
| 0.2–0.4 | 171 | 0.30 | 0.33 |
| 0.4–0.6 | 158 | 0.50 | 0.47 |
| 0.6–0.8 | 36 | 0.69 | 0.67 |
| 0.8–1.0 | 30 | 0.88 | 0.83 |
Basisrate keep: 0.41.

## Harte Kritik
- **Roh ist M-C keine Wahrscheinlichkeit, kalibriert schon (P6, P16):** der rohe Score ist um ~8.8 %
  fehlkalibriert (ECE 0.088) — als p genommen würde er lügen. Eine billige **isotonische OOF-Kalibrierung**
  halbiert das auf ECE 0.047 und liefert eine fast perfekt monotone Reliabilitätskurve (jeder Bin trifft
  die beobachtete keep-rate auf ±0.03). Damit ist belegt: **M-E darf eine kalibrierte keep-Wahrscheinlichkeit
  ausgeben** — die Confidence-Bänder (Iter 46) müssen nicht auf willkürlichen Perzentilen ruhen, sondern
  auf interpretierbaren p-Schwellen („dieser Artikel ist mit p≈0.5 ein keeper").
- **Aber Kalibrierung verbessert die Trennschärfe NICHT (P15, P9):** isotonische Regression ist monoton —
  sie verändert die *Rangordnung* nicht, nur die *Skala*. Die AUC bleibt 0.736, der Hard-Case bleibt hart
  (Iter 47). Kalibrierung macht den Score *ehrlich lesbar*, nicht *besser*. Ich verkaufe sie nicht als
  Leistungsgewinn — sie ist eine Benutzbarkeits-, keine Qualitätsverbesserung.
- **Geltungsbereich-Caveat ist hier kritisch (P3):** kalibriert wurde auf „alle Quellen" (Basisrate 0.41).
  Der blinde Strom hat Basisrate 0.21 — eine dort eingesetzte Kalibrierung muss auf strom-ähnlicher
  Verteilung gefittet werden, sonst sind die p-Werte systematisch zu hoch. Die **Methode** (isotonisch OOF)
  ist validiert, die konkreten p-Zahlen sind populationsabhängig. M-E braucht also einen Kalibrator, der
  auf dem **Produktions-Strom** (screening-mode) nachgezogen wird, nicht auf dem intentional-positiven Pool.
- **Bins gut besetzt → Kurve belastbar (P3):** 66/171/158/36/30 pro Bin — keine Ein-Punkt-Artefakte. Die
  Kalibrierungs-Aussage steht auf realer Masse, nicht auf Rauschen. (Im Gegensatz zu manchen blind-Strom-
  Zahlen mit n<10, die ich konsequent als unterbesetzt markiert habe.)

## → nächste Iteration
Iter 49: **Robustheit gegen fehlenden Abstract (Pfad-B-Fallback)** — Iter 34 zeigte: alle blind-LES liegen
in Pfad A (abstract-reich), Pfad B (43 %, kein Abstract) hat 0 LES. Was kann M-E auf Pfad B überhaupt
leisten, bevor Volltext geholt wird? Letzter Stress-Test vor der finalen Synthese (Iter 50).
