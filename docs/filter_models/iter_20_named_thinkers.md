# Iter 20 — named_thinkers als geerdete konzeptuelle Achse

## Anforderung
Iter 11: die blind-verfehlten LES sind *konzeptuell* verwandt (Haraway/„Queer Kin"), teilen aber keine
Referenzen → Iter 17/18 erreichen sie nicht (blind 4 %). Neue, nicht-bibliometrische Achse: die
summaries.json listen Benjamins `named_thinkers` (Barad, Haraway, Rancière…). Nennt der Artikel-Text
dieselben Denker? Test: Diskrimination + erreicht es speziell die konzeptuell-verwandten blind-keeper?

## Messung (`iter_20_named_thinkers.py`, 359 eindeutige Denker-Nachnamen)
| Gruppe | ≥1 Denker | Ø Denker |
|---|---|---|
| keeper | 35 % | 0.57 |
| LES | 34 % | 0.68 |
| IGN | 18 % | 0.21 |
| **blind keeper** | **28 %** | 0.36 |

Ratio keeper/IGN **1.93** · keep-AUC (n_thinker) 0.591 · blind-AUC 0.556.
4 blind-verfehlte LES (Iter 11): **„Making Queer Kin" → Haraway** ✓; AfD/„Auschwitz", „Rating villagers",
finnischer STEAM → keine.

## Harte Kritik
- **Erste Achse, die den blinden Strom wirklich erreicht (P6, P16):** 28 % der blind-keeper nennen einen
  Denker aus Benjamins Werk — **7× mehr** als die geteilten Refs (4 %, Iter 18). Und sie fängt genau die
  in Iter 11 diagnostizierte konzeptuelle Verwandtschaft: „Making Queer Kin" ↔ **Haraway**. Das ist die
  geerdete, *nicht-bibliometrische* Erdung, die der blinde Strom braucht — „behandelt Denker, mit denen
  du arbeitest (Haraway)" ist ein konkreter, benennbarer Bezug, kein Score und keine Konfabulation.
- **Aber schwach als Ranker und precision-gefährdet (P15, P3 — kein Overclaim):** AUC 0.59 (blind 0.56)
  ist *kein* Filter — es ist eine Anreicherungs-Achse. Schlimmer: Nachnamen-Matching über **359** Namen
  hat echtes False-Positive-Risiko — der Treffer „Donna" zeigt es (Allerweltswort/Vorname als
  vermeintlicher Denker-Nachname). Ohne Vornamen-/Kontext-Disambiguierung (analog Memory
  feedback_citation_disambiguation) produziert die Achse Scheinbezüge. **Vor Produktiv-Einsatz: härten**
  (Mindest-Namenslänge, Vor+Nachname-Match, Stoppliste für Namen=Wörter).
- **Erreicht nur 1 von 4 (P15):** „Erziehung nach Auschwitz" wird *nicht* gefangen — der Adorno-Bezug
  ist phrasen-, nicht namens-explizit (Adornos berühmter Titel ohne seinen Namen). Die finnischen/
  governance-Fälle bleiben ebenfalls leer. Die Achse erweitert die Reichweite, schließt die Lücke aber
  nicht. Ehrlich: ~28 % blind ist Fortschritt, nicht Lösung.
- **Komplementär, nicht ersetzend:** named_thinkers (konzeptuell) + geteilte Refs (bibliometrisch)
  überlappen nur teils — zusammen decken sie mehr keeper als jede allein. Gehört als **dritte
  Enrichment-Achse** in den Komponisten (Iter 19), mit Precision-Härtung.

## → nächste Iteration (Phase D — Robustheit/Ehrlichkeit)
Iter 21: die drei Enrichment-Achsen (own-Ref, bez-direkt, named_thinker) **kombiniert** auf
blind-keeper-Coverage messen — und das named_thinker-Precision-Risiko quantifizieren (wie viele Treffer
sind Allerweltsnamen?). Dann Phase D: zeitliche Validierung (Drift), Abstract-Fehlend-Robustheit,
Kalibrierungs-Ehrlichkeit des Komponisten.
