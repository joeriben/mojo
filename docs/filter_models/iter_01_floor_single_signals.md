# Iter 01 — Fundament: Floor & Einzelsignale

## Anforderung
Ehrlicher Boden vor jeder Komplexität (P4/P15): Was leistet jedes werk-geerdete Einzelsignal
allein? Und wie weit reicht Bibliometrie überhaupt (Recall-Decke)?

## Entwurf
- **Zielgröße:** `user_verdict` → keep/discard (P1).
- **Features (P2, own-work-Familie):** `f_own_coupling_union`, `f_citation_hit_count`,
  `f_trigger_author_match`, `f_ref_overlap_authored`.
- **Mechanismus:** binäre Schwellen (Signal≥1 → keep) + Union; keep-all als Floor.
- **2.0-Einordnung (P9):** das ist die committe own_refs/Veto-Up-Logik in ihrer rohesten Form.

## Messung (`iter_01_floor_single_signals.py`, n=461)
| Regel | f1_keep | keepPrec | keepRec |
|---|---|---|---|
| keep-all (Floor) | 0.579 | 0.408 | 1.000 |
| own_coupling_union ≥ 1 | 0.268 | **0.833** | 0.160 |
| citation_hit_count ≥ 1 | 0.200 | **0.955** | 0.112 |
| trigger_author_match | 0.021 | 1.000 | 0.011 |
| ref_overlap_authored ≥ 1 | 0.111 | 1.000 | 0.059 |
| UNION der vier | 0.312 | 0.837 | **0.191** |

**Kernzahl:** nur **36/188 (19,1 %)** der keep-Artikel tragen *irgendein* werk-geerdetes
bibliometrisches Signal → **bibliometrische Recall-Decke ≈ 19 %**.

## Harte Kritik
- **Vernichtend für reine Bibliometrie:** 81 % des für Benjamin Relevanten hat *keinen*
  direkten bibliometrischen Link zu seinem Werk. Ein Koppelungs-only-Filter ist als Recall-Instrument
  strukturell ungeeignet — bestätigt das 5×-Plateau (Memory) mit einer einzigen Zahl.
- Die Signale sind **als Veto-up** wertvoll (Präzision 0.83–1.0): wo sie feuern, fast immer keep.
  Als alleinige *Auswahl* sind sie wertlos. Das deckt sich mit Benjamin: „1 geteilte Ref = primitive
  Suchfunktion" — präzise, aber kein Recall.
- **3-Klassen nicht messbar** mit Binärregeln (LES-Rec=0 per Konstruktion, da alles auf „scannen"
  gemappt) — ehrlich vermerkt, kein Schönen.
- **Selbst-Fehler-Check:** kein Feature genutzt, das Herkunft verrät (P3 ok); aber `trigger`/`citation`
  sind selektions-korreliert (Memory: 65 % LES aus intentional-positiven Quellen) → die Präzision ist
  teils Selection-Bias, nicht reine Vorhersagekraft. Muss in Iter 06 / Phase D (Blind-Screening-Eval) geprüft werden.

## → nächste Iteration
Iter 02: Recall muss von woanders kommen → **Inhalts-/Embedding-Signale** (score_M7) als eigenständige
Achse messen, denn 81 % der Treffer sind bibliometrisch unsichtbar.
