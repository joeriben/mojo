# Gemini 3.5 Flash + MiMo-Patches — N=50 Vergleich zur Baseline

**Datum:** 2026-05-23T15:54:35.426495
**Konfig:** PATCHED_OUTRO = ASSESSMENT_OUTRO + MIMO_OUTRO_PATCHES (Regel A/B/C aus qcheck_mimo_promptv2.py)
**Gleiche Stichprobe** wie Baseline (seed=42), **gleiche Modell-Konfig** (reasoning.effort=low)

## Headline: Baseline **26/50 = 52%** → Patched **25/50 = 50%** (-1)
**Kosten:** $2.2026

- 7/50 Verdicts haben sich geändert
- davon **2 zum Besseren** (Patch korrigiert Baseline-Fehler)
- davon **3 zum Schlechteren** (Patch zerstört Baseline-Treffer)
- Saldo: -1

## Konfusionsmatrix (Patched)

| Opus → Gemini patched | ignorieren | scannen | lesenswert | pflichtlektuere |
|---|---:|---:|---:|---:|
| **ignorieren** | **2** | 8 | 5 | 0 |
| **scannen** | 1 | **3** | 8 | 0 |
| **lesenswert** | 0 | 2 | **19** | 1 |
| **pflichtlektuere** | 0 | 0 | 0 | **1** |

## Geänderte Verdicts (Patches haben Verdict gegenüber Baseline geflippt)

| Journal | Opus | Baseline | Patched | Effekt | Patched-Begründung |
|---|---|---|---|---|---|
| ZfE | `ignorieren` | `lesenswert` | `scannen` | ≈ anders falsch | Der Aufsatz ist wichtig für die allgemeine erziehungswissenschaftliche Diskursübersicht im Bereich der Schulforschung und Subjektivierungstheorie (Bezugslinie Ricken/Reh). Da jedoc |
| BDS | `lesenswert` | `lesenswert` | `scannen` | ✗ schlechter | Der Artikel ist für die Diskursübersicht im Bereich nachhaltiger Post-Digitalität und soziotechnischer Materialkreisläufe (Anthropozän-Debatte im Projekt 'cultural_resilience') von |
| STHV | `scannen` | `scannen` | `ignorieren` | ✗ schlechter | Das Thema der assistierten Reproduktionsmedizin (IVF) und epigenetischer Plastizität in der Embryonalentwicklung liegt außerhalb des medienpädagogischen, bildungstheoretischen und  |
| MedienPaed | `pflichtlektuere` | `scannen` | `pflichtlektuere` | ✓ besser | Es handelt sich um eine eigene Publikation der Forschungsgruppe (Co-Autorenschaft), die eine zentrale theoretische Säule des Projekts metakubi und der schulkulturellen Transformati |
| MedienPaed | `lesenswert` | `lesenswert` | `pflichtlektuere` | ✗ schlechter | Der Beitrag ist eine Pflichtlektüre, da er direkt auf dem am Lehrstuhl durchgeführten DiKuJu-Projekt aufbaut und die dortige Schlüsselvignette theoretisch weiterentwickelt. Zudem w |
| EPT | `scannen` | `lesenswert` | `scannen` | ✓ besser | Der Text verortet sich im Diskursfeld transformativer Bildung und bezieht sich explizit auf den UNESCO-Bericht 'Reimagining our futures together', verhandelt das Thema 'Widerstand' |
| JAE | `ignorieren` | `scannen` | `lesenswert` | ≈ anders falsch | Der Text bietet hohes Anregungspotenzial für das Projekt 'cultural_resilience', da die beschriebene 'kinästhetische Musikalität' exzellent an das Konzept der 'Rootedness' (leiblich |
