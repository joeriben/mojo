# Q-Check Assessment — Mistral Large vs vorhandene Opus-Datensätze

**Datum:** 2026-05-23T14:36:19.087455
**Stichprobe:** 50 Artikel aus `scripts/qcheck_assessment_ids.json` (stratifiziert)
**Mistral-Konfig:** `mistral-large-latest` nativ via api.mistral.ai (EU/DSGVO), `tool_choice='auto'`, implicit cache

## TL;DR

- **Verdict-Match: 19/50 = 38.0 %**
- **Lesenswert-Recall: 18/20 = 90.0 %** _(kritisch — MiMo war hier bei 78 %)_
- **Avg Cache-Hit:** 26.5 % (implicit; rein server-side bei Mistral)
- **Kosten gesamt:** Mistral $0.7977 · Opus orig $1.4002 · Faktor ~1/1.8
- **Avg/Call Mistral:** $0.0160

## Verdict-Konfusionsmatrix

| Opus → / Mistral ↓ | ignorieren | lesenswert | scannen |
|---|---|---|---|
| **ignorieren** | 0 | 0 | 0 |
| **lesenswert** | 4 | 18 | 14 |
| **scannen** | 11 | 2 | 1 |

## Mismatches (kritische Lektüre)

### #1 `PCS` — Towards a school-based ‘critical data education’
_article_id_: `768f89ebd1e7b5cc9fa66b353df343ba`

**Opus** — `scannen`
  *Kernthese:* (C-Tier: nur Screening, kein Agent)

**Mistral** — `lesenswert`
  *Kernthese:* Der Artikel adressiert die zunehmende Datafizierung der Gesellschaft und deren Implikationen für Schulen, insbesondere die Notwendigkeit einer ‚critical data education‘. Die Autor*innen berichten von drei Forschungsprojekten, die darauf abzielen, Jugendlichen ein kritisches Verständnis von digitalen Daten, deren Verarbeitung sowie den damit verbundenen ökonomischen und überwachungskapitalistischen Strukturen zu vermitteln. Die zentralen Lernziele umfassen: die Materialisierung von Daten und Datenverarbeitungsprozessen, das Verständnis der Implikationen dieser Prozesse sowie die Erprobung von S

---

### #4 `MedienPaed` — Big Data als datenbasierte Programmierung
_article_id_: `eb0cc5c0f8dd9472cbd170b7d628a711`

**Opus** — `lesenswert`
  *Kernthese:* Der Artikel analysiert datenbasierte Programmierung als Technologie aus der Perspektive der relationalen Medienpädagogik. Er untersucht die medienpädagogische Relevanz von Big Data und datenbasierten Programmierungstechnologien, indem er die Technologie selbst (statt nur gesellschaftlicher Entwicklungen oder Medieninhalte) in den Blick nimmt und damit einen technologiefokussierten Ansatz innerhalb der relationalen Medienpädagogik entwickelt.

**Mistral** — `scannen`
  *Kernthese:* Der Beitrag untersucht das Phänomen der datenbasierten Programmierung (Big Data und Machine Learning) aus einer medienpädagogischen Perspektive, die sich als „relationale Medienpädagogik“ versteht. Zentral ist die These, dass datenbasierte Programmierung nicht nur als technologisches Werkzeug, sondern als konstitutive Technologie moderner Medien verstanden werden muss, die gesellschaftliche Strukturen, Subjektivationsprozesse und pädagogische Praktiken prägt. Swertz analysiert diese Technologie als Teil eines medienpädagogischen Dispositivs, das über die bloße Anwendung von Algorithmen hinausg

---

### #6 `BJET` — Promoting students' artwork appreciation: An experiential learning‐based virtual reality approach
_article_id_: `063f00c2fd4ed025da945015a759cb92`

**Opus** — `ignorieren`
  *Kernthese:* (Screening: ignorieren)

**Mistral** — `scannen`
  *Kernthese:* Der Artikel untersucht die Wirksamkeit eines auf experiential learning basierenden Virtual-Reality-Ansatzes (EL-SVVR) zur Förderung der Kunstwerkanerkennung und -wertschätzung bei Studierenden. Die zentrale These ist, dass sphärische Video-basierte Virtual Reality (SVVR) im Vergleich zu herkömmlichen Lehrmethoden (z. B. Vorträge mit Präsentationen oder Videos) nicht nur die Lernerfolge, Motivation und Selbstwirksamkeit der Studierenden steigert, sondern auch deren kritisches Denken und Fähigkeiten in der digitalen Bildgestaltung verbessert. Der Ansatz nutzt die immersive Erfahrung, um Studiere

---

### #7 `BDS` — Data artivism and feminicide
_article_id_: `87f44a03f395a5e2ddbcf1307becf491`

