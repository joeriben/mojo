# Iter 09 — Per-Werk-max-Similarity zum Œuvre

## Anforderung
Iter 02: globale Korpus-Sim (score_M7) nur AUC 0.66. Memory (Profil-Modellierung): per-Werk-Embedding +
max über 161 Eigenwerke sollte mehr tragen als der globale Schwerpunkt. Offline (sentence-transformers).

## Messung (`iter_09_perwork_embedding.py`, MiniLM + TFIDF, 161 Pubs × 461 Artikel)
| Feature | keep-AUC | AUC unsichtbare-keep vs disc |
|---|---|---|
| ST per-Werk-max | 0.691 | 0.661 |
| TFIDF per-Werk-max | 0.609 | 0.561 |
| score_M7 (global, Referenz) | 0.692 | 0.657 |

## Harte Kritik
- **Hypothese nicht gestützt (P6/P15):** Per-Werk-max (0.691) ≈ globale Sim (0.692). Die per-Werk-
  Zerlegung hebt die keep-Diskrimination **nicht**. Der Inhalts-Kanal sitzt bei ~0.69 AUC fest,
  egal ob global oder per-Werk.
- **Wahrscheinliche Ursache:** per-Werk-Text = nur Titel+Venue (kein Volltext/Abstract der Eigenwerke
  verfügbar als kurzer Vektor). Title-only ist zu dünn, um die Multimodalität des Werks aufzulösen —
  d. h. die Hypothese ist nicht widerlegt, sondern **mit dieser Textbasis nicht testbar**. Ehrlich vermerkt.
- **TFIDF deutlich schwächer** (0.609) → lexikalische Überlappung Titel↔Abstract ist dünn; semantische
  Embeddings sind nötig. Bestätigt, dass score_M7 (Embedding) die richtige content-Achse ist.
- **Konsequenz:** der per-Werk-Gedanke bleibt für **Routing/Cluster/Trends** (Profil-Sketch) plausibel,
  ist aber **kein keep-Hebel**. Für Relevanz zählt nur, dass *irgendein* Inhalts-Signal ~0.69 AUC liefert —
  und das hat score_M7 schon. Keine Verbesserung hier.

## → nächste Iteration
Iter 10: Inhalts-Kanal sitzt bei 0.69, Bibliometrie bei 19 % Recall — **beste Kombination beider**
unter CV als ehrliches 3-Klassen-Modell (own+content+global-sim), gegen die ehrliche Leiste 0.544/0.589.
