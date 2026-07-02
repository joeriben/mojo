# Iter 31 — Modell M-C: Betriebspunkt (Synthese-Anker)

## Modell-Definition
**M-C** (empfohlenes blindes Ranking-Modell aus Iter 01–30):
`mean(rich-Content, journal-prior-lift-only) + Bibliometrie-Präzisions-Anker (Veto-up)`.
- rich-Content = global-rich-Sim (Titel+summary_de, Iter 29) — der tragende Hebel.
- journal-prior-lift-only = EB-Journal-Prior, nur Aufschlag, nie Abzug (Iter 26, serendipitäts-sicher).
- Bibliometrie-Anker = own_coupling/citation-Treffer ganz oben (Iter 16, hochpräzise wenn vorhanden).

## Messung (`iter_31_operating_point.py`, OOF, blinder Strom n=120, keep=25, LES=8)
| Sichtungslast | keep-Recall | keep-Precision | LES-Recall |
|---|---|---|---|
| 10 % | 20 % | 42 % | 38 % |
| **20 %** | **44 %** | **46 %** | **62 %** |
| 30 % | 52 % | 36 % | 75 % |
| 50 % | 64 % | 27 % | 75 % |
| 100 % | 100 % | 21 % | 100 % |

Referenz M7 (aktuell): @20 % keep-Recall 12 % / LES 12 %; @50 % 52 % / 50 %.

## Harte Kritik
- **Konkreter, belastbarer Nutzen (P16, P4):** wer die **obersten 20 %** des blinden Stroms liest, fängt
  mit M-C **62 % der Pflichtlektüre** (LES) — gegenüber **12 %** mit dem aktuellen M7. Die keep-Precision
  oben liegt bei 46 % (2,2× Basisrate 21 %). Das ist die integrierte Antwort auf „lohnt sich das System":
  ja, am Listenkopf liefert es das Mehrfache des Status quo, und das LES-Signal (das wertvollste) ist am
  stärksten verdichtet.
- **Die LES-Decke bei 75 % ist der ehrliche Wermutstropfen (P15):** der LES-Recall plateaut ab 30 %
  Sichtung bei 75 % — **2 der 8 LES** ranken im untersten Drittel. Das sind exakt die signalfreien,
  konzeptuell-relevanten Fälle aus Iter 11 (z. B. „Erziehung nach Auschwitz"), die der Ranker
  strukturell nicht hebt und die der Journal-Prior teils zusätzlich drückt. Sie sind nur über den
  **Eskalations-/Volltext-Pfad** erreichbar, nicht über besseres Ranking. M-C ist kein
  Vollständigkeits-Garant.
- **Precision fällt erwartbar (P6):** von 46 % (@20 %) auf 27 % (@50 %) — je tiefer man liest, desto mehr
  IGN. Das ist korrekt und unvermeidlich bei Basisrate 21 %; der Wert liegt im *Front-Loading* der
  Treffer, nicht in einem sauberen Schnitt (es gibt keinen, Iter 08).
- **n ist klein und die Zahlen sind grob (P3, P15):** 25 keeper / 8 LES → jede LES = 12,5 %, die
  Tabelle ist gequantelt und verrauscht. Auf dem echten 49-Journal-Strom (niedrigere Basisrate) wird die
  **Precision niedriger** liegen (mehr IGN pro Treffer), der Recall-Vorsprung am Kopf aber vermutlich
  erhalten bleiben. Nicht hochrechnen — als Richtung valide, als Punktwerte nicht.
- **Was M-C NICHT ist:** kein 3-Klassen-Entscheider (Iter 14/15: Decke strukturell), kein hochpräziser
  Sortierer (AUC ~0.70), kein Ersatz fürs Lesen. Es ist ein **Reihenfolge-Verbesserer**, der die
  Sichtungs-Ausbeute am Kopf vervielfacht — nicht mehr, aber das belegbar.

## → nächste Iteration
Iter 32: **Modell M-A/M-B/M-C/M-D im direkten Betriebspunkt-Vergleich** + der MOJO-1-`agent_verdict` als
vierte Referenz — schlägt das algorithmische M-C den bestehenden LLM-Agenten auf dem blinden Strom (LES-
Recall@20 %)? Das ist der entscheidende „lohnt 2.0 gegenüber 1.x"-Test.