**Opus** — `scannen`
  *Kernthese:* Der Artikel führt das Konzept "Data Artivism" ein – künstlerisch-handwerkliche Arbeiten, die Daten visualisieren und als Widerstandsform mobilisieren, um soziale Probleme (hier Femizid) sichtbar zu machen und anzuprangern. Anhand von drei Fallbeispielen plädiert er für eine vertiefte Auseinandersetzung der kritischen Daten 
- und Visualisierungsstudien mit Kunst und für eine gemeinsame Sprache mit lateinamerikanischen Aktivist*innen und Künstler*innen.

**Mistral** — `lesenswert`
  *Kernthese:* Der Beitrag führt den Begriff des „Data Artivism“ ein, um künstlerisch-aktivistische Praktiken zu beschreiben, die Daten und visuelle Kunst kombinieren, um soziale Probleme – insbesondere Feminizide – sichtbar zu machen und zu politisieren. Die Autor*innen argumentieren, dass solche Praktiken über konventionelle Datenvisualisierungen hinausgehen und alternative Wege eröffnen, Daten als Mittel des Widerstands und der advocacy zu mobilisieren. Am Beispiel von drei Projekten aus Lateinamerika wird gezeigt, wie Kunst, Handwerk und Datenanalyse ineinandergreifen, um feministische Anliegen zu stärke

---

### #9 `EPT` — Michel Serres: Divergences
_article_id_: `72da8be9352e51272ef3a73d606dc8b3`

**Opus** — `scannen`
  *Kernthese:* Der Artikel untersucht Michel Serres' Philosophie als Abkehr von der germanischen Bildungstradition (als egozentrischer, apolitischer Selbstkultivierung) und als Hinwendung zu einem ökologischen, ökozentrischen Denken im Sinne von Gregory Batesons "ecology of mind". Serres integriert auf ökologische Weise Poesie, Wissenschaft, Kunst, Ökologie und Politik, um philosophische Fragen zu stellen. Sein Stil und Inhalt durchbrechen die Grenzen traditioneller Philosophie und eröffnen ein neues Paradigma.

**Mistral** — `lesenswert`
  *Kernthese:* Der Artikel untersucht das Werk des französischen Philosophen Michel Serres und dessen Abweichung von der traditionellen westlichen Philosophie, insbesondere von der germanischen Bildungstradition des 18. und 19. Jahrhunderts. Serres wird als eco-zentrischer Denker dargestellt, der Poesie, Wissenschaft, Kunst, Ökologie und Politik integriert, um philosophische Fragen zu stellen. Sein Werk wird mit der Figur des Pierrot Lunaire assoziiert, der als Symbol für den Bruch mit traditionellen Grenzen und die Eröffnung eines neuen philosophischen Paradigmas steht.

---

### #10 `merz` — Friedrich, Jörg Phil (2023). Degenerierte Vernunft. Künstliche Intelligenz und die Natur des Denkens. München: Claudius. 125 S., 20,00 €
_article_id_: `6a8feec999224400b1ef801b200ad3ac`

**Opus** — `lesenswert`
  *Kernthese:* Rezension des Buches "Degenerierte Vernunft" von Jörg Phil Friedrich, das eine philosophische Abgrenzung von KI und menschlicher Vernunft vornimmt. KI wird als algorithmische, sinn- und bewusstseinslose Datenverarbeitung charakterisiert, die grundsätzlich von menschlichem Denken (Besinnung, Reflexion, Sinnsuche) verschieden sei. Die Unterscheidung soll helfen, mit Ängsten vor KI-Ersetzung umzugehen.

**Mistral** — `scannen`
  *Kernthese:* Jörg Phil Friedrichs Buch »Degenerierte Vernunft. Künstliche Intelligenz und die Natur des Denkens« hinterfragt den Begriff der KI und grenzt ihn von der natürlichen menschlichen Vernunft ab. Der Autor argumentiert, dass KI-Systeme keine Bewusstseins-, Intuitions- oder Sinnstiftungsfähigkeiten besitzen, sondern auf algorithmischen und datenverarbeitenden Methoden basieren. Ziel ist es, die Unterschiede zwischen menschlicher Vernunft – die durch Besinnung, Reflexion und Sinnsuche gekennzeichnet ist – und KI herauszuarbeiten, um deren scheinbare Überlegenheit einzuordnen und den Umgang mit diese

---

### #11 `MedienPaed` — Die Dualität von Kompetenz in tiefgreifend mediatisierten Welten
_article_id_: `f035990cc4e302bc50e22e0e1feed55c`

**Opus** — `scannen`
  *Kernthese:* Der Artikel rekonzeptualisiert "Medienkompetenz" in tiefgreifend mediatisierten Welten, indem er die definitorischen Wendungen des Begriffs im medienpädagogischen Diskurs nachzeichnet und schließlich ein eigenes Verständnis vorlegt, das Kompetenz und Performanz nach Giddens als zwei sich gegenseitig bedingende Dimensionen unterscheidet und zusätzlich zwischen Wirklichkeitskonstruktionen erster und zweiter Ordnung differenziert.

