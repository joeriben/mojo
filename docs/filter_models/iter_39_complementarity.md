# Iter 39 — Complementarity-Pool: die Triage-Falle an M-C

## Anforderung
Memory feedback_ground_truth: 41 % der LES aus complementarity-Quelle = „Triage-Falle" (Algo+Opus nur
~58–62 % Agreement). Reiht M-C die schwer-begründbaren complementarity-keeper ähnlich hoch wie die
offensichtlichen (citation/trigger)? Mittlerer M-C-Perzentil-Rang der keeper pro selection_mode.

## Messung (`iter_39_complementarity.py`)
| selection_mode | keeper | M-C Ø-Rang | rich-Rang | biblio-Treffer |
|---|---|---|---|---|
| citation | 21 | **91 %** | 93 % | 100 % |
| similarity | 33 | 69 % | 70 % | 15 % |
| screening | 25 | 59 % | 57 % | 0 % |
| **complementarity** | **88** | **57 %** | 53 % | 7 % |
| mixed | 19 | 55 % | 55 % | 11 % |
| trigger | 2 | 39 % | 39 % | 50 % |

complementarity-keeper Ø-Rang **57 %** vs citation/trigger **86 %** (−29 pp).

## Harte Kritik
- **M-C trifft das Offensichtliche, verfehlt das Komplementäre (P15, P16):** citation-keeper (91 %,
  100 % biblio-Anker) reiht M-C sehr hoch; die **complementarity**-keeper (57 %, nur 7 % biblio-Anker,
  und mit **88** die *größte* keeper-Gruppe) ~29 pp tiefer. Das ist die dokumentierte Triage-Falle,
  jetzt an M-C reproduziert: Relevanz, die *komplementär* (additiv zum Werk) statt *referenziell*
  (geteilte Quellen) ist, hat keinen bibliometrischen Fußabdruck und nur mittlere Content-Sim — M-C
  hat dort keinen Hebel.
- **Verbindet alle Hard-Case-Befunde der Serie (P6):** complementarity-Schwäche (Iter 39) = signalfreie
  konzeptuelle LES (Iter 11) = Frontier-Blindfleck digitale_kultur/resilienz (Iter 37). Drei Linsen,
  ein struktureller Kern: **generative, nicht-referenzielle Relevanz ist algorithmisch nicht greifbar.**
  Das ist keine Modellschwäche, die sich wegtrainieren ließe — es ist die Definition des Problems.
- **Ehrliche Rollen-Klärung (P11, P16):** M-Cs Wert liegt im **billigen Hochreihen des Offensichtlichen**
  (citation 91 %) und im **moderaten** Sortieren des Mittelfelds. Die complementarity-Treffer gehören
  zwingend ans LLM (Iter 32) — und selbst das LLM/Opus schafft dort nur ~62 % Agreement (Memory). Der
  ehrlichste Umgang: M-C reiht, markiert aber die **biblio-ankerlose Mittelzone** (57 %-Rang, kein
  Veto-Treffer) explizit als „algorithmisch unsicher → LLM/Lektüre", statt eine Sicherheit zu
  suggerieren, die es nicht hat.
- **Caveat (P3):** die complementarity-keeper stammen aus dem intentional-positiven Pool (selection_mode),
  nicht aus dem blinden Strom — gemessen wird „M-C auf der schweren intentional-positiven Menge", nicht
  blind. Die Aussage „M-C unterreiht komplementäre Relevanz" überträgt sich aber direkt auf den blinden
  Strom (dort sind die screening-keeper bei 59 %, ähnlich der complementarity-57 %, und ebenfalls
  biblio-ankerlos).
- **Konsequenz fürs System:** der substitutive Komponist (Iter 19) muss die „Leerstelle/nur-Score"-Fälle
  (= biblio-ankerlose Mittelzone) als das kennzeichnen, was sie sind: **Kandidaten für komplementäre
  Relevanz, die M-C nicht beurteilen kann** — der ehrlichste denkbare Output dort ist „relevant *könnte*
  sein, Begründung nur über Lektüre", nicht ein konfabulierter Bezug.

## → nächste Iteration
Iter 40: **Finaler Scorecard + empfohlene Architektur** — alle belastbaren Befunde (01–39) in einer
ehrlichen Leistungs-/Grenzen-Bilanz mit Spannen (Iter 36), der M-E-Architektur, den drei Werte-
Entscheidungen (Serendipität/Frontier/Kaskaden-Kosten) und der klaren Rollenteilung Algo↔LLM↔Lektüre.
