# Iter 02 — Inhalts-Achse (Embedding/TFIDF/Concept-Similarity)

## Anforderung
Iter 01 zeigte: Bibliometrie sieht nur 19 % der Treffer. Der Recall muss von der Inhalts-Achse
kommen. Frage: trägt Inhalts-Ähnlichkeit Signal — und rettet sie speziell die bibliometrisch
unsichtbaren Treffer?

## Entwurf
- **Features (P2, content-Familie):** `score_M6_TfidfSimilarity`, `score_M7_EmbeddingSimilarity`,
  `score_M10_ConceptVector` (bereits berechnet, gegen Benjamins Korpus — werk-geerdet, nicht Raum-Label).
- **Mechanismus:** Quantil-Schwellen-Sweep je Score → keep; plus AUC-Test der Embedding-Sim auf
  „unsichtbare Treffer vs discards".

## Messung (`iter_02_content_axis.py`)
| Score | best f1_keep | keepPrec | keepRec |
|---|---|---|---|
| TFIDF (M6) | 0.517 | 0.415 | 0.686 |
| **Embedding (M7)** | **0.615** | 0.535 | 0.723 |
| Concept (M10) | 0.599 | 0.474 | 0.814 |

**Komplementaritäts-Test:** Embedding-Median unsichtbare-keep 0.608 vs discards 0.582;
**AUC = 0.660** (unsichtbare Treffer vs discards, nur Embedding).

## Harte Kritik
- **Embedding ist die stärkste Einzelachse** (0.615 keep-F1) und schlägt die bibliometrische Union
  (0.312) klar — bestätigt: Recall lebt im Inhalt, nicht in den Refs.
- **Aber schwach komplementär:** AUC 0.66 auf den unsichtbaren Treffern heißt — Inhalt hebt sie nur
  leicht über die discards. Der Median-Abstand (0.608 vs 0.582) ist winzig. Das erklärt das ~0.60-Plateau:
  *beide* Achsen sind je für sich mäßig, und sie ergänzen sich nur teilweise.
- **3-Klassen weiter 0 LES-Rec** (Binärschwelle) — Schwellen-Modelle können die LES/SCAN-Grenze
  nicht ziehen; dafür braucht es ein echtes 3-Klassen-Modell (Phase B).
- **Ungeerdet (P16-Mangel):** Embedding-Sim sagt „ähnlich zum Korpus", nennt aber keinen *konkreten*
  Bezug. Als Relevanz-*Begründung* unbrauchbar — nur als Score. Das eigentliche Motiv (geerdete
  Bezüge) ist hier nicht bedient; bleibt für Phase C.
- **Selbst-Check:** Score-Spalten stammen aus dem Korpus, kein journal→Raum-Leak (P3 ok).

## → nächste Iteration
Iter 03: Wenn beide Achsen je mäßig sind — wie viel bringt ihre **Kombination**, und welche
**Feature-Familie** trägt unter sauberer CV den F1? Ablation own/trigger/content/all.
