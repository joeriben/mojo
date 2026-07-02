# Iter 46 — Confidence-banded Operating Point: was der Algo sicher tun darf

## Anforderung
Statt jeden Artikel hart keep/drop zu labeln (M-C-AUC 0.66 → ~34 % Fehlordnung), die M-E-Ausgabe in drei
Zonen schneiden: sicher-DROP (kein LLM) / unsicher (→ LLM/Lektüre) / sicher-KEEP (auto-surface). t_lo so
gewählt, dass im DROP-Band **0 LES** verloren gehen (Serendipitäts-Schutz, P-Serendipität); t_hi so, dass
das KEEP-Band ≥ 80 % keep-Precision hat. Wie groß muss das teure Mittelband sein? Blinder Strom, seed-gem.

## Messung (`iter_46_confidence_bands.py`, blinder Strom n=120, 8 LES, Basisrate 21 %)
| Zone | n | Anteil | keep-rate | LES darin |
|---|---|---|---|---|
| sicher-DROP (kein LLM) | 30 | 25 % | 10 % | **0** |
| unsicher → LLM/Lektüre | 90 | 75 % | 24 % | 8 |
| **sicher-KEEP (auto)** | **0** | **0 %** | — | — |

LES-Recall (nicht gedroppt) = **8/8 = 100 %**. LLM-Last (Mittelband) = **75 %**. Eingesparte LLM-Calls = **25 %**.

## Harte Kritik
- **Der Algo darf genau eine Sache sicher tun: ein Viertel verwerfen (P15, P16):** 25 % des blinden Stroms
  sind sicher-DROP **ohne ein einziges LES zu verlieren** (die 3 gedroppten keeper sind „scannen", nicht
  „lesenswert" — akzeptabel). Das ist ein **realer, deploybarer Gewinn**: −25 % LLM-Calls bei null
  Recall-Kosten. Nicht spektakulär, aber ehrlich und nutzbar.
- **Das sicher-KEEP-Band ist LEER — und das ist der ehrlichste Befund (P15, P9):** kein Score-Schwellwert
  erreicht ≥ 80 % keep-Precision auf dem blinden Strom. **Der Algo ist nie sicher genug, um etwas
  automatisch zu surfacen.** Das ist keine Modellschwäche, die ich glätten darf — es ist die direkte
  Bestätigung von Iter 32 (LLM schlägt Algo auf blinder Triage) und der dokumentierten 2.0-Linie:
  **der Algo ist Vorfilter, nicht Entscheider.** Sein einziger sicherer Akt ist die billige Ablehnung;
  das Surfacen bleibt LLM/Lektüre.
- **75 % Mittelband ist teuer — aber die Zahl ist die Wahrheit, nicht ein Versagen (P11):** wer 100 %
  LES-Recall will (Benjamins implizite Anforderung: nichts Wichtiges verpassen), muss 75 % an die teure
  Stufe geben. Der einzige Hebel, das Mittelband zu verkleinern, ist **besserer Inhalt** (rich_sim
  schärfen via Per-Werk-Summaries, Volltext) — nicht eine kühnere Schwelle. Eine kühnere t_lo (mehr
  droppen) würde sofort LES kosten (Iter 33: ab 30 % Drop −2 LES). Die 25/75-Teilung ist der Punkt, an
  dem Recall noch 100 % ist.
- **Sensitivität offengelegt (P3):** das leere KEEP-Band hängt am 80 %-Precision-Bar. Bei einem laxeren
  Bar (z. B. 50 %, immer noch 2.4× Basisrate) entstünde ein kleines auto-KEEP-Band — aber mit False
  Positives, die Benjamin als Müll im Digest sähe. Auf einer 21 %-Basisrate ist der Algo schlicht **kein
  zuverlässiger Akzeptierer**; das ist keine Tuning-Frage, sondern die Signalgrenze (Iter 11/13/36/43).
- **Produkt-Konsequenz (P6):** M-E liefert also drei Ausgaben, nicht ein Label — (1) eine kleine
  Auto-Ignorieren-Liste (25 %, geprüft 0 LES), (2) eine große „bitte LLM/lesen"-Liste (75 %, nach M-C
  vorsortiert, damit die Lektüre oben anfängt), (3) eine Erdungs-Annotation je Artikel (Iter 43/44).
  Das ehrliche Versprechen an Benjamin: „ich erspare dir ein Viertel sicher, sortiere den Rest, und
  erfinde nichts dazu" — nicht „ich entscheide für dich".

## → nächste Iteration
Iter 47: **Fehleranalyse der irreduziblen Hard-Cases** — die LES, die M-C tief reiht UND die kein
geerdeter Anker fängt (Schnittmenge aus Iter 39/43/46-Mittelband). Was kennzeichnet sie inhaltlich?
Qualitative Diagnose der Artikel, an denen Algo *und* Erdung gemeinsam scheitern — die harte Grenze
konkret benannt, nicht nur als Zahl.
