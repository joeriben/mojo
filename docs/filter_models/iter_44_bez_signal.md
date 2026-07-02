# Iter 44 — bezugsautoren-Coupling als Triage-Signal: Relevanz-Hebel oder nur Bezug-Lieferant?

## Anforderung
Iter 43: bez-direct (Artikel-Refs ∩ Bezugsautoren-Werke) ist der produktivste *Anker* (30 % der keeper).
Aber hebt er auch das *Relevanz-Urteil*? Test als zusätzliches Veto-Up auf M-C, keep-AUC + LES-Recall@20 %,
voll vs. blinder Strom (unverzerrt), seed-gemittelt (P15).

## Messung (`iter_44_bez_signal.py`, 5 Seeds)
bez-Treffer: gesamt 21 %, blinder Strom **2 %**.

| Menge | Modell | keep-AUC | LES@20 % |
|---|---|---|---|
| alle Quellen | M-C | **0.736 ± 0.002** | 46 % |
| alle Quellen | M-C + bez-Veto | 0.720 ± 0.001 | 44 % |
| blinder Strom | M-C | 0.666 ± 0.009 | 62 % |
| blinder Strom | M-C + bez-Veto | 0.680 ± 0.009 | **52 % ± 9pp** |

## Harte Kritik
- **bez als Triage-Veto schadet oder rauscht — klare Trennung von Anker und Relevanz (P6, P16):** auf
  allen Quellen senkt das bez-Veto die AUC (0.736→0.720) und LES@20 % (46→44), weil es **False Positives
  hochzieht** (Iter 43: 14 % der non-keeper haben bez-Treffer). Auf dem blinden Strom hebt es die AUC
  minimal (0.666→0.680), zerstört aber LES@20 % (62→52, ±9pp) — bei nur **2 %** bez-Treffer ist das
  ohnehin das Rauschen von 1–2 Artikeln, kein Signal. **Fazit: bezugsautoren ist ein Bezug-*Lieferant*
  (Iter 43), kein Relevanz-*Hebel*.** Das bestätigt die Iter-43-These „Anker ≠ Relevanz" sauber und
  unabhängig.
- **Saubere Rollentrennung für M-E (P11):** die bezugsautoren-DB gehört in die **Anreicherungs-/Erdungs-
  Schicht** (Bezug-Text im Eintrag), NICHT in den Ranker. Wer sie als Veto in die Triage zieht, kauft
  Precision-Verlust für nichts. Das ist eine konkrete, gemessene Architektur-Entscheidung, kein
  Geschmack.
- **Konsistenz-Check bestanden (P3):** die blind-Strom-M-C-Zahlen (AUC 0.666±0.009, LES@20 % 62 %) liegen
  exakt im Iter-36-Korridor (0.66±0.01). Kein neuer Glücksseed, keine Drift in der Mess-Pipeline — die
  Harness misst über vier Iterationen stabil dasselbe. Das ist die Art Selbst-Konsistenz, die P15/P3
  verlangen.
- **Grenze (P3, P14):** der bez-Test ist durch die zirkuläre DB-Seedung (Gold-Erstautoren) auf den
  intentional-positiven Pool verzerrt — die 2 % blind sind ehrlich, die 21 % gesamt nicht. Eine über das
  Gold hinaus skalierte bezugsautoren-DB (Memory: 16 404 Autoren) könnte die *Erdungs*-Coverage heben
  (Iter 43), aber dieser Test zeigt: sie würde die *Triage* trotzdem nicht verbessern, weil das Problem
  nicht Coverage, sondern die fehlende Relevanz-Trennschärfe des Anker-Signals ist. Mehr bez-Daten =
  mehr Bezüge, nicht bessere Triage.

## → nächste Iteration
Iter 45: **Trigger-Autoren-Veto als Standalone** (MacGilchrist/Jarke/Chun, Memory project_trigger_autoren —
Eskalation unabhängig vom Tier). Precision/Recall der Regel als Relevanz-Signal: wie viele keeper/LES fängt
die fixe Trigger-Liste, bei wie vielen False Positives? Prüft, ob die dokumentierte harte Eskalations-Regel
ihren Platz im Ranker verdient — anders als bezugsautoren.
