# Iter 34 — Modell M-D: Zwei-Pfad-System + LES-Bilanz

## Modell-Definition
**M-D** = M-C + Routing nach Abstract-Verfügbarkeit:
- **Pfad A (abstract-reich, ≥200 Z.):** M-C-Ranking → LLM entscheidet (Kaskade/voll).
- **Pfad B (abstract-arm, <200 Z.):** kein Content-Ranking (Iter 23: ≈Zufall); Bibliometrie-Präzisions-
  Treffer sofort, Rest depriodisiert/Eskalation.

## Messung (`iter_34_two_path.py` + Folgecheck, blinder Strom n=120, LES=8)
| | n | LES | scannen+LES (keep) |
|---|---|---|---|
| Pfad A (abstract-reich) | 69 | **8** | 16 |
| Pfad B (abstract-arm) | 51 | **0** | 9 |

| Betrieb | LLM-Calls | LES-Recall | Verlust |
|---|---|---|---|
| LLM auf alle 120 | 120 | 88 % (7/8) | — |
| **LLM auf ganz Pfad A** | **69** | **88 % (7/8)** | 0 LES, −9 scannen |
| Pfad A Kaskade @30 % → LLM | 21 | 50 % (4/8) | −4 LES |

## Harte Kritik
- **Der entlastende Kernbefund (P6, P15):** **alle 8 blinden LES liegen in Pfad A**; der abstract-arme
  Pfad B (43 % des Stroms) enthält **0 LES**. Die in Iter 23 gefürchtete Ranker-Schwäche auf
  abstract-armen Artikeln ist damit weit weniger schädlich: der blinde Fleck des Rankers **deckt sich
  mit dem nicht-relevanten Teil des Stroms**. Abstract-Armut korreliert hier mit Nicht-Relevanz
  (Editorials, Ankündigungen, Fringe-Quellen).
- **Daraus folgt der größte ehrliche Effizienzgewinn — und er liegt NICHT in der Kaskade (P7):** Pfad B
  herausrouten spart **43 % der LLM-Calls bei 0 LES-Verlust**. LLM auf *ganz* Pfad A (69 Calls) liefert
  die vollen **88 %** LES-Recall — gleich wie LLM-auf-alle, aber deutlich billiger. Der Ranker dient
  innerhalb Pfad A der **Reihung** (Spitze zuerst), nicht dem Gaten. Das ist sauberer als die
  Kaskaden-Schnitte aus Iter 33, die LES kosten.
- **Der ehrliche Preis (P15):** Pfad B hat **9 scannen-keeper** (36 % aller keeper). Pfad B
  wegzurouten kostet 0 Pflichtlektüren, aber diese 9 „mal-reinschauen"-Treffer. Für einen Scout, der
  Pflichtlektüre priorisiert, ist das ein exzellenter Tausch; für vollständige scannen-Abdeckung ist es
  ein Verlust. Das ist Benjamins Abwägung, nicht meine — ich beziffere sie (43 % Kosten ↔ 9 scannen),
  statt sie zu verstecken.
- **Caveat, scharf (P3):** „0 LES in Pfad B" steht auf n=51 mit nur 8 LES gesamt — **richtungsweisend,
  nicht garantiert**. Auf dem Live-Strom kann gelegentlich ein LES abstract-arm sein. Die Regel ist
  „abstract-arm ⇒ wahrscheinlich nicht-relevant", kein Naturgesetz. Pfad B sollte daher **deprioritisiert,
  nicht hart verworfen** werden (z. B. periodischer Sweep / Bibliometrie-Veto rettet gekoppelte Fälle).
- **Was M-D NICHT braucht (Korrektur an Iter 30/33):** der Volltext-Eskalationspfad ist hier **nicht**
  nötig, um LES aus abstract-armen Artikeln zu retten — dort sind keine. Er bleibt relevant für die
  **signalfreien konzeptuellen LES innerhalb Pfad A** (das 1 verbleibende von 8, Iter 11), die weder
  Ranker noch LLM-auf-Abstract zuverlässig fangen.

## → nächste Iteration
Iter 35: **Modell M-E = M-D + substitutiver Komponist** als End-to-End-Spezifikation, plus die
**Kosten-Bilanz in $** (LLM-Calls × gemessene Kosten/Call aus articles.db `llm_calls`) — was kostet ein
Volllauf unter M-E vs MOJO-1, und wo liegt die Einzelkosten-Verifikation (CLAUDE.md: niemals Batch ohne
Einzelkosten-Check)?
