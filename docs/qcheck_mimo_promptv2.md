# MiMo Q-Check Round 2 — Prompt-Patches getestet

**Datum:** 2026-05-16T11:51:13.057265
**Test-Set:** 5 Mismatches + 3 Kontroll-Matches aus `qcheck_assessment.json`
**Patches:** 3 Ergänzungen am ASSESSMENT_OUTRO — siehe Abschnitt unten
**Resultat:** **2/5 Mismatches gefixt**, **2/3 Kontrollen stabil**
**Q-Check-Kosten:** $0.1221

## Ergebnistabelle

| #  | Art | Opus | MiMo v1 | MiMo v2 (patched) | Bewertung |
|---:|---|---|---|---|---|
| #3 | CONTROL | `lesenswert` | `lesenswert` | `lesenswert` | ✓ stable |
| #6 | CONTROL | `ignorieren` | `ignorieren` | `scannen` | ⚠ regressed |
| #10 | MISMATCH | `lesenswert` | `scannen` | `scannen` | ✗ still diverged |
| #11 | CONTROL | `scannen` | `scannen` | `scannen` | ✓ stable |
| #22 | MISMATCH | `lesenswert` | `scannen` | `scannen` | ✗ still diverged |
| #25 | MISMATCH | `ignorieren` | `lesenswert` | `scannen` | ✗ still diverged |
| #44 | MISMATCH | `lesenswert` | `scannen` | `lesenswert` | ✓ fixed |
| #48 | MISMATCH | `lesenswert` | `scannen` | `lesenswert` | ✓ fixed |

## Pro Artikel — Detail

### #3 — MedienPaed (Opus+MiMo = lesenswert)
- _article_id_: `2c44a6fbe0a3524d43935e4842d48d6e`
- _Citation-Hits_: high=0, med=0
- _MiMo v2 cost_: $0.0379 · cache=5.9% · 41.87s

**Opus:** `lesenswert`
**MiMo v1 (alter Prompt):** `lesenswert`
**MiMo v2 (patched):** `lesenswert` — ✓ stable

**v2 Kernthese:** Waldecker kritisiert das Konzept der (digitalen/Daten-)Souveränität anhand qualitativer Studien zur Smart-Speaker-Nutzung. Er verbindet eine praxistheoretische Perspektive auf Daten mit einer kritisch-theoretischen Perspektive (Adorno/Horkheimer), um zu zeigen, dass Souveränitätsversprechen die eigentlichen Machtverhältnisse der Dateninfrastrukturen verdecken und dass die Nutzungspraxis selbst diese Souveränitätsannahme unterläuft.
**v2 Begründung:** Der Artikel bearbeitet den zentralen Begriff „Datensouveränität/digitale Souveränität" substantiell und kritisch — genau jenen Begriff, der im Projekt DiäS-KuBi als forschungsleitend verwendet wird. Die konzeptionelle Kritik am Souveränitätsbegriff selbst (nicht nur an fehlender Implementation) ist für die eigene Begriffsarbeit hochrelevant und produktiv irritierend: Jörissens Konzept der „digital-ästhetischen Souveränität" müsste sich positionieren gegenüber dem Einwand, dass Souveränität als solche ein problematisches Versprechen ist.

---

### #6 — MedienPaed (Opus+MiMo = ignorieren)
- _article_id_: `063f00c2fd4ed025da945015a759cb92`
- _Citation-Hits_: high=0, med=0
- _MiMo v2 cost_: $0.0114 · cache=96.9% · 32.89s

**Opus:** `ignorieren`
**MiMo v1 (alter Prompt):** `ignorieren`
**MiMo v2 (patched):** `scannen` — ⚠ regressed

**v2 Kernthese:** Der Artikel untersucht einen auf experiential learning basierenden Ansatz mit sphärischem Video-VR (EL-SVVR) zur Kunstbetrachtung in einem quasi-experimentellen Design mit 45 Studierenden. Die zentrale These ist, dass VR-basiertes experiential learning im Vergleich zu konventionellem Unterricht Lernleistung, Motivation, Selbstwirksamkeit, kritisches Denken und digitale Malperformance verbessert.
**v2 Begründung:** Der Artikel ist als Diskursindikator für MetaKuBi notierenswert (instrumentelle EdTech-Forschung zu Kunstbildung), bietet aber keinerlei Anregungspotenzial für Jörissens Forschung: Er operiert in einem fundamental anderen Paradigma, das genau jene solutionistische Werkzeuglogik verkörpert, die Jörissens kritisch-ästhetische und bildungstheoretische Perspektive gerade problematisiert.

