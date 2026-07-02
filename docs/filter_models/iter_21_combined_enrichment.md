# Iter 21 — drei Enrichment-Achsen kombiniert + named_thinker-Precision-Härtung

## Anforderung
Iter 20 zeigte named_thinker als „erste Achse, die blind erreicht" (28 %), aber mit Precision-Risiko.
Hier: (1) Selbst-Audit dieser Zahl, (2) Härtung + Precision-Verlust quantifizieren, (3) kombinierte
Coverage aller drei geerdeten Achsen.

## Selbstkorrektur (P3 — Provenienz/Leakage)
Iter 20 matchte Denker-Nachnamen auch gegen **`authors_lower`** (die Artikel-Autoren). Ein Artikel, der
von jemandem mit einem Denker-Nachnamen *verfasst* ist, „behandelt" diesen Denker aber nicht — das ist
ein Scheintreffer. Bereinigt (nur Titel+Abstract+Konzepte) sinkt named_thinker von 35 %/28 % auf
**23 %/20 %**. Die Iter-20-Zahl war aufgebläht; diese hier ist die ehrliche.

## Messung (`iter_21_combined_enrichment.py`)
roh 359 Nachnamen → gehärtet 275 distinktive (len≥6, Stoppliste) + 390 Vollnamen.
| Achse | keeper | IGN | Ratio | blind-keeper |
|---|---|---|---|---|
| own-Ref | 21 % | 7 % | 2.98 | 0 % |
| bez-direkt | 30 % | 14 % | 2.18 | 4 % |
| named_thinker roh | 23 % | 8 % | 2.71 | 20 % |
| named_thinker gehärtet | 14 % | 5 % | 3.02 | 8 % |
| **KOMBI own∪bez∪thinker-hart** | **46 %** | 21 % | 2.15 | **12 %** |

## Harte Kritik
- **Härtung = Precision rauf, Recall runter, ehrlich quantifiziert (P15):** Stoppliste + Mindest-
  Namenslänge halbieren die Coverage (blind 20 %→8 %), heben aber die Diskriminations-Ratio (2.71→3.02).
  Die rohe blind-Reichweite war teils Fehltreffer-Inflation. Iter 20s „28 %" schrumpft nach
  Autoren-Bereinigung *und* Härtung auf **8 %** — die Achse erreicht den blinden Strom, aber viel
  schwächer als der erste Eindruck. Genau hier wäre Selbsttäuschung leicht gewesen; die Zahl steht jetzt korrekt.
- **Kombi deckt knapp die Hälfte der keeper, aber kaum den blinden Strom (P15):** 46 % keeper-Coverage
  ist der bisher beste geerdete Wert, aber **88 % der blind-keeper bleiben ungeerdet**. Das ist die harte
  Wahrheit der Substitutiv-These auf dem realen Strom: für die große Mehrheit blinder Treffer gibt es
  *keinen* benennbaren Werk-Bezug — der Eintrag muss dort auf Score+Abstract+Leerstelle laufen (Iter 19),
  nicht auf erfundene Bezüge.
- **Kombi dilutiert Diskrimination (Ratio 2.15 < own 2.98):** je breiter die Vereinigung, desto mehr IGN
  fallen mit hinein. Für *Enrichment* (benennen, was da ist) ist das egal — die Bezüge sind einzeln
  verifizierbar. Als *Filter*-Signal wäre die sinkende Ratio ein Problem; deshalb bleibt es Enrichment.
- **Was das abschließend klärt:** die drei Achsen sind komplementär (own/bez = bibliometrisch,
  thinker = konzeptuell), aber ihre Summe ist keine Triage-Lösung — sie ist ein **ehrlicher Anreicherer**
  mit ~46 % keeper-Reichweite. Der blinde Strom bleibt strukturell (Iter 11) auf Ranking angewiesen.

## → nächste Iteration (Phase D)
Iter 22: **zeitliche Validierung / Drift** — die Gold-Daten über `year` splitten (Training auf älteren,
Test auf neueren Artikeln) und prüfen, ob der rich-Ranker (Iter 16) und das own+content-Modell zeitlich
stabil sind oder ob jüngere Jahrgänge (Lehrstuhl-Shift, Memory feedback_korpus_aufarbeitung) driften.
