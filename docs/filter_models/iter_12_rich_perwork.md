# Iter 12 — Per-Werk-Sim mit reichem Eigenwerk-Text (Summaries)

## Anforderung
Iter 09 fand per-Werk≈global, **aber nur mit Titel+Venue** (zu dünn, ehrlich vermerkt). Iter 11 zeigt:
die verfehlten LES sind *konzeptuell* einschlägig. `summaries.json` (53 Opus-Summaries: `summary_de` +
`key_terms` + `named_thinkers`) ist Benjamins Werk konzept-reich. Test: hebt reicher Eigenwerk-Text die
content-AUC, und steigen die 4 blind-verfehlten LES? Artikel-Seite ebenfalls angereichert (Abstract +
OpenAlex `concepts`/`topics`).

## Messung (`iter_12_rich_perwork.py`, MiniLM, 53 Summaries × 461)
| Feature | keep-AUC | unsichtbare-keep AUC |
|---|---|---|
| Summary-reich per-Werk | 0.690 | 0.656 |
| score_M7 (global, Ref) | 0.692 | 0.657 |

**Perzentil-Rang der 4 blind-verfehlten LES (screening-Strom, höher = relevanter):**
| Artikel | reich | global |
|---|---|---|
| Die AfD / „Erziehung nach Auschwitz" | **94 %** | 36 % |
| Mikrokosmoksia (STEAM, finnisch) | **75 %** | 23 % |
| Rating villagers (techno-moral governance) | 34 % | 21 % |
| Making Queer Kin | 28 % | 28 % |

## Harte Kritik
- **Aggregat-Hypothese erneut nicht bestätigt (P15):** reicher Summary-Text liefert 0.690 keep-AUC —
  praktisch identisch zu global (0.692) und zu Titel-only (Iter 09, 0.691). Der Inhalts-Kanal sitzt
  **stabil bei ~0.69 AUC**, egal welche Eigenwerk-Repräsentation. Das ist jetzt 3× repliziert → harte
  Decke des Abstract-Level-Matchings gegen dieses Label-Set. Wer „reicherer Text = bessere AUC" behauptet,
  ist widerlegt.
- **ABER der Aggregat-AUC verdeckt eine echte Komplementarität (P6, der eigentliche Befund):** auf
  Item-Ebene rankt der reiche Text *andere* Treffer hoch. Er hebt „Erziehung nach Auschwitz" von 36 %
  auf **94 %** und den finnischen STEAM-Text von 23 % auf **75 %** — exakt zwei der konzeptuell-relevanten
  LES, die die globale Abstract-Sim verfehlt. Dass die Aggregat-AUC trotzdem flach bleibt, heißt: der
  reiche Text *verliert* anderswo, was er hier gewinnt. Zwei ~gleich starke, aber **unterschiedlich
  irrende** Content-Achsen.
- **Warum 2 ja, 2 nein — ehrlich:** „Queer Kin" steigt *nicht* (28 %), obwohl Haraway als named_thinker
  im Werk steht — die Greenhouse/Labor-Rahmung dominiert das Embedding über den Kin-Begriff. „Techno-moral
  governance" nur 34 % — Datafizierung ist in den Summaries schwächer vertreten. Der Hebel ist also
  partiell, nicht universal; kein Overclaim.
- **Konsequenz:** ein einzelner AUC-Wert ist die falsche Linse. Zwei Achsen, die dieselbe Globalzahl
  haben, aber verschiedene Treffer finden, gehören **kombiniert** — nicht gegeneinander ausgewählt
  (das war Iter 09s Fehlschluss „per-Werk bringt nichts"). Das ist der erste positive Erdungs-Befund
  der Phase C.

## → nächste Iteration
Iter 13: **Kombination beider Content-Achsen** (global Abstract-Sim ⊕ reiche Summary-per-Werk-Sim) —
als max, als Mittel und als zwei LogReg-Features. Hebt die Kombination keep-AUC / LES-Recall über die
~0.69-Decke jeder Einzelachse? Wenn ja, ist Komplementarität der Hebel; wenn nein, ist die Decke total.
