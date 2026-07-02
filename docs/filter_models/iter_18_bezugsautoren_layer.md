# Iter 18 — zweite Erdungsschicht: bezugsautoren.db

## Anforderung
Iter 17: eigener Bezug deckt nur 21 % keeper (62/161 Pubs aufgelöst), blind 0 %. Zweite Schicht
(Memory project_bezugsautoren_db, 208 Autoren / 6404 Werke): teilt der Artikel Refs mit Umfeld-Autoren?
Zwei Varianten: **direkt zitiert** (Artikel zitiert ein bezugsautor-Werk) vs **breit gekoppelt** (teilt
*irgendeine* Ref mit der bezugsautor-Ref-Wolke). Frage: Coverage-Lift ohne Diskriminations-Verlust?

## Messung (`iter_18_bezugsautoren_layer.py`)
Wolken: own=537, bez_works=6263, bez_ref_cloud=**88 036**.
| Schicht | keeper | LES | IGN | blind keeper | Ratio keeper/IGN |
|---|---|---|---|---|---|
| nur own (Iter 17) | 21 % | 34 % | 7 % | 0 % | **2.98** |
| + bez direkt-zitiert | **37 %** | 47 % | 18 % | **4 %** | **2.04** |
| + bez gekoppelt (breit) | 79 % | 84 % | 71 % | 20 % | 1.11 |

## Harte Kritik
- **Die Direkt-Zitat-Schicht ist der Sweet Spot (P6, P16):** sie verdoppelt fast die keeper-Coverage
  (21 %→37 %), liefert die **erste** blinde Coverage (0 %→4 %) und hält die Diskrimination stark
  (Ratio 2.04 — keeper zitieren Umfeld-Autoren 2× häufiger als IGN). Das ist ein echter, geerdeter
  Anreicherungs-Gewinn: „Artikel zitiert Williamson/Gourlay/… aus deinem Umfeld" ist ein konkreter,
  verifizierbarer Bezug, kein Score.
- **Die breite Kopplungs-Schicht ist eine Falle, und ich weise sie zurück (P15, P8):** 79 % Coverage
  *sieht* großartig aus, aber Ratio **1.11** heißt: sie feuert auf IGN fast genauso oft wie auf keeper.
  Die 88 036-Ref-Wolke überlappt mit fast jeder Literaturliste — das ist **Rauschen als Coverage
  getarnt**. Hätte ich nur die Coverage-Spalte berichtet, wäre es ein Scheinerfolg gewesen; die
  Diskriminations-Ratio entlarvt ihn. Genau die Art Selbsttäuschung, die P15 verbietet. **Nicht
  verwenden.**
- **Blind bleibt fast leer (P15):** 4 % blinde Coverage ist messbar besser als 0 %, aber praktisch immer
  noch fast nichts. Der substitutive Bezug bleibt eine Anreicherung für den **bibliometrisch vernetzten**
  Teil (intentional-positives Umfeld + direkte Umfeld-Zitate), nicht für den konzeptuell-fernen blinden
  Strom. Konsistent mit Iter 11/17 — keine Wende, eine Bestätigung mit etwas mehr Reichweite.
- **Festlegung:** substitutive Bezugs-Komponente = `own` ⊕ `bez-direkt-zitiert` (keeper 37 %,
  Ratio 2.04). Wenn ein Bezug existiert: benennen (Publikation oder Umfeld-Autor + geteiltes Werk).
  Wenn nicht: **schweigen** — keine LLM-Konfabulation (das 2.0-Kernprinzip).

## → nächste Iteration
Iter 19: die beiden belastbaren Stränge zu einem **Eintrags-Komponisten** zusammenführen und seine
*Vollständigkeit/Ehrlichkeit* messen (nicht F1): Ranking-Score (rich, Iter 16) + grounded Bezug
(own⊕bez-direkt, Iter 18) + Abstract verbatim — und der Anteil Einträge mit (a) konkretem Bezug,
(b) nur Score, (c) bewusster Leerstelle. Das operationalisiert die Substitutiv-These statt sie zu behaupten.