**Mistral** — `lesenswert`
  *Kernthese:* Der Beitrag adressiert die Kontroversen um den Begriff der Medienkompetenz in tiefgreifend mediatisierten Welten und schlägt eine Neukonzeption vor. Die Autor*innen zeichnen die historischen und definitorischen Wendungen des Medienkompetenzbegriffs nach und kritisieren dessen Reduktion auf einzelne, medienbezogene Fertigkeiten. Stattdessen wird ein duales Verständnis von Kompetenz und Performanz im Anschluss an Anthony Giddens' Theorie der Strukturierung entwickelt, das beide Dimensionen als sich gegenseitig bedingend und reproduzierend fasst. Zudem wird zwischen Wirklichkeitskonstruktionen er

---

### #12 `BJET` — Youths' relationship with culture: Tracing sixth graders' learning through designing culturally centred multimedia projects
_article_id_: `90652e050b8e67a8a4e0d44bbef46f4e`

**Opus** — `scannen`
  *Kernthese:* Der Artikel untersucht, wie Sechstklässler*innen durch das Erstellen kulturspezifischer Multimedia-Projekte (Remixing) ihre Beziehung zu Kultur entwickeln und darstellen. Anhand einer Fallstudie mit 36 Projekten von 12 Schüler*innen zeigt er drei Formen der Symbolisierung auf, die vielfältige, reziproke Beziehungen zur eigenen und zu anderen Kulturen offenbaren. Die Arbeit plädiert dafür, die festgefahrenen Erwartungen der Dominanzkultur in formalen Lernumgebungen zu überwinden und stattdessen die Wissensbestände und Erfahrungen der Jugendlichen durch multimediales Remixen einzuladen.

**Mistral** — `lesenswert`
  *Kernthese:* Der Artikel untersucht, wie sechste Klassen durch die Gestaltung kulturell zentrierter Multimedia-Projekte ihre Beziehung zu Kultur entwickeln. Die Autor*innen argumentieren, dass formale Lernumgebungen oft von dominanten kulturellen Normen geprägt sind und dadurch die vielfältigen Zukunftsperspektiven von Jugendlichen einschränken. Am Beispiel von zwölf Schüler*innen wird gezeigt, wie diese durch das Remixen von Multimedia-Ressourcen ihre kulturellen Beziehungen symbolisch ausdrücken und weiterentwickeln. Dabei werden drei Formen der Symbolisierung identifiziert, die auf vielfältige und wechs

---

### #15 `PCS` — Neoliberalism and the social imaginary: interpreting study abroad policy in Japanese higher education
_article_id_: `85a2cee01c0d403c3e83dedf6fc8f911`

**Opus** — `ignorieren`
  *Kernthese:* (Screening: ignorieren)

**Mistral** — `scannen`
  *Kernthese:* Der Artikel untersucht die neoliberalen und marktgetriebenen Diskurse, die die Internationalisierung und die Förderung von Auslandsstudienprogrammen (Study Abroad, SA) in der japanischen Hochschulbildung prägen. Im Zentrum steht die Analyse, wie der Staat durch die Propagierung von Englisch als dominanter Lingua franca und die Konstruktion eines ,globalen Humankapitals‘ soziale Imaginarien schafft, die individuelle Mobilität als ökonomische Notwendigkeit und soziale Pflicht rahmen. Dabei werden essentialistische Kulturverständnisse reproduziert, und die Erwartungen an Rückkehrende bleiben vage

---

### #16 `ZfE` — Individuelle Schüler*innenprofile des situationalen und dispositionalen Interesses und ihre Bedeutung für die Wahrnehmung der Unterrichtsqualität im Fach Mathem
_article_id_: `a1d1395d112b8315a528a3a46f1dd7a7`

**Opus** — `ignorieren`
  *Kernthese:* (Screening: ignorieren)

**Mistral** — `scannen`
  *Kernthese:* Der Artikel untersucht die Bedeutung individueller Profile des situationalen und dispositionalen Interesses von Schüler*innen der 8. Jahrgangsstufe für ihre Wahrnehmung der Unterrichtsqualität im Fach Mathematik. Mit einem personenzentrierten Ansatz werden vier charakteristische Profile identifiziert: konsistent hohes oder niedriges Interesse sowie Mischprofile mit hohem situationalem bei niedrigem dispositionalem Interesse (und umgekehrt). Die Studie zeigt, dass Schüler*innen mit konsistent positiven motivational-affektiven Voraussetzungen oder hohem situationalem Interesse die Unterrichtsqua

---

### #18 `BDS` — Generating reality and silencing debate: Synthetic data as discursive device
_article_id_: `050f065cb58259d9f55f40caa420ca8d`

**Opus** — `scannen`
  *Kernthese:* Der Artikel analysiert synthetische Daten nicht nur als technisches, sondern als diskursives und politisches Phänomen. Die Autoren kritisieren, dass synthetische Daten oft als "technical solutionism" präsentiert werden, der ethisch-politische Debatten um KI-Bias, Privatsphäre und Plattformökonomie zu schließen versucht, statt sie zu führen. Sie zeigen, wie synthetische Daten selbst politisch sind und als diskursive Geräte wirken.

