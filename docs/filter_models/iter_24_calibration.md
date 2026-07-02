# Iter 24 — Kalibrierungs-Ehrlichkeit des Keep-Rankers

## Anforderung
Wenn der Komponist (Iter 19) eine keep-Wahrscheinlichkeit impliziert, muss sie stimmen. Isotonic-
kalibrierte P(keep) aus rich_sim (OOF), Reliability auf dem screening-Strom, getrennt abstract-voll/arm.
ECE = mittlerer |vorhergesagt − tatsächlich|.

## Messung (`iter_24_calibration.py`)
| Teilmenge | Brier | ECE | Auffälligkeit |
|---|---|---|---|
| GESAMT (n=461, Basis 41 %) | 0.217 | **0.044** | gut: 12/33/42/48/63 % ≈ 17/36/39/52/57 % |
| SCREENING blind (n=120, Basis 21 %) | 0.208 | **0.201** | sagt 39 %→**0 %**, 59 %→33 % (überschätzt) |
| SCREENING abstract-voll (n=69, Basis 23 %) | 0.206 | 0.185 | weiterhin mies |

## Harte Kritik
- **Die gute Gesamt-Kalibrierung ist eine Fata Morgana (P15, P3 — der Kernbefund):** ECE 0.044 auf der
  Mischmenge sieht vorbildlich aus, aber auf dem blinden Strom explodiert er auf **0.201** (5×). Der
  Score „lügt" dort: er verspricht 39 % keep, wo 0 % sind. Hätte ich nur die Gesamt-Kalibrierung
  berichtet, wäre das ein grober Etikettenschwindel gewesen.
- **Die Ursache ist Basisraten-Verschiebung, nicht der Abstract (P6):** der Kalibrator lernt die
  Mischmengen-Basisrate (41 %); der blinde Strom hat 21 %. Da auch abstract-voll-blind mies bleibt
  (0.185), liegt es nicht an fehlenden Abstracts (Iter 23), sondern an der **Quellen-Komposition** des
  Trainings. Jedes auf dem Gold-Satz kalibrierte Wahrscheinlichkeits-Modell überschätzt keep auf dem
  realen Strom — ein genereller, harter Vorbehalt gegen „P(relevant)=X %"-Anzeigen.
- **Das validiert iter_19s Design (P16, P8):** der Komponist zeigt **Perzentil-Rang** („oberes X %"),
  nicht „P(keep)=Y %". Ränge sind **basisraten-invariant** — der beste Artikel bleibt der beste, egal
  wie selten keeper sind. Wahrscheinlichkeiten brechen unter Basisraten-Shift. Die Rang-Anzeige war also
  nicht nur Geschmack, sondern die einzig ehrliche Wahl; dieser Test liefert die Begründung nachträglich.
- **Ehrlich über n und Monotonie:** die Nicht-Monotonie blind (39 %→0 %, dann 47 %→31 %) ist teils
  Rauschen (~20–29/Bin). Die *systematische Überschätzung* (vorhergesagt > tatsächlich in den oberen
  Bins) ist aber konsistent und durch den Basisraten-Mechanismus erklärt — kein Artefakt.
- **Konsequenz:** falls je eine Wahrscheinlichkeit angezeigt werden soll, muss sie **auf der blinden
  Basisrate** (re-)kalibriert werden, nicht auf dem Gold-Mix. Default bleibt: Rang zeigen, nicht Prozent.

## → nächste Iteration
Iter 25: **Journal-Prior-Stabilität** — Iter 05 fand Per-Journal-Prior als in-sample-Leak. Hier: über
wie viele Journals ist der Gold-Satz verteilt, wie dünn ist die Per-Journal-Masse, und ist ein
geshrinkter (Empirical-Bayes) Journal-Prior auf dem blinden Strom stabil genug, um als schwacher
Zusatz-Anker zu taugen — oder ist die Per-Journal-Schätzung schlicht zu verrauscht?
