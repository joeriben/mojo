# Iter 38 — per-Verortung-balancierter Ranker (Reparatur des blinden Flecks)

## Anforderung
Iter 37: globaler rich-Schwerpunkt ÄKB-dominiert → Frontier (digitale_kultur/resilienz) tief gereiht.
Reparatur: pro Diskursraum ein Eigenwerk-Schwerpunkt (aus discourse-gelabelten Publikationen), Artikel
gegen den Schwerpunkt SEINES Raums ranken. Hebt das die Frontier ohne Kern-Schaden?

## Messung (`iter_38_balanced_ranker.py`, blinder Strom)
| Diskursraum | keeper | global-Rang | balanciert-Rang |
|---|---|---|---|
| **resilienz** | 3 | 38 % | **52 %** (+14) |
| **digitale_kultur** | 12 | 44 % | **48 %** (+4) |
| medienpaed | 7 | 74 % | 69 % (−5) |
| aesthetische_kulturelle_bildung | 5 | 70 % | 64 % (−6) |
blind keep-AUC: global 0.629 → balanciert 0.620.

## Harte Kritik
- **Die Reparatur wirkt — aber sie ist eine Umverteilung, kein Gewinn (P15, P11):** der balancierte
  Ranker hebt resilienz (+14 pp) und digitale_kultur (+4 pp), senkt aber medienpaed (−5) und ÄKB (−6),
  und die Gesamt-AUC fällt minimal (0.629→0.620). Weil Perzentil-Ränge **nullsummig** sind, kann die
  Frontier nur auf Kosten des Kerns steigen. Es gibt keinen freien Fairness-Gewinn — nur eine bewusste
  **Verschiebung der Aufmerksamkeit** von Kern zu Frontier.
- **Erneut eine Werte-, keine Metrik-Entscheidung (P11, P16):** wie bei der Serendipität (Iter 26) hängt
  die richtige Wahl an Benjamins Präferenz: priorisiert er die wachsende Kante (Cultural Resilience,
  AI4ArtsEd) über die Effizienz im etablierten Kern, ist die Balancierung richtig — auch bei −0.01 AUC.
  Das gehört konfigurierbar (per-Verortung-Gewichte in profile.json), nicht hart verdrahtet.
- **Die aktuelle Implementierung ist die schwache Version (P3, P6):** die per-Diskurs-Schwerpunkte sind
  hier aus Publikations-**Titeln+Venue** gebaut (kein Summary-Text — die Summaries sind nicht discourse-
  gelabelt, und der Zotero-Key↔Hash-Join fehlt). Titel-Text ist dünn (Iter 09). Mit discourse-gelabelten
  **Summary**-Schwerpunkten (summary_de) wäre die Frontier-Anhebung vermutlich sauberer und der Kern-
  Verlust kleiner. Der gemessene +14/+4-Lift ist also eine **Untergrenze** des Möglichen — als
  Aufarbeitungs-Aufgabe vermerkt (Summaries um discourse-Label erweitern).
- **Versöhnt mit Iter 27 (P3):** Iter 27 verwarf die per-Cluster-Topologie für *Aggregat-AUC* — zu Recht.
  Iter 38 zeigt ihren Wert auf der *Fairness*-Achse. Beides stimmt: Topologie hilft nicht der globalen
  Trennschärfe, aber der disziplinären Ausgewogenheit. Keine Kehrtwende, eine Differenzierung nach Zweck.

## → nächste Iteration
Iter 39: **Complementarity-Pool-Test** (Memory feedback_ground_truth: die „Triage-Falle" — 41 % der
LES aus complementarity-Quelle, wo Algo+Opus je nur ~58–62 % Agreement). Wie reiht M-C die
complementarity-stämmigen keeper gegenüber den citation/trigger-stämmigen? Das prüft, ob M-C die
*schwer-begründbaren* Treffer trifft oder nur die offensichtlichen.
