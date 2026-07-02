# Iter 33 — Vorfilter-Kaskade: M-C reiht → LLM entscheidet (Kosten/Recall)

## Anforderung
Die tatsächliche 2.0-Betriebsweise (Iter 32): Algo ordnet, LLM entscheidet die Spitze. Kosten (LLM-Calls)
vs LES-Recall — wie viel Last spart die Reihung, ohne LES *vor* dem LLM wegzuschneiden? Gegen Iter 08.

## Messung (`iter_33_cascade_cost.py`, blinder Strom n=120, LES=8)
| Betrieb | LLM-Calls | Kosten | LES-Recall |
|---|---|---|---|
| LLM-only (kein Vorfilter) | 120 | 100 % | **88 %** |
| Kaskade @20 %-Cutoff | 24 | 20 % | 50 % |
| **Kaskade @30 %-Cutoff** | 36 | 30 % | **62 %** |
| Kaskade @40 % | 48 | 40 % | 62 % |
| Kaskade @50 % | 60 | 50 % | 62 % |
| Kaskade @70 % | 84 | 70 % | 62 % |

## Harte Kritik
- **Die Kaskade spart real Kosten, kostet aber Recall — kein Gratis-Mittagessen (P15, P16):** bei 30 %-
  Cutoff fallen 70 % der LLM-Calls weg, aber der LES-Recall sinkt von **88 % (LLM-only) auf 62 %** — das
  sind 2 der 8 Pflichtlektüren, die der Algo wegschneidet, bevor das (bessere) LLM sie sehen könnte. Für
  einen Scout, der nichts verpassen darf, ist das ein **echter** Tradeoff, keine reine Effizienz.
  Bestätigt Iter 08 hart: Vorfilter + hoher Recall sind unvereinbar bei diesem Signal.
- **Das Plateau bei 62 % ist der entscheidende Befund (P6):** ab 30 %-Cutoff bringt mehr LLM-Last **null**
  zusätzliche LES. Die fehlenden 2 LES sind entweder unter M-Cs Reichweite (die signalfreien
  konzeptuellen Fälle, Iter 11/31) oder werden vom LLM selbst verworfen — in beiden Fällen hilft ein
  höherer Cutoff nicht. Wer über 30 % hinaus geht, zahlt mehr Geld für genau 0 zusätzliche Treffer.
- **Daraus folgt ein klarer Betriebspunkt (P7):** **LLM auf M-Cs oberste ~30 %** = 70 % Kostenersparnis
  bei 62 % LES-Recall. Wer die 88 % will, muss **alles** ans LLM geben (volle Kosten) — ODER die 2
  unerreichbaren LES über den **Volltext-Eskalationspfad** (Iter 30/§2.5) holen, statt sie dem
  abstract-basierten Ranker zuzumuten. Die Kaskade ersetzt diesen Pfad nicht.
- **Ehrlich über die Größenordnung (P3):** 8 LES → jede ist 12,5 %. „62 %" = 5 LES, „88 %" = 7 LES. Auf
  diesem n sind das Einzel-Artikel-Effekte; die *Form* (Plateau, Kosten-Recall-Antagonismus) ist robust,
  die exakten Prozente nicht. Auf dem Volllauf-Strom mit mehr LES wäre die Kurve glatter — aber die
  Aussage „Vorfilter kostet Recall" bleibt.
- **Was das für 2.0 heißt:** der ökonomische Wert des Algorithmus ist real (70 % weniger LLM-Calls),
  aber begrenzt und erkauft. Sein *unbestrittener* Wert liegt woanders: in der **Reihung** (Benjamin
  liest die Spitze zuerst) und der **geerdeten Anreicherung** (Iter 19), nicht im Wegschneiden.

## → nächste Iteration
Iter 34: **Modell M-D = M-C + Zwei-Pfad-Routing** (abstract-reich → Ranker→LLM-Kaskade; abstract-arm →
Bibliometrie+Eskalation, Iter 23/30) als vollständiges System-Diagramm + die kombinierte
LES-Recall/Kosten-Bilanz beider Pfade. Das ist die erste *vollständige* 2.0-Filter-Architektur.
