# Iter 11 — Anatomie der Fehler: sind die verfehlten LES überhaupt geerdet?

## Anforderung
Vor dem Bau von Phase C (geerdete Bezüge): **wo** scheitert own+content, und teilen die verfehlten
LES *irgendein* geerdetes Signal? Wenn die Hard-Cases signalfrei sind, kann auch Volltext-Erdung sie
nicht retten (Memory feedback_ground_truth: 72 Items, wo Algo+Opus beide falsch liegen).

## Messung (`iter_11_error_anatomy.py`, OOF own+content)
| | LES | getroffen | verfehlt | verfehlt-signalfrei |
|---|---|---|---|---|
| GESAMT | 79 | 42 | 37 | 12/37 |
| SCREENING (blind) | 8 | 4 | **4** | **4/4** |

Signal-Mittelwerte (getroffene vs. verfehlte LES, GESAMT): own_coupling 1.29 ↔ **0.08**, citation
1.38 ↔ **0.11**, ref_overlap_authored 0.36 ↔ **0.00**, content-Sim 0.656 ↔ 0.594. Trigger-Ref-Overlap
ist bei verfehlten *höher* (5.05 ↔ 3.07) → Rauschen, bestätigt Iter 03.

**Die 4 verfehlten blind-LES (alle coupling=0, citation=0, Sim<0.615):**
- `[ZfPaed]` Die AfD und eine ‚Erziehung nach Auschwitz' — Adorno → Bildungstheorie (Sim 0.551)
- `[BDS]` Rating villagers' morality: Techno-moral governance via data scoring, rural China (Sim 0.525)
- `[STHV]` Making Queer Kin in the Labor of the Greenhouse — Haraway/Posthumanismus (Sim 0.538)
- `[RAeE]` Mikrokosmoksia … STEAM-laboratoriossa — ÄKB, **finnisch** (Sim 0.533)

## Harte Kritik
- **Der getroffene/verfehlte-Split ist fast vollständig bibliometrisch (P6):** getroffene LES haben
  ~1.3 Kopplung/Zitation, verfehlte ~0.1 — das Modell trifft genau die geerdeten und verfehlt genau
  die ungeerdeten. Das ist keine Modellschwäche, sondern Datenlage.
- **Strukturelle Decke benannt, nicht behauptet (P15):** die 4 blind-verfehlten LES sind **4/4
  signalfrei** — null Kopplung, null Zitation, null Coautor, null Ref-Overlap, Sim unter keep-Median.
  Phase C (geteilte Referenzen mit benanntem Eigenwerk) kann sie **nicht** treffen: sie teilen keine
  Referenzen. Das ist die ehrliche Grenze jeder *bibliometrischen* Erdung auf dem blinden Strom.
- **Aber die Diagnose zeigt den richtigen Hebel:** alle vier sind **konzeptuell** einschlägig (Adorno/
  Bildungstheorie, Datafizierung, Posthumanismus, ÄKB) — die Relevanz liegt im *Thema*, nicht im
  geteilten Text oder den geteilten Referenzen. MiniLM-Abstract-Embedding sieht das nicht (der finnische
  Text wird zusätzlich durch die Sprache gedrückt). Der nächste Hebel ist also **Konzept-Raum**
  (OpenAlex concepts/topics vs. Benjamins Konzeptprofil), nicht Text-Sim und nicht Refs.
- **Ehrlichkeit über n:** 4 blind-verfehlte LES sind anekdotisch. Der *Mechanismus* (Relevanz konzeptuell,
  nicht lexikalisch/bibliometrisch) ist aber an konkreten Titeln nachvollziehbar und deckt sich mit dem
  dokumentierten Hard-Case-Befund. Als Richtung belastbar, als Quote nicht.

## → nächste Iteration
Iter 12: **Konzept-Raum-Erdung** — überlappen die OpenAlex-`concepts`/`topics` dieser Artikel mit
Benjamins Konzeptprofil (aus `own_refs`/Eigenwerk-Konzepten), auch wenn Text-Embedding und Referenzen
es nicht tun? Wenn ja, ist Konzept-Overlap ein geerdeter Hebel für genau die konzeptuell-relevanten
Treffer, die Iter 02/09 verfehlen.