**Mistral** — `lesenswert`
  *Kernthese:* Der Artikel untersucht synthetische Daten als technisches und diskursives Phänomen im Kontext der KI-Entwicklung. Die Autor*innen argumentieren, dass synthetische Daten nicht nur als Lösung für ethische Probleme wie algorithmischen Bias oder Datenschutz (Privacy) vermarktet werden, sondern selbst politische und diskursive Effekte entfalten, indem sie ethisch-politische Debatten über KI ‚schließen‘ und damit zum Schweigen bringen. Synthetische Daten werden dabei als Teil eines technologischen Solutionismus analysiert, der soziale Probleme durch technische Mittel zu lösen verspricht, ohne deren 

---

### #19 `EPT` — The smiling philosopher: Emotional labor, gender, and harassment in conference spaces
_article_id_: `565369f1d279ba6bb15958d2774979f5`

**Opus** — `ignorieren`
  *Kernthese:* (Screening: ignorieren)

**Mistral** — `scannen`
  *Kernthese:* Der Artikel untersucht aus philosophischer Perspektive, wie Frauen in akademischen Konferenzumgebungen ungleiche Bedingungen erfahren, insbesondere im Hinblick auf emotionale Arbeit, Geschlechterrollen und Belästigung. Zentral wird die These vertreten, dass Konferenzen als soziale Räume von strukturellen Ungleichheiten durchzogen sind, die sich in emotionaler Arbeit (nach Arlie Hochschild) und affektiven Dynamiken (nach Sara Ahmed) manifestieren. Frauen werden demnach systematisch in Rollen gedrängt, die emotionale Managementleistungen erfordern, während gleichzeitig ihre fachliche Autorität i

---

### #21 `ZfPaed` — What is the Relationship Between Knowledge in Mathematics and Knowledge in Economics?
_article_id_: `b5df9c7e962cbf61b3e99f5e0d085318`

**Opus** — `ignorieren`
  *Kernthese:* (Screening: ignorieren)

**Mistral** — `scannen`
  *Kernthese:* Der Artikel untersucht die Zusammenhänge zwischen fachlichem Wissen (CK) und fachdidaktischem Wissen (PCK) bei Lehrkräften, die sowohl in Mathematik als auch in Wirtschaftswissenschaften ausgebildet werden oder unterrichten. Die zentrale These ist, dass尽管 die Wissensstrukturen fachspezifisch organisiert sind, fachliches Wissen in Mathematik auch mit fachdidaktischem Wissen in Wirtschaftswissenschaften korreliert und potenziell förderlich für dessen Vermittlung sein könnte.

---

### #23 `PDSE` — Stressing Out the ‘Damsel in Distress’: Intersectional Shifts in Women’s Representation in Video Games
_article_id_: `2b060f4a6c3ed89a76d9ee24916d64b7`

**Opus** — `scannen`
  *Kernthese:* Der Artikel untersucht die sich wandelnde Repräsentation von Frauen in Videospielen durch eine postdigitale feministische Linse. Er zeigt, dass alltägliche Aushandlungen von Misogynie im kompetitiven Spiel durch die infrastrukturelle Gestaltung postdigitaler Plattformen bedingt sind, nicht nur durch textuelle Repräsentation. Empirisch wird intersectionelles Self-Positioning von Spielerinnen als prägend für die Rezeption weiblicher Avatare herausgearbeitet. Die Studie argumentiert, dass Repräsentation, digitale Infrastrukturen und Communities/Policy eine Triade bilden, die bestehende Machtstruk

**Mistral** — `lesenswert`
  *Kernthese:* Der Artikel untersucht die sich wandelnde Repräsentation von Frauen in Videospielen unter intersectionellen Gesichtspunkten. Anhand qualitativer Interviews mit 19 Teilnehmenden analysiert die Studie, wie traditionelle Geschlechterklischees wie die ‚Damsel in Distress‘ fortbestehen, gleichzeitig aber komplexere weibliche Protagonistinnen an Bedeutung gewinnen. Die Autor*innen verorten diese Entwicklungen in postdigitalen feministischen Rahmenwerken, die zeigen, wie offline bestehende Vorurteile in digitale Räume übertragen werden und dort sowohl misogyne Strukturen verstärken als auch Widerstan

---

### #24 `EthicsEd` — ‘Equipping students with an ethical compass.’ What does it mean, and what does it imply?
_article_id_: `392a1473ce0c10a0ae59332160bd1529`

**Opus** — `ignorieren`
  *Kernthese:* (Screening: ignorieren)

