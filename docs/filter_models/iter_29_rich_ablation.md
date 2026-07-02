# Iter 29 — Ablation der rich-Text-Bestandteile

## Anforderung
Iter 13/27: reicher Eigenwerk-Text hebt die content-AUC. Welcher Teil trägt — `summary_de` (teuer, Opus),
`key_terms` oder `named_thinkers` (billig)? Kosten-Relevanz (P13): ist der Opus-Summary-Schritt nötig?

## Messung (`iter_29_rich_ablation.py`, global-rich-Schwerpunkt)
| rich-Variante | AUC gesamt | AUC **screening** |
|---|---|---|
| nur Titel | 0.680 | 0.593 |
| **Titel+summary_de** | 0.679 | **0.648** |
| Titel+key_terms | 0.676 | 0.571 |
| Titel+named_thinkers | 0.701 | 0.565 |
| key_terms allein | 0.673 | 0.579 |
| VOLL (alle) | 0.679 | **0.648** |

## Harte Kritik
- **`summary_de` ist der tragende Teil — und er ist nicht wegzusparen (P13, P6 — ehrliche Kosten-Antwort):**
  auf dem blinden Strom liefert Titel+summary_de **0.648**, identisch mit VOLL. key_terms und
  named_thinkers *allein* sind mit 0.571/0.565 sogar **schlechter als der Titel allein** (0.593) und
  addieren nichts auf summary_de drauf (VOLL = Titel+summary_de). Die Hoffnung „die billigen key_terms
  reichen" ist **widerlegt** — der teure Opus-Summary trägt die semantische Diskrimination, die kurzen
  Vokabellisten nicht. Das ist die unbequeme, aber gemessene Antwort: der Summary-Schritt ist
  gerechtfertigt, nicht redundant.
- **Eine Selection-Bias-Falle entlarvt (P15, P3):** named_thinkers sieht „gesamt" mit 0.701 am besten aus —
  aber das ist Inflation: intentional-positive Artikel wurden teils gezogen, *weil* sie Benjamins Denker
  zitieren, also matcht named_thinkers dort prächtig. Auf dem blinden Strom bricht es auf **0.565** ein
  (schlechter als Titel). Wer „gesamt" gelesen hätte, wäre der falschen Achse gefolgt. Erneut bestätigt:
  screening-only ist die einzige ehrliche Linse, „gesamt" lügt systematisch nach oben.
- **Konsistent mit Iter 20 (P8):** named_thinkers ist eine **Anreicherungs**-Achse (benenne den geteilten
  Denker, wenn präsent), **keine Ranking**-Achse. Iter 20 zeigte den Anreicherungs-Wert (28→8 % blind
  nach Härtung), Iter 29 zeigt den Nicht-Ranking-Wert (0.565). Beide Befunde greifen sauber ineinander —
  dieselbe Achse, zwei Rollen, klar getrennt.
- **Konsequenz für die Pipeline:** der rich-Ranker = Titel+`summary_de` (Opus). key_terms/named_thinkers
  fließen NUR in den Komponisten als benennbare Bezüge, nicht in den Score. Das ist auch die einfachste
  Variante (P13): ein Feld weniger im Ranking-Text.

## → nächste Iteration
Iter 30 (Phase-C/D-Abschluss): **Abstract-Anreicherung quantifizieren** — Iter 23 zeigte, dass 43 % des
blinden Stroms abstract-los sind und der Ranker dort versagt. Wenn die Pipeline OpenAlex-Abstracts
nachlädt (`articles.openalex_abstract` existiert teils), wie viele der abstract-losen Artikel bekommen
einen, und wie weit erholt sich die rich-AUC auf der erholten Teilmenge? Schließt die Robustheits-Lücke.
