# Iter 26 — vollständiger blinder Ranker + Serendipitäts-Lackmustest

## Anforderung
Iter 25: mean(journal,rich)=0.702 blind. Hier: Ensemble als Recall@Last vs M7 — und der kritische Test,
ob die Journal-Komponente die **Serendipitäts-keeper** (keeper in Journals mit sonst ≤1 keeper)
verschluckt. Das ist der Robustheits-Test fürs Scout-Versprechen (cross-disziplinäre Funde).

## Messung (`iter_26_ensemble_serendipity.py`)
**SCREENING Recall@Last (n=120, keep=25):**
| Ranker | AUC | R@10% | R@20% | R@30% | R@50% |
|---|---|---|---|---|---|
| M7 (aktuell) | 0.517 | 4 % | 12 % | 32 % | 52 % |
| rich (Iter 16) | 0.632 | 20 % | 32 % | 48 % | 68 % |
| **ens(journal,rich)** | **0.702** | 20 % | **44 %** | 52 % | 68 % |
| rich+lift-only (Fix) | 0.664 | 20 % | 44 % | — | — |

**Serendipitäts-keeper (Perzentil-Rang, höher=besser):**
| Artikel | rich | mean-ens | lift-only |
|---|---|---|---|
| `[MedienPaed]` (post-)digitales Erzählen | 96 % | 82 % | 82 % |
| `[ZfPaed]` Erziehung nach Auschwitz | 94 % | 82 % | 82 % |
| `[ArtsEdPolRev]` NAEA connected arts networks | **81 %** | **28 %** | **69 %** |
| `[STHV]` Making Queer Kin | 28 % | 46 % | 22 % |
| `[DCE]` Surveillance Capitalism in Schools | 19 % | 35 % | 14 % |

## Harte Kritik
- **Die AUC-Verbesserung verdeckt eine Tail-Regression, die dem Scout-Zweck widerspricht (P15, P8 — der
  Kernbefund):** das Ensemble hebt die blinde AUC auf 0.702 und R@20 % auf 44 % (4× M7), aber es
  **begräbt 3 von 5 Serendipitäts-keepern** — am drastischsten „NAEA connected arts networks"
  (ArtsEdPolRev, ÄKB-einschlägig): rich-Content rankt es korrekt auf 81 %, der Journal-Prior drückt es
  auf **28 %**, weil ArtsEdPolRev im Sample kaum keeper hat. Der Prior überstimmt ein starkes
  Inhalts-Signal und verschluckt genau den cross-disziplinären Fund, für den der Scout existiert. Hätte
  ich nur die AUC berichtet, wäre dieser Schaden unsichtbar geblieben.
- **Der Lift-only-Fix repariert die Katastrophe, kostet aber (P6, P4):** Journal-Prior nur als Aufschlag
  für überdurchschnittliche Journals, nie als Abzug → ArtsEdPolRev steigt zurück auf 69 %, R@20 % bleibt
  44 %, AUC 0.664. Preis: er opfert die *korrekten* Lifts (STHV/DCE, wo der Prior richtig half). Kein
  Blend dominiert — das ist eine echte Pareto-Front, kein Tuning-Defizit.
- **Es ist eine Werte-, keine Metrik-Entscheidung (P11, P16):** „4 Punkte AUC gegen das Verschlucken von
  Außenseiter-Funden" lässt sich nicht objektiv auflösen. Für einen Scout, dessen dokumentierter Wert
  (Memory feedback_scout_relevance, Positionalitäts-Report) gerade die disziplinäre Breite ist, wiegt
  die Serendipität schwerer als die Effizienz. Diese Spannung gehört **sichtbar gemacht**, nicht still
  wegoptimiert. (Per Autonomie-Direktive keine Rückfrage — ich lege einen verteidigbaren Default fest
  und dokumentiere ihn.)
- **Default-Festlegung (P7):** **rich-Content ist der primäre, serendipitäts-sichere Ranker.** Der
  Journal-Prior wird als **optionale, abschaltbare Effizienz-Schicht** (lift-only) geführt, mit
  dokumentiertem Außenseiter-Risiko — niemals als hartes Gate und niemals mit Veto-down. So bleibt der
  4×-M7-Recall am Listenkopf verfügbar, ohne die ÄKB/STS-Außenseiter strukturell zu opfern.

## → nächste Iteration
Iter 27: **Per-Diskursraum-Schwellen** statt eines globalen Rankers — Benjamins 5 Verortungen haben
verschiedene keep-Basisraten und Signal-Stärken (Memory feedback_korpus_aufarbeitung). Ist ein
Ranking *pro Verortung* (z. B. ÄKB-Artikel gegen ÄKB-Eigenwerk) trennschärfer als der globale rich-Sim —
oder zu dünn besetzt? (Adressiert die Profil-Sketch-Topologie aus project_profile_modelling.)
