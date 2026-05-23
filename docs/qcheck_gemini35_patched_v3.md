# Gemini 3.5 Flash + V3-Patches (Konsistenz + Beheimatungen) — N=50

**Datum:** 2026-05-23T16:54:07.274622
**Konfig:** ASSESSMENT_OUTRO + V3-Patches (Konsistenz-Regel + 5 Beheimatungen)
**Gleiche Stichprobe** wie Baseline (seed=42), **gleiche Modell-Konfig** (reasoning.effort=low)

## Headline: Baseline **26/50 = 52%** → V3 **25/50 = 50%** (-1)
**Kosten:** $2.2134

- 9/50 Verdicts haben sich geändert
- davon **2 zum Besseren** (V3 korrigiert Baseline-Fehler)
- davon **3 zum Schlechteren** (V3 zerstört Baseline-Treffer)
- Saldo: -1

## Konfusionsmatrix (V3)

| Opus → Gemini V3 | ignorieren | scannen | lesenswert | pflichtlektuere |
|---|---:|---:|---:|---:|
| **ignorieren** | **4** | 8 | 3 | 0 |
| **scannen** | 2 | **1** | 8 | 0 |
| **lesenswert** | 0 | 2 | **20** | 0 |
| **pflichtlektuere** | 0 | 0 | 1 | **0** |

## Geänderte Verdicts (V3 vs. Baseline)

| Journal | Opus | Baseline | V3 | Effekt | V3-Begründung |
|---|---|---|---|---|---|
| ZfE | `ignorieren` | `lesenswert` | `scannen` | ≈ anders falsch | Der Artikel ist hochgradig anschlussfähig an die erziehungswissenschaftliche Kernbeheimatung (Allgemeine Pädagogik / Schultheorie / Subjektivierungstheorie) und bietet wichtige Dis |
| STHV | `scannen` | `scannen` | `ignorieren` | ✗ schlechter | Der Artikel befasst sich mit medizinethnographischen und biopolitischen Dynamiken der assistierten Reproduktion sowie Epigenetik in der Postgenomik. Er berührt keines der aktiven F |
| BJET | `ignorieren` | `scannen` | `ignorieren` | ✓ besser | Der Beitrag vertritt ein rein technologisch-instrumentelles Verständnis von generativer KI als funktionales Feedback-Werkzeug im Rahmen des klassischen Community-of-Inquiry-Modells |
| MedienPaed | `pflichtlektuere` | `scannen` | `lesenswert` | ≈ anders falsch | Es handelt sich hierbei um die eigene Veröffentlichung der Autor*innengruppe (pub_id: H2C4LUW8), die für die disziplinäre Verortung in der Allgemeinen Pädagogik und Schultheorie ze |
| MedienPaed | `lesenswert` | `lesenswert` | `scannen` | ✗ schlechter | Der Artikel ist für die Diskursübersicht in der Medienbildung relevant, da er die Ausgestaltung und pädagogische Logik digitaler Erklärformate zu gesellschaftlichen Krisen im Horiz |
| EPT | `ignorieren` | `lesenswert` | `scannen` | ≈ anders falsch | Der Artikel ist relevant für die Disziplinäre Beheimatung 1 (Allgemeine Pädagogik / Bildungsphilosophie) und berührt aktuelle Debatten um generative KI (Projekt AI4ArtsEd). Die kla |
| JAE | `scannen` | `scannen` | `ignorieren` | ✗ schlechter | Der Beitrag befasst sich im Schwerpunkt mit US-amerikanischer Rhetoriktheorie, Kriminologie und der historischen Auseinandersetzung mit weißer Vorherrschaft. Es gibt keine nennensw |
| JAE | `scannen` | `lesenswert` | `None` | ≈ anders falsch |  |
| ArtsEdPolRev | `ignorieren` | `scannen` | `ignorieren` | ✓ besser | Der Beitrag bietet eine rein deskriptive Auswertung von Social-Media-Formaten während der Pandemie auf Marketing-Ebene und weist keine theoretischen oder konzeptionellen Anknüpfung |
