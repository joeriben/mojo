# Q-Check Assessment — MiMo vs vorhandene Opus-Datensätze

**Datum:** 2026-05-16T11:19:23.949767
**Stichprobe-Plan:** 50 stratified articles (lesenswert/scannen/ignorieren-Mix)
**Tatsächlich auswertbar:** 50 (Rest hat 402/403 erlitten — OpenRouter weekly key limit)
**MiMo-Konfig:** `xiaomi/mimo-v2.5-pro`, `tool_choice='auto'`, `cache_control: ephemeral`

## TL;DR

- **Verdict-Match: 35/50 = 70.0 %** (auf den auswertbaren Calls)
- **Cache greift NICHT** — alle 50 Calls cache=0 %. Mein früheres Bisection-Ergebnis ("99 % mit `tool_choice='auto'`") ist mit diesem Prompt-Format nicht reproduzierbar.
- **MiMo-Kosten auf den auswertbaren Calls:** $1.2286 (Opus-Vergleich aus DB: $1.4002).
- **Blocker:** OpenRouter weekly key limit ($10) erschöpft → restliche 0 Calls liefen ins 402. Für volle Lauf-Reproduktion entweder bis Reset warten oder Weekly-Cap bei OpenRouter erhöhen.

## Aggregate (auswertbare Calls)

- Erfolgreich: 50 / 50 (0 mit 402/403 abgebrochen)
- MiMo-cost gesamt: $1.2286
- Opus-cost gesamt (aus articles.db): $1.4002
- Avg/Call MiMo: $0.0246
- Avg/Call Opus: $0.0280
- Faktor MiMo/Opus auf dieser Mini-Stichprobe: 1/1.14

### Verdict-Konfusionsmatrix

| Opus → / MiMo ↓ | FAIL | ignorieren | lesenswert | scannen |
|---|---|---|---|---|
| **FAIL** | 0 | 0 | 0 | 1 |
| **ignorieren** | 0 | 11 | 0 | 2 |
| **lesenswert** | 0 | 1 | 16 | 4 |
| **scannen** | 0 | 3 | 4 | 8 |

## Failures (402/403)

_0 Calls abgebrochen wegen OpenRouter-Wochenlimit:_

## Mismatches (Quality-Lektüre)

_15 von 50 auswertbaren — bitte einzeln prüfen:_

### #7 `BDS` — Data artivism and feminicide
_article_id_: `87f44a03f395a5e2ddbcf1307becf491`

**Opus** — `scannen`
  *Kernthese:* Der Artikel führt das Konzept "Data Artivism" ein – künstlerisch-handwerkliche Arbeiten, die Daten visualisieren und als Widerstandsform mobilisieren, um soziale Probleme (hier Femizid) sichtbar zu machen und anzuprangern. Anhand von drei Fallbeispielen plädiert er für eine vertiefte Auseinandersetzung der kritischen Daten 
