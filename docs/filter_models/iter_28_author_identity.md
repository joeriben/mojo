# Iter 28 — Author-Identitäts-Achse (Negativ + Leak-Fang)

## Anforderung
Bisherige geerdete Achsen: Refs (own/bez-works), Inhalt (rich), Journal-Prior. Fehlt die Autor-Identität:
schreibt der Artikel von jemandem, den Benjamin kennt? Kandidaten geprüft auf Diskrimination, blind-
Coverage und **Zirkularität** (P3).

## Messung (`iter_28_author_identity.py`)
| Achse | feuert | keeper | IGN | Ratio | blind-keeper | AUC |
|---|---|---|---|---|---|---|
| f_coauthor_hits | 20 | 5 % | 4 % | 1.45 | 4 % | 0.509 |
| f_trigger_author_match | 2 | 1 % | 0 % | ∞ | 0 % | — |

`bezugsautoren.author_seed`: **alle 221 Einträge role=`first_author`** — die Autoren wurden AUS den
Gold-Artikeln geseedet → „Artikel-Autor ∈ bezugsautoren" ist **zirkulär**.

## Harte Kritik
- **Author-Identität ist keine nutzbare unabhängige Achse — ehrliches Negativ (P6, P15):**
  Koautorschaft feuert nur 20× und diskriminiert kaum (Ratio 1.45, keep-AUC 0.509 = Zufall). Der
  Trigger-Autor-Match feuert im ganzen Gold-Satz **2×** und blind **0×** — als Eskalations-Heuristik
  (Memory project_trigger_autoren) mag er punktuell wertvoll sein, als *statistisches* Triage-Signal ist
  er irrelevant. Beide tragen nichts zur Ranking-/Filter-Leistung bei.
- **Leak verhindert (P3 — der eigentliche Ertrag):** der naheliegende „bezugsautor-Autor-Match" wäre ein
  **Zirkelschluss** gewesen — die 208 bezugsautoren SIND die Erstautoren genau dieser Artikel. Hätte ich
  das als Feature gebaut, hätte es auf dem Gold-Satz glänzend ausgesehen und auf neuen Daten nichts
  getaugt. Der Provenienz-Check (author_seed.role) fängt das ab, bevor es zur aufgeblähten Kennzahl wird.
  Genau die Disziplin, die heute früher gefehlt hat.
- **Klärt die Achsen-Landschaft abschließend:** die tragenden geerdeten Achsen sind **Refs** (own/bez-
  works, Iter 17/18), **Inhalt** (rich-Text, Iter 13/27), **Journal-Prior** (Iter 25) und **named_thinker**
  (Iter 20, mit Härtung). Autor-Identität gehört NICHT dazu. Das ist eine Negativ-Abgrenzung mit Wert:
  sie verhindert, dass die nächste Iteration Energie in eine tote Achse steckt.
- **Wichtige Unterscheidung, fair (P8):** „nicht nützlich als Triage-Signal" ≠ „nicht nützlich als
  Anreicherung/Eskalation". Ein Trigger-Autor-Treffer bleibt ein legitimer *Eskalations*-Auslöser
  (benannte Person, hoher Präzisionswert *wenn* er feuert) — er ist nur kein Recall-Hebel und kein
  Ranking-Feature. Ich verwerfe die statistische Rolle, nicht die operative.

## → nächste Iteration
Iter 29: **Ablation der rich-Text-Bestandteile** — welcher Teil des reichen Eigenwerk-Texts trägt die
content-AUC: `summary_de`, `key_terms` oder `named_thinkers`? Das zeigt, ob der Hebel die inhaltliche
Zusammenfassung oder das Vokabular/die Denker ist — und ob der teure Opus-Summary-Schritt nötig ist oder
key_terms allein reichen (Kosten-Relevanz, P13).
