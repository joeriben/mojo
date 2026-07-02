# Strategie 06 — Projekt-Achse als Erdungssignal (ehrlicher Negativ-Befund → Umdeutung)

## Ist-Zustand (gemessen, `/tmp/s6.py`)
`projects.json` ist reich (5 Projekte, Beschreibung + relevance_shifts + connected_publications), aber in
keinem Signal genutzt. Probe — Projekt-Anker-Ähnlichkeit (max über 5 Projekte) als keep-Signal:
| Maßstab | keep-AUC |
|---|---|
| alle Quellen | 0.624 |
| **blinder Strom** | **0.410** (schlechter als Zufall!) |
| pro Projekt blind | 0.41–0.47 (alle < 0.5) |
| Korrelation proj_sim ↔ rich_sim | 0.21 |

## Strategie v1
Projekt-Beschreibungen embedden, max-Ähnlichkeit als keep-Relevanz-Signal nutzen.

## Adversariale Kritik (v1)
**v1 ist gemessen schädlich:** blind-AUC 0.410 liegt *unter* Zufall. Die Probe hat mich vor dem Einbau
eines kontraproduktiven Signals bewahrt (R2 — genau wozu die nachgelagerte Messung da ist). Zwei Gründe:
1. **Grant-Prosa ≠ wissenschaftliche Relevanz:** „Post-Anthropocene", „Metavorhaben", Förder-Sprache matcht
   einen *anderen* Artikel-Cluster als die tatsächlichen keeper.
2. **Möglicherweise sogar invers:** hohe Projekt-Ähnlichkeit kann „bereits abgedeckt → weniger
   interessant" bedeuten; die echten keeper sind oft *komplementär* (neue Richtung), nicht projekt-nah
   (= die complementarity-Falle, Iter 39). Korrelation 0.21 mit rich_sim bestätigt: misst etwas anderes —
   aber das Andere ist nicht keep.

## Strategie v2 (anders erden + Achse umdeuten)
1. **Nicht auf Grant-Prosa ankern, sondern auf `connected_publications`:** die je Projekt verknüpften
   echten Werke (3–6 Stück) per Summary/Volltext embedden. Wissenschaftlicher Text statt Förder-Sprache —
   vermutlich diskriminativer (zu MESSEN, nicht zu behaupten).
2. **Achse umdeuten — Routing statt Relevanz:** die Messung sagt, Projekt-Nähe taugt nicht für keep/drop.
   Also als **Tagging/Routing**-Signal verwenden („welchem Projekt ordnet sich ein *bereits als keeper
   erkannter* Artikel zu?") — Organisation des Digests, nicht Filterung. Das ist derselbe Lernschritt wie
   Iter 43/44/45: manches Material erdet/organisiert, ohne Relevanz zu ranken.
3. **relevance_shifts separat:** die `relevance_shifts` (was am Projekt sich verschiebt) sind potenziell
   *zukunftsgerichteter* als die Beschreibung — als eigener Anker testen (Frontier-Signal, Iter 37/38).
4. **Projekt-Volltexte** (Strat 07) als reichere Anker, falls verfügbar.

## Erwarteter Effekt & Messbarkeit (R2, P15)
v1 ist widerlegt (0.410). v2-Erwartung offen: connected_publications-Anker *könnte* besser sein, aber ich
projiziere keine Zahl — Phase 2 misst. Ehrlich denkbares Ergebnis: die Projekt-Achse bleibt ein
Routing-/Organisations-Signal, kein Relevanz-Hebel. Auch das wäre ein valides, nützliches Resultat
(Digest-Strukturierung nach aktiven Projekten).

## → Benjamin-Aufgabe?
Nein für v2-Schritt 1–3. Schritt 4 (Projekt-Volltexte) → Strat 07.

## → nächste
Strat 07: Projekt-Volltexte/Anträge — die reichste denkbare Projekt-Repräsentation, aber Verfügbarkeit
ungewiss (möglicher zweiter Benjamin-Trigger).