- und Visualisierungsstudien mit Kunst und für eine gemeinsame Sprache mit lateinamerikanischen Aktivist*innen und Künstler*innen.
  *Verdict-Begründung:* Der Artikel berührt das Beobachtungsfeld (künstlerische Widerstandspraktiken, dekoloniale Perspektiven), bietet aber keine konkreten argumentativen Anschlüsse an Jörissens spezifische Publikationen; shared reference frames allein reichen nicht für 'lesenswert'.
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    - Data Artivism als cross-disziplinärer Import: Verbindet kritische Datenwissenschaft, partizipative visuelle Forschungsmethoden und aktivistische Kunst – eine Schnittstelle, die für Forschungen zu hybr
    - Expliziter Fokus auf lateinamerikanische Aktivist*innen und dekoloniale Perspektiven – berührt Jörissens Interesse an postkolonialen Irritationen bildungstheoretischer Diskurse (vgl. 'Territorien der 

**MiMo** — `lesenswert`
  *Kernthese:* Der Beitrag führt den Begriff „data artivism" ein und versteht darunter künstlerisch-handwerkliche Praktiken, die Daten zu Feminizid visuell-politisch intervenieren, um gesellschaftliche Missstände sichtbar zu machen und hegemoniale Unsichtbarmachung herauszufordern. Anhand dreier lateinamerikanischer Beispiele (darunter gestickte Datenvizualisierungen, Schnittarbeiten und Netzwerkinstallationen) wird argumentiert, dass Kunst und Handwerk jenseits konventioneller Datenvisualisierung alternative Modi der Datenmobilisierung eröffnen. Der Text plädiert für eine stärkere Verknüpfung kritischer Dat
  *Verdict-Begründung:* Der Beitrag bietet Anregungspotenzial für das Cultural-Resilience-Projekt, da er einen anderen theoretischen Diskursraum (feministische Data Studies, lateinamerikanische Artivismus-Forschung) auf das gleiche Problemfeld bezieht: ästhetische Praxis als kollektive Widerstandsform gegen hegemoniale Unsichtbarmachung. Die konkreten Beispiele gestickter und geschnittener Datenvisualisierungen könnten a
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    - [
    - "
    - D
    - e
    - r

---

### #10 `merz` — Friedrich, Jörg Phil (2023). Degenerierte Vernunft. Künstliche Intelligenz und die Natur des Denkens. München: Claudius. 125 S., 20,00 €
_article_id_: `6a8feec999224400b1ef801b200ad3ac`

**Opus** — `lesenswert`
  *Kernthese:* Rezension des Buches "Degenerierte Vernunft" von Jörg Phil Friedrich, das eine philosophische Abgrenzung von KI und menschlicher Vernunft vornimmt. KI wird als algorithmische, sinn- und bewusstseinslose Datenverarbeitung charakterisiert, die grundsätzlich von menschlichem Denken (Besinnung, Reflexion, Sinnsuche) verschieden sei. Die Unterscheidung soll helfen, mit Ängsten vor KI-Ersetzung umzugehen.
  *Verdict-Begründung:* Stellt eine prägnante philosophische Gegenposition zu Jörissens posthumanistischen, relationalen KI-Konzeptualisierungen dar – relevant als Kontrastfolie und zur Schärfung der eigenen Argumentation.
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    - Rezension einer Monographie, die eine explizit anti-posthumanistische, bewusstseinsphilosophische Position zu KI vertritt – direkter Kontrast zu Jörissens relationalen, agentiell-realistischen und pos
    - Thematisiert die öffentliche Wahrnehmungskrise („Warum halten wir KI-Produkte für besser?“), die Jörissen ebenfalls als „Wahrnehmungskrise“ analysiert (LEHKCH59), aber aus diametral entgegengesetzter 

**MiMo** — `scannen`
  *Kernthese:* Rezension von Jörg Phil Friedrichs "Degenerierte Vernunft" (2023), das KI und menschliche Vernunft als grundsätzlich unvergleichbar darstellt: KI operiert algorithmisch ohne Bewusstsein, Intuition oder ästhetisch-moralische Fähigkeiten, während menschliches Denken auf Sinngebung, Besinnung und Reflexion beruht. Das Ziel ist, den Begriff der natürlichen menschlichen Vernunft zu schärfen, um den Umgang mit KI-Entwicklungen zu ermöglichen.
  *Verdict-Begründung:* Die referierte Position (KI und menschliche Vernunft prinzipiell unvergleichbar) reproduziert genau die anthropozentrische Trennung, die Jörissens Arbeit (LEHKCH59, L224MAYL) kritisch überschreitet. Die Rezension bestätigt Diskurstrends, bietet aber kein Anregungspotenzial für aktuelle Projekte.
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    - Die Rezension in merz zeigt, dass die KI-Vernunft-Debatte in der deutschen Medienpädagogik-Diskursöffentlichkeit weiterhin in einem eher essentialistisch-humanistischen Rahmen verhandelt wird, der KI 

---

### #15 `PCS` — Neoliberalism and the social imaginary: interpreting study abroad policy in Japanese higher education
_article_id_: `85a2cee01c0d403c3e83dedf6fc8f911`

**Opus** — `ignorieren`
  *Kernthese:* (Screening: ignorieren)
  *Verdict-Begründung:* Screening: Japanese study abroad, neoliberalism, English proficiency, n
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    _(keine)_

**MiMo** — `scannen`
  *Kernthese:* Der Beitrag analysiert japanische Study-Abroad-Politik durch die Linse neoliberaler Gouvernementalität und des sozialen Imaginären (Castoriadis, Taylor). Er zeigt, wie marktgetriebene Logiken Studentenmobilität, englischsprachige Hegemonie und essentialistisch-kulturalistische Interpretationen von Auslandsaufenthalten strukturieren und dabei eine informelle, für viele untragbare soziale Schuld zwischen Individuum und Staat produzieren. Foucaults Biopolitik-Konzept dient als theoretischer Rahmen für die Analyse gouvernementaler Steuerungsmechanismen.
  *Verdict-Begründung:* Der Beitrag liegt innerhalb des Beobachtungsfeldes (Neoliberalismuskritik, Hegemonie, gouvernementale Steuerung von Bildung) und bietet einzelne bemerkenswerte konzeptionelle Impulse (Sozialschuld, epistemische Sprachhegemonie). Es fehlen jedoch substantielle Anschlüsse an Jörissens Forschungsgegenstände (ästhetische Bildung, kulturelle Resilienz, Postdigitalität, KI) oder aktive Projekte, die übe
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    - Die Analyse der Produktion informeller Sozialschulden durch gouvernementale Bildungspolitik ist ein bemerkenswerter konzeptioneller Zug, der über rein kompetenz- oder kulturalistische Rahmungen von In
    - Die Verknüpfung von Sprachhegemonie (Englisch als epistemisches Modell) mit neoliberaler Gouvernementalität berührt strukturell die Thematik kultureller Hegemonie in KI-Trainingsdaten, wie sie im ai4a

---

### #18 `BDS` — Generating reality and silencing debate: Synthetic data as discursive device
_article_id_: `050f065cb58259d9f55f40caa420ca8d`

**Opus** — `scannen`
  *Kernthese:* Der Artikel analysiert synthetische Daten nicht nur als technisches, sondern als diskursives und politisches Phänomen. Die Autoren kritisieren, dass synthetische Daten oft als "technical solutionism" präsentiert werden, der ethisch-politische Debatten um KI-Bias, Privatsphäre und Plattformökonomie zu schließen versucht, statt sie zu führen. Sie zeigen, wie synthetische Daten selbst politisch sind und als diskursive Geräte wirken.
  *Verdict-Begründung:* Der Artikel berührt Jörissens Beobachtungsfeld (KI-Ethik, Solutionismus-Kritik), zeigt aber keine spezifischen argumentativen Bezüge zu seinen konkreten Publikationen.
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    - Die Perspektive auf synthetische Daten als 'discursive device' (nicht nur technisches) ist ein innovativer konzeptueller Zugang zur KI-Ethik.
    - Die These des 'silencing debate' durch solutionistische Ansätze verbindet technische mit politischen Analysen auf produktive Weise.
    - Die integrative Betrachtung von algorithmischem Bias, Privatsphäre und Plattformökonomie unter einem Dach bietet eine holistische Kritik der Dateneconomy.

**MiMo** — `lesenswert`
  *Kernthese:* Der Artikel analysiert synthetische Daten (durch GANs und andere generative Systeme erzeugte Trainingsdaten) als nicht rein technisches, sondern als diskursives Dispositiv. Die Autor*innen argumentieren, dass synthetische Daten als vermeintliche Lösung für ethisch-politische Probleme der KI (Bias, Privatsphäre, Plattformökonomie) fungieren, dabei aber die zugrundeliegenden Debatten nicht befrieden, sondern vielmehr zum Verstummen bringen — ein technologischer Solutionismus, der das Politische von Dateninfrastrukturen unsichtbar macht.
  *Verdict-Begründung:* Der Artikel adressiert auf STS-basierter Ebene genau den infrastrukturellen Blindpunkt, den AI4ArtsEd bearbeitet: wie Trainingssysteme hegemoniale Logiken verfestigen. Die Analyse von synthetischen Daten als diskursivem Dispositiv — das Bias-Probleme nicht löst, sondern unsichtbar macht — liefert ein produktives Begriffsangebot für die kritische Auseinandersetzung mit generativer KI im Kontext kul
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    - D
    - i
    - e
    -  
    - R

---

### #22 `BJET` — Learning to work with the black box: Pedagogy for a world with artificial intelligence
_article_id_: `332c5b6047a06ea69481233edf6b3e84`

**Opus** — `lesenswert`
  *Kernthese:* Der Artikel definiert Künstliche Intelligenz relational-epistemologisch als eine spezifische Interaktion, in der ein computergestütztes Artefakt ein nicht nachvollziehbares Urteil über einen optimalen Handlungsverlauf liefert – und damit per Definition als Black Box agiert. Statt die Black Box erklären zu wollen, plädiert er für eine Pädagogik, die den Umgang mit opaken, partiellen und ambivalenten Situationen lehrt, welche die verstrickten Beziehungen zwischen Menschen und Technologien widerspiegeln. Konkret werden zwei Ansätze skizziert: die Orientierung an Qualitätsstandards („Spielregeln“)
  *Verdict-Begründung:* Der Artikel bietet eine konkrete pädagogische Positionierung zum Umgang mit KI-Opazität, die die in Jörissens Publikationen entwickelten Konzepte der relationalen Bildungstheorie, der Wahrnehmungskrise und des agentiellen Realismus direkt aufgreifen, erweitern oder kontrastieren könnte. (Verifikation ohne Ergebnis abgebrochen, Assessment-Verdict übernommen)
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    - Der Artikel operationalisiert das Black-Box-Problem als definitionsgemäße Eigenschaft von KI („cannot be traced“) und leitet daraus eine pädagogische Grundhaltung der Arbeit mit Opazität ab – ein beme
    - Die explizite Bezugnahme auf eine „relational epistemology“ und die Betonung von „entangled relationships“ weist auf eine theoretische Nähe zu posthumanistischen und neomaterialistischen Ansätzen hin,

**MiMo** — `scannen`
  *Kernthese:* Bearman & Ajjawi schlagen eine Pädagogik für eine KI-mediierte Welt vor, die auf einer relationalen Epistemologie basiert: KI wird als „black box" definiert, deren unverfolgbare Urteile nicht erklärt, sondern im Umgang mit Opazität, Partialität und Ambiguität produktiv bearbeitet werden sollen. Zwei konkrete pädagogische Ansätze werden vorgeschlagen: die Orientierung an Qualitätsstandards als soziale Regulierungskontexte von KI sowie bedeutungsvolle Interaktionen mit KI als Teil sozio-technischer Ensembles.
  *Verdict-Begründung:* Der Artikel adressiert KI-Pädagogik aus einer pragmatischen Hochschuldidaktik-Perspektive, die konzeptionell in eine andere Richtung zielt als Jörissens kritisch-ästhetische Ansätze. Für Diskursübersicht relevant, aber kein Anregungspotenzial für die eigenen Projekte — die pädagogische Rahmung („mit der Black Box arbeiten" statt sie zu dekonstruieren) ist ein bewusst kontrastierender Ansatz, der k
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    - Der Artikel bildet einen bemerkenswerten Gegenentwurf zu Jörissens Ansatz einer kritisch-kreativen KI-Pädagogik (Prompt Interception, Hegemonie-Dekonstruktion): Statt die Black Box aufzubrechen oder z
    - Die explizite Weigerung, Erklärbarkeit (XAI) als pädagogisches Ziel zu verfolgen, steht im Widerspruch zu Ansätzen, die wie Jörissen (LEHKCH59) die epistemologische Differenz zwischen menschlicher Her
    - Diskursrelevant: Der Artikel zeigt eine breite Akzeptanz einer pragmatisch-pragmatistischen KI-Pädagogik in der anglophonen Hochschulforschung (BJET), die Jörissens kritisch-ästhetische Intervention a

---

### #23 `PDSE` — Stressing Out the ‘Damsel in Distress’: Intersectional Shifts in Women’s Representation in Video Games
_article_id_: `2b060f4a6c3ed89a76d9ee24916d64b7`

**Opus** — `scannen`
  *Kernthese:* Der Artikel untersucht die sich wandelnde Repräsentation von Frauen in Videospielen durch eine postdigitale feministische Linse. Er zeigt, dass alltägliche Aushandlungen von Misogynie im kompetitiven Spiel durch die infrastrukturelle Gestaltung postdigitaler Plattformen bedingt sind, nicht nur durch textuelle Repräsentation. Empirisch wird intersectionelles Self-Positioning von Spielerinnen als prägend für die Rezeption weiblicher Avatare herausgearbeitet. Die Studie argumentiert, dass Repräsentation, digitale Infrastrukturen und Communities/Policy eine Triade bilden, die bestehende Machtstruk
  *Verdict-Begründung:* Das Thema (postdigitale Kulturen, Videospiele) berührt das Beobachtungsfeld, aber es gibt keine spezifischen argumentativen Anschlüsse an Jörissens publizierte Positionen (kulturelle Resilienz, kritische KI-Praxis, Bildungstheorie).
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    - Der Artikel zeigt empirisch, wie die infrastrukturelle Gestaltung von Plattformen (nicht nur Repräsentation) die alltägliche Aushandlung von Misogynie im kompetitiven Spiel bedingt – eine materialisti

**MiMo** — `ignorieren`
  *Kernthese:* Der Beitrag untersucht die sich wandelnde Repräsentation von Frauen in Videospielen mittels semi-strukturierter Interviews (N=19) und verankert die Analyse in postdigital-feministischen Frameworks. Die Autor*innen argumentieren, dass Alltagsverhandlungen von Misogynie im kompetitiven Gaming durch die Infrastrukturdesigns postdigitaler Plattformen konditioniert werden und dass intersectionale Selbstpositionierung die Rezeption weiblicher Spielerinnen, Avatare und Charaktere prägt.
  *Verdict-Begründung:* Der Beitrag bewegt sich in den feministischen Game Studies und behandelt Geschlechterrepräsentation in Videospielen — ein Forschungsfeld, das mit keiner der eigenen Publikationen, Projekte oder Diskurspositionen substantiell verknüpft ist. Auch die Verwendung des Begriffs „postdigital" dient hier einer anderen analytischen Agenda (Geschlechterpolitik digitaler Plattformen) als der eigenen (ästheti
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    _(keine)_

---

### #24 `EthicsEd` — ‘Equipping students with an ethical compass.’ What does it mean, and what does it imply?
_article_id_: `392a1473ce0c10a0ae59332160bd1529`

**Opus** — `ignorieren`
  *Kernthese:* (Screening: ignorieren)
  *Verdict-Begründung:* Screening: Generic ethics education discourse, no digital/material/rela
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    _(keine)_

**MiMo** — `scannen`
  *Kernthese:* Der Artikel untersucht die Metapher des „ethischen Kompasses" in der professionellen Hochschulbildung an niederländischen Universities of Applied Sciences. Auf Basis eines Literaturreviews werden drei Cluster ethischer Kompass-Modelle unterschieden (Inhalt, Form, Nutzung), und es wird evaluiert, welches Modell sinnvoll zur Professionalisierung beitragen kann. Der Fokus liegt auf character education und Tugendethik im Kontext beruflicher Bildung.
  *Verdict-Begründung:* Der Artikel gehört zum weiten Feld der Erziehungs- und Bildungswissenschaft, berührt jedoch weder kulturelle/ästhetische Bildung noch Medienpädagogik, post-digitale Kultur oder relationale Bildungstheorie. Die verwendete theoretische Tradition (Tugendethik, character education) und der Gegenstand (berufsethische Kompassbildung an Fachhochschulen) bieten kein Anregungspotenzial für Jörissens Forsch
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    _(keine)_

---

### #25 `EERJ` — Educating for anti-complicity: A pedagogical response to political and structural violence
_article_id_: `7bf4e3fc9b71aebf70a34428c0c94806`

**Opus** — `ignorieren`
  *Kernthese:* Der Artikel von Michalinos Zembylas behandelt die pädagogische Herausforderung der Komplizenschaft in politischer und struktureller Gewalt. Er argumentiert für die Entwicklung von Anti-Komplizenschafts-Pädagogiken, die die Komplexität „geteilter Komplizenschaften“ anerkennen und durch affekttheoretische Ansätze ein nicht-binäres Verständnis von Komplizenschaft und Widerstand ermöglichen.
  *Verdict-Begründung:* Der Artikel behandelt politische Gewalt und Anti-Komplizenschafts-Pädagogik, die thematisch nicht mit Jörissens Forschungsschwerpunkten (kulturelle Resilienz, Digitalität, post-digitale Jugendkulturen, generative KI) verbunden sind.
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    _(keine)_

**MiMo** — `lesenswert`
  *Kernthese:* Zembylas untersucht pädagogische Zugänge zur "Anti-Komplizenschaft" (anti-complicity) angesichts politischer und struktureller Gewalt, in der Lernende, Lehrende und deren Communities bereits in gewaltförmige Institutionen, Normen und Praktiken eingebettet sind. Er argumentiert, dass Komplizenschaft und Widerstand nicht binär gedacht werden sollten, und schlägt eine Pädagogik der "shared complicities" vor, die affektive Praxen im Klassenzimmer nutzt, ohne deren Risiken zu ignorieren. Theoretisch verbindet der Text Affekttheorie (Ahmed, Protevi) mit politischem Denken (Butler, Mills, Kaba).
  *Verdict-Begründung:* Der Artikel adressiert strukturell dasselbe Problemfeld wie Jörissens Cultural-Resilience-Rahmen — insbesondere die Dimension Resistance als kollektive, nicht-binäre Praxis der Destabilisierung hegemonialer Normordnungen —, allerdings aus einer anderen theoretischen Tradition (Affekttheorie + kritische Pädagogik statt posthumanistischer Relationalontologie). Diese Verschiedenheit bei thematischer 
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    - Der Diskurs um Komplizenschaft als nicht-binäre Kategorie (weder Täter noch Unbeteiligter) ist ein bemerkenswerter theoretischer Zugang, der für die Konzeptualisierung von Widerstand (Resistance) in d
    - Zembylas' Fokus auf affektive Praxen im institutionellen Kontext (Klassenzimmer) könnte für die Dimension der Rootedness (sinnlich-leibliches Gewahrwerden von Verstrickung) produktiv sein, da er Affek
    - Michalinos Zembylas ist eine profilierte Stimme im Feld der Affektpädagogik und kritischen Erziehungswissenschaft; der Artikel erscheint im European Educational Research Journal, einem zentralen Organ

---

### #26 `EduTheory` — Signature of Attention: Historical Ambiguities and Elisions in Contemporary Psychological Framings of Attending
_article_id_: `35296fb7ecff14df6afa037b1ed68e67`

**Opus** — `scannen`
  *Kernthese:* Der Artikel untersucht die historische Genealogie des Aufmerksamkeitsbegriffs und zeigt, wie gegenwärtige Diskurse über eine "Aufmerksamkeitskrise" im Kontext von Digitalisierung, Medien und KI auf lange vernachlässigte spirituelle Signaturen zurückzuführen sind. Die Autoren rekonstruieren, wie das europäisch-christliche Mönchtum Praktiken zur Disziplinierung von Aufmerksamkeit entwickelte, die mit Prozessen des Othering und der Kritik verbunden waren, und argumentieren, dass heutige pädagogische Ansätze zur "Aufmerksamkeitskrise" noch immer von diesen spirituellen Signaturen, binären Logiken 
  *Verdict-Begründung:* Der Artikel berührt Jörissens Beobachtungsfeld (Aufmerksamkeitskrise, Digitalisierung, KI), bietet aber keine konkrete argumentative Anschlussstelle zu seinen spezifischen Analysen algorithmischer Aufmerksamkeit oder transformer-Architekturen.
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    - Der Artikel verbindet aktuelle Diskurse über digitale Aufmerksamkeitskrisen mit mittelalterlichen monastischen Praktiken der Aufmerksamkeitsdisziplin – ein ungewöhnlicher historischer Tiefenblick, der
    - Die Analyse zeigt, wie Othering-Prozesse (sowohl spirituell als auch demografisch) bereits in mittelalterlichen Aufmerksamkeitspraktiken eingeschrieben waren und wie diese in christliche Reichsbildung

**MiMo** — `lesenswert`
  *Kernthese:* Der Beitrag verfolgt eine Genealogie des Konzepts „Aufmerksamkeit" (attention) von mittelalterlichen christlich-klösterlichen Praktiken bis zu gegenwärtigen Diskursen über die „Aufmerksamkeitskrise" in digitalisierten Bildungskontexten. Saari und Baker argumentieren, dass zeitgenössische pädagogische Interventionen gegen Ablenkung (meditation, nature, unplugging) noch immer von Signaturen der Spiritualität durchzogen sind und dabei binäre Logiken des Othering reproduzieren, die in den mittelalterlichen Disziplinierungspraktiken eingeschrieben waren.
  *Verdict-Begründung:* Der Beitrag ist lesenswert, weil er das Konzept „Aufmerksamkeitskrise" — das in Jörissens Arbeiten zu Wahrnehmungskrisen (LEHKCH59), zum Regime des Komputablen (M8RZJRHN) und zur Aufmerksamkeitsökonomie postdigitaler Jugendkulturen implizit präsent ist — genealogisch radikal historisiert und mit postkolonialer Kritik verbindet. Die historiographische Tiefenschärfe und die Verknüpfung von Aufmerksa
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    - [
    - "
    - D
    - e
    - r

---

### #28 `LMT` — Mapping pedagogies: applying cartographic practice to the public sphere
_article_id_: `4042cb9b0f78b891066dcacbcd065906`

**Opus** — `scannen`
  *Kernthese:* (C-Tier: nur Screening, kein Agent)
  *Verdict-Begründung:* C-Tier: Screening-Pass, keine Agent-Analyse.
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    _(keine)_

**MiMo** — `ignorieren`
  *Kernthese:* Der Artikel konzipiert, wie demokratisierte Partizipation an räumlicher Wissensproduktion über Open-Source-Mapping-Plattformen (OpenStreetMap, Humanitarian OpenStreetMap) in pädagogische Praxis übersetzt werden kann. Anhand einer Critical Discourse Analysis von Forumartikeln zu Grassroots Mapping und digitaler Teilnehmendenbeobachtung bei HOT-Projekten werden feministische und gemeindeorientierte Mapping-Initiativen im Globalen Süden (Tanzania, Peru, Lesotho, Liberia, Nigeria) dokumentiert, insbesondere die Mentoring-Praxis weiblicher Studierender im digitalen Mapping.
  *Verdict-Begründung:* Der Artikel bewegt sich im Feld Civic Cartography / Partizipatives GIS / Counter-Mapping und verhandelt weder ästhetische Bildung noch Medienbildung im für Jörissen relevanten Sinne. Trotz der oberflächlichen Berührungspunkte (Partizipation, Globaler Süden, digitale Praxis, Latour-Referenz) fehlt jede substantielle Verbindung zu den Forschungsfeldern, Projekten oder theoretischen Perspektiven des 
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    - Der Artikel dokumentiert eine bemerkenswerte Reihe konkreter Mapping-Initiativen im Globalen Süden (Crowd2Map Tanzania, GAL School Peru, Map Lesotho, OSM Liberia/Nigeria, YouthMappers), die als Fallbe
    - Die explizite Verbindung von feministischer Ethik (craft, care, cultivation) mit digital-mapping-basierter Pädagogik im Globalen Süden ist als Diskursindikator für die Ausweitung partizipativer Forsch

---

### #29 `AIandSoc` — From 'objectivity' to obedience: LLMs as discourse, discipline, and power
_article_id_: `d0400090247ee6dafb78c786b5e07dab`

**Opus** — `scannen`
  *Kernthese:* (C-Tier: nur Screening, kein Agent)
  *Verdict-Begründung:* C-Tier: Screening-Pass, keine Agent-Analyse.
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    _(keine)_

**MiMo** — `lesenswert`
  *Kernthese:* Der Beitrag argumentiert, dass Bias in Large Language Models kein technisches Versagen ist, sondern ein struktureller Effekt epistemischer und institutioneller Regime, in denen diese Systeme entwickelt und aligned werden. Mittels Foucaults Macht/Wissen-Konzept und postkolonialer Theorie werden LLMs als produktive diskursive Apparate konzeptualisiert, die bestimmte Weisen des Wissens, Sprechens und Argumentierens normalisieren — insbesondere über den Mechanismus von RLHF, der situative menschliche Urteile über „Hilfreichkeit" in skalierbare Optimierungsziele übersetzt und so historisch kontinge
  *Verdict-Begründung:* Der Artikel arbeitet am selben Problemkreis wie AI4ArtsEd (kulturelle Hegemonie und Bias in generativer KI) und wie die eigenen Texte zu Wahrnehmungskrisen (LEHKCH59) und zum Regime des Komputablen (M8RZJRHN), allerdings aus einer explizit foucaultschen statt ranzière'schen Perspektive. Die RLHF-Analyse als Normalisierungsmechanismus bietet eine konkrete technische Konkretisierung, die für die Pro
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    - [
    - "
    - D
    - i
    - e

---

### #31 `STHV` — Mythologies of Wealth in Platform Economies: The Case of the Ride-Hailing Platform Didi in China
_article_id_: `6229d32572e6ba7a31aefe2feba078fe`

**Opus** — `ignorieren`
  *Kernthese:* Der Artikel reaktiviert den Mythos-Begriff aus den Sozialwissenschaften, um digitale Technologien und Plattformökonomien zu untersuchen. Anhand einer ethnografischen Studie der chinesischen Ride-Hailing-Plattform Didi zeigt er, wie Mythologien mit vergangenheitsorientierten Erzählstrukturen Individuen helfen, Technologien und Geschäftspraktiken zu verstehen und daran zu glauben. Diese Plattform-Mythologien werden von kulturellen Rahmungen und dominanten Narrativen geformt, spiegeln die Hoffnungen und kollektiven Erfahrungen der Akteure wider und mobilisieren Individuen, wodurch die Plattform i
  *Verdict-Begründung:* Keine substantiellen Bezüge zu den Forschungsbereichen des Empfängers (kulturelle Resilienz, postdigitale Jugendkulturen, ästhetische Bildung, generative KI); der Artikel behandelt wirtschaftssoziologische Fragen der Plattformökonomie und Spekulation im chinesischen Kontext.
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    _(keine)_

**MiMo** — `scannen`
  *Kernthese:* Der Artikel reaktiviert den Mythosbegriff (Barthes, Lévi-Strauss) für die Analyse von Plattformökonomien und zeigt anhand einer ethnografischen Studie der chinesischen Ride-Hailing-Plattform Didi, wie kollektives Storytelling und „Plattform-Mythologien" das Commitment von Nutzer*innen und Investor*innen aufrechterhalten. Die Autor*innen argumentieren, dass Mythen und spekulatives Kapital sich wechselseitig stabilisieren und die Verzauberung digitaler Technologien als konstitutiver Bestandteil von Plattformökonomien verstanden werden muss.
  *Verdict-Begründung:* Der Artikel berührt zwar Jörissens Forschungsfeld (Digitalität, Plattformökonomien, kritische Technologieanalyse), liefert aber keine spezifischen Anschlüsse an Bildungstheorie, ästhetische Bildung oder die aktiven Forschungsprojekte. Die Diskursfeld-Beobachtung (STS-Kritik an Plattformmythologien) ist relevant, aber der Beitrag adressiert andere Probleme und andere Disziplinen.
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    - D
    - i
    - e
    -  
    - V

---

### #33 `ZfPaed` — Funktionalität und Normativität als bildungstheoretische Perspektiven auf Bildung für Nachhaltige Entwicklung
_article_id_: `f226c988e32e9a73020916c00343a443`

**Opus** — `scannen`
  *Kernthese:* Der Artikel analysiert das Verhältnis von Bildung und Nachhaltigkeit als Dialektik zwischen funktionaler und normativer Perspektive. Er kritisiert die gegenwärtige Konzentration auf Sachinhalte nachhaltigen Handelns (funktionale Ebene) und plädiert dafür, Prinzipien wie Mündigkeit und soziale Gerechtigkeit als bildungsphilosophische Grundlage einer an Nachhaltigkeit normierten Bildung zu etablieren.
  *Verdict-Begründung:* Thematisch relevant im Beobachtungsfeld Nachhaltigkeit und Bildungstheorie, aber keine konkreten argumentativen Anschlüsse an Jörissens posthumanistische, relationale und kulturelle Resilienz-Perspektive erkennbar.
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    - Die funktional-normative Dialektik als analytisches Rahmenkonzept für Bildung für nachhaltige Entwicklung stellt eine klare systematische Unterscheidung bereit, die in der bildungstheoretischen Diskus

**MiMo** — `None`
  *Kernthese:* 
  *Verdict-Begründung:* 
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    _(keine)_

---

### #44 `MedienPaed` — Zur Bedeutung des Nichtwissens und die Suche nach Problemlösungen
_article_id_: `75641a28b53daef73187d6754027e3ac`

**Opus** — `lesenswert`
  *Kernthese:* Der Artikel argumentiert, dass Nichtwissen ein entscheidendes Unterscheidungsmerkmal zwischen Mensch und KI ist und den Menschen in unsicheren Situationen zu Problemlösungen und Urteilen befähigt. Diese einzigartigen menschlichen Fähigkeiten stellen laut den Autoren eine zentrale Bildungsaufgabe dar, bei der Medienpädagogik eine Aufklärungs- und Gestaltungsfunktion zwischen individuell-sozialem Kontingentem und technischen Umwelten übernimmt.
  *Verdict-Begründung:* Die explizite Zitation von Jörissens früherer Grundlagenarbeit erfordert eine Prüfung, wie die Autoren seine Positionen aufgreifen oder kritisieren – dies könnte argumentative Anschlüsse oder Widersprüche zu seinen jüngeren KI-bezogenen Arbeiten aufdecken. (Verifikation ohne Ergebnis abgebrochen, Assessment-Verdict übernommen)
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    - Explizite Zitation von Jörissen/Marotzki (2009) 'Medienbildung – Eine Einführung', was eine direkte Auseinandersetzung mit grundlegenden Positionen des Forschers signalisiert.
    - Anthropologische Fokussierung auf Nichtwissen als zentrales Differenzkriterium Mensch/Maschine – ein ungewöhnlicher Zugang in der KI-Debatte, der eher philosophisch-kybernetisch als technologisch argu

**MiMo** — `scannen`
  *Kernthese:* Der Beitrag argumentiert, dass Nichtwissen ein zentrales Unterscheidungsmerkmal zwischen Mensch und Maschine darstellt und den Menschen zu Problemlösung und Urteilsfähigkeit befähigt. Diese Fähigkeiten werden als bleibende Bildungsaufgabe bestimmt, wobei die Medienpädagogik eine Aufklärungs- und Gestaltungsfunktion für die Verbindung von menschlichem Kontingenzwissen und technischen Umwelten einnimmt. Theoretisch wird der Beitrag auf Systemtheorie (Luhmann, Baecker), Pragmatismus (Dewey) und medienphilosophische Ansätze (Hörl, Mersch, Sesink) gestützt.
  *Verdict-Begründung:* Der Beitrag berührt mit KI und Bildung ein für Jörissen relevantes Thema, jedoch aus einer explizit humanistisch-systemtheoretischen Perspektive, die strukturell konträr zu den eigenen post-anthropozentrischen, agential-realistischen und STS-informierten Ansätzen verläuft. Die Nichtwissens-These als Mensch-Maschine-Unterscheidungsmerkmal ließe sich mit Jörissens eigenen Arbeiten zur Wahrnehmungskr
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    - Die explizit humanistische Rahmung von Nichtwissen als menschliche Spezifik gegenüber KI steht in direktem Spannungsverhältnis zu post-anthropozentrischen und posthumanistischen Perspektiven, wie sie 
    - Werner Sesinks Arbeiten zu KI und Bildung (1990, 2012) werden als historische Referenz eingebunden — eine ältere medienpädagogische Auseinandersetzung mit KI, die in der aktuellen KI-Debatte kaum rezi

---

### #48 `ZfPaed` — Wolkige Verheißungen
_article_id_: `338efe035846be4b48363278b62d3bdc`

**Opus** — `lesenswert`
  *Kernthese:* Der Artikel kritisiert am Beispiel der digitalen Schul-Cloud die Verschmelzung von Lernen und Konsumieren in cloudgesteuerten Lernpraktiken sowie die fortschreitende Kontrolle von Lernprozessen durch Learning Analytics und Datafizierung, die mit der Produktion umfassender Daten und dem Versprechen von Vorhersagbarkeit von Schüler*innenleistungen einhergeht.
  *Verdict-Begründung:* Der Artikel adressiert mit der digitalen Schul-Cloud ein konkretes Beispiel für Datafizierung und algorithmische Steuerung in der Bildung, was direkt mit Jörissens Arbeiten zu Digitalität in der Schulkultur, educational governance und der Kritik an solutionistischen Ansätzen korrespondiert. (Verifikation ohne Ergebnis abgebrochen, Assessment-Verdict übernommen)
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    - Fokussierung auf das konkrete Beispiel der digitalen Schul-Cloud als Fallstudie für breitere Digitalisierungsphänomene in der Bildung
    - Explizite Kritik an der Verschmelzung von Lernen und Konsumieren in digitalen Lernpraktiken
    - Analyse von Datafizierungseffekten und Vorhersagbarkeitsversprechen durch Learning Analytics

**MiMo** — `scannen`
  *Kernthese:* Der Beitrag analysiert am Beispiel der digitalen Schul-Cloud die Transformation von Vermittlungswissen und bildungspolitischer Steuerung. Er vertritt zwei Kernthesen: die Verschmelzung von Lernen und Konsumieren in cloudgesteuerten Lernpraktiken sowie die fortschreitende Kontrolle von Lernprozessen durch Learning Analytics, die mit einer umfassenden Datenproduktion einhergeht und Vorhersagbarkeit von Schüler*innenleistung verspricht.
  *Verdict-Begründung:* Der Beitrag behandelt mit Learning Analytics, Dateninfrastrukturen und der Kritik an cloud-basierter Bildungssteuerung Themen, die für die Forschungsprojekte DiäS-KuBi und ComeArts sowie für Jörissens erziehungstheoretische Digitalitätsperspektive relevant sind. Es handelt sich jedoch um eine bildungssoziologisch und -politische Analyse der Schul-Cloud, die weder den ästhetischen noch den kulturpä
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    - Der Beitrag bietet eine kritische Analyse der Schul-Cloud als konkrete Infrastruktur — ein Gegenstand, der in der DiäS-KuBi- und ComeArts-Diskussion um Digitalität in der Schulkultur relevant ist, abe
    - Die These der Verschmelzung von Lernen und Konsumieren berührt die in Jörissens Arbeiten diskutierte Kommerzialisierung digitaler Bildungsmedien (vgl. Plattformökonomien in 9JZX4LMW) und den Solutioni

---

## Matches (Stichproben-Kontrolle)

### #1 `PCS` — Towards a school-based ‘critical data education’  → beide `scannen`
_article_id_: `768f89ebd1e7b5cc9fa66b353df343ba`

**Opus** — `scannen`
  *Kernthese:* (C-Tier: nur Screening, kein Agent)
  *Verdict-Begründung:* C-Tier: Screening-Pass, keine Agent-Analyse.
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    _(keine)_

**MiMo** — `scannen`
  *Kernthese:* Pangrazio und Selwyn schlagen ein schulbasiertes Konzept einer „critical data education" vor, das auf drei Lernzielen basiert: Materialisierung von Daten und Datenverarbeitung, Verständnis der Implikationen der Datenverarbeitung sowie Erprobung von Strategien zum Schutz persönlicher Daten. Ausgehend von drei empirischen Forschungsprojekten argumentieren die Autor:innen, dass bestehende „Cybersafety"-Programme durch einen kritisch-pädagogischen Ansatz ersetzt werden müsse, der die politische Ökonomie der Daten (Überwachungskapitalismus, Datenwirtschaft) adressiert.
  *Verdict-Begründung:* Der Artikel bewegt sich thematisch im Nahfeld (Datafizierung, Algorithmisierung, kritische Bildung) und Pangrazio/Selwyn sind im publizierten Werk als Referenzen vertreten. Allerdings fehlt eine Verbindung zur ästhetischen Dimension digitaler Bildung, zu post-digitaler Kulturtheorie oder zu bildungstheoretischer Systematik — den zentralen Bezugspunkten der eigenen Forschung. Der rein freireanisch-
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    - D
    - e
    - r
    -  
    - A

---

### #2 `LMT` — Fixing higher education through technology: Canadian media coverage of massive open online courses  → beide `scannen`
_article_id_: `07bb2ede01951ed1899eba1d66a753d7`

**Opus** — `scannen`
  *Kernthese:* (C-Tier: nur Screening, kein Agent)
  *Verdict-Begründung:* C-Tier: Screening-Pass, keine Agent-Analyse.
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    _(keine)_

**MiMo** — `scannen`
  *Kernthese:* Dumitrica analysiert anhand einer thematischen Analyse englischsprachiger kanadischer Printmedien (2012–2014), wie MOOCs und Hochschulbildung diskursiv konstruiert werden. Zentrale These ist, dass Tageszeitungen MOOCs als einfache technologische Lösung für eine vermeintlich ineffiziente Hochschule rahmen, während Fachzeitschriften der akademischen Community das Verhältnis von Technologie, Hochschule und Geld kritisch hinterfragen und alternative, gemeinwohlorientierte Bildungsimaginarien entwickeln.
  *Verdict-Begründung:* Die Kritik an technologischem Solutionismus und neoliberaler Rahmung von Bildungstechnologie korrespondiert konzeptionell mit Jörissens Begriff des Solutionismus (v.a. M8RZJRHN, BRYT324Y), doch der konkrete Gegenstand (MOOCs, kanadische Hochschulpolitik, 2012–2014) ist für keinen der aktiven Forschungsprojekte anschlussfähig. Der Artikel ist zudem inhaltlich veraltet und bewegt sich in einem Disku
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    - D
    - i
    - e
    -  
    - U

---

### #3 `merz` — Zur empirischen und theoretischen Kritik der Datensouveränität anhand der Smart-Speaker-Nutzung  → beide `lesenswert`
_article_id_: `2c44a6fbe0a3524d43935e4842d48d6e`

**Opus** — `lesenswert`
  *Kernthese:* Der Beitrag kritisiert die Konzepte der digitalen bzw. Datensouveränität sowohl empirisch (anhand qualitativer Studien zur Smart-Speaker-Nutzung) als auch theoretisch mittels praxistheoretischer Perspektive auf Daten und kritisch-theoretischer Perspektive (Adorno/Horkheimer) auf den Souveränitätsbegriff. Die zentrale These ist, dass diese Konzepte problematisch sind, wenn sie eine Stärkung der Nutzenden gegenüber Staat und Online-Oligopolen fordern.
  *Verdict-Begründung:* Direkte argumentative Verbindung zu Jörissens Konzeptualisierung von digitaler Souveränität in der Schulkultur, die eine konkrete Ressourcentransferprüfung erfordert. (Verifikation ohne Ergebnis abgebrochen, Assessment-Verdict übernommen)
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    - Kritische Auseinandersetzung mit dem viel verwendeten Begriff der 'Datensouveränität' durch Verknüpfung von Adorno/Horkheimer's kritischer Theorie mit praxistheoretischer Datenanalyse.
    - Empirische Grundlage durch qualitative Studien zur Smart-Speaker-Nutzung im Alltagskontext.

**MiMo** — `lesenswert`
  *Kernthese:* Der Beitrag kritisiert das Konzept der digitalen bzw. Datensouveränität mithilfe einer praxistheoretischen Perspektive auf Daten und einer kritisch-theoretischen Perspektive (Adorno/Horkheimer) auf den Souveränitätsbegriff selbst. Anhand qualitativer Studien zur Smart-Speaker-Nutzung wird argumentiert, dass Souveränität als normatives Leitkonzept für digitale Teilhabe problematisch ist, da es auf einer verfügungshaltigen Subjektivität beruht, die der Praxis des Alltagsgebrauchs nicht entspricht.
  *Verdict-Begründung:* Der Artikel liefert eine fundierte kritische Auseinandersetzung mit dem Souveränitätsbegriff, der zentraler Gegenstand des laufenden DiäS-Projekts (Digitale-Ästhetische Souveränität) ist. Die These, dass Souveränität als Verfügungskonzept die Praxis digitaler Aneignung verfehlt, erfordert eine Positionierung — entweder als produktive Gegenposition oder als Ausgangspunkt für eine Differenzierung äs
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    - Der Artikel dekonstruiert 'Souveränität' als normatives Leitkonzept digitaler Bildung mithilfe kritischer Theorie — eine Argumentation, die direkt auf das laufende DiäS-Projekt (Digitale-Ästhetische S
    - Die praxistheoretische Analyse der Smart-Speaker-Nutzung zeigt, dass Nutzende Souveränität gar nicht anstreben, sondern in situative Arrangements eingehen — ein Befund, der für die Frage, ob und wie ä
    - Die Verbindung von Adorno/Horkheimers Souveränitätskritik mit Praxistheorie ist eine seltene Kombination in der deutschsprachigen Medienpädagogik und verdient Diskursübersicht-Beachtung.

---

### #4 `MedienPaed` — Big Data als datenbasierte Programmierung  → beide `lesenswert`
_article_id_: `eb0cc5c0f8dd9472cbd170b7d628a711`

**Opus** — `lesenswert`
  *Kernthese:* Der Artikel analysiert datenbasierte Programmierung als Technologie aus der Perspektive der relationalen Medienpädagogik. Er untersucht die medienpädagogische Relevanz von Big Data und datenbasierten Programmierungstechnologien, indem er die Technologie selbst (statt nur gesellschaftlicher Entwicklungen oder Medieninhalte) in den Blick nimmt und damit einen technologiefokussierten Ansatz innerhalb der relationalen Medienpädagogik entwickelt.
  *Verdict-Begründung:* Der Artikel entwickelt die relationale Medienbildungskonzeption von Jörissen weiter und importiert sie für eine konkrete technologiefokussierte Analyse datenbasierter Programmierung als medienpädagogischen Gegenstand.
  *Bezüge:*
    - _U6RW4WMN_: 
    - _XTJR5DRD_: 
  *Bemerkenswert:*
    - Der Artikel zitiert explizit zwei frühere Werke von Benjamin Jörissen (2009 und 2016), was auf eine direkte Auseinandersetzung mit seiner Medienbildungskonzeption hindeutet.
    - Die Fokussierung auf die Technologie von Medien (datenbasierte Programmierung) als Analysegegenstand entspricht der von Jörissen mehrfach thematisierten relationalen Perspektive auf Medienbildung und 
    - Der Artikel transferiert Jörissens relationale Medienbildungskonzeption auf einen spezifischen technologischen Gegenstand (Big Data/datenbasierte Programmierung) und entwickelt damit eine technologief

**MiMo** — `lesenswert`
  *Kernthese:* Der Beitrag analysiert datenbasierte Programmierung (Big Data) als Technologie aus einer relationalen Medienpädagogik, die neben gesellschaftlichen Entwicklungen und Medieninhalten/-strukturen die Technologieanalyse als dritte Dimension einbezieht. Zentral ist die These, dass medienpädagogische Relevanz nicht nur über Inhalte oder Nutzungskontexte, sondern über die Analyse technologischer Strukturen datenbasierter Systeme erschlossen werden muss.
  *Verdict-Begründung:* Der Beitrag explizit zitiert und rezipiert das eigene Medienbildung-Konzept (Jörissen/Marotzki 2009) als Grundlage einer relationalen Medienpädagogik und wendet dieses auf datenbasierte Programmierung an — ein Gegenstand, der unmittelbar mit Jörissens laufender Arbeit zu Algorithmisierung, Datafizierung und dem Regime des Komputablen korrespondiert. Die Rezeption des eigenen frameworks in der tech
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    - Der Beitrag explizit relational frames 'relationale Medienpädagogik' und zitiert dabei Jörissen/Marotzki 2009 als Referenztext — dies ist ein bemerkenswertes Signal für die Rezeption des eigenen Medie
    - Die Fokussierung auf Technologieanalyse als eigenständige medienpädagogische Dimension (neben Inhalts- und Gesellschaftsanalyse) korrespondiert mit Jörissens Ansatz, Digitalität als strukturelle Trans
    - Der Diskussionsgegenstand 'datenbasierte Programmierung' tangiert Jörissens fortlaufende Arbeit zu Algorithmisierung, Datafizierung und dem Regime des Komputablen (M8RZJRHN; LEHKCH59), berührt also ei

---

### #5 `merz` — Inkommunikabilität  → beide `lesenswert`
_article_id_: `f7effb3600bca9989e1ce001da967f6d`

**Opus** — `lesenswert`
  *Kernthese:* Der Artikel schlägt vor, den Begriff der Inkommunikabilität (nicht-Kommunizierbarkeit) systematisch in die Theorie der Medienbildung zu integrieren. Er argumentiert, dass Netzwerke nicht nur Konnektivität, sondern auch konstitutive Grenzen der Kommunikation produzieren, und entwickelt daraus die Kontur eines virtuellen, passiven Subjekts, das sich nicht auf Partizipationsnachweise reduzieren lässt.
  *Verdict-Begründung:* Der Artikel zitiert Jörissens Arbeit direkt und entwickelt substantielle theoretische Erweiterungen: Er importiert das Konzept der Inkommunikabilität in Jörissens relationale Medienbildungstheorie und erweitert dessen Subjektivationstheorie um die Dimension des Nicht-Kommunizierbaren als konstitutives Grenzphänomen.
  *Bezüge:*
    - _XTJR5DRD_: 
    - _U6RW4WMN_: 
  *Bemerkenswert:*
    - Der Begriff 'Inkommunikabilität' als systematisches Konzept für Medienbildung ist ein ungewöhnlicher, aber potentiell fruchtbarer theoretischer Import, der die Aufmerksamkeit auf das 'Andere der Konne
    - Die Verknüpfung von Luhmanns Systemtheorie mit Fragen der Subjektbildung in digitalen Netzwerken stellt eine interessante Kreuzung dar, die für relationale Bildungstheorien relevant sein könnte.

**MiMo** — `lesenswert`
  *Kernthese:* Der Beitrag schlägt vor, den Begriff der „Inkommunikabilität" als konstitutives Anderes von Konnektivität systematisch in die Theorie der Medienbildung zu integrieren. Ausgehend von der Diagnose, dass Netzwerkgesellschaft nicht nur Subjektivierung durch Partizipation, sondern auch Erfahrungen der Begrenztheit von Kommunikation hervorbringt, wird ein passives, virtuelles Subjekt konzipiert, das sich nicht auf seine Vernetzungsleistungen reduzieren lässt. Theoretischer Rahmen ist eine Luhmann'sche Systemtheorie kombiniert mit Überlegungen zu Passivität (Busch) und Entnetzung (Stäheli).
  *Verdict-Begründung:* Der Beitrag arbeitet explizit innerhalb des medienbildungstheoretischen Diskurses, den Jörissen mitgeprägt hat (explizite Zitation), und führt einen Begriff ein — Inkommunikabilität — der die eigene Subjektivierungs- und Resilienztheorie produktiv herausfordert. Die Idee eines passiven Subjekts, das sich der Vernetzungslogik entzieht, bietet Anregungspotenzial sowohl für die Cultural-Resilience-Th
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    - Der Begriff der Inkommunikabilität als Gegenstück zur Konnektivität ist eine bemerkenswerte theoretische Innovation für die Medienbildungsdiskussion: Er verschiebt den Fokus von Partizipation und Vern
    - Die explizite Bezugnahme auf Jörissen/Meyer 2015 (Subjekt Medium Bildung) zeigt, dass Pause innerhalb desselben theoretischen Diskurses argumentiert — die Referenz auf Subjektivierungstheorien im Medi
    - Die Verbindung von Luhmann'scher Systemtheorie mit Deleuze's Bartleby-Figur und Stähelis Entnetzungssoziologie ist ein ungewöhnlicher theoretischer Mix, der Anregungspotenzial für die Überlegungen zu 

---

### #6 `BJET` — Promoting students' artwork appreciation: An experiential learning‐based virtual reality approach  → beide `ignorieren`
_article_id_: `063f00c2fd4ed025da945015a759cb92`

**Opus** — `ignorieren`
  *Kernthese:* (Screening: ignorieren)
  *Verdict-Begründung:* Screening: VR for artwork appreciation, applied art education tech.
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    _(keine)_

**MiMo** — `ignorieren`
  *Kernthese:* Der Beitrag untersucht einen erfahrungsbasierten VR-Lernansatz (EL-SVVR) für die Kunstbetrachtung im Hochschulkontext. In einem quasi-experimentellen Design mit 45 Studierenden wird nachgewiesen, dass SVVR-basiertes experiential learning gegenüber konventionellem Unterricht Lernleistung, Motivation, Selbstwirksamkeit, kritisches Denken und digitale Malperformance verbessert.
  *Verdict-Begründung:* Der Artikel bewegt sich vollständig im instrumentell-technikintegrierenden EdTech-Paradigma, das Jörissens Arbeit explizit kritisch gegenübersteht (Solutionismus-Kritik, Tool-Perspektive vs. transformationsorientierte Perspektive). Es gibt keine theoretischen, methodischen oder konzeptionellen Berührungspunkte — die topische Überlappung (Kunst + Technologie + Bildung) ist allein nicht ausreichend 
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    _(keine)_

---

### #8 `MedienPaed` — Eine kritische Bildungstheorie post-digitaler Subjektivität  → beide `lesenswert`
_article_id_: `126ed69489dc33a0465fd80bceb44209`

**Opus** — `lesenswert`
  *Kernthese:* Leineweber's article outlines a programmatic framework for a critical education theory of post-digital subjectivity. Based on post-digital paradigms and the premise that digital media embed specific decision-making powers, it interrogates and reinterprets the core subject-theoretical concepts of autonomy and alienation through a relational approach, aiming to combine theoretical examinations of the subject with practical attempts at subjective liberation.
  *Verdict-Begründung:* The article directly imports and engages with Jörissen's relational media education framework, applying it to the reinterpretation of critical theory concepts (autonomy, alienation) in post-digital contexts, which represents a substantive theoretical connection.
  *Bezüge:*
    - _U6RW4WMN_: 
  *Bemerkenswert:*
    - The article explicitly cites Benjamin Jörissen's publications on media education and design/subjectivation (Bettinger & Jörissen 2022, Jörissen 2015), indicating direct engagement with his work.
    - It attempts to bridge critical theory with post-digital paradigms by reinterpreting autonomy and alienation - core concepts of Frankfurt School critical theory - through relational approaches relevant
    - The focus on 'decision-making powers inscribed in digital media' resonates with Jörissen's work on algorithmic subjectivation and distributed agencies in post-digital culture.

**MiMo** — `lesenswert`
  *Kernthese:* Der Beitrag entwirft programmatisch eine kritische Bildungstheorie post-digitaler Subjektivität. Auf Basis post-digitaler Paradigmen und der Prämisse eingeschriebener Entscheidungsmächte digitaler Medien werden die Begriffe Autonomie und Entfremdung im Sinne einer relationalen Haltung reinterpretiert, um theoretische Subjektbefragung und praktische Befreiungsversuche analytisch zu verknüpfen.
  *Verdict-Begründung:* Der Beitrag zitiert zwei Jörissen-Publikationen explizit und arbeitet im gleichen Problemfeld (relationale Bildungstheorie, post-digitale Subjektivität, Souveränität/Autonomie). Die Reinterpretation von Autonomie und Entfremdung als relationale Kategorien bietet Anregungspotenzial insbesondere für das DiäS-KuBi-Projekt (Souveränität) und die Cultural-Resilience-Theorie (Freiheit als Rekonfiguratio
  *Bezüge:*
    - _U6RW4WMN_: 
  *Bemerkenswert:*
    - Der Artikel zitiert explizit Jörissens 'Medienbildung' (Bettinger/Jörissen 2022) und 'Bildung der Dinge' (2015) sowie Engel/Mayweg/Carnap 2022 zu 'postdigital bedingter Souveränität' — er positioniert
    - Die Reinterpretation von Autonomie und Entfremdung als relationale Kategorien für post-digitale Subjektivität ist ein bemerkenswerter theoretischer Schritt, der Jörissens eigenes Spannungsfeld zwische
    - Der Beitrag erscheint in MedienPädagogik und markiert damit eine Positionierung im medienpädagogischen Diskurs, die kritische Bildungstheorie und Post-Digitalität systematisch zusammenführt — für die 

---

### #9 `EPT` — Michel Serres: Divergences  → beide `scannen`
_article_id_: `72da8be9352e51272ef3a73d606dc8b3`

**Opus** — `scannen`
  *Kernthese:* Der Artikel untersucht Michel Serres' Philosophie als Abkehr von der germanischen Bildungstradition (als egozentrischer, apolitischer Selbstkultivierung) und als Hinwendung zu einem ökologischen, ökozentrischen Denken im Sinne von Gregory Batesons "ecology of mind". Serres integriert auf ökologische Weise Poesie, Wissenschaft, Kunst, Ökologie und Politik, um philosophische Fragen zu stellen. Sein Stil und Inhalt durchbrechen die Grenzen traditioneller Philosophie und eröffnen ein neues Paradigma.
  *Verdict-Begründung:* Der Artikel berührt Jörissens Beobachtungsfeld (Kritik individualistischer Bildung, ökologisch-relationale Wende), bietet aber keine konkrete Argumenttransfer oder Zitation, die eine substantielle Verbindung begründet.
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    - Explizite Gegenüberstellung von Serres' ökozentrischem Denken mit der germanischen Bildungstradition (Bildung als egozentrische, apolitische Selbstkultivierung) – eine direkte philosophische Formulier
    - Verwendung von Gregory Batesons 'ecology of mind' als Referenzrahmen für Serres' ökologischen Ansatz – ein Konzept, das für relationale, posthumane Bildungstheorie anschlussfähig ist.

**MiMo** — `scannen`
  *Kernthese:* Der Artikel zeigt, wie Serres' Philosophie sich von der klassischen deutschen Bildungstradition (Selbstkultivierung durch Introspektion, Ich-Zentriertheit) absetzt und stattdessen ein öko-zentrisches, relationales Denken entfaltet, das Dichtung, Wissenschaft, Kunst, Ökologie und Politik integriert. Pierrot Lunaire (Giraud/Schoenberg) wird als Leitfigur für Serres' paradigmatisch grenzüberschreitenden Philosophiestil vorgeschlagen.
  *Verdict-Begründung:* Die Kritik am individualistischen Bildungsbegriff und der Hinweis auf öko-zentrisches, relationales Denken bei Serres berühren Jörissens kulturelle Resilienz auf konzeptioneller Ebene. Allerdings bleibt der Artikel rein philosophiehistorisch und bietet weder posthumanistische Anschlüsse noch methodische Impulse, die über Diskursübersicht hinaus Anregungspotenzial erzeugen würden.
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    - Der Artikel positioniert Serres' Denken als Abkehr von der deutschen Bildungstradition hin zu Batesons Ecologie of Mind — eine Diagnose, die für Jörissens eigenes Projekt der relationalen Bildungstheo
    - Interessant ist die These, dass Serres' Philosophiestil selbst paradigmatisch grenzüberschreitend ist (Poiesis + Wissenschaft + Ökologie) — das erinnert an Jörissens Überlegungen zu cross-aesthetische
    - Fehlende Rezeption von Haraway, Barad, Latour oder posthumanistischer Theoriebildung trotz der klar relational-ökologischen Stoßrichtung. Zeigt eine Rezeptionslücke in der angloamerikanischen Serres-R

---

### #11 `MedienPaed` — Die Dualität von Kompetenz in tiefgreifend mediatisierten Welten  → beide `scannen`
_article_id_: `f035990cc4e302bc50e22e0e1feed55c`

**Opus** — `scannen`
  *Kernthese:* Der Artikel rekonzeptualisiert "Medienkompetenz" in tiefgreifend mediatisierten Welten, indem er die definitorischen Wendungen des Begriffs im medienpädagogischen Diskurs nachzeichnet und schließlich ein eigenes Verständnis vorlegt, das Kompetenz und Performanz nach Giddens als zwei sich gegenseitig bedingende Dimensionen unterscheidet und zusätzlich zwischen Wirklichkeitskonstruktionen erster und zweiter Ordnung differenziert.
  *Verdict-Begründung:* Der Beitrag berührt medienpädagogische Grundlagendebatten im Beobachtungsfeld, zeigt jedoch keine konkreten argumentativen Anschlüsse an Jörissens spezifische Publikationen.
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    - Der Versuch, den stark kritisierten und teils verworfenen Begriff 'Medienkompetenz' durch eine Giddens-inspirierte Dualitätstheorie zu revitalisieren, stellt eine interessante Intervention in den deut
    - Die Unterscheidung zwischen Wirklichkeitskonstruktionen erster und zweiter Ordnung in Verbindung mit Kompetenz/Performanz könnte Anschlüsse an Diskussionen über implizites Wissen und habituelle Dimens

**MiMo** — `scannen`
  *Kernthese:* Der Beitrag zeichnet die definitorischen Wendungen des Konzepts Medienkompetenz im medienpädagogischen Diskurs nach und schlägt ein eigenes Verständnis vor, das auf Giddens' Dualität von Kompetenz und Performanz sowie auf einer Unterscheidung von Wirklichkeitskonstruktionen erster und zweiter Ordnung (nach Schütz/Luckmann) basiert. Ziel ist es, implizite Denkweisen über Kompetenz sichtbar zu machen, ohne eine Seite der Dualität zu privilegieren, und die Frage nach Kompetenz in tiefgreifend mediatisierten Welten über die Aufschlüsselung einzelner medienbezogener Fähigkeiten hinauszuführen.
  *Verdict-Begründung:* Der Beitrag ist demselben Diskursfeld zuzuordnen wie Jörissens Arbeiten zu Medienbildung und Digitalität, bietet aber kein spezifisches Anregungspotenzial: Die Giddens'sche Dualitätsperspektive verbleibt innerhalb einer kognitivistisch-struktionistischen Rahmung, die in Jörissens Ansätzen zugunsten relationaler, agentiell-realistischer und posthumanistischer Perspektiven bereits überschritten wurd
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    - D
    - e
    - r
    -  
    - V

---

### #12 `BJET` — Youths' relationship with culture: Tracing sixth graders' learning through designing culturally centred multimedia projects  → beide `scannen`
_article_id_: `90652e050b8e67a8a4e0d44bbef46f4e`

**Opus** — `scannen`
  *Kernthese:* Der Artikel untersucht, wie Sechstklässler*innen durch das Erstellen kulturspezifischer Multimedia-Projekte (Remixing) ihre Beziehung zu Kultur entwickeln und darstellen. Anhand einer Fallstudie mit 36 Projekten von 12 Schüler*innen zeigt er drei Formen der Symbolisierung auf, die vielfältige, reziproke Beziehungen zur eigenen und zu anderen Kulturen offenbaren. Die Arbeit plädiert dafür, die festgefahrenen Erwartungen der Dominanzkultur in formalen Lernumgebungen zu überwinden und stattdessen die Wissensbestände und Erfahrungen der Jugendlichen durch multimediales Remixen einzuladen.
  *Verdict-Begründung:* Der Artikel berührt das Beobachtungsfeld Digitalität und kulturelle Bildung, bietet aber keine konkreten argumentativen Anschlüsse zu Jörissens spezifischen Publikationen (z.B. kulturelle Resilienz, Post-Digitalität, agentieller Realismus).
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    - Empirische Fallstudie zu Remixing als Mittel der kulturellen Artikulation in formalen Schulsettings – konkrete Anschauung für Diskurse um digitale Artikulation und kulturelle Hybridisierung in Bildung

**MiMo** — `scannen`
  *Kernthese:* Der Artikel untersucht, wie Sechstklässler*innen in den USA durch die Erstellung kulturell zentrierter Multimedia-Projekte (Remixing) ihre Beziehungen zu Kultur entwickeln und symbolisch repräsentieren. Mittels einer Fallstudie werden 36 Remixing-Projekte von 12 Schüler*innen analysiert, wobei drei Formen des Symbolisierens identifiziert werden, die vielfältige kulturelle Beziehungen sichtbar machen.
  *Verdict-Begründung:* Der Artikel berührt Jörissens Themenfelder (Jugend, Kultur, multimediale Praxis, Remix), operiert aber in einem fundamental anderen theoretischen Paradigma (US-Learning-Sciences, Constructionism, individuelle Symbolisierung vs. kollektive relationale Transformation). Weder für aktuelle Projekte noch für die eigenen Argumente ergibt sich spezifisches Anregungspotenzial; die Verwendung von "futuriti
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    - D
    - e
    - r
    -  
    - A

---

### #13 `MedienPaed` — Die epistemische Krise am Beispiel der AfD und die Verantwortung der Medienpädagogik  → beide `lesenswert`
_article_id_: `fcf7903515402abec1d3c1f28f26e153`

**Opus** — `lesenswert`
  *Kernthese:* Der Artikel diskutiert die epistemische Krise als gesellschaftliches Krisensymptom am Beispiel der medialen Positionierungen der AfD. Ausgehend von der Prämisse, dass Digitalität und Postdigitalität nicht nur Handlungsweisen, sondern auch kulturelle Normen und politische Stabilität transformieren, analysiert er die Aushandlungsformen im Korridor von Desinformation/Populismus und vermachteten Kommunikationsräumen. Der Beitrag zeigt zentrale Merkmale der epistemischen Krise aus Sicht von Medialität und Digitalität auf und erörtert, wie sich die Medienpädagogik dazu verhalten kann.
  *Verdict-Begründung:* Der Artikel importiert explizit Jörissens relationales Medienbildungskonzept und transferiert es in den politischen Kontext der epistemischen Krise. Dies stellt eine substantielle Verbindung und Erweiterung dar, die für Jörissens eigene Arbeiten zur Digitalität und politischen Dimensionen von Medienbildung relevant ist.
  *Bezüge:*
    - _U6RW4WMN_: 
  *Bemerkenswert:*
    - Der Artikel operationalisiert den abstrakten Begriff der 'epistemischen Krise' konkret anhand der AfD als politischem Akteur und deren medialer Strategien.
    - Er versucht, medienpädagogische Verantwortung in einem politisch hoch aufgeladenen Feld zu definieren – ein eher seltenes Unterfangen in der Medienpädagogik.
    - Der Beitrag stellt eine direkte Verbindung zwischen relationaler Medienbildungstheorie und konkreter politischer Gegenwartsdiagnose her, was eine ungewöhnliche Anwendung darstellt.

**MiMo** — `lesenswert`
  *Kernthese:* Der Beitrag diskutiert am Beispiel der medialen Inszenierung und Medienpolitik der AfD die epistemische Krise als Symptom postdigitaler gesellschaftlicher Transformation. Zentral ist die These, dass Digitalität neue Formen der öffentlichen Aushandlung etabliert, die im Spannungsfeld von Desinformation/Populismus und vermachteten Kommunikationsräumen Deliberation und rationalen Diskurs als Idealisierungen ohne Unterbau erscheinen lassen. Gemkow fragt, wie sich Medienpädagogik als Reaktion auf diese Krise verhalten kann und sollte.
  *Verdict-Begründung:* Der Beitrag setzt sich explizit mit Jörissens Medienbildungskonzept auseinander und verbindet es mit der epistemischen Krise als gesellschaftspolitischem Phänomen — ein Verbindungspunkt, der für die Arbeiten zu postdigitaler Kultur, demokratischer Transformation (MetaKuBi) und Widerständigkeit produktiv sein kann. Die explizite Rezeption strukturaler Medienbildung in einem medienpädagogisch-politi
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    - Der Beitrag zitiert drei zentrale Texte von Jörissen (Medienbildung 2022, Medienbildung-Einführung 2009, Strukturale Medienbildung 2010) und rahmt sein Argument damit direkt im Anschluss an Jörissens 
    - Der Beitrag verbindet die epistemische Krise mit der Postdigitalitätsthese — Digitalität transformiere nicht nur Handlungsweisen, sondern auch kulturelle Normen und politische Stabilität. Diese Diagno
    - Die Analyse der AfD auf TikTok und in Social-Media-Strategien als Fall epistemischer Krise bietet eine konkrete Anschlussstelle für die Überlegungen zu Algorithmizität und algorithmischer Normalisieru

---

### #14 `EPT` — Educating the temporal imagination: Teaching time for justice in a warming world  → beide `lesenswert`
_article_id_: `641bb1ec866e734027416bca2aa2c992`

**Opus** — `lesenswert`
  *Kernthese:* Der Artikel argumentiert, dass Klimawandel ein „temporales Problem“ darstellt, das Spannungen zwischen menschlichen und nicht-menschlichen Zeitlichkeiten erzeugt und unterschiedliche Gemeinschaften zu unterschiedlichen Zeitregimen zwingt. Um Klima(un)gerechtigkeit zu verstehen, benötigen Schüler*innen eine „temporale Imagination“, die sensibilisiert für die politische Rolle von Zeit in einer erwärmenden Welt. Der Artikel entwickelt eine „temporale Pädagogik“ mit fünf Praktiken (relationale Zeit, Rhythmus, Antizipation und Reparation, temporale Suspension, kritisches Timekeeping) und drei pädag
  *Verdict-Begründung:* Der Artikel erweitert Jörissens Konzept kultureller Resilienz substantiell um eine explizite temporale Dimension und bietet mit seinen fünf Zeitpraktiken und drei pädagogischen Bewegungen einen konkreten operationalisierbaren Rahmen für Bildungsprozesse im Anthropozän.
  *Bezüge:*
    - _3W9X5QLZ_: 
    - _A93WTEZQ_: 
  *Bemerkenswert:*
    - Die explizite Verbindung von Zeitlichkeit und Klimagerechtigkeit im pädagogischen Kontext stellt einen originären Beitrag dar, der bildungstheoretisch bisher unterbelichtet ist.
    - Die Integration indigener und dekolonialer Zeitkonzepte („relational time“, „rhythm“) mit westlichen Zukunftsforschungsansätzen zeigt eine cross-disziplinäre und epistemisch pluralistische Herangehens
    - Die Konkretisierung der temporalen Pädagogik in fünf Praktiken und drei Bewegungen bietet einen operationalisierbaren Rahmen für Unterricht und Bildungsprogramme.

**MiMo** — `lesenswert`
  *Kernthese:* Keri Facer argumentiert, dass die Auseinandersetzung mit dem Klimawandel in der Bildung eine "temporale Imagination" erfordert, die für die politischen Dimensionen von Zeitlichkeit im Kontext einer sich erwärmenden Welt sensibilisiert. Sie entwickelt eine "temporale Pädagogik" aus fünf Praktiken (relationale Zeit, Rhythmus, Antipation und Reparation, temporale Suspension, kritisches Zeitmanagement) und drei pädagogischen Bewegungen (Interruption, Attention, Encounter), die aus öffentlichen Künsten, indigener Bildung, dekolonialer Praxis und Zukunftsforschung zusammengeführt werden.
  *Verdict-Begründung:* Die Konzeption einer temporalen Pädagogik für den Klimakontext bietet unmittelbares Anregungspotenzial für das Projekt Kulturelle Resilienz: Die drei pädagogischen Bewegungen (interruption of dominant temporal frames, attention to plural timings, encounter through judgement) lassen sich strukturell als zeitliche Dimension der drei Momente Rootedness/Resourcefulness/Resistance lesen — insbesondere 
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    - Die Verknüpfung von temporaler Gerechtigkeit, Klimawandel und dekolonialer/indigener Zeitkonzeptionen ist im Diskurs der Allgemeinen Pädagogik bemerkenswert — Educational Philosophy and Theory ist hie
    - Die drei pädagogischen Bewegungen (interruption, attention, encounter) bilden ein kompaktes operatives Schema, das über den Klimakontext hinaus anschlussfähig sein könnte — etwa an Überlegungen zu kul
    - Facer arbeitet mit Baraitser (Enduring Time) und Lefebvre (Rhythmanalysis) — zwei Autor*innen, die im bisherigen Diskurs der Allgemeinen Erziehungswissenschaft zu Digitalität/Resilienz kaum rezipiert 

---

### #16 `ZfE` — Individuelle Schüler*innenprofile des situationalen und dispositionalen Interesses und ihre Bedeutung für die Wahrnehmung der Unterrichtsqualität im Fach Mathem  → beide `ignorieren`
_article_id_: `a1d1395d112b8315a528a3a46f1dd7a7`

**Opus** — `ignorieren`
  *Kernthese:* (Screening: ignorieren)
  *Verdict-Begründung:* Screening: Empirical motivation study, no theoretical connection.
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    _(keine)_

**MiMo** — `ignorieren`
  *Kernthese:* Der Beitrag analysiert mittels Latent-Class-Analyse (N=940, 8. Klasse) vier Schüler*innenprofile aus situationalem und dispositionalem Interesse im Fach Mathematik und deren Zusammenhang mit der Wahrnehmung von Unterrichtsqualität. Ergebnis: Konsistente bzw. hohe situationale Interesseprofile korrelieren signifikant positiver mit der Unterrichtseinschätzung.
  *Verdict-Begründung:* Die Studie ist der quantitativen pädagogischen Psychologie (Interesseforschung, Unterrichtsqualität im Fach Mathematik) zuzuordnen und berührt keines der Forschungsfelder, theoretischen Bezugssysteme oder laufenden Projekte von Jörissen (kulturelle Bildung, Medienbildung, relationale Bildungstheorie, posthumanistische Ansätze, kulturelle Resilienz, KI/Ästhetik).
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    _(keine)_

---

### #17 `RAeE` — Ecologies of Death, Ecologies of Mourning: A Biophilosophy of Non/Living Arts  → beide `lesenswert`
_article_id_: `19df0fcd7d882d336505ff720613788a`

**Opus** — `lesenswert`
  *Kernthese:* Der Artikel untersucht aus der Perspektive der „Queer Death Studies" gegenwärtige Trauer-Imaginationen und die Auseinandersetzung mit mehr-als-menschlichem Tod, Sterben und Artensterben im Kontext planetarischer Umweltkrisen. Zeitgenössische Kunst dient als Ort, an dem eine ökologische Ontologie des Todes sichtbar und ethische Territorien des Eco-Grief entfaltet werden. Eine „Biophilosophie des Nicht/Lebenden" rahmt Tod und Verlust als relationale, ökologische (nicht individuell-psychologische) Phänomene im Anthropozän.
  *Verdict-Begründung:* Der Artikel operiert aus einer anderen theoretischen Tradition (Queer Death Studies, posthumanistische Biophilosophie) auf einem Problemfeld, das strukturell direkt an die Cultural-Resilience-Theorie anschließt: mehr-als-menschliche Vulnerabilität, ökologische Trauer, Kunst als Ort ethisch-ästhetischer Verhandlung im Anthropozän. Die thanato-ökologische Perspektive bietet produktive Reibung für di
  *Bezüge:*
    - _ZSSJ4BPL_: 
    - _AC9GZ3JY_: 
  *Bemerkenswert:*
    - ‚Queer Death Studies' als theoretischer Rahmen für die Analyse ökologischer Trauer in den Künsten ist ein ungewöhnlicher cross-disziplinärer Import, der Tod/Sterben/Extinktion als relationales, ökolog
    - Die Figur einer ‚Biophilosophie des Nicht/Lebenden' (non/living) bietet einen konzeptuellen Gegenpol zur ‚Fortsetzung des Lebens' in der Kulturellen Resilienz: Wo Cultural Resilience auf das Fortbeste
    - Die Verbindung von Anthropozän-Affekten (Angst, Wut, Trauer) mit zeitgenössischer Kunst als ethisch-ästhetischem Verhandlungsraum schließt phänomenal an die Rootedness-Dimension der Cultural Resilienc

**MiMo** — `lesenswert`
  *Kernthese:* Der Artikel von Marietta Radomska untersucht im Rahmen der Queer Death Studies, wie zeitgenössische Kunst Auseinandersetzungen mit mehr-als-menschlichem Sterben, Aussterben und Verlust ermöglicht. Er entfaltet eine ökologische Ontologie des Todes und zeigt, wie sich ethische Territorien ökologischer Trauer (eco-grief) in künstlerischen Praktiken entfalten.
  *Verdict-Begründung:* Der Artikel bearbeitet ökologische Trauer, Verlust und mehr-als-menschliche Vulnerabilität als künstlerisch-ästhetisches Phänomen – exakt jenen Bereich, der laut relevance shifts für das Projekt Cultural Resilience als Rootedness-Dimension relevant ist, ohne diesen Begriff zu verwenden. Die Verbindung von queerer Todesforschung, Biophilosophie und zeitgenössischer Kunst bietet als andere theoretis
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    - Queer Death Studies ist ein noch relativ junges Forschungsfeld, das Tod und Sterben aus queer-feministischer und posthumanistischer Perspektive untersucht – eine für die Diskursübersicht relevante Str
    - Der Artikel verbindet explizit planetarische Krisen, mehr-als-menschliche Vulnerabilität und künstlerische Praxis als Erkenntnismedium – eine Konfiguration, die strukturell mit der Cultural-Resilience

---

### #19 `EPT` — The smiling philosopher: Emotional labor, gender, and harassment in conference spaces  → beide `ignorieren`
_article_id_: `565369f1d279ba6bb15958d2774979f5`

**Opus** — `ignorieren`
  *Kernthese:* (Screening: ignorieren)
  *Verdict-Begründung:* Screening: gender/emotional labor at conferences, no digital/cultural/a
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    _(keine)_

**MiMo** — `ignorieren`
  *Kernthese:* Der Artikel untersucht aus philosophischer Perspektive, wie Geschlechterverhältnisse und emotionale Arbeit die Erfahrung von Wissenschaftler*innen auf akademischen Konferenzen prägen. Unter Rückgriff auf Hochschilds Konzept der emotional labor und Ahmads Figur der feminist killjoy werden geschlechtsspezifische Erfahrungen von Frauen auf Konferenzen – einschließlich Belästigung und emotionalem Management – analysiert.
  *Verdict-Begründung:* Der Artikel behandelt Gender und emotionale Arbeit im Kontext akademischer Konferenzen – ein Thema, das in keinem Zusammenhang mit Jörissens Forschungsfeldern (Medienbildung, kulturelle Resilienz, ästhetische Bildung, Postdigitalität, generative KI) steht. Keine konzeptionelle, methodische oder diskursive Anschlussfähigkeit erkennbar.
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    _(keine)_

---

### #20 `MedienPaed` — Das Design der digitalen Mediengesellschaft  → beide `lesenswert`
_article_id_: `ad2626dd8e30357526d6041db761ee8c`

**Opus** — `lesenswert`
  *Kernthese:* Der Beitrag integriert Medien- und Designtheorie, um eine medienpädagogische Theorie der digitalen Gesellschaft zu entwerfen. Er argumentiert, dass digitale Anwendungen subjektive Handlungs1 und Entscheidungsspielräume durch designte Vermittlungsweisen und Aufforderungsstrukturen konfigurieren. Medienbildung wird als Fähigkeit zur kritischen Distanznahme, Einschätzung und gegebenenfalls Ablehnung dieser technisch-medialen Strukturen definiert, was die Relevanz einer zeitgemäßen allgemeinen (Medien)Bildungstheorie unterstreicht.
  *Verdict-Begründung:* Der Artikel erweitert Jörissens relationalen Medienbildungsansatz durch die Integration von Designtheorie und entwickelt konkrete pädagogische Implikationen für eine medienpädagogische Theorie der digitalen Gesellschaft, wobei er direkt auf Jörissens Publikationen Bezug nimmt.
  *Bezüge:*
    - _U6RW4WMN_: 
    - _XTJR5DRD_: 
  *Bemerkenswert:*
    - Der Beitrag explizit zitiert zwei von Jörissens Schlüsseltexten zu Design/Subjektivation (2015) und Medienbildung (2022), was eine direkte Auseinandersetzung signalisiert.
    - Die Konvergenz von Medien- und Designtheorie zur Formulierung einer medienpädagogischen Gesellschaftstheorie stellt einen ungewöhnlichen, interdisziplinären Import dar, der für Jörissens design– und m
    - Die Definition von Medienbildung als Fähigkeit zur kritischen Distanznahme, Einschätzung und gegebenenfalls Ablehnung technisch-medialer Strukturen qua Design operationalisiert Jörissens relationalen 

**MiMo** — `lesenswert`
  *Kernthese:* Der Beitrag integriert Medien- und Designtheorie, um eine medienpädagogische Theorie der digitalen Gesellschaft zu entwerfen. Zentral ist die These, dass digitale Medien durch designte Aufforderungsstrukturen und pädagogische Inskriptionen subjektive und gesellschaftliche Handlungsspielräume konfigurieren. Medienbildung wird als Fähigkeit definiert, solche Vermittlungsweisen kritisch zu erkennen, einzuschätzen und sich ihnen ggf. zu entziehen.
  *Verdict-Begründung:* Der Beitrag arbeitet explizit mit Jörissens Konzepten („Bildung der Dinge" als Design-Subjektivations-Theorie, „Medienbildung" als relationales Konzept) und adressiert mit der Theorie algorithmischer Aufforderungsstrukturen und dem Postulat kritischer Distanznahme zentrale Problemstellungen des DiäS-KuBi-Projekts (digitale-ästhetische Souveränität) sowie der AI4ArtsEd-Reflexion zu hegemonialen Log
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    - [
    - "
    - D
    - e
    - r

---

### #21 `ZfPaed` — What is the Relationship Between Knowledge in Mathematics and Knowledge in Economics?  → beide `ignorieren`
_article_id_: `b5df9c7e962cbf61b3e99f5e0d085318`

**Opus** — `ignorieren`
  *Kernthese:* (Screening: ignorieren)
  *Verdict-Begründung:* Screening: Relationship between math and economics knowledge in teacher
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    _(keine)_

**MiMo** — `ignorieren`
  *Kernthese:* Der Beitrag untersucht Zusammenhänge zwischen fachlichem Wissen (CK) und fachdidaktischem Wissen (PCK) der Fächer Mathematik und Wirtschaftswissenschaften bei N=96 Sekundarstufen-Lehrkräften. Die Ergebnisse zeigen substantielle Zusammenhänge innerhalb und zwischen den Fächern, wobei mathematisches CK auch mit PCK in Wirtschaftswissenschaften korreliert.
  *Verdict-Begründung:* Der Artikel ist fernab des Beobachtungsfelds: Er behandelt fachspezifisches Lehrkräftewissen in Mathematik/Wirtschaftsdidaktik im Shulman-Paradigma — es gibt keine konzeptionelle, methodische oder diskursive Berührungspunkte mit kultureller/ästhetischer Bildung, Medienbildung, postdigitaler Kultur oder einem der aktiven Forschungsprojekte. Selbst die ComeArts-Professionalsierungsforschung operiert
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    _(keine)_

---

### #27 `PDSE` — Generative AI and the Automating of Academia  → beide `scannen`
_article_id_: `8b7aa60331dd3262becfb6fb6207fbeb`

**Opus** — `scannen`
  *Kernthese:* Der Artikel untersucht die Einführung generativer KI in der britischen Hochschulbildung vor dem Hintergrund neoliberaler Audit-Kulturen und prekärer Arbeitsbedingungen. Basierend auf einer Umfrage unter 284 UK-Akademiker:innen argumentiert er, dass KI-Werkzeuge die Dysfunktionen neoliberaler Logik nicht lindern, sondern verlängern und die akademische Krise vertiefen. Gleichzeitig sehen die Autor:innen Potenzial für positive Disruption der Arbeitsindustrialisierung und Re-Engagement mit wissenschaftlichem Handwerk.
  *Verdict-Begründung:* Der Artikel berührt Jörissens Beobachtungsfeld (KI in Bildung), bleibt aber in einem spezifischen arbeitssoziologischen und hochschulpolitischen Diskurs verhaftet, der nicht substantiell mit seinen Argumenten zu kultureller Resilienz, ästhetischer Bildung oder epistemologischen KI-Krisen verbunden ist.
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    - Empirischer Fokus auf akademische Arbeitsbedingungen unter KI-Nutzung – ein spezifischer Ausschnitt der KI-Diskussion, der in Jörissens Arbeiten weniger prominent ist.
    - Kombination von Prekaritätsforschung mit KI-Diskurs – ungewöhnliche Verknüpfung von Arbeitssoziologie und Technology Studies im Hochschulkontext.

**MiMo** — `scannen`
  *Kernthese:* Der Artikel untersucht die Nutzung generativer KI-Tools (insbesondere ChatGPT) durch britische Wissenschaftler*innen (n=284) im Kontext neoliberaler Hochschulkultur mit Überarbeit, Prekarität und Audit-Kultur. Die zentrale These ist, dass GAI-Tools die Dysfunktionen neoliberaler Logik nicht lindern, sondern eher verlängern, gleichzeitig aber als Quelle „positiver Disruption" der Industrialisierung akademischer Arbeit und als Katalysator für eine Rückkehr zu „scholarly craftsmanship" genutzt werden könnten.
  *Verdict-Begründung:* Der Artikel berührt zwar das Themenfeld Generative KI + Bildung, behandelt aber akademische Arbeitsbedingungen und nicht die kulturelle, ästhetische oder kritisch-pädagogische Dimension von KI, die für die Forschungsprojekte (insb. AI4ArtsEd, kulturelle Resilienz, DiäS) relevant wäre. Die neoliberalismuskritische Perspektive hat eine oberflächliche Resonanz mit dem Freiheitsbegriff der kulturellen
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    - Der Artikel erscheint in Postdigital Science and Education, einer für Jörissens Diskursraum relevanten Zeitschrift, signalisiert aber eine Verschiebung des Journals hin zu Higher-Education-Labour-Stud
    - Die dialektische Figur, GAI als gleichzeitig neoliberales Verlängerungs- UND disruptives Potenzial zu rahmen, ist als Diskursbewegung im Feld bemerkenswert – auch wenn sie hier nicht theoretisch ausge

---

### #30 `merz` — Möslein-Tröppner, Bodo/Bernhard, Willi (2018). Digitale Gamebooks in der Bildung. Spielerisch lehren und lernen mit interaktiven Stories. Wiesbaden: Springer Ga  → beide `ignorieren`
_article_id_: `30634074641508931bfd8dcaf0ce345f`

**Opus** — `ignorieren`
  *Kernthese:* (Screening: ignorieren)
  *Verdict-Begründung:* Screening: Gamebooks in education, applied, no theory
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    _(keine)_

**MiMo** — `ignorieren`
  *Kernthese:* Der Beitrag ist eine Rezension des Buches „Digitale Gamebooks in der Bildung" (Möslein-Tröppner/Bernhard 2018) in merz | medien + erziehung. Das Buch stellt digitale Gamebooks als kollaborative, spielerische Methode der Wissensvermittlung vor und bietet eine Schritt-für-Schritt-Anleitung zur Erstellung eigener Gamebooks für Lehr-Lernkontexte, einschließlich Templates und Downloadmaterialien.
  *Verdict-Begründung:* Rein praxisorientierte Werkzeugvorstellung ohne theoretische oder kritische Anschlussfähigkeit: Kein Bezug zu post-digitaler Kulturtheorie, ästhetischer Bildung, kultureller Resilienz oder einem der aktiven Projekte. Keine Diskursrelevanz.
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    _(keine)_

---

### #32 `PCS` — Relational trouble and student victimisation at schools – categorisation, caring and institutionalisation  → beide `ignorieren`
_article_id_: `f87fc203d5897e90b5616ed8d120b55a`

**Opus** — `ignorieren`
  *Kernthese:* (Screening: ignorieren)
  *Verdict-Begründung:* Screening: school victimisation study, no theoretical connection
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    _(keine)_

**MiMo** — `ignorieren`
  *Kernthese:* Der Beitrag untersucht, wie schwedische Sekundarschulen Schüler*innen, die verschiedenen Formen von Gewalt und Missbrauch ausgesetzt waren, definieren und kategorisieren. Auf Basis von Interviews an sechs Schulen zeigt sich ein wiederkehrendes Muster der Definitionsschwierigkeit und Ambivalenz bei der Übergabe an externe Professionelle (Polizei, Sozialdienste), wobei die Kategorisierung selbst als sozio-politischer Kampf um die Rahmung „problematischer" Situationen analysiert wird.
  *Verdict-Begründung:* Der Beitrag ist dem Bereich der institutionellen Schulforschung/Soziologie der Schule zuzuordnen und behandelt die Kategorisierung von Mobbing/Gewaltfällen im institutionellen Alltag. Es bestehen keine erkennbaren Anknüpfungspunkte an die Forschungsfelder Kulturelle/Ästhetische Bildung, Medienpädagogik, Digitalität, kulturelle Resilienz oder posthumanistische Bildungstheorie. Die theoretischen Ref
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    _(keine)_

---

### #34 `merz` — Computerspiele im Kindes- und Jugendalter  → beide `ignorieren`
_article_id_: `368171a729ec5ac2f58b9027d128131b`

**Opus** — `ignorieren`
  *Kernthese:* (Screening: ignorieren)
  *Verdict-Begründung:* Screening: Entwicklungspsychologische Studie zu Serious Games, eher ang
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    _(keine)_

**MiMo** — `ignorieren`
  *Kernthese:* Der Beitrag fasst Forschungsbefunde zu geschlechtsspezifischen Präferenzen von Kindern und Jugendlichen bei Computerspielen (Genres, Spielanforderungen, Spielfiguren) zusammen und leitet daraus entwicklungspsychologische sowie medienkonzeptionelle Implikationen für Serious Games ab. Die Perspektive ist klinisch-psychologisch und gender-fokussiert; der Diskurs um Internet Gaming Disorder und therapeutische Spieleanwendungen steht im Zentrum.
  *Verdict-Begründung:* Der Beitrag bewegt sich im Feld der klinischen Entwicklungspsychologie und Gender-Forschung zu Computerspielen/Serious Games und hat weder konzeptionell noch diskursiv eine Verbindung zu Jörissens Forschungsfeldern (ästhetische/kulturelle Bildung, Post-Digitalität, kulturelle Resilienz, KI in der Kunstpädagogik).
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    _(keine)_

---

### #35 `SAE` — Artistic and Cultural Impacts of Western-Style Art Instruction in Yoruba Schools in Nigeria  → beide `lesenswert`
_article_id_: `d0fcbba89342a4b5470af8efab7a997e`

**Opus** — `lesenswert`
  *Kernthese:* Der Artikel untersucht die künstlerischen und kulturellen Auswirkungen westlich geprägter Kunstunterrichtspraktiken in Yoruba-Schulen in Nigeria. Er zeichnet den Einfluss westlicher Missionare, Kolonialpolitik und postkolonialer Bildungspolitik nach, diskutiert die modernistisch geprägte Kunstpädagogik von Aina Onabolu (die traditionelle Praktiken durch moderne Methoden ersetzen wollte) und stellt diesem Ansatz Übergangspraktiken indigener Yoruba-Künstler*innen gegenüber, die sowohl den Modernismus als auch etablierte traditionelle Methoden überschreiten. Als philosophische Grundlage für diese
  *Verdict-Begründung:* Der Artikel erweitert substantiell Jörissens Kritik an eurozentrischer Bildungstheorie durch konkrete empirische Fallstudie zur Kolonialisierung des Kunstunterrichts und bietet mit Transmodernismus eine theoretische Alternative, die das Konzept kultureller Resilienz bereichern kann.
  *Bezüge:*
    - _6WYG2HJG_: 
    - _A93WTEZQ_: 
  *Bemerkenswert:*
    - Der Artikel bietet eine konkrete historische Fallstudie zur Kolonialisierung von Kunstunterricht in Westafrika (Yoruba/Nigeria), die für postkoloniale Bildungstheorie hochrelevant ist.
    - Die Einführung von Transmodernismus (Dussel) als philosophische Alternative zu Modernismus/Traditionalismus stellt einen interessanten theoretischen Import dar, der über die übliche postkoloniale Krit
    - Die Analyse der "transitional practices" indigener Künstler*innen, die weder rein traditionalistisch noch modernistisch sind, zeigt Muster kreativer Resilienz, die auch für nicht-digitale Kontexte rel

**MiMo** — `lesenswert`
  *Kernthese:* Der Beitrag untersucht die künstlerischen und kulturellen Auswirkungen westlicher Kunsterziehung in yorubaischen Schulen Nigerias, beginnend mit christlichen Missionierungsaktivitäten über Kolonialzeit bis hin zu postkolonialen Bildungsreformen. Adejumo zeigt, wie traditionelle yorubaische Kunstpraktiken durch modernistische Methoden nach dem Vorbild Aina Onabolus verdrängt wurden, und stellt dem das transmodernistische Paradigma des Künstlers Yemi Bisiri gegenüber, das über sowohl traditionalistische als auch modernistische Grenzen hinausgeht. Der Beitrag schließt mit dem Vorschlag, Transmode
  *Verdict-Begründung:* Der Artikel behandelt die Dekolonisierung künstlerischer Bildung als historisch-materialen Prozess — ein Thema, das in Jörissens postkolonialer Bildungskritik (6WYG2HJG) und im Cultural-Resilience-Framework (3W9X5QLZ, ZSSJ4BPL) zentral verankert ist. Das Transmodernismus-Konzept (Dussel) bietet produktive Reibung mit der eigenen Rahmung kultureller Resilienz, insbesondere was die Rootedness-Dimens
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    - Der Beitrag führt Transmodernismus (Dussel) als alternatives philosophisches Rahmenwerk für Arts Education ein, das über die gängige Dichotomie von Modernismus vs. Traditionalismus in postkolonialen K
    - Die Fallstudie zeigt ein Muster der Verdrängung indigener Wissenssysteme durch koloniale Bildungsstrukturen (modernistische Kunsterziehung als zivilisatorisches Projekt), das strukturell parallel zu J

---

### #36 `merz` — Hass und Hetze im Internet - Analyse und Intervention  → beide `ignorieren`
_article_id_: `f32d82c001f2c005e38942b688469729`

**Opus** — `ignorieren`
  *Kernthese:* (Screening: ignorieren)
  *Verdict-Begründung:* Screening: Hass im Internet, pädagogische Intervention
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    _(keine)_

**MiMo** — `ignorieren`
  *Kernthese:* Der Beitrag stellt das Format „Counter Speech" als pädagogisches Interventionsformat vor, um Jugendliche für rassistische und rechtsextreme Äußerungen im Internet zu sensibilisieren und demokratische Gegenrede als Handlungsoption zu eröffnen. Er beschreibt, wie Engagement gegen Hass im Netz ambivalente Aufmerksamkeitsdynamiken erzeugt und wie (medien-)pädagogische Praxis dies aufgreifen kann.
  *Verdict-Begründung:* Der Text ist ein kurzer praxisorientierter Beitrag ohne theoretischen Tiefgang, der weder mit dem bildungs- oder kulturtheoretischen Zugriff noch mit den konkreten Themen (ästhetische Bildung, kulturelle Resilienz, Post-Digitalität, Digitalität) der Forschung von Jörissen verknüpft ist. Es gibt keine Anschlusspunkte für aktuelle Projekte.
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    - Der Beitrag ist 2017 erschienen und damit ein frühes Dokument der Counter-Speech-Diskussion im deutschsprachigen (medien-)pädagogischen Feld, das inzwischen erheblich weiterentwickelt wurde — als Disk

---

### #37 `Resilience` — &lt;em&gt;36.5 / Bodo Inlet&lt;/em&gt;, Kenya, 2019  → beide `ignorieren`
_article_id_: `bd3ab96b623ecc9f0983d6344be490a2`

**Opus** — `ignorieren`
  *Kernthese:* (Screening: ignorieren)
  *Verdict-Begründung:* Screening: Photo essay, no substantive content.
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    _(keine)_

**MiMo** — `ignorieren`
  *Kernthese:* Der Beitrag ist ein einzelnes Foto mit Bildunterschrift einer Performance-Veranstaltung in Bodo Village, Kenia (2019), publiziert in der Zeitschrift Resilience: A Journal of the Environmental Humanities. Es handelt sich nicht um einen Forschungsartikel mit Argument, Theorie oder Methodik, sondern um eine visuelle Dokumentation.
  *Verdict-Begründung:* Der Beitrag ist kein Forschungsartikel, sondern eine einzelne Fotodokumentation ohne argumentativen Gehalt. Keinerlei Anschluss an die Forschungsbereiche oder Projekte — die geographische Verbindung zu Kenia (AI4ArtsEd) ist rein zufällig und konzeptionell irrelevant.
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    _(keine)_

---

### #38 `BDS` — Data infrastructure studies on an unequal planet  → beide `lesenswert`
_article_id_: `1e9d80cf1ffe08ff1e628c04dcc82e47`

**Opus** — `lesenswert`
  *Kernthese:* Der Artikel analysiert Datenzentren als infrastrukturelle Werkzeuge des multinationalen digitalen Kapitalismus und argumentiert, dass deren Energie- und Extraktions-Dynamiken ein Assemblage von Umweltbeziehungen organisieren, das ungleiche kapitalistische Systeme durch Energie- und Umweltpolitiken reproduziert. Die energiezentrierte Analyse ermöglicht es, die planetaren ökologischen Folgen digitaler Daten für Subjekte jenseits einzelner Technologien zu theoretisieren.
  *Verdict-Begründung:* Der Artikel erweitert konkret Jörissens Argumente zu materiellen Grundlagen digitaler Technologien im Anthropozän und liefert empirische Phänomene für die Entwicklung kultureller Resilienz, insbesondere für das Widerstandsmoment (Resistance).
  *Bezüge:*
    - _BRYT324Y_: 
    - _A93WTEZQ_: 
  *Bemerkenswert:*
    - Fokus auf Energie-Rahmen als analytische Linse für Dateninfrastrukturen – verschiebt Perspektive von einzelnen Technologien zu systemischen Umweltwirkungen und Kapitalismus-Reproduktion.
    - Explizite Verbindung von Datenkolonialismus, Extraktivismus und ungleichen Kapitalismen – relevant für postkoloniale und resilienztheoretische Perspektiven in der Bildungsforschung.
    - Verbindung von Infrastrukturstudien mit Umweltgeographie – interdisziplinärer Import in Medien-/Bildungsforschung, der die materiell-energetische Dimension digitaler Technologien konkretisiert.

**MiMo** — `lesenswert`
  *Kernthese:* Der Artikel untersucht Rechenzentren (data centers) als Infrastrukturen multinationalen digitalen Kapitalismus und argumentiert, dass deren Energieverbindungen, CO₂-Fußabdrücke und extraktive Dynamiken ein Ensemble von Umweltbeziehungen organisieren, das ungleiche kapitalistische Systeme reproduziert. Der Autor plädiert dafür, die planetaren Umweltauswirkungen digitaler Dateninfrastrukturen jenseits einzelner Technologien zu denken und verbindet dabei Media Studies, Geographie und kritische Infrastrukturforschung.
  *Verdict-Begründung:* Der Artikel bearbeitet die materiellen und ökologischen Dimensionen digitaler Infrastrukturen, die Jörissen in eigenen Publikationen als blinder Fleck der Medientheorie ("immaterial bias") identifiziert hat. Die planetare Perspektive auf Digitalität und extraktiven Kapitalismus bietet zudem Anregungspotenzial für das Cultural-Resilience-Projekt, das planetare Krisen und post-anthropozäne Bildungst
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    - Der Artikel formuliert eine fundierte Kritik an der Unsichtbarkeit materieller und energetischer Grundlagen digitaler Infrastrukturen und deren planetarer Umweltfolgen — ein Themenfeld, das in der deu
    - Die Verbindung von data colonialism, extractivism und digitaler Infrastruktur über mehrere Disziplinen (Media Studies, Geographie, Soziologie) ist bemerkenswert als Fallbeispiel für genau die Art inte
    - Mit 115 Referenzen bietet der Artikel einen umfassenden Überblick über den Diskussionsstand in den kritischen Data/Infrastruktur Studies, der für Diskursübersicht nützlich ist.

---

### #39 `AIandSoc` — The hopes and fears of artificial intelligence: a comparative computational discourse analysis  → beide `scannen`
_article_id_: `483ad5bbf8ce98def4504f6156f854c4`

**Opus** — `scannen`
  *Kernthese:* (C-Tier: nur Screening, kein Agent)
  *Verdict-Begründung:* C-Tier: Screening-Pass, keine Agent-Analyse.
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    _(keine)_

**MiMo** — `scannen`
  *Kernthese:* Der Artikel untersucht mittels computergestützter Diskursanalyse (Topic Modeling, Sentiment-Analyse), wie drei Akteursgruppen — Parlamentarier*innen, Unternehmensberatungen und Reddit-Nutzer*innen — Künstliche Intelligenz diskursiv rahmen. Die Analyse zeigt drei koexistierende Diskurse: einen ethisch-gesellschaftlichen (Politik), einen transformativ-ökonomischen (Beratungen) und einen technisch-funktionalen (Laienexpert*innen), jeweils mit unterschiedlichen Hoffnungs- und Angst-Sentiments.
  *Verdict-Begründung:* Thematisch tangential (KI-Diskurs), aber weder theoretisch noch methodisch anschlussfähig an Jörissens Forschung. Die organisationssoziologische Perspektive und die deskriptive Diskurskartierung bieten kein konkretes Anregungspotenzial für laufende Projekte. Allenfalls als Diskursübersicht zur öffentlichen KI-Rahmung relevant.
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    - D
    - i
    - e
    -  
    - M

---

### #40 `EPT` — Bild, Bildung and the ‘romance of the soul’: Reflections upon the image of Meister Eckhart  → beide `ignorieren`
_article_id_: `34c6602217cbeafbd040e435a6b17a1c`

**Opus** — `ignorieren`
  *Kernthese:* (Screening: ignorieren)
  *Verdict-Begründung:* Screening: Religious ethics, image of Meister Eckhart, no digital/cultu
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    _(keine)_

**MiMo** — `ignorieren`
  *Kernthese:* Der Aufsatz rekonstruiert das Bildungskonzept Meister Eckharts ausgehend von der Plotinischen Bildhauer-Metapher: Bildung wird als spirituelle Transformation verstanden, die in der Rückwendung des Bildes zu seinem göttlichen Archetyp besteht (ent-bilden und Neugestaltung nach dem wahren Bild). Der Text argumentiert für eine nicht-reduktionistische, religiöse Dimension von Ethik und Ästhetik im Verhältnis zur moralischen Bildung des Selbst.
  *Verdict-Begründung:* Der Aufsatz bewegt sich in einer mittelalterlich-neuplatonischen Bildungstradition (Plotinus, Eckhart, Hegel), die mit den Forschungsprojekten und Publikationen des Forschenden keine substantielle Verbindung aufweist. Weder die neomaterialistisch-posthumanistische Rahmung kultureller Resilienz noch die post-digitale Ästhetik- und Medienbildungsperspektive werden berührt; auch der Diskurs über digi
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    - D
    - i
    - e
    -  
    - P

---

### #41 `merz` — Zwischen 0 und 1  → beide `lesenswert`
_article_id_: `7c14b4aa513c7730df4be67079ebfd67`

**Opus** — `lesenswert`
  *Kernthese:* Der Beitrag untersucht, wie Konzeptionen subjektivierender Digitalisierung in allgemein- und medienpädagogischen Forschungen dargestellt werden und hinterfragt, ob individuelle Souveränität angesichts des digitalen Wandels als medienpädagogische Zielkategorie noch tragfähig und praktisch umsetzbar ist.
  *Verdict-Begründung:* Der Artikel setzt sich explizit mit Jörissens Publikation zur Subjektivation in post-digitaler Kultur auseinander und hinterfragt medienpädagogische Zielkategorien, die Jörissens relationale Bildungstheorie direkt betreffen und seine Kritik individualistischer Subjektkonzeptionen aufgreifen.
  *Bezüge:*
    - _XTJR5DRD_: 
    - _ZSSJ4BPL_: 
  *Bemerkenswert:*
    - Der Beitrag zitiert explizit Jörissens Arbeit zur Subjektivation in der post-digitalen Kultur, was eine direkte Auseinandersetzung mit seinen Argumenten signalisiert.
    - Die Fragestellung nach der (Un-)Tragfähigkeit individueller Souveränität im digitalen Wandel berührt zentrale Spannungsfelder in Jörissens relationaler Bildungstheorie und Kritik individualistischer S

**MiMo** — `lesenswert`
  *Kernthese:* Der Beitrag untersucht, wie Konzeptionen subjektivierender Digitalisierung in der allgemeinen und medienpädagogischen Forschung dargestellt werden, und fragt, ob individuelle Souveränität angesichts des digitalen Wandels als medienpädagogische Zielkategorie noch konzeptionell tragfähig und praktisch umsetzbar ist. Die Autoren rekonstruieren verschiedene Positionen zum Verhältnis von Subjektivierung und Digitalität und diskutieren die Reichweite souveränitätsorientierter Ansätze kritisch.
  *Verdict-Begründung:* Der Beitrag zitiert Jörissens Arbeit zu Subjektivation und ästhetischer Freiheit explizit und setzt sich mit der medienpädagogischen Souveränitätsdebatte auseinander. Für das DiäS-KuBi-Projekt ist die kritische Frage nach der Tragfähigkeit von Souveränität als Zielkategorie unmittelbar relevant, und die dekonstruktive Position des Zweitautors (Böhmer) bietet produktives Reibungspotenzial zur eigen
  *Bezüge:*
    - _XTJR5DRD_: 
  *Bemerkenswert:*
    - [
    - "
    - D
    - e
    - r

---

### #42 `REPCS` — The (academic) chair: Embodied relations of arrival, place, and hospitality  → beide `scannen`
_article_id_: `1fd641480a35c7e58c8865cb887e2846`

**Opus** — `scannen`
  *Kernthese:* Der Artikel untersucht den Stuhl als alltäglichen Gegenstand durch die Linse feministischer Neuer Materialismen und Affekttheorie. Die Autorinnen argumentieren, dass Stühle vitale Objekte mit affektiven und symbolischen Bedeutungen sind, die verkörperte Praktiken des "Mattering" und Fragen von Ankunft, Ort und Gastfreundschaft aufwerfen. Anhand persönlicher Erfahrungen und experimentellen Schreibens entfalten sie, wie Stühle Beziehungen zwischen Körpern und nicht-menschlichen Akteuren konstituieren.
  *Verdict-Begründung:* Der Artikel berührt thematisch Neue Materialismen (geteilter Referenzrahmen), bietet aber keine konkreten argumentativen Anschlüsse an Jörissens spezifische Publikationen zu Digitalität, kultureller Resilienz oder KI.
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    - Kreative Anwendung neomaterialistischer Theorie auf einen banalen Alltagsgegenstand (Stuhl) im akademisch-organisationalen Kontext; untersucht, wie institutionelle Sitzordnungen verkörperte Macht- und

**MiMo** — `scannen`
  *Kernthese:* Der Aufsatz nutzt feministischen Neuen Materialismus und Affekttheorie, um den akademischen Stuhl als lebendiges Objekt zu lesen und so verkörperte Beziehungen von Ankunft, Ort und Gastlichkeit in der akademischen Arbeit zu reflektieren. Persönliche Erfahrungen und experimentelles Schreiben werden eingesetzt, um materielle Beziehungen zwischen Körpern und nicht-menschlichen Verwandten sichtbar zu machen.
  *Verdict-Begründung:* Obwohl feministischer Neuer Materialismus im theoretischen Repertoire des Forschers verankert ist, behandelt der Aufsatz einen völlig anderen Gegenstandsbereich (akademische Möbel, Gastlichkeit, persönliche Reflexion) ohne Anschluss an Bildungstheorie, kulturelle Resilienz, Digitalität oder ästhetische Bildung. Keine produktive Reibung für aktuelle Projekte erkennbar.
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    _(keine)_

---

### #43 `MedienPaed` — Zwischen Optimierung und ludischen Gegenstrategien  → beide `lesenswert`
_article_id_: `8401709869b600169d595df5035231a7`

**Opus** — `lesenswert`
  *Kernthese:* Der Beitrag analysiert post-digitale Regime der Optimierung auf Social Media Plattformen am Beispiel TikTok-Nutzung zweier 12-jähriger Mädchen aus der DiKuJu-Studie. Er zeigt, wie algorithmisch gesteuerte Optimierungsappelle strukturell in Plattformen eingelagert sind und spezifische Affizierungsrelationen erzeugen. Die Analyse verdeutlicht, dass an der Schnittstelle zwischen Plattform und Jugendlichen Freundschaft gleichzeitig in Prozesse der Optimierung und ludische Gegenstrategien eingebettet ist.
  *Verdict-Begründung:* Der Beitrag erweitert und importiert konkrete Konzepte aus Jörissens Forschung: Er vertieft die empirische Fallstudie aus der gemeinsamen DiKuJu-Studie und operationalisiert das Konzept des 'Regime des Komputablen' für die TikTok-Analyse. Als Koautorin ist Anna Carnap direkt an der Weiterentwicklung der Forschung beteiligt.
  *Bezüge:*
    - _8MLTG7RB_: 
    - _M8RZJRHN_: 
  *Bemerkenswert:*
    - Empirische Vertiefung und Weiterentwicklung der DiKuJu-Studie durch eine der Koautorinnen (Anna Carnap), was eine interne Fortführung der Forschung darstellt.
    - Kombination von Optimierungslogik und ludischen Gegenstrategien als analytische Perspektive für die Erforschung post-digitaler Jugendkulturen - eine innovative Erweiterung der Diskussion um widerständ
    - Konkrete Anwendung von Jörissens Konzept des 'Regime des Komputablen' auf Social Media Plattformen, was eine empirische Operationalisierung des theoretischen Rahmens ermöglicht.

**MiMo** — `lesenswert`
  *Kernthese:* Der Beitrag von Flasche und Carnap untersucht anhand der Plattform TikTok, wie post-digitale Optimierungsregime algorithmisch in Social-Media-Praktiken eingelagert sind und welche Affizierungsrelationen sie erzeugen. Am Beispiel zweier 12-jähriger Mädchen aus der DiKuJu-Studie wird rekonstruiert, wie Freund*innenschafts- und Positionierungspraktiken gleichzeitig in Optimierungsdynamiken und ludische Gegenstrategien eingebettet sind.
  *Verdict-Begründung:* Der Beitrag baut direkt auf Jörissens Konzept des ‚Regime des Komputablen‘ und der post-digitalen Jugendkulturanalyse auf, konkretisiert beides am Fall TikTok und entstammt dem eigenen Forschungsfeld der DiKuJu-Studie. Für das DiäS-KuBi-Projekt (digitale-ästhetische Souveränität) liefert er zudem eine empirisch fundierte Analyse algorithmischer Optimierungsdynamiken und ludischer Gegenstrategien a
  *Bezüge:*
    - _M8RZJRHN_: 
    - _8MLTG7RB_: 
    - _XTJR5DRD_: 
  *Bemerkenswert:*
    - Die Autorinnen sind enge Mitarbeiterinnen von Jörissen und Teil des Forschungszusammenhangs mehrerer aktiver Projekte (ComeArts, DiäS-KuBi). Der Beitrag entsteht also direkt aus dem eigenen Forschungs
    - Der Beitrag verknüpft Optimierungskritik (Foucaults Gouvernementalität, Bröcklings unternehmerisches Selbst) mit dem Konzept ludischer Gegenstrategien — eine produktive theoretische Spannung, die für 
    - Die Analyse von TikTok als Fall algorithmischer Optimierungsroutinen bietet eine präzise empirische Konkretisierung der in LEHKCH59 (Wahrnehmungskrisen) diskutierten Umweltfaktizität (Environmentalitä

---

### #45 `MedienPaed` — Dream Machine  → beide `lesenswert`
_article_id_: `2559fb92116e641805878c2be9485fb4`

**Opus** — `lesenswert`
  *Kernthese:* Der Artikel beschreibt ein künstlerisch-forschendes Projekt mit Studierenden, die mithilfe von XR-Technologien (Luma 3D Capture) ästhetische Utopien für nachhaltige Stadtentwicklung im Anthropozän entwerfen. Der Beitrag fragt nach den Potenzialen hochimmersiver digitaler Medientechnologien für zukunftsorientiertes Denken und deren Einsatz im Kunstunterricht.
  *Verdict-Begründung:* Der Artikel erweitert konkret das Konzept der Post Internet Art Education und Cultural Hacking aus Meyer/Jörissen 2018 durch Anwendung auf XR-Technologien und nachhaltige Stadtutopien, was eine substantielle Ressource für Jörissens Arbeit zur post-digitalen ästhetischen Bildung darstellt.
  *Bezüge:*
    - _Y3R8HWUA_: 
  *Bemerkenswert:*
    - Direkte Zitation von Meyer/Jörissen 2018 ('Post Internet Art Education') – explizite Auseinandersetzung mit einem zentralen Text des Forschers.
    - Verbindung von Anthropozän-Diskurs, Nachhaltigkeit und XR-Technologien in der kunstpädagogischen Praxis – ungewöhnliche Konstellation.
    - Fokus auf 'hostile design'/Gentrifizierung und Gegenentwürfe via digitaler Utopien – konkrete politisch-Lästhetische Intervention.
    - Anwendung des Cultural-Hacking-Konzepts auf konkrete XR-Technologien und Stadtutopien – operationalisiert ein theoretisches Konzept für die Praxis.

**MiMo** — `lesenswert`
  *Kernthese:* Der Beitrag untersucht künstlerisch-forschende Potenziale immersiver XR-Technologien (insbesondere Luma 3D Capture) für die Gestaltung urbaner Räume im Anthropozän. Studierende identifizieren städtische Problemlagen, entwerfen aus inklusiver Perspektive künstlerisch-ästhetische Utopien und reflektieren kritisch die Bildungspotenziale der eingesetzten Technologien für den Kunstunterricht.
  *Verdict-Begründung:* Der Beitrag verbindet spekulativ-utopisches Design mit XR-Technologien im Horizont des Anthropozäns und adressiert damit strukturell das Resourcefulness-Moment des Cultural-Resilience-Projekts (kollektive Futurabilität durch kreative Welthervorbringung). Die direkte Zitation von Meyer & Jörissen 2018 sowie die kritische Haltung gegenüber digitalen Werkzeugen als bloße Instrumente machen ihn für di
  *Bezüge:*
    - _Y3R8HWUA_: 
  *Bemerkenswert:*
    - Der Beitrag kombiniert künstlerische Forschung mit inklusiver Perspektive und spekulativem Stadt-Design via XR – eine für die Medienpädagogik seltene Konstellation, die die Schnittstelle von Urban Stu
    - Die kritische Beleuchtung der Luma 3D Capture-App als Bildungsinstrument (nicht nur als Tool) entspricht dem in mehreren Projekten verfolgten Ansatz, digitale Technologien als kulturelle Apparate zu b
    - Gernot Böhme (Atmosphäre) wird referenziert – dies ist bemerkenswert, da Böhmes Atmosphärenbegriff für das Konzept der Rootedness im Cultural-Resilience-Strang produktiv wäre (sinnlich-leibliches Gewa

---

### #46 `BDS` — Dashboard stories: How narratives told by predictive analytics reconfigure roles, risk and sociality in education  → beide `lesenswert`
_article_id_: `3fbfe623753fe0802b92c9e47ad10a96`

**Opus** — `lesenswert`
  *Kernthese:* Der Artikel untersucht, wie predictive Analytics in der Bildung – insbesondere über Data Dashboards – persuasive Narrative erzeugt, die Lehrer*innen als Manager, Schüler*innen als Risiken rekonfigurieren und Sozialität auf maschinenlesbare Interaktionen reduzieren. Durch narrative Analyse eines führenden Systems zeigt er, wie Dashboards Kausalität zwischen visualisierten ‚Fakten‘ implizieren und strukturelle Ungleichheiten unsichtbar machen. Abschließend werden Möglichkeiten skizziert, solche Geschichten zu unterbrechen und umzugestalten.
  *Verdict-Begründung:* Der Artikel liefert konkrete empirische und theoretische Ressourcen, die Jörissen bereits in seiner eigenen Arbeit importiert hat – die Analyse von Jarke und Macgilchrist wird in Jörissens Publikation zitiert und für seine Argumentation zur Invisibilisierung durch Dashboards genutzt.
  *Bezüge:*
    - _62A5VC7E_: 
  *Bemerkenswert:*
    - Narratologische Analyse von Data Dashboards als Methode, um persuasive und kausale Implikationen von Lernanalysesystemen zu entschlüsseln.
    - Fokus auf die Rekonfiguration von pädagogischen Rollen (Lehrer als Manager) und Sozialität durch predictive Analytics – ein konkreter Beitrag zur Debatte um Datafizierung und educational governance.

**MiMo** — `lesenswert`
  *Kernthese:* Der Artikel untersucht, wie Predictive-Analytics-Dashboards in Bildungskontexten narrative Strukturen erzeugen, die Lehrkräfte zu Manager*innen und Schüler*innen zu Risikokategorien umformen. Die Autorinnen argumentieren, dass diese Dashboards durch ihre räumlich-zeitlichen Darstellungen, Figurenkonstellationen und Kausalitätsimplikationen Geschichten erzählen, die strukturelle Ungleichheiten unsichtbar machen und Sozialität auf maschinenlesbare Interaktionen reduzieren.
  *Verdict-Begründung:* Der Artikel liefert eine empirisch konkrete narratologische Analyse von Dashboard-Systemen, die die von Jörissen (2025) diagnostizierte Invisibilisierung durch datenanalytische Instrumente auf Mikroebene bestätigt und erweitert. Die ungewöhnliche methodologische Perspektive (Erzähltheorie auf Algorithmen) sowie die Relevanz für das DiäS-KuBi-Projekt und die Diskussion um Digitalität in der Schulku
  *Bezüge:*
    - _62A5VC7E_: 
    - _BXCLZ5M7_: 
  *Bemerkenswert:*
    - D
    - i
    - e
    -  
    - n

---

### #47 `MedienPaed` — Für eine ‹technologiebewusste Medienpädagogik› jenseits der Digitalisierung  → beide `lesenswert`
_article_id_: `1ff89357567aad3e039e6656e91c15ab`

**Opus** — `lesenswert`
  *Kernthese:* Der Artikel plädiert für eine technologiebewusste Medienpädagogik, die digitale Technologien nicht nur instrumentell versteht, sondern als eigen- und widerständige Größen. Er entwickelt eine technikgenetische Position, die digitale Technologieentwicklung als sukzessive Ausbildung technischer Objekte und damit verbundener praktischer und soziokultureller Milieus begreift, wobei Technologien als kulturhistorisch kontingenter Rückgriff auf «Archive der Technizität» verstanden werden. Exemplarisch analysiert er ChatGPT und die Experience API (xAPI).
  *Verdict-Begründung:* Der Artikel erweitert Jörissens relationale Medienbildungskonzeption substantiell durch eine technikgenetische Perspektive, die explizit auf seine Arbeiten Bezug nimmt und diese weiterentwickelt.
  *Bezüge:*
    - _U6RW4WMN_: 
  *Bemerkenswert:*
    - Artikel zitiert explizit zwei Jörissen-Publikationen zur Medienbildung und zu Critical Software Studies - deutet auf direkte argumentative Auseinandersetzung hin.
    - Entwickelt ein spezifisches technikgenetisches Konzept der «Archive der Technizität», das kulturhistorische Kontingenz digitaler Technologien betont.
    - Operationalisiert theoretische Position an zwei konkreten technischen Objekten (ChatGPT, xAPI) mit pädagogischer Relevanz.

**MiMo** — `lesenswert`
  *Kernthese:* Der Beitrag von Richter und Allert plädiert für eine „technologiebewusste Medienpädagogik", die Technik als eigenständige und widerständige Größe ernst nimmt, statt sie im Diskurs um Digitalisierung und Postdigitalität zu vergessen. Sie entwickeln eine technikgenetische Position, wonach digitale Technologien als kulturhistorisch kontingente Rückgriffe auf „Archive der Technizität" zu verstehen sind, und illustrieren dies an ChatGPT und Experience API (xAPI). Im Zentrum steht eine analytische Unterscheidung zwischen der spezifischen Struktur/Operationsweise einer Technologie und ihrer praktisch
  *Verdict-Begründung:* Der Beitrag zitiert Jörissen' Arbeit direkt und arbeitet im selben Diskursraum medienpädagogischer Materialitätstheorie. Für das Projekt DiäS-KuBi (Digitale-Ästhetische Souveränität) ist die technikgenetische Perspektive als konzeptioneller Gegenpol oder Ergänzung zur eigenen Digitalitätstheorie von Anregungspotenzial. Die explizite Auseinandersetzung mit der eigenen Software- und Materialitätsarb
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    - Der Beitrag zitiert sowohl Bettinger/Jörissen 2022 (Medienbildung) als auch Jörissen/Verständig 2016 (Code, Software und Subjekt) explizit und setzt sich damit als Referenzrahmen auseinander — ein dir
    - Das Konzept der ‹Archive der Technizität› als kulturhistorisch akkumulierte algorithmische Techniken und repräsentationale Formen bietet einen eigenständigen theoretischen Import, der die Cultural-Res
    - Christoph Richter und Heidrun Allert sind zentrale Akteure im Diskurs um Digitalität und Medienbildung in der Erziehungswissenschaft — dieser Beitrag ist ein Marker für die Verschiebung der Diskussion
    - Die konkreten Technikanalysen (ChatGPT-Architektur, xAPI-Spezifikation) illustrieren einen Anspruch an medienpädagogische Technologiekompetenz, der für das DiäS-Projekt (Digitale-Ästhetische Souveräni

---

### #49 `MedienPaed` — Medienbildung und Schulkultur. Implikationen der Verbindung von Medienbildung und Schulkultur für die Medienpädagogik  → beide `lesenswert`
_article_id_: `97892a7d2926c8f739d343198f2fdcc5`

**Opus** — `lesenswert`
  *Kernthese:* Der Beitrag diskutiert die Disziplinierung der Medienpädagogik am Beispiel Schule und verbindet eine poststrukturalistisch gedachte Medienbildung (Entdichotomisierung von Subjekt und Medien) mit dem Konzept der Schulkultur. Dadurch wird eine neue, kritische Perspektive eröffnet, die bisherige medienpädagogische Theoreme, insbesondere das Medienkompetenzkonzept, in Frage stellt.
  *Verdict-Begründung:* Der Artikel zitiert explizit eine gemeinsame Publikation von Jörissen (Fromme & Jörissen 2010) und setzt sich damit auseinander; dies erfordert eine inhaltliche Prüfung der Aufnahme. (Verifikation ohne Ergebnis abgebrochen, Assessment-Verdict übernommen)
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    _(keine)_

**MiMo** — `lesenswert`
  *Kernthese:* Der Beitrag von Grünberger und Münte-Goussar (2017) diskutiert die Konstituierung der Medienpädagogik als Disziplin am Beispiel von Schule als genuin pädagogischem Ort. Er verbindet ein poststrukturalistisches Medienbildungskonzept (Entdichotomisierung von Subjekt und Medien) mit dem Schulkultur-Konzept (Helsper) zu einer holistischen, kritischen Perspektive, die das etablierte Medienkompetenzkonzept (Baacke) als unzureichend für die Erfassung weitreichender Medialisierungsprozesse in Schule in Frage stellt.
  *Verdict-Begründung:* Der Artikel adressiert ein Kernthema von Jörissens Forschung — die Verbindung von Medienbildung und Schulkultur — und zitiert seine Arbeit explizit. Er ist insbesondere für die Projekte DiäS-KuBi (Lehrkräfte-Kompetenz an der Schnittstelle Digitalität und Schulkultur) und MetaKuBi (institutionelle Transformation in der Kulturellen Bildung) relevant. Die poststrukturalistische Rahmung und der Fokus 
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    - Der Beitrag zitiert Fromme & Jörissen 2010 explizit als Referenzarbeit im Feld der Medienbildung — dies bestätigt, dass Jörissens Medienbildungsbegriff im deutschsprachigen Diskurs als zentraler Bezug
    - Der Versuch, Medienbildung und Schulkultur systematisch zusammenzuführen, markiert 2017 einen noch seltenen Brückenschlag zwischen der medienpädagogischen und der erziehungswissenschaftlichen Schulkul
    - Die Kritik am Medienkompetenzkonzept und der Vorschlag einer offenen, nicht vorschnell abgrenzenden medienpädagogischen Perspektive sind diskursanalytisch bemerkenswert als Positionierung innerhalb de

---

### #50 `EERJ` — De-individualising the ‘NEET problem’: An ecological systems analysis  → beide `ignorieren`
_article_id_: `4e2d0cd620236203bfab2da8c4bda4b3`

**Opus** — `ignorieren`
  *Kernthese:* (Screening: ignorieren)
  *Verdict-Begründung:* Screening: NEET problem, ecological systems, no theoretical overlap
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    _(keine)_

**MiMo** — `ignorieren`
  *Kernthese:* Der Artikel untersucht mittels einer qualitativen Längsschnittstudie in London, warum junge Menschen nach dem Schulabschluss in den NEET-Status (Not in Education, Employment or Training) geraten. Gestützt auf Bronfenbrenners ökologische Systemtheorie wird argumentiert, dass die Individualisierung des „NEET-Problems" verfehlt ist; stattdessen müssen strukturelle Bedingungen (Kürzungen im Bildungsbereich, Arbeitsmarkttransformationen, sozioökonomische Deprivation) als Ursachen verstanden werden.
  *Verdict-Begründung:* Der Artikel arbeitet in einem deutlich anderen Diskursraum (britische Jugendübergangsforschung, NEET-Policy, Bronfenbrenner) als Jörissens Forschung. Es gibt keine substanziellen Verbindungen zu dessen Publikationen oder laufenden Projekten — weder zu kultureller Resilienz, postdigitalen Jugendkulturen, noch zu ästhetischer Bildung oder Medienpädagogik.
  *Bezüge:*
    _(keine)_
  *Bemerkenswert:*
    - D
    - e
    - r
    -  
    - A

---
