# Iter 22 — zeitliche Validierung → entlarvt `year` als Selection-Bias-Leck

## Anforderung
Phase D: prüfen, ob Modelle zeitlich driften (Training alt → Test neu). Befund schon bei der
Jahresverteilung: **es gibt keine Zeitachse zum Validieren** — also umgewidmet zum Leak-Test von `year`.

## Messung (`iter_22_temporal_drift.py`)
| Jahr | n | keep-Rate | LES |
|---|---|---|---|
| 2022–2025 (intentional-positiver Backfill) | 57 | 80–100 % | 30–77 % |
| **2026 (Screening-Strom)** | 393 | **33 %** | 10 % |

`f_year_normalized` keep-AUC = 0.358 (Info, aber invers). **Leak-Test (macro-F1, OOF):**
| Modell | gesamt | nur 2026-Strom |
|---|---|---|
| own+content | 0.514 | 0.476 |
| own+content **+ year** | **0.535** (↑) | **0.445** (↓) |

## Harte Kritik
- **Der Gold-Satz hat keine Zeitachse — das ist selbst der Befund (P3):** 393/461 Artikel sind 2026
  (der Screening-Strom), die 57 älteren sind der intentional-positive Backfill (citation/trigger/…).
  „Alt" heißt hier nicht „früher", sondern „wurde gezogen, weil Benjamin es zitiert/behandelt" — `year`
  ist mit `selection_mode` **konfundiert** und damit ein verkappter Label-Proxy. Ein zeitlicher
  Train/Test-Split ist unmöglich und wäre Selbsttäuschung gewesen.
- **Der Leak ist konkret nachgewiesen (P3, P15):** `year` als Feature **hebt** die Gesamt-macro-F1
  (0.514→0.535), **senkt** aber den ehrlichen 2026-Strom (0.476→0.445). Das ist die Signatur eines
  Bias-Lecks: es exploitiert das Konfund „alt=keep" auf der Mischmenge und ist auf dem echten Strom
  schädliches Rauschen. Jede Kennzahl, die `year` nutzt und „gesamt" berichtet, ist aufgebläht.
- **Validiert rückwirkend die Eval-Disziplin (P5/P3):** meine Modelle (own+content) nutzen `year`
  bewusst NICHT, und ich habe durchweg screening-only als ehrliche Zahl berichtet. Dieser Test zeigt,
  warum das richtig war — und liefert eine generelle Regel: **jedes Feature, das mit `selection_mode`
  korreliert (year, evtl. journal-Identität), muss gegen den blinden Strom geprüft werden, nicht gegen
  die Mischmenge.**
- **Nebenbefund, ehrlich:** der 2026-Strom ist auch ohne year etwas schwerer (0.476 vs gesamt 0.514) —
  konsistent mit Iter 06 (Selection-Bias bläht die Headline). Keine neue Decke, eine Bestätigung.
- **Grenze:** „2026-Strom" ≠ exakt „screening selection_mode" (2026 enthält auch ein paar
  similarity/complementarity-Items). Als Näherung des blinden Stroms tauglich, aber nicht identisch mit
  der `screening`-Definition aus Iter 06 — vermerkt, nicht verschwiegen.

## → nächste Iteration
Iter 23: **Abstract-Fehlend-Robustheit** — wie viele Gold-Artikel haben keinen/kurzen Abstract, und wie
stark bricht der rich-Ranker (der auf Abstract+Konzepten beruht) auf diesen ein? Der reale Strom hat
OJS/RSS-Quellen ohne Abstract (Memory Sonderfälle) — die Degradation muss bekannt sein, bevor man dem
Ranker traut.