---

### #10 — merz / Friedrich-Rezension (Opus=lesenswert)
- _article_id_: `6a8feec999224400b1ef801b200ad3ac`
- _Citation-Hits_: high=0, med=0
- _MiMo v2 cost_: $0.0105 · cache=97.5% · 25.55s

**Opus:** `lesenswert`
**MiMo v1 (alter Prompt):** `scannen`
**MiMo v2 (patched):** `scannen` — ✗ still diverged

**v2 Kernthese:** Der Text ist eine Rezension des Buches "Degenerierte Vernunft" von Jörg Phil Friedrich (2023), das die These vertritt, KI und natürliche menschliche Vernunft seien grundsätzlich nicht vergleichbar: KI operiere auf Basis von Algorithmen und Datenverarbeitung ohne Bewusstsein, Intuition oder ästhetisch-moralische Fähigkeiten, während menschliches Denken durch Besinnung, Reflexion und Sinnsuche gekennzeichnet sei. Die Rezension lobt den verständlichen Schreibstil, bemerkt aber, dass die Kapitel teils unverbunden nebeneinanderstehen.
**v2 Begründung:** Das rezensierte Buch behandelt KI vs. menschliche Vernunft aus einer philosophischen Perspektive, die mit Jörissens relational-posthumanistischem Rahmen (agential realism, verteilte Agency, Wahrnehmungskrise) nicht kompatibel ist. Die Diskursposition ist für Übersicht relevant, aber da es sich nur um eine kurze Rezension ohne eigenständigen analytischen Mehrwert handelt und das Buch selbst keine bildungs- oder medientheoretische Argumentation entfaltet, fehlt das konkrete Anregungspotenzial für laufende Projekte.

---

### #11 — MedienPaed (Opus+MiMo = scannen)
- _article_id_: `f035990cc4e302bc50e22e0e1feed55c`
- _Citation-Hits_: high=0, med=0
- _MiMo v2 cost_: $0.0128 · cache=95.4% · 35.22s

**Opus:** `scannen`
**MiMo v1 (alter Prompt):** `scannen`
**MiMo v2 (patched):** `scannen` — ✓ stable