**Mistral** — `scannen`
  *Kernthese:* Der Artikel untersucht die Metapher des „ethischen Kompasses“ als Leitbild für die Ausbildung von Professionellen, insbesondere an niederländischen Hochschulen für angewandte Wissenschaften (UAS). Die Autor*innen identifizieren drei Interpretationscluster des Begriffs: den Inhalt (z. B. Werte, Tugenden, Prinzipien), die Form (z. B. innere Haltung, Reflexionsfähigkeit, Intuition) und die Nutzung (z. B. Orientierungshilfe in Entscheidungssituationen). Auf dieser Grundlage wird evaluiert, welche Art von ethischem Kompass sinnvoll in der Ausbildung vermittelt werden kann und welche Grenzen dabei b

---

### #25 `EERJ` — Educating for anti-complicity: A pedagogical response to political and structural violence
_article_id_: `7bf4e3fc9b71aebf70a34428c0c94806`

**Opus** — `ignorieren`
  *Kernthese:* Der Artikel von Michalinos Zembylas behandelt die pädagogische Herausforderung der Komplizenschaft in politischer und struktureller Gewalt. Er argumentiert für die Entwicklung von Anti-Komplizenschafts-Pädagogiken, die die Komplexität „geteilter Komplizenschaften“ anerkennen und durch affekttheoretische Ansätze ein nicht-binäres Verständnis von Komplizenschaft und Widerstand ermöglichen.

**Mistral** — `lesenswert`
  *Kernthese:* Der Artikel adressiert die pädagogische Herausforderung, Komplizenschaft in politischen und strukturellen Gewaltverhältnissen zu thematisieren und zu überwinden. Zentral ist die Frage, wie eine Pädagogik der „Anti-Komplizenschaft“ (anti-complicity) gestaltet werden kann, wenn Lehrende, Lernende und ihre Gemeinschaften bereits in Institutionen, Normen und Praktiken verstrickt sind, die politische oder strukturelle Gewalt reproduzieren – sei es als Täter*innen, Kollaborateur*innen oder Zuschauende. Der Beitrag argumentiert, dass eine nicht-binäre Perspektive auf Komplizenschaft und Widerstand, d

---

### #26 `EduTheory` — Signature of Attention: Historical Ambiguities and Elisions in Contemporary Psychological Framings of Attending
_article_id_: `35296fb7ecff14df6afa037b1ed68e67`

**Opus** — `scannen`
  *Kernthese:* Der Artikel untersucht die historische Genealogie des Aufmerksamkeitsbegriffs und zeigt, wie gegenwärtige Diskurse über eine "Aufmerksamkeitskrise" im Kontext von Digitalisierung, Medien und KI auf lange vernachlässigte spirituelle Signaturen zurückzuführen sind. Die Autoren rekonstruieren, wie das europäisch-christliche Mönchtum Praktiken zur Disziplinierung von Aufmerksamkeit entwickelte, die mit Prozessen des Othering und der Kritik verbunden waren, und argumentieren, dass heutige pädagogische Ansätze zur "Aufmerksamkeitskrise" noch immer von diesen spirituellen Signaturen, binären Logiken 

**Mistral** — `lesenswert`
  *Kernthese:* Der Artikel untersucht die historischen Wurzeln und Auslassungen (Elisionen) in zeitgenössischen psychologischen und pädagogischen Diskursen über Aufmerksamkeit, insbesondere im Kontext von Digitalisierung, Medienvielfalt und generativer KI. Die Autor*innen argumentieren, dass aktuelle Debatten über die sogenannte „Aufmerksamkeitskrise“ – und die damit verbundenen Lösungsvorschläge wie Meditation, Naturerfahrung oder digitales Detoxing – auf eine längere, oft ausgeblendete „Signatur“ des Spirituellen zurückgehen. Diese Signatur verknüpft Aufmerksamkeit mit Vorstellungen tiefer persönlicher Tra

---

### #27 `PDSE` — Generative AI and the Automating of Academia
_article_id_: `8b7aa60331dd3262becfb6fb6207fbeb`

**Opus** — `scannen`
  *Kernthese:* Der Artikel untersucht die Einführung generativer KI in der britischen Hochschulbildung vor dem Hintergrund neoliberaler Audit-Kulturen und prekärer Arbeitsbedingungen. Basierend auf einer Umfrage unter 284 UK-Akademiker:innen argumentiert er, dass KI-Werkzeuge die Dysfunktionen neoliberaler Logik nicht lindern, sondern verlängern und die akademische Krise vertiefen. Gleichzeitig sehen die Autor:innen Potenzial für positive Disruption der Arbeitsindustrialisierung und Re-Engagement mit wissenschaftlichem Handwerk.

**Mistral** — `lesenswert`
  *Kernthese:* Der Artikel untersucht die Auswirkungen generativer Künstlicher Intelligenz (GAI), insbesondere großer Sprachmodelle wie ChatGPT, auf die Arbeitsbedingungen und Selbstverständnisse von Akademiker*innen im UK. Die zentrale These lautet, dass GAI-Tools die neoliberalen Dysfunktionen der Hochschulbildung nicht lindern, sondern verstärken: Sie automatisieren und intensivieren die auditkulturellen Logiken von Effizienz, Produktivität und Prestige, während sie gleichzeitig die Prekarität und Überlastung akademischer Arbeit vertiefen. Die Autor*innen argumentieren jedoch, dass GAI auch als potenziell

