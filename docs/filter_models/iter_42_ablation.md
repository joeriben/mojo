# Iter 42 — Feature-Ablation: Essenz vs. Schmuck in M-C

## Anforderung
Welches Signal trägt M-C wirklich? Drop-one-out (rich_sim / Journal-Prior / Biblio-Veto), keep-AUC +
LES-Recall@20 %, seed-gemittelt (P15: Spannen statt Glücksseed). Grundlage für die M-E-Spezifikation:
was ist essenziell, was schmückend.

## Messung (`iter_42_ablation.py`, 5 Seeds, alle Quellen)
| Variante | keep-AUC | LES-Recall@20 % |
|---|---|---|
| **M-C voll** (rich+Prior+Biblio-Veto) | **0.736 ± 0.002** | **46 % ± 1pp** |
| ohne Biblio-Veto | 0.718 ± 0.002 | 40 % ± 2pp |
| ohne Journal-Prior | 0.709 ± 0.000 | 41 % ± 0pp |
| ohne rich_sim (nur Prior+Veto) | **0.694 ± 0.004** | **51 % ± 2pp** |

Beitrag zur keep-AUC: **rich_sim +0.041**, Journal-Prior +0.027, Biblio-Veto +0.018.

## Harte Kritik
- **Der scheinbare Widerspruch ist der eigentliche Befund (P6, P15):** „ohne rich_sim" hat die
  *schlechteste* AUC (0.694) und zugleich die *beste* LES-Recall@20 % (51 % vs voll 46 %). Kein Fehler —
  eine **Arbeitsteilung**: das **Biblio-Veto** hebt die bibliometrisch verankerten LES (own_coupling/
  citation) hart an die Spitze (score 1+mc) → exzellente Top-20-%-Ausbeute, aber darunter ist alles
  ungeordnet → schlechte Gesamt-AUC. **rich_sim** liefert die breite Rangordnung (beste AUC), addiert
  aber wenig an der äußersten Spitze, weil die dortigen LES schon biblio-gefangen sind. Die beiden sind
  **komplementär, nicht redundant.**
- **Das korrigiert/präzisiert Iter 40 (P3):** Iter 40 sagte „rich-sim trägt 96 %". Stimmt *für die
  globale AUC* — aber **für die im Betrieb relevante Top-K-Kaskade trägt das Biblio-Veto überproportional**,
  weit mehr, als sein AUC-Beitrag (+0.018) suggeriert. Wer nur auf AUC schaut, unterschätzt das Veto;
  wer nur auf Top-K-Recall schaut, unterschätzt rich_sim. **Beide Metriken zusammen** geben das ehrliche
  Bild — eine einzelne hätte in die Irre geführt.
- **Für M-E heißt das (P11, P16):** keine Komponente streichen. rich_sim = Pflicht (globale Ordnung,
  Generalisierung auf neue Journals, Iter 40). Biblio-Veto = Pflicht (Top-Präzision, billig, geerdet).
  Journal-Prior = nützlich bei bekannten Journals (+0.027), aber Memorisierung (Iter 40) — als
  konfigurierbarer, nie-veto-down-Lift behalten, nicht als Kern verkaufen.
- **Grenze des Tests (P3):** „alle Quellen" enthält den intentional-positiven Pool — die Biblio-Veto-
  Stärke ist dort überzeichnet (citation-keeper sind per Konstruktion biblio-positiv, Iter 39). Auf dem
  reinen blinden Strom (Iter 36: M-C-AUC 0.66±0.01, rich 0.632) ist der Veto-Beitrag kleiner, weil dort
  nur ~0–3 % Biblio-Treffer liegen. Die *Rangfolge* der Komponenten (rich ≥ Prior ≥ Veto für AUC) bleibt,
  die *Beträge* schrumpfen. Ehrlich: die Tabelle ist die obere Schätzung des Veto-Werts.

## → nächste Iteration
Iter 43: **Grounded-Bezug-Coverage auf der keep-Menge** — der eigentliche Produkt-Output. Wie viele der
keeper bekommen einen ECHTEN geerdeten Werk-/Autor-Bezug (own_refs ∩ article-refs bzw. bezugsautoren),
und wie viele bleiben „Leerstelle"? Verbindet Triage (M-C) mit dem substitutiven Komponisten (Iter 19)
und der Konfabulations-Vermeidung (Memory feedback_llm_bezuege).
