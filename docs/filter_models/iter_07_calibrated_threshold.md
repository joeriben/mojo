# Iter 07 — Kalibrierte P(keep) + Threshold, screening-only gemessen

## Anforderung
Iter 06: der Wert sitzt im blinden Strom (`screening`), wo LES selten ist. `balanced` ist brutal.
Hier: isotonisch kalibrierte P(keep), Threshold bewusst gewählt, sauber OOF, screening-only ausgewertet.

## Messung (`iter_07_calibrated_threshold.py`, 5-fold OOF, isotonic)
Threshold-Sweep P(keep):
| thr | keepF1·all | keepRec·all | **keepF1·screening** | keepRec·scr | keepN·scr |
|---|---|---|---|---|---|
| 0.3 | 0.623 | 0.835 | **0.357** | 0.600 | 59 |
| 0.4 | 0.581 | 0.617 | 0.200 | 0.240 | 35 |
| 0.5 | 0.519 | 0.441 | 0.095 | 0.080 | 17 |
| 0.6 | 0.369 | 0.255 | 0.000 | 0.000 | 5 |

Kalibrierung ehrlich (P̄ → reale keep-Rate): 0.14→0.16, 0.31→0.33, 0.48→0.49, 0.64→0.50, 0.95→0.85.

## Harte Kritik
- **Die ehrlichste Zahl bisher:** auf `screening` (echter blinder Strom) erreicht das kalibrierte
  work+content-Modell maximal **keep-F1 0.357** (thr 0.3: Recall 0.60, Precision ~0.25). Höhere
  Thresholds kollabieren auf 0. Der algorithmische Filter kann die blinde Triage **nicht** leisten.
- **Kalibrierung ist gut** (P̄≈real bis 0.6, danach leicht überkonfident) — d. h. das Modell *weiß*,
  dass es unsicher ist; die Wahrscheinlichkeiten sind brauchbar als **Routing-Signal**, nicht als Urteil.
- **Strategische Konsequenz (P9, dokumentierte Linie):** Genau das stützt die committe 2.0-Architektur —
  algorithmischer Filter als **hoher-Recall-Vorfilter** (thr 0.3 → 60 % screening-Recall bei grobem
  Aussieben), und die **LLM-Volltext-Eskalation** macht die eigentliche Arbeit auf den Überlebenden.
  Der Filter soll nicht entscheiden, sondern die Kandidatenmenge für die teure Stufe verkleinern.
- **Schwäche:** thr=0.3 behält auf screening 59 Artikel für 60 % Recall — Precision ~0.25, d. h. 3 von 4
  sind Fehlalarm. Als Vorfilter tolerierbar (LLM sortiert nach), als Endurteil nicht. Die Kosten/Coverage-
  Frontier dieses Vorfilters muss explizit vermessen werden (Phase C/D).
- **P16 weiter offen:** das Modell liefert P(keep), aber keine *geerdete Begründung*. Das eigentliche
  Motiv bleibt für Phase C (geerdete Bezüge statt Score).

## → nächste Iteration
Iter 08: den Vorfilter-Gedanken ernst nehmen — **2-Stufen-Design**: hoher-Recall-Cut (thr für ~90 %
keep-Recall) misst, wie stark die Kandidatenmenge schrumpft (Inferenz-Ersparnis) bei welchem Recall-Verlust.
