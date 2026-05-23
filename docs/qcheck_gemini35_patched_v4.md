# Gemini 3.5 Flash + V4-Patches (Konsistenz negativ + positiv) — N=50

**Datum:** 2026-05-23T17:15:11.191088
**Konfig:** ASSESSMENT_OUTRO + V4-Patches
**Gleiche Stichprobe** wie Baseline (seed=42), **gleiche Modell-Konfig** (reasoning.effort=low)

## Headline (gegen Opus, *nicht* Goldstandard): Baseline **26/50** → V4 **24/50** (-2)
**Kosten:** $2.3024

- 7/50 Verdicts haben sich geändert
- davon **1 zum Besseren** (V4 korrigiert Baseline gegen Opus)
- davon **3 zum Schlechteren** (V4 zerstört Baseline-Treffer gegen Opus)
- Saldo: -2

## Konfusionsmatrix (V4)

| Opus → Gemini V4 | ignorieren | scannen | lesenswert | pflichtlektuere |
|---|---:|---:|---:|---:|
| **ignorieren** | **3** | 5 | 7 | 0 |
| **scannen** | 2 | **1** | 9 | 0 |
| **lesenswert** | 0 | 1 | **20** | 0 |
| **pflichtlektuere** | 0 | 0 | 1 | **0** |

## Geänderte Verdicts (V4 vs. Baseline)

| Journal | Opus | Baseline | V4 | Effekt (vs Opus) | V4-Begründung |
|---|---|---|---|---|---|
| STHV | `scannen` | `scannen` | `ignorieren` | ✗ schlechter | Der Beitrag verortet sich in der medizinischen Anthropologie und den Science and Technology Studies der Reproduktionsmedizin. Er weist keine Anknüpfungspunkte zu den medien-, kultu |
| BJET | `ignorieren` | `scannen` | `ignorieren` | ✓ besser | Der Beitrag ist klassischer empirisch-quantitativer Instruktionspsychologie und EdTech-Forschung zuzuordnen; es gibt keine spezifischen Anschlüsse an post-digitale, medienbildungst |
| MedienPaed | `pflichtlektuere` | `scannen` | `lesenswert` | ≈ anders falsch | Es handelt sich um eine eigene koaktiv verfasste Publikation des Forschers (mit Leopold und Tanja Klepacki), die für die Projekte MetaKuBi (Schulkultur, Transformation) und DiäS-Ku |
| RAeE | `lesenswert` | `lesenswert` | `None` | ✗ schlechter |  |
| JAE | `scannen` | `scannen` | `ignorieren` | ✗ schlechter | Der Artikel untersucht Narrative des Widerstands gegen White Supremacy im spezifisch US-amerikanischen Kontext auf Basis von Kenneth Burke und Religionsrhetorik. Da er sich primär  |
| JAE | `ignorieren` | `scannen` | `lesenswert` | ≈ anders falsch | Der transdisziplinäre Import von Tanz- und Bewegungstheorien in die qualitative Spiel- und Kindheitsforschung bietet ein hohes Anregungspotenzial für die Rekonstruktion ästhetische |
| JAE | `ignorieren` | `scannen` | `lesenswert` | ≈ anders falsch | The article is highly relevant for ComeArts and general post-digital aesthetic theory, as its phenomenological approach to aural imitation and 'hearing via the other' provides a pr |
