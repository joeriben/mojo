# Iter 08 — 2-Stufen-Vorfilter: Kosten/Coverage-Frontier

## Anforderung
Iter 07: Filter taugt als hoher-Recall-Vorfilter. Frage: bei welchem keep-Recall schrumpft die
LLM-Kandidatenmenge wie stark? Memory-Ziel: ~50–60 % Inferenz-Ersparnis. Gesamt + screening-only.

## Messung (`iter_08_prefilter_coverage.py`, OOF kalibrierte P(keep))
| Ziel-Recall | behaltene Kandidaten (gesamt) | Ersparnis | behaltene (screening) | Ersparnis |
|---|---|---|---|---|
| 99 % | 99 % | 1 % | 98 % | 3 % |
| 95 % | 89 % | 11 % | 90 % | 10 % |
| 90 % | 82 % | 18 % | 85 % | 15 % |
| 80 % | 64 % | 36 % | 71 % | 29 % |

## Harte Kritik
- **Memory-Annahme widerlegt (P15):** „~50–60 % Inferenz-Ersparnis" gilt **nicht** bei hohem Recall.
  Bei 95 % keep-Recall spart der Vorfilter nur **~10 %**; 50 %+ Ersparnis erst, wenn man ~30–40 % der
  Treffer wegwirft (Recall < 80 %). Das ist für einen Forschungs-Scout, der Entdeckungen *nicht*
  verpassen darf, inakzeptabel.
- **Ursache, nicht Symptom:** das ist kein Tuning-Problem, sondern die direkte Folge von Iter 01/07 —
  das keep-Signal in own+content ist zu schwach, um bei hohem Recall scharf zu trennen. Mehr
  Threshold-Akrobatik ändert das nicht.
- **Konsequenz:** der algorithmische Filter ist **weder** ein guter Entscheider (blind keep-F1 ~0.36,
  Iter 07) **noch** ein starker Vorfilter (~10 % Ersparnis bei 95 % Recall). Sein realistischer Nutzen
  ist eng: grobes Wegschneiden der klaren IGN (die untersten P-Bins) + Veto-up der hochpräzisen
  Bibliometrie-Treffer (Iter 01). Die eigentliche Trennung muss von besserem **Inhalt** kommen.
- **Offene Schwäche:** ich messe Ersparnis an der 461er-Mischung; auf dem echten Volllauf-Strom (49
  Journals, sehr niedrige keep-Basisrate) könnte der Vorfilter bei den klaren IGN mehr sparen.
  Das braucht den Volllauf-Strom, nicht den Gold-Satz → als Limit vermerkt, nicht überschätzt.

## → nächste Iteration (Phase C — das eigentliche Motiv)
Iter 09: Inhalt besser machen statt Bibliometrie weiter melken — **Per-Werk-max-Similarity** zum Œuvre
(nicht globaler Korpus-Schwerpunkt; Profil-Sketch: per-Werk-Embedding), und ob das die schwache
content-AUC (0.66, Iter 02) hebt.
