# Iter 49 — Pfad-B-Fallback: M-E ohne Abstract

## Anforderung
Iter 34: alle blind-LES in Pfad A (abstract-reich), Pfad B (kein Abstract) hatte 0 LES. Was kann M-E aus
Metadaten auf Pfad B überhaupt leisten — ist er sicher zu deprioritisieren (→ erst Volltext holen), oder
versteckt er Relevantes? Blinder Strom + gesamt.

## Messung (`iter_49_pathb_fallback.py`)
| Menge | n | keep | LES | Ø rich | rich-AUC |
|---|---|---|---|---|---|
| Pfad A (Abstract), gesamt | 381 | 45 % | 78 | 0.40 | **0.702** |
| Pfad B (kein Abstract), gesamt | 80 | 22 % | 1 | 0.37 | 0.607 |
| **Pfad A blind** | 69 | 23 % | **8** | 0.39 | **0.684** |
| **Pfad B blind** | 51 | 18 % | **0** | 0.36 | **0.532** |

Pfad B blind: keeper Ø rich **0.36** = non-keeper Ø rich **0.36** → keine Trennung.

## Harte Kritik
- **Auf Pfad B ist M-E aus Metadaten blind — und das ist sauber gemessen (P6, P15):** Titel-only-rich_sim
  trennt den blinden Pfad B *gar nicht* (AUC 0.532 ≈ Zufall; keeper- und non-keeper-Mittel identisch bei
  0.36). Es gibt schlicht kein verwertbares Signal ohne Abstract. M-E darf hier **kein Urteil vortäuschen**
  — jede keep/drop-Entscheidung auf Pfad-B-Metadaten wäre Münzwurf.
- **Deprioritisieren ist sicher UND korrekt (P11, P16):** die 51 blinden Pfad-B-Artikel enthalten **0 LES**
  — sie nach Volltext-Holung zurückzustellen verliert sofort **0** wichtige Treffer (die 9 keeper sind
  „scannen"-Niveau, kein LES). Korrekte M-E-Route: **Pfad B nicht scoren, sondern direkt in die Volltext-
  Holung** (OA-PDF, die dokumentierte Eskalation). Das spart LLM-Calls auf rauschigem Input und holt das
  einzig brauchbare Signal (den Text) für genau die Fälle, wo Metadaten fehlen.
- **Die unbequeme Nuance, die ich nicht verschweige (P3, P15):** „0 LES auf Pfad B" heißt vielleicht
  nicht „nicht relevant", sondern „**konnte nicht beurteilt werden**". Wenn der Ground-Truth (user_verdict)
  teils abstract-basiert vergeben wurde, sind abstract-lose Artikel systematisch *unter*-als-LES-gelabelt —
  weil es nichts zu lesen gab. Genau der Iter-47-Hard-Case „Surveillance Capitalism in Schools" (concepts
  leer, rich 0.28) ist ein Pfad-B-Artikel, der LES IST. Das **stärkt** die Volltext-Empfehlung: Pfad B ist
  die Zone, in der der Ground-Truth selbst blind ist — Volltext-Holung ist dort nicht nur sicher, sondern
  **nötig, um überhaupt ein valides Urteil zu erzeugen**.
- **Konsequenz für die Architektur (P9):** M-E ist ein **Zwei-Pfad**-System (Iter 34 bestätigt, Iter 49
  quantifiziert): Pfad A → rich_sim-Scoring + Confidence-Bänder (Iter 46) + Kalibrierung (Iter 48); Pfad B
  → ohne Metadaten-Urteil direkt zur Volltext-Holung, dann wie Pfad A behandeln. Kein einheitlicher
  Schwellwert über beide — das wäre der Fehler, der Pfad-B-Rauschen als Signal missdeutet.
- **Caveat (P3):** Pfad-A-rich-AUC fällt blind von 0.702 (gesamt) auf 0.684 — der Selection-Bias hebt die
  Gesamt-Zahl. Konsistent mit der ganzen Serie; die ehrliche Pfad-A-blind-Zahl ist 0.684, nicht 0.70.

## → nächste Iteration
Iter 50: **Finale Synthese — M-E-Spezifikation + ehrliche Leistungs-/Grenzen-Bilanz.** Alle belastbaren
Befunde (01–49) in einer Architektur, mit Spannen (Iter 36), Rollenteilung Algo↔LLM↔Lektüre (Iter 32/46),
Zwei-Pfad-Routing (Iter 34/49), Erdung-vs-Relevanz-Trennung (Iter 43/44/45), den drei Werte-Entscheidungen
(Serendipität/Frontier/Kosten) und der benannten harten Grenze (Iter 47).
