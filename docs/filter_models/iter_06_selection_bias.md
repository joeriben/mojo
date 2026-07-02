# Iter 06 — Selection-Bias / Blind-Screening-Eval

## Anforderung
Der reale Use-Case ist der *blinde* einlaufende Strom. Memory: 65 % der LES stammen aus
intentional-positiven Quellen. Frage: bricht die Performance auf der blinden Teilmenge ein?

## Messung (`iter_06_selection_bias.py`, selection_mode aus articles.db)
LES-Anteil je Herkunft — bestätigt den Bias scharf:
| selection_mode | n | LES% | keep% |
|---|---|---|---|
| citation | 22 | 86.4 | 95.5 |
| mixed | 20 | 75.0 | 95.0 |
| trigger | 2 | 100 | 100 |
| complementarity | 187 | 16.0 | 47.1 |
| **screening** (echt blind) | 120 | **6.7** | 20.8 |
| similarity | 110 | 4.5 | 30.0 |

LogReg own+content nach Herkunft:
| Teilmenge | n | f1_3cls | f1_keep | LES-Rec |
|---|---|---|---|---|
| ALLE | 461 | 0.514 | 0.605 | 0.532 |
| „BLIND" (screening+similarity+unknown) | 230 | 0.485 | **0.459** | 0.462 |
| intentional-positiv | 231 | 0.494 | 0.692 | 0.545 |

## Harte Kritik
- **Schlagzeilen sind aufgebläht:** auf der (näherungsweise) blinden Teilmenge fällt keep-F1 von
  0.605 → **0.459**. Die intentional-positiven Artikel (per citation/coupling/similarity ausgewählt)
  füttern dem Modell genau die Signale, auf die es hört → zirkulär hohe Performance dort. Der reale
  einlaufende Strom ist die blinde Teilmenge, und dort ist der Filter schwach.
- **Selbst-gefangener Eigenfehler (P6):** ich habe `similarity` in „blind" gesteckt, obwohl es
  *content-intentional-positiv* ist (per Embedding-Sim ausgewählt). Das echte Blind = `screening`
  allein (n=120, nur 6.7 % LES, 20.8 % keep — extrem unbalanciert). → Iter (Phase D) muss
  screening-only sauber auswerten; die 0.459 sind eine optimistische Untergrenze des Einbruchs.
- **Zusammen mit Iter 05:** zwei Inflationsquellen aufgedeckt — (a) in-sample-Per-Journal-Leak in der
  „Bar", (b) Selection-Bias in der Headline-Performance. Ehrlich ist der algorithmische Filter auf
  dem blinden Strom **deutlich** unter 0.54.
- **Konsequenz fürs Ziel:** auf `screening` ist LES so selten (6.7 %), dass LES-Recall dort das
  eigentliche, sehr schwere Problem ist — und genau dort sitzt der Wert für Benjamin (echte
  Entdeckungen im blinden Strom). Phase B/C müssen an dieser Teilmenge gemessen werden, nicht am Mix.

## → nächste Iteration (Phase B)
Iter 07: erstes ernsthaftes werk-geerdetes Relevanzmodell mit **kalibrierten Wahrscheinlichkeiten +
Threshold auf LES-Recall** (statt brutalem class_weight), Bewertung getrennt für screening-only.