**v2 Kernthese:** Der Beitrag von Mehlan und Holten zeichnet die definitorischen Wendungen des Medienkompetenzbegriffs im medienpädagogischen Diskurs nach und schlägt ein eigenes Modell vor, das Kompetenz und Performanz (in Anlehnung an Giddens' Dualität von Struktur) als sich wechselseitig bedingende Dimensionen fasst. Ergänzend wird zwischen Wirklichkeitskonstruktionen erster und zweiter Ordnung unterschieden, um implizite Denkweisen über Kompetenz sichtbar zu machen. Das Ziel ist, den Kompetenzbegriff zu rehabilitieren, ohne ihn auf einzelne medienbezogene Teilkompetenzen zu reduzieren.
**v2 Begründung:** Der Beitrag bewegt sich im selben diskursiven Feld wie Jörissens Arbeiten zu Medienbildung und berührt den Kompetenz-Bildungs-Diskurs, den Jörissen/Bettinger explizit als Gegenposition zu ihrer relationalen Medienbildung konzipieren. Der Giddens'sche Dualitätsvorschlag ist diskursrelevant, aber da Jörissen den Kompetenzbegriff nicht rehabilitieren, sondern durch ein relationales Bildungskonzept ersetzen will, fehlt der spezifische Anregungswert für die eigene Positionierung. Eine Vertiefung in die Wirklichkeitskonstruktionen-zweiter-Ordnung-These wäre nötig, um zu klären, ob sie über den Gidde

---

### #22 — BJET / Bearman+Ajjawi black-box (Opus=lesenswert, User: hochrelevant)
- _article_id_: `332c5b6047a06ea69481233edf6b3e84`
- _Citation-Hits_: high=0, med=0
- _MiMo v2 cost_: $0.0127 · cache=96.8% · 35.89s

**Opus:** `lesenswert`
**MiMo v1 (alter Prompt):** `scannen`
**MiMo v2 (patched):** `scannen` — ✗ still diverged

**v2 Kernthese:** Der Artikel definiert KI über eine relationale Epistemologie als Black Box (nicht-tracebare algorithmische Urteile) und argumentiert für eine Pädagogik, die nicht versucht, die Black Box zu öffnen, sondern den Umgang mit Opazität, Ambiguität und Teilinformation zu lehren. Zwei konkrete pädagogische Ansätze werden vorgeschlagen: die Orientierung an Qualitätsstandards als soziale Regulierungsrahmen und die Ermöglichung bedeutungsvoller Interaktionen mit KI-Systemen als soziotechnischen Ensembles.
**v2 Begründung:** Die Black-Box-Thematik ist für Jörissens Wahrnehmungskrisen- und Opazitätsarbeit (LEHKCH59, M8RZJRHN) konzeptionell anschlussfähig, und die Ablehnung von Explainable AI als Lösungspfad resoniert mit Jörissens Kritik am Solutionismus. Der Artikel verbleibt jedoch in einem rein pragmatischen Hochschuldidaktik-Rahmen ohne ästhetisch-bildungstheoretische, kulturkritische oder posthumanistische Fundierung — die drei Dimensionen, die für Jörissens KI-Arbeit zentral sind. Eine relationale Epistemologie ohne Bezug zu Barad, Rancière oder ästhetischer Bildung bleibt hier oberflächlich. Für Diskursübers

---

### #25 — EERJ / Zembylas anti-complicity (Opus=ignorieren, User: ignorieren)
- _article_id_: `7bf4e3fc9b71aebf70a34428c0c94806`
- _Citation-Hits_: high=0, med=0
- _MiMo v2 cost_: $0.0115 · cache=96.9% · 28.46s

**Opus:** `ignorieren`
**MiMo v1 (alter Prompt):** `lesenswert`
**MiMo v2 (patched):** `scannen` — ✗ still diverged

**v2 Kernthese:** Zembylas entwickelt den Begriff einer „Anti-Complicity Pedagogy", die auf Affect Theory und politischer Theorie (Butler, Ahmed, Mills) aufbaut. Er argumentiert, dass Pädagogik Komplizenschaft nicht binär (unschuldig/schuldig), sondern als relational-ambivalentes Gefüge behandeln müsse, um Lernenden einen Umgang mit politischer und struktureller Gewalt zu ermöglichen, ohne in die Falle einfacher Unschuldsnarrative zu verfallen.
**v2 Begründung:** Der Text arbeitet innerhalb der Beobachtungsfelder (pädagogische Theorie, Strukturelle Gewalt, Hegemonie, Widerstand) und referenziert Autor:innen, die auch in Jörissens Publikationen vorkommen (Butler, Ahmed). Die theoretische Rahmung ist jedoch primär politisch-affekttheoretisch (Affect Theory + Critical Race Theory) und berührt nicht die ästhetisch-bildungstheoretischen Dimensionen, die für Jörissens Cultural-Resilience-Programm und die aktiven Projekte zentral sind. Konzeptuelle Anschlüsse an die eigene Arbeit (z.B. Differenz zwischen politischem Widerstand und ästhetischem Dissens) wären 

---

### #44 — MedienPaed / de Witt+Leineweber (Opus=lesenswert, Zitation-Hit, User: must-read)
- _article_id_: `75641a28b53daef73187d6754027e3ac`
- _Citation-Hits_: high=1, med=0
- _MiMo v2 cost_: $0.0143 · cache=93.7% · 45.44s

**Opus:** `lesenswert`
**MiMo v1 (alter Prompt):** `scannen`
**MiMo v2 (patched):** `lesenswert` — ✓ fixed

**v2 Kernthese:** Der Beitrag von de Witt und Leineweber (2020) behandelt das Verhältnis von menschlichem Nichtwissen und Künstlicher Intelligenz. Die These lautet, dass Nichtwissen ein zentrales Unterscheidungsmerkmal zwischen Mensch und Maschine darstellt und den Menschen zu Problemlösungen und Urteilen in unsicheren Situationen befähigt. Medienpädagogik wird als Aufklärungs- und Gestaltungsinstanz positioniert, die zwischen dem individuell/sozial Kontingenten und den materiell-technischen Umwelten vermittelt.
**v2 Begründung:** Regel A greift: Der Beitrag zitiert Jörissen/Marotzki 2009 (Medienbildung – Eine Einführung) explizit und positioniert sich im selben Diskursfeld. Zudem behandelt er KI und Nichtwissen aus einer systemtheoretisch-pragmatistischen Perspektive, die für das AI4ArtsEd-Projekt (kritische KI-Perspektive) sowie für die eigene Wahrnehmungskrise-Argumentation als produktive Kontrastfolie dienen kann.

---

### #48 — ZfPaed / Höhne+Karcher+Voss Wolkige Verheißungen (Opus=lesenswert)
- _article_id_: `338efe035846be4b48363278b62d3bdc`
- _Citation-Hits_: high=0, med=0
- _MiMo v2 cost_: $0.0110 · cache=98.9% · 28.0s

**Opus:** `lesenswert`
**MiMo v1 (alter Prompt):** `scannen`
**MiMo v2 (patched):** `lesenswert` — ✓ fixed

**v2 Kernthese:** Der Beitrag analysiert kritisch die digitale Schul-Cloud als Infrastruktur der Transformation von Bildungsmedien und bildungspolitischer Steuerung. Zwei Thesen stehen im Zentrum: (1) die Verschmelzung von Lernen und Konsumieren in cloudgesteuerten Lernpraktiken und (2) die fortschreitende Kontrolle von Lernprozessen durch Learning Analytics mit dem Verspruch der Vorhersagbarkeit von Schüler*innenleistung anhand umfassender Datenproduktion.
**v2 Begründung:** Der Artikel behandelt mit Datafizierung von Lernprozessen, Educational Governance und der Transformation schulischer Infrastrukturen durch Cloud-Plattformen zentrale Themen, die Jörissen in seinen Arbeiten zu Digitalität in der Schulkultur (BXCLZ5M7), zur erziehungstheoretischen Analyse von Datafizierung und "augmented educational decision making" (62A5VC7E) sowie zur Invisibilisierung medialer Vollzüge durch Dashboards verhandelt. Die kritische Perspektive auf Learning Analytics und die Verschmelzung von Lernen/Konsumieren bieten Anregungspotenzial für die eigene Positionierung insbesondere i

---

## Eingesetzte Patches (Ergänzung zum ASSESSMENT_OUTRO)

```
=== ZUSÄTZLICHE REGELN (MiMo-Kalibrierung) ===

**Regel A — Zitations-Trigger (hartes Inklusionskriterium):**
Wenn der Citation-Tracker im User-Prompt einen "Sicheren Treffer" oder "Wahrscheinlichen
Treffer" meldet, ist das Verdict MINDESTENS `lesenswert` — unabhängig von theoretischer
Tradition oder thematischer Distanz. Die Begründung MUSS die Zitation explizit aufgreifen
und eine Hypothese formulieren, WIE die Autoren die zitierte Arbeit nutzen (affirmativ,
kritisch, modifizierend, als Grundlage, als Kontrast).

**Regel B — Anschluss auch bei pragmatischer Übersetzung:**
Auch wenn das theoretische Vokabular fremd ist, gilt: wenn der Text einen SCHLÜSSELBEGRIFF
der eigenen Arbeit (Bildung, Datafizierung, Medienbildung, Resilienz, ästhetische Praxis,
agentieller Realismus, Wahrnehmungskrise, Black-Box, Postdigitalität, Subjektivierung, …)
substantiell verhandelt — affirmativ, kritisch oder pragmatisch übersetzend — ist er
`lesenswert`. Eine didaktische/pragmatische Lesart einer der eigenen Theoriearbeiten ist
ANLASS zur Lektüre, KEIN Abwertungsgrund. "Andere theoretische Tradition" ist kein
Ausschlussgrund, wenn die zentralen Begriffe geteilt werden.

**Regel C — Cultural Resilience negativ abgrenzen:**
"Cultural Resilience" im Jörissen-Forschungsprogramm ist spezifisch
ÄSTHETISCH-BILDUNGSTHEORETISCH fundiert (Vergegenständlichung, Resonanz, ästhetische
Welterzeugung, kulturelle Praxis als Resilienzform). Es ist NICHT identisch mit:
- politischer Resistance / Widerstandspädagogik (Ahmed/Butler/Zembylas-Stil)
- postkolonialer Komplizenschafts-Pädagogik
- affekttheoretischer Mobilisierung als Selbstzweck
- Resilienz im psychologisch-individuellen Sinn

Texte, die diese politisch-affektiven oder psychologischen Konzepte ohne ästhetisch-
bildungstheoretischen Anschluss verhandeln, sind NICHT automatisch `lesenswert` für
dieses Programm. Eine reine Keyword-Übereinstimmung ("resistance", "resilience") genügt
NICHT.
```