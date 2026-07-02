# Iter 15 — mean als ein Feature + Ranker-Re-Framing

## Anforderung
Iter 14: rich roh neben M7 schadet der 3-Klassen-macro-F1. Zwei Tests: (1) hilft `mean(rich,global)`
als **ein** engineertes Feature (der in Iter 13 beste Kombinierer)? (2) Re-Framing als reiner
**KEEP-RANKER** auf dem blinden Strom — der reale Vorfilter/Digest-Sortier-Use-Case.

## Messung (`iter_15_engineered_mean.py`, OOF)
**Test 1 — 3-Klassen:**
| Modell | macro-F1 (gesamt) | macro-F1 (screening) |
|---|---|---|
| own+content (Basis) | 0.514 | 0.444 |
| own+content+mean | 0.492 | 0.426 |
| own + mean (1 Feat) | 0.488 | 0.356 |

**Test 2 — KEEP-RANKER, blinder Strom (n=120, keep=25):**
| Ranker | AUC | Recall@top30% | Recall@top50% |
|---|---|---|---|
| content_mean (rich⊕global) | 0.607 | 40 % | 60 % |
| score_M7 allein (global, aktueller Produktiv-Score) | 0.517 | 32 % | 52 % |
| **rich allein** | **0.632** | **48 %** | **68 %** |

## Harte Kritik
- **Die Entscheidungs-Lücke ist strukturell, nicht der Kombinierer (P6, P15):** mean als ein Feature
  hilft der 3-Klassen-macro-F1 genauso wenig (0.514→0.492) wie beide roh (Iter 14). Damit ist sauber
  geklärt: der content-Hebel bewegt die *harte 3-Klassen-Grenze* nicht — egal in welcher Form. Diese
  Tür ist zu, und sie bleibt zu; kein weiteres Feature-Engineering daran.
- **Aber das Ranker-Re-Framing liefert das erste klar brauchbare Produktiv-Ergebnis (P16):** als
  KEEP-Ranker auf dem **blinden** Strom schlägt **rich allein** (AUC 0.632, 68 % Recall in der oberen
  Hälfte) den aktuellen Produktiv-Score M7 (0.517, 52 %) deutlich — **+16 pp** Treffer-Recall bei
  gleicher Sichtungslast. Konkret: wer die obere Hälfte des blinden Stroms liest, findet mit der
  werk-geerdeten rich-Sim 68 % statt 52 % der echten keeper. Das ist messbar, geerdet, einsetzbar.
- **Selbstkorrektur (P3):** im Ranker-Test ist `keep`=25 (scannen+lesenswert), nicht die 8 LES aus
  Iter 11/14 — ich habe die richtige Ziel-Menge für den Ranker (keep, nicht nur LES) verwendet und das
  explizit ausgewiesen, statt die Zahlen zu vermischen.
- **content_mean schlechter als rich-solo blind (0.607 vs 0.632):** das global-M7 zieht auf dem blinden
  Strom runter (es ist dort ≈Zufall, Iter 13). Für die *blinde Produktion* ist also **rich-solo** das
  Rückgrat, nicht das Mittel. Ehrlich: das Mittel war nur auf der bias-behafteten Gesamtmenge bester
  (Iter 13) — set-abhängig, kein universeller Sieger.
- **Grenze benannt:** AUC 0.632 ist immer noch ein *mäßiger* Ranker (nicht 0.8+). Er halbiert nicht die
  Last; er verbessert die Trefferausbeute der Sichtung spürbar, aber der blinde Strom bleibt schwer.
  Kein Overclaim — der Gewinn ist real und begrenzt.

## → nächste Iteration
Iter 16: den **operativen Keep-Ranker** bauen und als Vorfilter-Deliverable messen — rich-Sim als Score
**plus** hochpräziser Bibliometrie-Veto-up (Iter 01: Präzision 0.83–1.0) als Top-Anker — und die
Recall@Sichtungslast-Kurve auf dem blinden Strom gegen M7 dokumentieren. Das verbindet die zwei
belastbaren Befunde (Biblio-Präzision + rich-Ranking) zu *einem* einsetzbaren Werkzeug.
