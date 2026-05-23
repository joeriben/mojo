# Gemini 3.5 Flash — Re-Test der Divergenzen (high-effort + sauberes Schema)

**Datum:** 2026-05-23T15:40:41.938533
**Ausgangspunkt:** 24 Divergenzen aus N=50-Lauf
**Änderungen:** `reasoning.effort=low → high`, Tool-Schema: nur `kernthese`/`verdict`/`verdict_begruendung` required
**Kosten:** $1.5675

## Ergebnis: 4 von 24 Verdicts geändert (1 korrekt zu Opus geflippt, 3 immer noch falsch)

**Implizierte neue Gesamt-Rate**: (26 + 1) / 50 = **54.0%**
(vorher: 26/50 = 52.0%)

## Per-Artikel-Vergleich

| # | Journal | Opus | Gemini low | Gemini high | Δ | Begründung high |
|---:|---|---|---|---|---|---|
|  | Discourse | `scannen` | `lesenswert` → `scannen` |  ✓ | Der Aufsatz ist für die Diskursübersicht im Bereich posthumanistischer und neomaterialistischer Bildungstheorie wertvoll, da er eine Brücke zur kulturhistorischen Schule schlägt. D |
|  | EthicsEd | `scannen` | `lesenswert` = `lesenswert` |  | Der Text ist hochgradig anschlussfähig für das Projekt „Cultural Resilience“, da Hadots „spiritual exercises“ als strukturierte Praktiken der Welt-Wahrnehmung und habituellen Trans |
|  | Discourse | `scannen` | `lesenswert` = `lesenswert` |  | Der Text bietet ein hochgradig anschlussfähiges dekoloniales Theorieangebot (über Glissants relationelle Ontologie) für das Projekt ›cultural_resilience‹, das Jörissens eigene Arbe |
|  | EERJ | `scannen` | `lesenswert` = `lesenswert` |  | Der Artikel bietet hochgradig produktive konzeptionelle Reibungsflächen für die Projekte DiäS-KuBi (hinsichtlich digital-ästhetischer Souveränität von Lehrkräften gegenüber visuali |
|  | ZfE | `ignorieren` | `lesenswert` = `lesenswert` |  | Die Studie stellt eine exzellente kontrastive Ergänzung zu Jörissens relationaler Bildungstheorie dar: Sie analysiert präzise jene individualisierte Scheinfreiheit und Responsibili |
|  | ZfE | `ignorieren` | `scannen` = `scannen` |  | Der Beitrag ist wertvoll für die allgemeine Diskursübersicht zur Lehrerprofessionalitätsforschung in den Geisteswissenschaften. Da er jedoch keinen direkten Bezug zu postdigitaler  |
|  | ZfE | `ignorieren` | `scannen` = `scannen` |  | Der Beitrag liefert eine solide Diskursübersicht zur OER-Infrastruktur und deren Policy-Entwicklungen in Deutschland, verbleibt jedoch bezüglich generativer KI in einer rein arbeit |
|  | BJET | `ignorieren` | `scannen` = `scannen` |  | Das Thema berührt die Nutzung generativer KI in der Hochschullehre, verbleibt jedoch methodisch und theoretisch in einer klassischen quantitativ-empirischen EdTech-Tradition, die k |
|  | MedienPaed | `pflichtlektuere` | `scannen` → `ignorieren` |  ✗ | Da Sie diesen Artikel gemeinsam mit Leopold und Tanja Klepacki selbst verfasst haben und dieser bereits in Ihrer Publikationsliste erfasst ist, ist keine weitere Auseinandersetzung |
|  | merz | `lesenswert` | `scannen` = `scannen` |  | Die Rezension ist für die Diskursübersicht im medienpädagogischen Feld (merz) relevant, da sie die Rezeption traditionell-humanistischer Abgrenzungsargumente dokumentiert. Für die  |
|  | EPT | `scannen` | `lesenswert` = `lesenswert` |  | Der Text bietet essentielles Anregungspotenzial für das Projekt `cultural_resilience`, da er die leiblich-somatische Dimension der 'Rootedness' (Verwurzelung) mithilfe der Differen |
|  | EPT | `scannen` | `lesenswert` = `lesenswert` |  | Der Artikel bietet hohe konzeptionelle Reibungsflächen und produktives Anregungspotenzial für das aktive Projekt [cultural_resilience], da er die dortigen Kernmomente „Resourcefuln |
|  | EPT | `ignorieren` | `lesenswert` = `lesenswert` |  | Der Artikel bietet ein produktives philosophisches Kontrastprogramm zu Jörissens eigenen epistemologischen Analysen von generativer KI (z. B. in LEHKCH59), indem er die Grenze des  |
|  | EduTheory | `ignorieren` | `lesenswert` = `lesenswert` |  | Der Text bietet exzellente konzeptionelle Anschlüsse für das Verständnis von Influencer-Kulturen und mimetischem Lernen im Kontext postdigitaler Jugendkulturen und Medienbildung. |
|  | EduTheory | `ignorieren` | `scannen` = `scannen` |  | Der Beitrag verbleibt in einem stark individualistischen und normativ-humanistischen Paradigma der analytischen Philosophie; er vernachlässigt postdigitale, relationale oder materi |
|  | EPT | `ignorieren` | `lesenswert` = `lesenswert` |  | Der Artikel bietet ein exzellentes Anregungspotenzial für die Projekte 'cultural_resilience' und 'diaes_kubi': Die Verknüpfung von ökosophischen Rastern (Guattari) mit raumästhetis |
|  | REPCS | `scannen` | `lesenswert` = `lesenswert` |  | Der Artikel bietet exzellente Anregungspotenziale für das aktive Forschungsprojekt „Cultural Resilience“, da er phänomenologische bzw. affektive Dimensionen technologischer Krisen  |
|  | JAC | `scannen` | `lesenswert` = `lesenswert` |  | Der Text bietet hohes Anregungspotenzial für die Projekte DiäS-KuBi (digitale ästhetische Souveränität) und ComeArts sowie für die Arbeiten zum „Regime des Komputablen“, da heidari |
|  | JAE | `scannen` | `lesenswert` = `lesenswert` |  | Der Text bietet hervorragendes anregungstheoretisches Potenzial für das Projekt [cultural_resilience], da er mit Tagores Universitätsmodell eine nicht-westliche Perspektive auf die |
|  | JAE | `ignorieren` | `scannen` → `lesenswert` |  ✗ | Der Artikel bietet ein klares Anregungspotenzial für das Projekt *cultural_resilience*, da das Konzept der 'kinästhetischen Musikalität' als weltverbindende Praxis strukturell eng  |
|  | ArtsEdPolRev | `ignorieren` | `scannen` = `scannen` |  | Der Artikel ist für die Diskursübersicht zur musealen Vermittlung und Transformation in Krisenzeiten nützlich, bietet jedoch keine tiefergehenden theoretischen oder methodischen In |
|  | REPCS | `ignorieren` | `scannen` → `lesenswert` |  ✗ | Der Beitrag bietet trotz einer anderen theoretischen Tradition (US-amerikanische Critical Literacy vs. erziehungswissenschaftliche Digitalitäts- und Bildungstheorie) hohes Anregung |
|  | JAE | `ignorieren` | `lesenswert` = `lesenswert` |  | Der Artikel bietet über die leiblich-somatische Erfahrunsmethode und das Konzept des relationalen „erweiterten Selbst“ wertvolles Anregungspotenzial für das Projekt „Cultural Resil |
|  | JAE | `ignorieren` | `scannen` = `scannen` |  | Der Beitrag bewegt sich im Kernbereich ästhetischer und mimetischer Lerntheorien in der Musikpädagogik, verbleibt jedoch rein im Rahmen intersubjektiver, analoger Mensch-Mensch-Bez |