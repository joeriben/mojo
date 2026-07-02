# Iter 16 — operativer Keep-Ranker (rich-Sim + Bibliometrie-Veto-up)

## Anforderung
Die zwei belastbaren Befunde zu *einem* Werkzeug verbinden: Bibliometrie hochpräzise aber selten
(Iter 01), rich-Sim bester blinder Ranking-Hebel (Iter 15). Deliverable: Recall@Sichtungslast gegen
den aktuellen Produktiv-Score M7. „Sichtungslast" = welcher Anteil des Stroms muss gelesen werden.

## Messung (`iter_16_operative_ranker.py`)
**GESAMT (n=461, keep=188, Basisrate 41 %):**
| Ranker | AUC | R@10% | R@20% | R@30% | R@50% |
|---|---|---|---|---|---|
| M7 (aktuell) | 0.692 | 18 % | 31 % | 45 % | 65 % |
| rich | 0.690 | 19 % | 30 % | 42 % | 64 % |
| **rich+Biblio-Veto** | **0.709** | 20 % | 34 % | 44 % | 66 % |

**SCREENING / blinder Strom (n=120, keep=25, Basisrate 21 %):**
| Ranker | AUC | R@10% | R@20% | R@30% | R@50% |
|---|---|---|---|---|---|
| M7 (aktuell) | 0.517 | 4 % | 12 % | 32 % | 52 % |
| **rich** | **0.632** | **20 %** | **32 %** | **48 %** | **68 %** |
| rich+Biblio-Veto | 0.624 | 20 % | 32 % | 48 % | 68 % |

## Harte Kritik
- **Belastbares Produktiv-Ergebnis (P16, P4):** auf dem blinden Strom holt der rich-Ranker am
  Listenkopf **5× mehr** Treffer als M7 (R@10 %: 20 % vs 4 %) und durchgehend mehr (R@50 %: 68 % vs
  52 %). Da die Aufmerksamkeit eines Forschers genau oben liegt, ist das der relevante Gewinn — und er
  ist vollständig in Benjamins **zusammengefasstem Œuvre** geerdet (summaries.json), nicht in
  Diskurs-Labels. Das ist die saubere Umkehrung des heutigen Zirkularitäts-Fehlers.
- **Veto-Effekt ehrlich differenziert (P15):** der Biblio-Veto hilft **gesamt** (AUC 0.692→0.709, weil
  dort 42 Treffer feuern), ist auf dem **blinden** Strom aber neutral bis minimal negativ (0.632→0.624,
  weil er kaum feuert und der 1 Treffer nicht zwingend der Top-Keeper ist). Kein Overclaim: der Veto ist
  ein **Präzisions-Anker** (wenn er feuert, ist er fast sicher richtig — Iter 01), kein Recall-Hebel.
  Für Produktion bedeutet das: rich-Sim als Score, Biblio-Treffer oben angeheftet — als Garantie, nicht
  als AUC-Trick.
- **Grenze klar benannt:** AUC 0.632 blind ist ein *brauchbarer*, kein *starker* Ranker. Bei R@50 % bleiben
  32 % der Treffer unter der Sichtungsschwelle. Wer nichts verpassen darf, muss weiter (fast) alles
  sichten — der Ranker verbessert die **Reihenfolge** (früher mehr Treffer), nicht die Vollständigkeit.
  Das deckt sich mit Iter 08 (Vorfilter spart bei hohem Recall wenig).
- **Was offen bleibt (P3):** alle Zahlen auf n=120 blind / 25 keep — richtungsweisend, verrauscht. Der
  echte Test ist der Volllauf-Strom (49 Journals, sehr niedrige Basisrate); dort könnte der Vorsprung am
  Kopf größer *oder* kleiner sein. Als Limit vermerkt, nicht hochgerechnet (P14/Memory: keine
  optimistischen Projektionen aus Einzeltests).

## → nächste Iteration (Phase C — das eigentliche 2.0-Motiv)
Iter 17: Wechsel von *Ranking* zu **geerdeten Bezügen** (feedback_llm_bezuege_konfabulation = der
eigentliche Grund für 2.0). Nicht „wie relevant", sondern „**welcher** konkrete Eigenwerk-Bezug" —
geteilte Referenzen zwischen Artikel und benanntem Eigenwerk (`own_refs/pub_refs` + `bezugsautoren.db`).
Diagnose: für wie viele keeper lässt sich überhaupt ein *konkreter* geteilter Bezug benennen (statt
LLM-Konfabulation)? Das ist die Substitutiv-Komponente, nicht der Score.