---

### #28 `LMT` — Mapping pedagogies: applying cartographic practice to the public sphere
_article_id_: `4042cb9b0f78b891066dcacbcd065906`

**Opus** — `scannen`
  *Kernthese:* (C-Tier: nur Screening, kein Agent)

**Mistral** — `lesenswert`
  *Kernthese:* Der Artikel untersucht, wie demokratisierte Formen der partizipativen Kartographie – insbesondere durch Open-Source-Plattformen wie OpenStreetMap – in pädagogische Praktiken übersetzt werden können. Im Fokus stehen Bildungsprojekte im Global South, die feministische und gemeinschaftsorientierte Ansätze verfolgen und eine Ethik der Sorgfalt, des Handwerks und der Kultivierung gegenüber korporativen oder externen Forschungsparadigmen betonen. Der Autor analysiert, wie solche Projekte, etwa Crowd2Map Tanzania oder YouthMappers, durch Mentoring und partizipative Methoden räumliches Wissen produzie

---

### #29 `AIandSoc` — From 'objectivity' to obedience: LLMs as discourse, discipline, and power
_article_id_: `d0400090247ee6dafb78c786b5e07dab`

**Opus** — `scannen`
  *Kernthese:* (C-Tier: nur Screening, kein Agent)

**Mistral** — `lesenswert`
  *Kernthese:* Der Artikel untersucht Large Language Models (LLMs) nicht als technische Fehlfunktionen, sondern als strukturelle Effekte epistemischer und institutioneller Regime. Mit Rückgriff auf Michel Foucaults Macht/Wissen-Konzept und postkoloniale Theorie werden LLMs als produktive diskursive Apparate analysiert, die bestimmte Weisen des Wissens, Sprechens und Denkens normalisieren. Besonderes Augenmerk liegt auf Reinforcement Learning from Human Feedback (RLHF), das situierte menschliche Urteile in skalierbare Optimierungsziele übersetzt und dabei historische Normen in algorithmisch stabilisierte Stan

---

### #30 `merz` — Möslein-Tröppner, Bodo/Bernhard, Willi (2018). Digitale Gamebooks in der Bildung. Spielerisch lehren und lernen mit interaktiven Stories. Wiesbaden: Springer Ga
_article_id_: `30634074641508931bfd8dcaf0ce345f`

**Opus** — `ignorieren`
  *Kernthese:* (Screening: ignorieren)

**Mistral** — `scannen`
  *Kernthese:* Der Beitrag stellt das Konzept der „Digitalen Gamebooks“ als innovatives Instrument für game-based Learning vor, das spielerische und kollaborative Elemente mit digitalen Möglichkeiten verbindet. Möslein-Tröppner und Bernhard beschreiben, wie Gamebooks – ursprünglich aus der Unterhaltungsliteratur und Computerspielindustrie stammend – für Bildungszwecke adaptiert werden können. Der Fokus liegt auf der Erstellung interaktiver Stories, die durch individuelle Entscheidungen der Spielenden geformt werden und so motivationale Lernprozesse anregen. Der Band bietet eine praxisorientierte Anleitung zu

---

### #31 `STHV` — Mythologies of Wealth in Platform Economies: The Case of the Ride-Hailing Platform Didi in China
_article_id_: `6229d32572e6ba7a31aefe2feba078fe`

**Opus** — `ignorieren`
  *Kernthese:* Der Artikel reaktiviert den Mythos-Begriff aus den Sozialwissenschaften, um digitale Technologien und Plattformökonomien zu untersuchen. Anhand einer ethnografischen Studie der chinesischen Ride-Hailing-Plattform Didi zeigt er, wie Mythologien mit vergangenheitsorientierten Erzählstrukturen Individuen helfen, Technologien und Geschäftspraktiken zu verstehen und daran zu glauben. Diese Plattform-Mythologien werden von kulturellen Rahmungen und dominanten Narrativen geformt, spiegeln die Hoffnungen und kollektiven Erfahrungen der Akteure wider und mobilisieren Individuen, wodurch die Plattform i

**Mistral** — `lesenswert`
  *Kernthese:* Der Artikel untersucht die Rolle von Mythen und kollektivem Storytelling in der Plattformökonomie am Beispiel der chinesischen Ride-Hailing-Plattform Didi. Die Autor*innen argumentieren, dass Plattformen wie Didi nicht nur durch technische oder ökonomische Logiken, sondern maßgeblich durch Mythen geprägt sind, die vergangene Erfahrungen, kulturelle Narrative und kollektive Hoffnungen aufgreifen. Diese Mythen ermöglichen es Akteur*innen ohne technisches Fachwissen, die Technologien und Geschäftspraktiken der Plattformökonomie zu verstehen und an sie zu glauben. Sie stützen zudem spekulative Inv

