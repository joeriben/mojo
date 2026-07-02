# Iter 25 — Journal-Prior-Stabilität (Empirical-Bayes)

## Anforderung
Iter 05: roher Per-Journal-Prior = in-sample-Leak. Hier sauber: EB-geshrinkter Prior (Journal-keep-Rate
zur Globalrate gezogen, Pseudo-Count k), **OOF** gemessen — taugt er als blinder Zusatz-Anker?

## Messung (`iter_25_journal_prior_eb.py` + Folgechecks)
26 Journals, Median 6 Artikel/Journal, 4 mit n=1. Top: AIandSoc (147, 30 %), MedienPaed (52, 56 %),
merz (32, 59 %), BJET (27, 33 %).
| Prior (OOF) | AUC gesamt | AUC screening |
|---|---|---|
| EB k=5 (mixed-trainiert) | 0.689 | 0.690 |
| EB k=2 **screening-only-trainiert** | — | **0.711** |
| rich-Ranker (Iter 16, Referenz) | — | 0.632 |
| **mean(journal-prior, rich)** | — | **0.702** |

## Harte Kritik
- **Der überraschend stärkste blinde Einzel-Hebel — und er ist NICHT zirkulär (P6, P9):** der OOF-EB-
  Journal-Prior erreicht screening-AUC **0.69–0.71**, *besser* als der content-Ranker (0.632). Screening-
  only trainiert wird er sogar stärker (0.711) → **kein** Selection-Bias-Artefakt. Wichtig zur Abgrenzung
  vom heutigen Zirkularitäts-Fehler: das ist die **empirische keep-Rate pro Journal aus Benjamins echten
  Verdikten**, keine label-abgeleitete Tautologie wie „Diskursraum-Zugehörigkeit". Das Journal, in dem
  etwas erscheint, ist real informativ über Relevanz.
- **Aber brüchig, und die Brüchigkeit ist gefährlich (P15, P8 — der eigentliche Vorbehalt):** von 18
  screening-Journals haben **9 null keeper** und nur 4 ≥2. Der Prior lernt also v. a. „diese Journals
  pauschal ignorieren". Als *harte* Regel würde er exakt die **unerwarteten cross-disziplinären Funde**
  unterdrücken — einen keeper in einem sonst-ignorierten Journal —, und das ist der Kernwert eines
  Forschungs-Scouts. Ein Journal-Gate würde Benjamins bestehende Journal-Gewohnheiten **einzementieren**
  und Serendipität töten. Deshalb: **weiches Additiv, niemals Gate.**
- **Shrinkage ist nötig und wirkt (P4):** k=0 (roh) 0.679, k=5 0.690, k=20 0.654 — ohne Shrinkage zu
  verrauscht (dünne Journals), zu viel Shrinkage löscht das Signal. k≈5 ist der gemessene Sweet Spot,
  nicht geraten.
- **Klärt Iter 05 statt es zu widersprechen:** Iter 05 fand den *in-sample*-Per-Journal-Prior als Leak
  in der *3-Klassen-Cascade-macro-F1*. Hier ist es der *OOF*-Prior als *binäre keep-AUC* — beide Aussagen
  stimmen, verschiedene Metrik/Validierung. Kein Widerspruch, eine Präzisierung.
- **Komplementär zu rich (P6):** mean(journal, rich) = **0.702** > beide einzeln. Journal = grob „welche
  Journals", rich = fein „welche Artikel darin". Das ist die empirisch beste blinde Ranking-Kombination
  der gesamten Serie.

## → nächste Iteration
Iter 26: den **vollständigen blinden Ranker** als Ensemble messen (journal-prior ⊕ rich ⊕ biblio-veto)
mit Recall@Sichtungslast vs. M7 (Iter 16) — und explizit prüfen, ob die Journal-Komponente die
„Serendipitäts"-keeper (keeper in 0-keeper-Journals) verschluckt. Das ist der Robustheits-Lackmustest
für das Scout-Versprechen.
