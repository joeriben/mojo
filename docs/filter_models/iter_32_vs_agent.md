# Iter 32 — Modell M-C vs MOJO-1 LLM-Agent (der 2.0-vs-1.x-Test)

## Anforderung
Schlägt das algorithmische M-C den bestehenden MOJO-1-LLM-`agent_verdict` auf dem blinden Strom bei
gleicher Sichtungslast? Der entscheidende „lohnt 2.0 gegenüber 1.x"-Test — ehrlich, ohne Schönung.

## Messung (`iter_32_vs_agent.py`, blinder Strom n=120, keep=25, LES=8)
| System | Last | keep-Recall | keep-Prec | LES-Recall |
|---|---|---|---|---|
| **MOJO-1 agent_verdict (LLM)** | 16 % | **44 %** | **58 %** | **88 %** |
| M-A (M7, ~MOJO-1-Score) @16 % | 16 % | 8 % | 11 % | 12 % |
| M-B (rich) @16 % | 16 % | 24 % | 32 % | 12 % |
| M-C (rich+journal+Anker) @16 % | 16 % | 24 % | 32 % | 38 % |

## Harte Kritik (der wichtigste Ehrlichkeits-Befund der Serie)
- **Das LLM schlägt den Algorithmus deutlich — und das muss klar gesagt werden (P15, P16):** der MOJO-1-
  Agent fängt bei 16 % Last **88 % der Pflichtlektüre** (7 von 8 LES), M-C nur **38 %** (3 von 8). Auch
  bei keep-Recall (44 % vs 24 %) und Precision (58 % vs 32 %) liegt das LLM vorn. Jede Erzählung „der
  algorithmische 2.0-Ansatz ersetzt das teure LLM" ist damit **direkt widerlegt**. Das war heute eine
  reale Versuchung; die Messung verbietet sie.
- **Das ist KEIN Argument gegen 2.0 — es präzisiert dessen Rolle (P9, P11):** die dokumentierte 2.0-Linie
  (Memory feedback_llm_bezuege_konfabulation, feedback_volltext_pflicht) war **nie** „Algorithmus
  ersetzt LLM-Triage". Sie war: (a) die **Kommentar-Konfabulation** durch geerdete Bezüge ersetzen
  (Iter 17–19, erreicht: 0 ungrounded Behauptungen), (b) das LLM nur auf **Volltext** sinnvoll einsetzen
  (Abstract-Paraphrase = verbranntes Geld), (c) den Algorithmus als **Vorfilter/Ranking**, der LLM-Last
  spart. Iter 32 bestätigt diese Arbeitsteilung empirisch: das LLM bleibt der beste **Entscheider**, der
  Algorithmus liefert **Reihung + Erdung**, nicht das Urteil.
- **M-C schlägt aber den naiven M7-Score klar (P6):** gegenüber dem aktuellen Produktiv-Score (M-A, LES
  12 %) verdreifacht M-C die LES-Ausbeute (38 %) bei gleicher Last. Innerhalb der *algorithmischen*
  Liga ist M-C der klare Fortschritt — nur eben nicht gegen das LLM.
- **Konsequenz für die Architektur (P7):** der richtige Einsatz ist **Algorithmus ordnet → LLM
  entscheidet die Spitze → Komponist erdet den Eintrag**. Der Algorithmus ersetzt das LLM nicht, er
  fokussiert es: statt 120 Abstracts liest das LLM die obersten ~30–50 % (M-C @50 %: 75 % LES-Recall
  als Vorfilter-Decke), und der Rest läuft kostenarm. Die 0 LLM-Calls des Rankers sind ein
  Kosten-, kein Qualitätsargument.
- **Caveat (P3):** welches Modell `agent_verdict` erzeugte (Opus vs DeepSeek-Screening), ist hier nicht
  verifiziert; die 88 % LES-Recall sind beeindruckend genug, dass die Schlussrichtung (LLM > Algo)
  unabhängig vom genauen Modell hält. Auf dem echten Strom kostet jeder Agent-Call Geld — der
  Kosten-Qualitäts-Tradeoff (Iter 35) ist die offene Frage, nicht das Qualitäts-Ranking.

## → nächste Iteration
Iter 33: **Vorfilter-Kaskade quantifizieren** — wenn M-C die obersten X % an den LLM-Agenten gibt und den
Rest verwirft, welche LES-Recall/Kosten-Kurve entsteht (Algo-Reihung × LLM-Entscheid)? Das ist die
*tatsächliche* 2.0-Betriebsweise — und der ehrliche Test, wie viel LLM-Last der Ranker spart, ohne zu
viele LES zu verlieren (gegen Iter 08: Vorfilter spart bei hohem Recall wenig).
