# Iter 13 — Kombination der zwei Content-Achsen

## Anforderung
Iter 12: global Abstract-Sim und reiche Summary-per-Werk-Sim sind beide ~0.69 AUC, irren aber
*unterschiedlich*. Test: schlägt die Kombination die 0.69-Decke jeder Einzelachse? max / Mittel /
LogReg, OOF CV, keep-AUC gesamt + unsichtbare-keep + **screening-Strom** (der reale blinde Fall).

## Messung (`iter_13_content_combo.py`, MiniLM, OOF)
| Kombination | keep-AUC | unsichtbar-AUC | screening-AUC |
|---|---|---|---|
| global allein | 0.692 | 0.657 | **0.517** |
| rich allein | 0.690 | 0.656 | **0.632** |
| max(rich,global) | 0.697 | 0.661 | 0.619 |
| **mean(rich,global)** | **0.728** | **0.693** | 0.607 |
| LogReg(rich,global) OOF | 0.722 | 0.687 | 0.596 |

## Harte Kritik (zwei echte, geerdete Befunde — erstmals in Phase C)
- **Die Decke ist NICHT total (P6, P15):** `mean(rich,global)` = **0.728** keep-AUC / **0.693**
  unsichtbar — **+0.036** über die beste Einzelachse. Die in Iter 12 vermutete Komplementarität ist
  real und nutzbar. Damit ist Iter 09s Schluss „per-Werk bringt nichts" **falsifiziert** — er galt nur
  für die *isolierte* Betrachtung dünnen Titel-Texts, nicht für reiche, kombinierte Erdung.
- **Der wichtigere Befund steht in der screening-Spalte:** auf dem **blinden** Strom ist global allein
  **0.517** (praktisch Zufall!), rich allein **0.632**. Die globale Korpus-Aggregation — der bisherige
  Produktiv-Score M7 — ist auf dem realen Entdeckungs-Strom **fast nutzlos**; der werk-geerdete reiche
  Summary-Sim ist dort der klar bessere Hebel. Das ist der erste Befund, der das 2.0-Motiv (Erdung im
  Œuvre statt globaler Haufen) *empirisch* trägt statt es nur zu postulieren.
- **mean schlägt LogReg (0.728 vs 0.722):** der gelernte Kombinierer überanpasst leicht; das simple
  Mittel ist robuster und braucht kein Training. Einfachste Lösung zuerst (Projekt-Konvention) — bestätigt.
- **Ehrlichkeit über n (P15):** screening-AUC steht auf **8 Positiven** (120 Items). 0.632 vs 0.517 ist
  richtungsweisend, aber die absolute Zahl ist verrauscht — nicht als Punkt-Schätzung verkaufen. Der
  *Mechanismus* (global blind ≈ Zufall, rich blind > global) ist konsistent mit Iter 11/12 und damit
  belastbar als Richtung.
- **Offene Schwäche:** mean(rich,global) ist auf dem *blinden* Strom (0.607) leicht schlechter als rich
  allein (0.632) — global zieht dort runter. D.h. die beste Kombi ist set-abhängig: auf der breiten
  (bias-behafteten) Menge gewinnt das Mittel, auf dem blinden Strom rich-solo. Für Produktion heißt das:
  rich-Sim ist das Rückgrat, global nur additiv auf der breiten Menge. Muss in der Modell-Iteration
  (iter_14) sauber getrennt gemessen werden.

## → nächste Iteration
Iter 14: den reichen Summary-Sim ins **volle 3-Klassen-Modell** falten (own + rich + global) und ehrlich
gegen die Leiste (Boden 0.544/0.589, own+content 0.514) messen — hebt die werk-geerdete Achse die
*tatsächliche* Triage-macro-F1 / LES-Recall, oder bleibt der Gewinn auf die AUC-Rangordnung beschränkt?