---

### #32 `PCS` — Relational trouble and student victimisation at schools – categorisation, caring and institutionalisation
_article_id_: `f87fc203d5897e90b5616ed8d120b55a`

**Opus** — `ignorieren`
  *Kernthese:* (Screening: ignorieren)

**Mistral** — `scannen`
  *Kernthese:* Der Artikel untersucht, wie schwedische Schulen Opfer von Gewalt und Missbrauch unter Schüler*innen kategorisieren und institutionell bearbeiten. Die zentrale These lautet, dass Schulverantwortliche Schwierigkeiten haben, solche Vorfälle klar zu definieren und einzuordnen. Gleichzeitig zeigt sich eine Ambivalenz im Umgang mit externen Institutionen wie Polizei und Sozialdiensten: Einerseits wird die Übernahme durch Professionelle als Entlastung erlebt, andererseits führt sie zu einem Kontrollverlust und Informationsdefiziten seitens der Schulen. Die Studie verdeutlicht damit einen soziopolitis

---

### #33 `ZfPaed` — Funktionalität und Normativität als bildungstheoretische Perspektiven auf Bildung für Nachhaltige Entwicklung
_article_id_: `f226c988e32e9a73020916c00343a443`

**Opus** — `scannen`
  *Kernthese:* Der Artikel analysiert das Verhältnis von Bildung und Nachhaltigkeit als Dialektik zwischen funktionaler und normativer Perspektive. Er kritisiert die gegenwärtige Konzentration auf Sachinhalte nachhaltigen Handelns (funktionale Ebene) und plädiert dafür, Prinzipien wie Mündigkeit und soziale Gerechtigkeit als bildungsphilosophische Grundlage einer an Nachhaltigkeit normierten Bildung zu etablieren.

**Mistral** — `lesenswert`
  *Kernthese:* Der Artikel adressiert das Verhältnis von Bildung und Nachhaltiger Entwicklung (BNE) und untersucht, wie sich pädagogische Ansätze zwischen einer funktionalen und einer normativen Perspektive positionieren. Die zentrale These lautet, dass eine einseitige Fokussierung auf die Vermittlung von Sachinhalten nachhaltigen Handelns (funktionale Ebene) zu kurz greift und stattdessen eine bildungsphilosophische Fundierung durch Prinzipien wie Mündigkeit und soziale Gerechtigkeit (normative Ebene) notwendig ist, um Bildung als Teil einer nachhaltigen Gesellschaft zu gestalten.

---

### #34 `merz` — Computerspiele im Kindes- und Jugendalter
_article_id_: `368171a729ec5ac2f58b9027d128131b`

**Opus** — `ignorieren`
  *Kernthese:* (Screening: ignorieren)

**Mistral** — `scannen`
  *Kernthese:* Der Artikel fasst aktuelle Forschungsbefunde zu geschlechtsspezifischen Präferenzen, Spielgenres, Spielanforderungen und Spielfiguren von Computerspieler*innen im Kindes- und Jugendalter zusammen. Dabei werden medienkonzeptionelle und entwicklungspsychologische Implikationen für Serious Games kritisch reflektiert. Der Fokus liegt auf der Frage, wie geschlechtsspezifische Unterschiede in der Nutzung von Computerspielen verstanden und für pädagogische sowie therapeutische Zwecke (z. B. Serious Games) nutzbar gemacht werden können.

---

### #36 `merz` — Hass und Hetze im Internet - Analyse und Intervention
_article_id_: `f32d82c001f2c005e38942b688469729`

**Opus** — `ignorieren`
  *Kernthese:* (Screening: ignorieren)

**Mistral** — `scannen`
  *Kernthese:* Der Beitrag adressiert das Phänomen von Hass und Hetze im Internet, insbesondere rechtsextreme und rassistische Äußerungen, und stellt das Format „Counter Speech“ als medienpädagogische Interventionsstrategie vor. Zentral wird die Sensibilisierung Jugendlicher für rassistische Äußerungen und die Förderung demokratischer Gegenrede in digitalen Räumen behandelt. Der Fokus liegt auf der praktischen Umsetzung in der (medien-)pädagogischen Arbeit, um Jugendliche zu befähigen, sich aktiv gegen Hass im Netz zu engagieren.

---

### #37 `Resilience` — &lt;em&gt;36.5 / Bodo Inlet&lt;/em&gt;, Kenya, 2019
_article_id_: `bd3ab96b623ecc9f0983d6344be490a2`

**Opus** — `ignorieren`
  *Kernthese:* (Screening: ignorieren)

**Mistral** — `lesenswert`
  *Kernthese:* Der Artikel dokumentiert und reflektiert das künstlerisch-partizipative Projekt »36.5 / Bodo Inlet« in Kenia, das 2019 in Bodo Village durchgeführt wurde. Im Zentrum steht eine performative Intervention, bei der lokale Gemeinschaften und Künstler*innen gemeinsam den steigenden Meeresspiegel und dessen ökologische sowie kulturelle Auswirkungen auf die Küstenregion thematisieren. Das Projekt verbindet ökologische Sensibilisierung mit ästhetischen Praktiken und kollektiven Ritualen, um Resilienz als gemeinschaftlichen, transformativen Prozess erfahrbar zu machen.

