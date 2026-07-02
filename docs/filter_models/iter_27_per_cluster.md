# Iter 27 — Per-Cluster-Ranking (Profil-Sketch-Topologie)

## Anforderung
project_profile_modelling: per-Werk-Embedding + Soft-Cluster schlägt globale Haufen-Aggregation. Iter 12
testete das Extrem (per-Werk-max ≈ global). Hier der Mittelweg: 53 Eigenwerk-Summaries in K Cluster
(KMeans), Artikel gegen den **ähnlichsten** Cluster-Schwerpunkt ranken. Voll geerdet, KEINE Diskurs-Labels.

## Messung (`iter_27_per_cluster.py`, MiniLM, reicher Text beidseitig)
| Repräsentation | AUC gesamt | AUC screening |
|---|---|---|
| global Schwerpunkt | 0.679 | **0.648** |
| per-Cluster K=3 | 0.675 | 0.621 |
| per-Cluster K=5 | 0.672 | 0.618 |
| per-Cluster K=7 | 0.663 | 0.638 |
| per-Cluster K=10 | 0.683 | 0.621 |
| per-Werk-max (Iter 12) | 0.690 | 0.632 |

## Harte Kritik
- **Die Profil-Sketch-Topologie-Hypothese ist widerlegt (P6, P15):** global, K-Cluster (K=3…10) und
  per-Werk liegen alle in einem schmalen Band (gesamt 0.66–0.69, screening 0.62–0.65). Keine Topologie
  schlägt die globale Aggregation für die keep-Diskrimination. Die in project_profile_modelling
  vermutete Überlegenheit der Soft-Cluster-Struktur trägt für *diese* Aufgabe **nicht**. Damit ist die
  Hypothese über drei Iterationen (09 per-Werk-Titel, 12 per-Werk-reich, 27 per-Cluster) konsistent
  falsifiziert — nicht aus einem Lauf geschlossen.
- **Klärt und korrigiert Iter 13 (P3 — Ehrlichkeit über die eigene frühere Lesart):** ich hatte den
  blinden Gewinn „rich" der **per-Werk**-Zerlegung zugeschrieben. Iter 27 zeigt: der Hebel war der
  **reiche Text** (summary_de + key_terms + named_thinkers), NICHT die per-Werk-Aggregation. Global-rich
  (screening 0.648) ist sogar minimal *besser* als per-Werk-rich (0.632). Der Sprung von M7 (0.517,
  Iter 13) auf ~0.65 kam vom Textinhalt, nicht von der Topologie.
- **Konsequenz für Produktion (P13 — einfachste Lösung):** der rich-Ranker sollte den **globalen
  rich-Schwerpunkt** verwenden, nicht per-Werk-max — simpler (eine Zentroid-Sim statt 53 Maxima) und
  marginal besser. Der gecachte `rich_sim` (per-Werk-max) aus Iter 12 ist für die bisherigen Iterationen
  innerhalb des Rauschens äquivalent; für die Synthese (Phase E) wird global-rich als kanonische Variante
  vermerkt.
- **Was offen bleibt, ehrlich:** die per-Werk/Cluster-Topologie *kann* für andere Profil-Zwecke (Trend-
  Diskursräume, Eskalations-PrioScore, Digest-Sortierung nach Cluster) sinnvoll sein — das habe ich hier
  NICHT getestet, nur die keep-Diskrimination. Ich verwerfe die Topologie für *Triage/Ranking*, nicht
  pauschal für die Profil-Modellierung. Kein Über-Generalisieren.

## → nächste Iteration
Iter 28: **Author-Identitäts-Achse** — die bisherigen Achsen sind Refs/Inhalt/Journal. Fehlt: schreibt
der Artikel von einem Autor, den Benjamin schon zitiert/koautort hat (nicht Trigger-Liste, sondern aus
own_refs/bezugsautoren abgeleitet)? f_coauthor_hits + bezugsautoren-Autor-Match als geerdete Identitäts-
Achse, Diskrimination + blind-Coverage. Ergänzt den Komponisten um „Autor, den du kennst".