---

### #39 `AIandSoc` — The hopes and fears of artificial intelligence: a comparative computational discourse analysis
_article_id_: `483ad5bbf8ce98def4504f6156f854c4`

**Opus** — `scannen`
  *Kernthese:* (C-Tier: nur Screening, kein Agent)

**Mistral** — `lesenswert`
  *Kernthese:* Der Artikel untersucht mittels computergestützter Diskursanalyse, wie verschiedene Akteursgruppen (Politiker*innen, Beratungsfirmen, Laienexpert*innen auf Reddit) Künstliche Intelligenz (KI) als gesellschaftliches Phänomen deuten und bewerten. Die zentrale These ist, dass KI als umkämpftes „Issue Field“ verstanden werden kann, in dem heterogene Akteure konkurrierende Deutungen, Hoffnungen und Ängste artikulieren. Politiker*innen betonen ethische und gesellschaftliche Implikationen, Beratungsfirmen sehen KI primär als wirtschaftliche Chance, während Laienexpert*innen technische Aspekte in den V

---

### #40 `EPT` — Bild, Bildung and the ‘romance of the soul’: Reflections upon the image of Meister Eckhart
_article_id_: `34c6602217cbeafbd040e435a6b17a1c`

**Opus** — `ignorieren`
  *Kernthese:* (Screening: ignorieren)

**Mistral** — `scannen`
  *Kernthese:* Der Artikel untersucht das Bild des Bildhauers, das von Plotin geprägt und von Meister Eckhart adaptiert wurde, um die religiös-transzendente Dimension von Ethik und Bildung zu reflektieren. Im Zentrum steht der Begriff der ‚Bildung‘ (Bild) als Prozess des ‚Ent-bildens‘ (Loslösung von weltlichen Bindungen) und der Rückwendung des Selbst zu seinem göttlichen Urbild. Dieser Prozess wird als dynamische Transformation verstanden, die das Individuum zu seiner wahren Identität und Würde als Abbild des Göttlichen führt. Bildung wird dabei als ein spiritueller und ethischer Vorgang gefasst, der über f

---

### #42 `REPCS` — The (academic) chair: Embodied relations of arrival, place, and hospitality
_article_id_: `1fd641480a35c7e58c8865cb887e2846`

**Opus** — `scannen`
  *Kernthese:* Der Artikel untersucht den Stuhl als alltäglichen Gegenstand durch die Linse feministischer Neuer Materialismen und Affekttheorie. Die Autorinnen argumentieren, dass Stühle vitale Objekte mit affektiven und symbolischen Bedeutungen sind, die verkörperte Praktiken des "Mattering" und Fragen von Ankunft, Ort und Gastfreundschaft aufwerfen. Anhand persönlicher Erfahrungen und experimentellen Schreibens entfalten sie, wie Stühle Beziehungen zwischen Körpern und nicht-menschlichen Akteuren konstituieren.

**Mistral** — `lesenswert`
  *Kernthese:* Der Artikel untersucht den alltäglichen Gegenstand „Stuhl“ aus einer feministisch-neomaterialistischen Perspektive und schreibt ihm eine lebendige, affektive und relationale Vitalität zu. Dabei wird der Stuhl nicht als bloßer funktionaler Gegenstand, sondern als aktiver Teil von verkörperten Ankunfts-, Orts- und Gastfreundschaftspraktiken verstanden. Am Beispiel des „akademischen Stuhls“ werden symbolische und affektive Bedeutungen analysiert, die sich aus der Besetzung und Nutzung von Stühlen in akademischen Kontexten ergeben. Durch experimentelles Schreiben und persönliche Reflexionen werden

---

### #50 `EERJ` — De-individualising the ‘NEET problem’: An ecological systems analysis
_article_id_: `4e2d0cd620236203bfab2da8c4bda4b3`

**Opus** — `ignorieren`
  *Kernthese:* (Screening: ignorieren)

**Mistral** — `lesenswert`
  *Kernthese:* Der Artikel adressiert das Phänomen NEET (Young People Not in Education, Employment or Training) und dekonstruiert dessen Individualisierung in politischen und pädagogischen Diskursen. Anhand einer qualitativen Längsschnittstudie mit 53 jungen Menschen in London wird gezeigt, wie strukturelle Bedingungen wie Kürzungen im Bildungs- und Unterstützungssystem, sozioökonomische Benachteiligung und transformationsbedingte Veränderungen des Arbeitsmarkts zu schulischer Entfremdung und letztlich zum NEET-Status führen. Die Autor*innen argumentieren, dass das ‚NEET-Problem‘ nicht als individuelles Vers

---
