# Q-Check Trends — Mistral Large vs MiMo-Baseline

**Datum:** 2026-05-23T14:44:36.019089
**Stichprobe:** 3 Cluster × bis zu 40 Artikel
**Mistral-Konfig:** `mistral-large-latest` nativ via api.mistral.ai (EU/DSGVO), max_tokens=16000

## Übersicht

| Cluster | Artikel | Mistral $ | Mistral chars | Mistral cache | MiMo $ | MiMo chars | Jaccard |
|---|---:|---:|---:|---:|---:|---:|---:|
| digitale_kultur | 40 | $0.0131 | 13,094 | 0% | $0.0159 | 9,518 | 0.17 |
| medienpaed | 40 | $0.0140 | 12,955 | 0% | $0.0210 | 11,406 | 0.19 |
| erziehungswiss | 40 | $0.0136 | 14,697 | 0% | $0.0199 | 10,948 | 0.19 |

**Summen:** Mistral $0.0406  ·  MiMo (recycled) $0.0568  ·  Faktor ~1/1.40
**Avg term-Jaccard:** 0.188

## Output-Vergleich (volle Markdown-Texte)

### Cluster: `digitale_kultur` — Digitale Kultur

_Artikel:_ 40  ·  _Jaccard:_ 0.17

#### Mistral Large ($0.0131, 13,094c, cache=0%, 72.7s)

# Trendbeobachtung: Digitale Kultur (2024–2026)

## Überblick
Das Fenster umfasst 40 Beiträge aus sechs Journalen, wobei *AI & Society* (12) und *STHV* (14) dominieren, gefolgt von *DCE* (5) und *BDS* (6). Auffällig ist die starke Präsenz **kritischer Reflexionen zu KI und algorithmischer Steuerung** – nicht als technologische Innovation, sondern als **soziotechnische Infrastruktur**, die Machtverhältnisse, epistemische Ordnungen und ethische Grundfragen neu verhandelt. Gleichzeitig häufen sich Beiträge, die **postdigitale Phänomene** (z. B. moralische Präsenz, räumliche Rhetorik, queere Kinship) jenseits von Technologiezentrismus untersuchen. Methodisch fallen **computergestützte Diskursanalysen** (TF-IDF, VADER) und **ethnografische Zugänge** auf, die digitale Praktiken in konkreten Kontexten verorten.

---

## Konsolidierende Diskurse

### 1. **Kritische KI-Literacy: Von Skills zu normativen Architekturen**
Der Diskurs um KI-Kompetenz verschiebt sich von instrumentellen Fähigkeiten („Wie nutze ich KI?“) zu **kritisch-reflexiven und strukturellen Fragen** („Wie richtet KI Handlungsräume aus?“). Zentral ist die Unterscheidung zwischen *operationalen* und *normativen* Dimensionen von KI-Alignment.

- **Scheibenzuber et al. (2026, #7)**: *Scenario-Based AI Literacy Scale (SAILS)* – Validierung eines Messinstruments, das zwischen **instrumentellen** (z. B. KI für Präsentationen nutzen) und **kritisch-reflexiven Skills** (z. B. Deepfakes erkennen) unterscheidet. Zeigt, dass traditionelle Digitalkompetenzen nicht auf KI übertragbar sind.
- **Josifović & Noller (2026, #12)**: *Agency and Alignment* – Argument für eine **normative Architektur** der Mensch-KI-Interaktion, die KI als *teleologische Erweiterung* menschlicher Handlungsfähigkeit fasst (nicht als autonomes Subjekt). Alignment wird als **Einbettung in justifikatorische Praktiken** (z. B. Recht) konzipiert.
- **Okoro (2026, #13)**: *Comparative Book Review* – Gegenüberstellung von **computationaler Formalisierung** (Kearns/Roth) und **soziotechnischer Governance** (Shin). Konsens: KI-Ethik erfordert **mehrschichtige Interventionen** – von algorithmischen Constraints bis zu institutionellen Praktiken.
- **Hasan (2026, #15)**: *Hard to Find, Harder to Understand* – Dokumentenanalyse von 20 KI-Tools für Lehrkräfte zeigt **systematische Intransparenz**: Kein Tool offenbart Trainingsdaten oder Limitationen. Kritik an der **„Blackbox-Pädagogik“** generativer KI.

**Charakteristik**: Der Cluster verbindet **empirische Messung** (SAILS) mit **philosophischer Fundierung** (Alignment als normative Praxis) und **praktischer Kritik** (Transparenzdefizite). Autor*innen wie Josifović und Noller prägen eine Position, die KI nicht als Werkzeug, sondern als **infrastrukturelle Macht** begreift.

---

### 2. **Postdigitale Pädagogik: Moralische Präsenz und räumliche Rhetorik**
Ein zweiter Strang untersucht **Bildungspraktiken in postdigitalen Räumen**, wobei klassische Konzepte (Agency, Raum, Zugehörigkeit) **phänomenologisch und ethisch neu verhandelt** werden. Technologie wird hier nicht als Medium, sondern als **Bedingung der Möglichkeit von Erfahrung** analysiert.

- **McBride et al. (2026, #1)**: *„Hands Off“ Learning* – Kritik an der **algorithmischen Wende** in der Hochschullehre: Curricula, Bewertung und Didaktik würden zunehmend von **„screen-biased, information-centric schemes“** dominiert. Forderung nach **Resistenz durch pädagogische Präsenz**.
- **Furnes (2026, #3)**: *„Here I Am“* – Einführung des **Hineni-Konzepts** (Lévinas/Buber) als **ethische Haltung** in digitalen Räumen: Moralische Präsenz als **Voraussetzung für Bildung**, nicht als deren Ergebnis. Relevant für Debatten um **digitale Trauma-Begleitung**.
- **Stewart & Le (2026, #4)**: *Mapping Belonging* – **Relationalität als Schlüssel** für Zugehörigkeit in digitalen/physischen Lernumgebungen. Empirische Studie zeigt, dass **hybride Räume** Zugehörigkeit nicht automatisch fördern, sondern **institutionelle Praktiken** (z. B. Mentoring) erfordern.
- **Lucia (2026, #2)**: *Framing Space* – Rhetorische Analyse von Apples *Vision Pro*-Marketing: **Lefebvre/Soja** werden genutzt, um zu zeigen, wie digitale Räume als **„dritte Räume“** konstruiert werden, die **soziale Hierarchien** (Elitismus) naturalisieren.

**Charakteristik**: Der Cluster arbeitet mit **phänomenologischen und poststrukturalistischen Theorien** (Lévinas, Lefebvre, Biesta), um **Bildung als ethische Praxis** jenseits von Technologieoptimismus oder -pessimismus zu denken. Autor*innen wie Furnes und Stewart verbinden **empirische Forschung** (Zugehörigkeit, Rhetorik) mit **normativen Ansprüchen** (Präsenz, Relationalität).

---

### 3. **Algorithmen als Weltmacher: Von der Multiplizität zur Governance**
Algorithmen werden nicht mehr als neutrale Werkzeuge, sondern als **aktive Produzenten sozialer Ordnungen** analysiert. Der Fokus liegt auf **ihren multiplen Existenzweisen** und der Frage, wie sie **Handlungsräume strukturieren**.

- **Schrøder et al. (2026, #24)**: *A Tool, Connector, or Data Processor* – Ethnografie der Entwicklung eines **Kindeswohl-Algorithmus** in Dänemark. Identifiziert drei **„Algorithm-Worlds“**:
  1. Algorithmus als **docile tool** (Fallbearbeitung),
  2. als **data-connector** (öffentliche Infrastruktur),
  3. als **data processor** (rechtliche Bewertung).
  Argument: Algorithmen sind **keine singulären Entitäten**, sondern **heterogen konstruiert**.
- **Talašová (2026, #6)**: *The Data of Care* – Analyse der **Datenfizierung von Care-Arbeit**: Algorithmen schaffen **„moralische Temporalitäten“** (z. B. Reaktionszeiten auf Sensoren), die **intergenerationelle Machtverhältnisse** verschieben (jüngere Familienmitglieder gewinnen „temporale Autorität“).
- **Xing & Zheng (2026, #37)**: *Patchwork Surveillance* – Studie zu Chinas *Health Code Systems*: Zeigt, wie **street-level actors** (lokale Behörden) Algorithmen **umdeuten**, um **Accountability-Labor** zu betreiben. Algorithmen werden **nicht als Überwachungstools**, sondern als **Werkzeuge der Rechenschaftsvermeidung** genutzt.

**Charakteristik**: Der Cluster verbindet **STS-Perspektiven** (Multiplizität, Akteur-Netzwerk-Theorie) mit **kritischer Governance-Forschung**. Autor*innen wie Schrøder und Talašová zeigen, dass Algorithmen **soziale Realitäten nicht abbilden, sondern produzieren** – und dass ihre Wirkung von **lokalen Praktiken** abhängt.

---

## Differenzierungen und offene Spannungen

### 1. **KI-Ethik: Formalisierung vs. soziotechnische Governance**
Die Debatte um KI-Ethik spaltet sich in zwei Lager:
- **Computationale Formalisierung** (Kearns/Roth, rezensiert in #13): Ethische Probleme als **technisch lösbar** (z. B. durch mathematische Constraints).
- **Soziotechnische Governance** (Shin, rezensiert in #13; Hasan #15): Bias und Schaden als **emergente Eigenschaften dynamischer Systeme**, die **institutionelle Reformen** erfordern.

**Beiträge im Konflikt**:
- **Lin et al. (2026, #9)**: *Policy Analysis of Generative AI* – Nutzt **TF-IDF/VADER**, um US-Politik zu analysieren. Forderung nach **„narrowly tailored provenance requirements“** (technische Lösung).
- **Martineau et al. (2026, #39)**: *ChatGPT, a Colonialist Agent* – Argumentiert, dass KI **kommunikatives Handeln kolonisiert** (Habermas) und daher **auf instrumentelle Nutzung beschränkt** werden muss.

**Spannung**: Während #9 **regulatorische Lösungen** vorschlägt, warnt #39 vor der **Illusion technischer Kontrolle** und fordert **soziale Grenzen** für KI.

---

### 2. **Transparenz in KI: Dokumentenanalyse vs. ethnografische Kritik**
Die Forderung nach Transparenz wird unterschiedlich operationalisiert:
- **Hasan (2026, #15)**: Dokumentenanalyse von 20 KI-Tools zeigt **systematische Intransparenz** (fehlende Angaben zu Trainingsdaten, Limitationen).
- **Schrøder et al. (2026, #24)**: Ethnografie zeigt, dass Transparenz **nicht ausreicht**: Selbst wenn Algorithmen erklärt werden, bleibt ihre **soziale Einbettung** (z. B. in rechtliche Praktiken) undurchsichtig.

**Divergenz**: #15 fordert **mehr Information**, #24 argumentiert, dass **Transparenz allein keine Machtverhältnisse aufdeckt**.

---

### 3. **Digitale Agency: Individuelle Skills vs. strukturelle Bedingungen**
Der Agency-Diskurs oszilliert zwischen **individueller Handlungsfähigkeit** und **struktureller Einbettung**:
- **Rikala et al. (2026, #5)**: *Multilayered Framework of Digital Agency* – Systematischer Review identifiziert **drei Ebenen** von Agency: individuelle, soziale, institutionelle.
- **Cabral (2026, #8)**: *Reinterpreting ‘Noncompliance’* – Argumentiert, dass **„Noncompliance“** von ehemals inhaftierten Jugendlichen **strategische Agency** in einem System **„strukturierter Verletzungen“** ist.

**Spannung**: Während #5 Agency als **messbare Kompetenz** fasst, zeigt #8, dass Agency **nur im Kontext von Machtverhältnissen** verstanden werden kann.

---

## Methodische Beobachtungen

1. **Computergestützte Diskursanalyse**:
   - **Lin et al. (2026, #9)**: TF-IDF/VADER zur Analyse von **287 News-Artikeln + 3921 Reddit-Posts** (KI-Politik in den USA).
   - **Steinhardt & Göbel (2026, #34)**: Quantitative/qualitative Analyse von **72.500 Weibo-Posts** (Social Credit System).
   - **Trend**: Zunahme **großflächiger Textanalysen** mit **Sentiment-Tools**, um **öffentliche Diskurse** zu KI zu kartieren.

2. **Ethnografische Methoden**:
   - **Schrøder et al. (2026, #24)**: Ethnografie der **Algorithmen-Entwicklung** in Dänemark.
   - **Chacko (2026, #16)**: **Botanische Ethnografie** („Making Queer Kin in the Greenhouse“) als Methode, um **posthumane Pädagogik** zu erforschen.
   - **Trend**: Ethnografie wird genutzt, um **digitale Praktiken in konkreten Kontexten** (Krankenhäuser, Gewächshäuser, Algorithmen-Workshops) zu verorten.

3. **Mehrautor*innen-Kollaborationen**:
   - **Rikala et al. (2026, #5)**: 6 Autor*innen (Review-Studie).
   - **Do et al. (2026, #14)**: 7 Autor*innen (*Graphilosophy*-Projekt).
   - **Trend**: Zunahme **interdisziplinärer Teams** (Informatik, Philosophie, Pädagogik), besonders bei **technisch-philosophischen Hybridprojekten**.

4. **Dokumentenanalyse**:
   - **Hasan (2026, #15)**: Analyse von **Websites von 20 KI-Tools**.
   - **Talašová (2026, #6)**: Analyse von **Care-Apps und Sensoren**.
   - **Trend**: Fokus auf **„offizielle“ Dokumente** (Websites, Richtlinien) als **Datenquelle**, um **Transparenzlücken** aufzudecken.

---

## Ausreißer und Einzelgänger

1. **Graphilosophy (Do et al., 2026, #14)**
   - **Thema**: Entwicklung eines **multilingualen Wissensgraphen** für die *Vier Bücher* der ostasiatischen Philosophie.
   - **Methode**: Kombination von **NLP, semantischen Embeddings und humanistischer Interpretation**.
   - **Ausreißer**: Einziger Beitrag, der **KI für geisteswissenschaftliche Wissensrepräsentation** nutzt – jenseits von Ethik oder Bildung.

2. **Two or Three Confusions About Vibrations (Mommersteeg, 2026, #20)**
   - **Thema**: Ethnografie von **Protesten gegen Verkehrslärm als Vibrationen** in Paris.
   - **Argument**: Vibrationen **entziehen sich sensorischen Kategorien** (Lärm vs. Vibration) und **regulatorischen Modellen**.
   - **Ausreißer**: **Nicht-digitaler Fokus** in einem digitalen Diskursraum; zeigt, wie **analoge Phänomene** digitale Governance herausfordern.

3. **Making Queer Kin in the Labor of the Greenhouse (Chacko, 2026, #16)**
   - **Thema**: **Pflanzen als „Co-Lehrerinnen“** in STS-Kursen; Reflexion über **queere Kinship** (Haraway).
   - **Methode**: **Botanische Praxis** als pädagogisches Experiment.
   - **Ausreißer**: **Radikal posthumaner Ansatz**, der **Bildung als mehr-als-menschliche Praxis** denkt.

4. **More Instrument than Data (Ribes & Monteiro, 2026, #28)**
   - **Thema**: Plädoyer für **„upstream“-Forschung** zu **Instrumenten der Datengenerierung** (nicht zu Daten selbst).
   - **Argument**: Daten sind **keine Rohstoffe**, sondern **Produkte von Instrumenten**, deren **Referenzialität** (was Daten „bedeuten“) **instabil** ist.
   - **Ausreißer**: **Methodologische Provokation**, die **Datenzentrismus** in STS hinterfragt.

---

## Absenzen

1. **Kritische Medienpädagogik**:
   - Fehlende Beiträge, die **medienpädagogische Konzepte** (z. B. Medienkritik, Partizipation) auf KI übertragen. Die Debatte wird dominiert von **Ethik** (Alignment) und **Kompetenz** (Literacy), nicht von **pädagogischen Praktiken**.

2. **Kulturelle Bildung und Ästhetik**:
   - Kaum Beiträge zu **künstlerischen Praktiken mit KI** (Ausnahme: #9 zu generativer KI in der Kunst). Unklar bleibt, wie **ästhetische Bildung** in postdigitalen Räumen gedacht wird.

3. **Globaler Süden jenseits von China/Indien**:
   - Fast alle nicht-westlichen Perspektiven stammen aus **China** (#11, #19, #29, #34, #37) oder **Palästina** (#11). Fehlende Stimmen aus **Afrika, Lateinamerika (außer #26) oder Südostasien**.

4. **KI in der Schule**:
   - Während #7 (SAILS) KI-Literacy für **Berufsbildung** untersucht, fehlen Studien zu **KI in schulischen Kontexten** (z. B. Chatbots im Unterricht, algorithmische Bewertung).

#### MiMo ($0.0159, 9,518c, recycled)

# Trendbeobachtung: Digitale Kultur (2024–2026)

## Überblick
Das Beobachtungsfenster umfasst 40 Beiträge aus dem Jahr 2026. STHV (Science, Technology, and Human Values) dominiert mit 12 Artikeln, gefolgt von BDS (Big Data and Society) mit 8 und AIandSoc (AI & Society) mit 7. DCE (Digital Culture & Education) hat 6 Beiträge, während BJET und REPCS je einen einbringen. Der erste Durchgang zeigt ein starkes Übergewicht einer **soziotechnischen, kritischen Perspektive** auf algorithmische Systeme, KI und Digitalisierung. Konventionelle Bildungs- und Technologieoptimierungs-diskurse sind deutlich schwächer vertreten. Der Diskurs bewegt sich von einer reaktiven Kritik zu einer differenzierten Analyse der spezifischen gesellschaftlichen Formationen, die digitale Systeme ermöglichen oder stärken.

## Konsolidierende Diskurse

### 1. Kritik an algorithmischer Macht und Systemtransparenz
Dieser Cluster analysiert die Undurchsichtigkeit, Machtstrukturen und gesellschaftlichen Konsequenzen algorithmischer und KI-Systeme. Er verbindet technische Kritik mit politischer und sozialer Theorie.
*   **McBride, Thumlert & Nolan (2026, ID:1fb1690)**: Kritisiert die komplizenhafte Übernahme algorithmischer Logiken im Hochschulsystem.
*   **Hasan (2026, ID:0ffce912)**: Untersucht eklatante Intransparenz bei Bildungs-KI-Tools (fehlende Angaben zu Trainingsdaten, Prozessen).
*   **Schrøder, Ratner & Kocksch (2026, ID:8acead9d)**: Entwickelt den Begriff der "algorithm-worlds" und zeigt, wie ein Algorithmus in Kinderwohlfahrts-Verwaltung multiple, weltkonstituierende Versionen annehmen kann.
*   **Li (2026, ID:aaf3e98d)**: Führt den Begriff der "Technopolitics of labor expendability" ein, um zu zeigen, wie algorithmisches Management in China Arbeitskräfte nicht nur verwaltet, sondern ihre Entbehrlichkeit konstituiert.
*   **Kirkpatrick (2026, ID:17e718ae)**: Analysiert Deepfakes nicht nur als Schadensursache, sondern als Verletzung einer normativen Autorität über die eigene Identität ("right against algorithmic conscription").

### 2. Bildung in und für eine algorithmische Ära: Zwischen Agency und Kapitulation
Dieser Cluster verhandelt die Spannung zwischen der Kritik an der Digitalisierung von Bildung und dem Versuch, konstruktive Konzepte für digitale Agency und Literacy zu entwickeln.
*   **Scheibenzuber et al. (2026, ID:7d29db11)**: Entwickeln ein validiertes Messinstrument (SAILS), das instrumentelle und kritisch-reflexive KI-Kompetenzen voneinander unterscheidet – ein pragmatischer Ansatz.
*   **Rikala et al. (2026, ID:b499feb3)**: Systematisiert den Begriff der "digital agency" durch eine Review, um seine konzeptionelle Fragmentierung zu überwinden.
*   **Stewart & Le (2026, ID:847da955)**: Karten "Belonging" in höherer Bildung im digitalen Zeitalter und fragen nach relationalen Pädagogiken.
*   **McBride, Thumlert & Nolan (2026, ID:1fb1690)**: Bieten die kontrastierende, ablehnende Position: Der "algorithmic turn" führe zu einer "Hands-Off"-Pädagogik.
*   **Furnes (2026, ID:2fdddfd3)**: Stellt eine philosophische Gegenposition auf: "Moralische Präsenz" als vor-digitale pädagogische Bedingung, verankert in Levinas/Buber.

### 3. Soziotechnische Perspektiven auf Überwachung, Datifizierung und Kontrolle
Aus STS-Perspektive werden konkrete Fallstudien zu Überwachungssystemen und deren Einbettung in lokale Machtgefüge untersucht. Der Fokus liegt auf Praxis, Implementierung und unbeabsichtigten Konsequenzen.
*   **Xing & Zheng (2026, ID:69fbeb4f)**: Analysieren Chinas Health Code Systems als kontingentes "sociotechnical assemblage" und betonen die unbeachtete "accountability labor" von Straßenbeamten.
*   **Steinhardt & Göbel (2026, ID:e9f55ea7)**: Untersuchen quantitativ und qualitativ, wie das Social-credit-System auf chinesischen Social-Media-Plattformen als Lösung für "gesellschaftliche Anomie" legitimiert wird.
*   **Talašová (2026, ID:355878f4)**: Analysiert die Datafizierung häuslicher Pflege ("data of care") und zeigt, wie Algorithmen neue temporale Regime einführen, die Care-Arbeit moralisieren und individualisieren.
*   **Plasil et al. (2026, ID:bd1d60c5)**: Verfolgen, wie die Einführung eines Gesundheitsdatenraums (Epic) in Norwegen Begriffe von "Qualität" im Gesundheitswesen transformiert.

### 4. Digitale Gerechtigkeit, Marginalisierung und gesellschaftliche Teilhabe
Dieser Cluster untersucht, wie digitale Technologien bestehende Ungleichheiten (re)produzieren oder neue Formen der Exklusion schaffen.
*   **Miltner et al. (2026, ID:ec2689a8)**: Zeigen empirisch, dass UK-Coding-Bootcamps am meisten jungen, nicht-behinderten, finanzstabilen Briten ohne Pflegeverantwortung nützen und so Claims der Inklusivität widerlegen.
*   **Gasparotto (2026, ID:9429b9a8)**: Analysiert, wie NLP-Praktiken durch mangelnde Standardisierung schädliche Sprachideologien reproduzieren und indigene mexikanische Sprachen marginalisieren.
*   **Belotti et al. (2026, ID:10bd860d)**: Weisen in einem Interview-Experiment nach, dass KI-Chatbots Altersdiskriminierung (Ageism) praktizieren, während sie Sexismus vermeiden – ein "doppeltes Standard"-Problem.
*   **Jabali et al. (2026, ID:923687fa)**: Untersuchen die Adoption von KI durch palästinensische Frauen in häuslichen Räumen und legen eine Kluft zwischen wahrgenommener Nützlichkeit und Absicht zur Nutzung offen, geprägt von kulturellen Normen.

## Differenzierungen und offene Spannungen

### Spannung 1: Digitale Systeme als Instrument der Kontrolle vs. als Räume für neue Agency
*   Die kritische Position findet sich in Beiträgen wie **Li (ID:aaf3e98d)**, die algorithmisches Management als Werkzeug der Disziplinierung und Entmenschlichung sehen.
*   Demgegenüber stehen Ansätze wie **Rikala et al. (ID:b499feb3)**, die "digitale Agency" als konstruktives Kompetenzkonzept systematisieren wollen, oder **Xing & Zheng (ID:69fbeb4f)**, die die unbeabsichtigten Praktiken und Gegenstrategien der Nutzer*innen betonen.

### Spannung 2: Umgang mit generativer KI – von grundsätzlicher Ablehnung bis zu normativer Einhegung
*   **McBride et al. (ID:1fb1690)** vertreten eine positionelle Ablehnung der "algorithmic turn" in der Bildung.
*   **Josifović & Noller (ID:1520f09e)** entwickeln dagegen ein normatives philosophisches Framework ("normative interface") für die Einbindung von KI in menschliche Handlungsdomänen.
*   **Martineau et al. (ID:10bd860d)** analysieren ChatGPT mit Habermas als "kolonialistischen Agenten", der die Lebenswelt bedroht, während **Zimmer (ID:767db40e)** mit dem "model collapse" eine technische Grenze der KI-Entwicklung selbst beschreibt.

## Methodische Beobachtungen
*   **Ethnographische und qualitative STS-Ansätze dominieren in den Beiträgen von STHV und BDS** (z.B. Xing & Zheng, Schrøder et al., Li). Der Fokus liegt auf Praktiken, Implementierungsprozessen und lokalen Aushandlungen.
*   **Mixed-Methods und quantitative Ansätze sind in AIandSoc und BDS präsent**, oft zur Analyse von Diskursen (z.B. Steinhardt & Göbel: Quantitative + qualitative Analyse von 72.500 Social-Media-Posts) oder zur Messung von Kompetenzen (SAILS in BJET).
*   **Auffällig ist das methodische Interesse an der Analyse von Large Language Models (LLMs) selbst als Gegenstand**: Durch Interviews mit Chatbots (Belotti et al.) oder die Diskursanalyse von ChatGPT-Gesprächen (Martineau et al.). Dies geht über reine Inhaltsanalyse hinaus zu einer Untersuchung der KI als sozio-kommunikativen Akteur.
*   **Inhaltsanalyse von Policy-Dokumenten und Plattform-Daten** findet sich in Lin et al. (AI-und-Kunst-Policies) und Hasan (Transparenz von Bildungs-KI-Websites).

## Ausreißer und Einzelgänger
*   **Chacko (2026, ID:1c1b483f, STHV)**: Der Beitrag über "Making Queer Kin in the Labor of the Greenhouse" verbindet STS mit Pflanzen-Kognition und queerer Theorie. Berührt digitale Kultur nur am Rande (durch pädagogische Praxis), ist aber ein bemerkenswerter methodischer Ausreißer (ethnographisches "learning-by-doing").
*   **Mommersteeg (2026, ID:6d0eaf39, STHV)**: "Two or Three Confusions About Vibrations" analysiert Proteste gegen Verkehrslärm als Vibrationen. Ein thematischer Ausreißer, der sensorische Epistemologie und Umweltregulierung verbindet, jedoch keinen direkten Bezug zu digitaler Kultur hat.
*   **Do et al. (2026, ID:e496837e, AIandSoc)**: "Graphilosophy" ist ein sehr technisch-methodischer Beitrag (Knowledge-Graphen, NLP) zur Digitalisierung klassischer chinesisch-vietnamesischer Philosophie. Er steht zwischen Digital Humanities und AI-Research.

## Absenzen
*   **Ästhetik und künstlerische Praxis digitaler Kultur**: Abgesehen vom Policy-Artikel zu generativer AI und Kunst (Lin et al.) fehlen Beiträge, die sich mit der Transformation von Wahrnehmung, Materialität oder künstlerischer Produktion durch digitale Medien auseinandersetzen.
*   **Europäische Digitalisierungsdiskurse**: Während China- und USA-Fokussierungen stark sind (auch in STS-Beiträgen), fehlen Analysen zu spezifisch europäischen Debatten (z.B. EU AI Act, digitale Souveränität, europäische Bildungsplattformen).
*   **Kinder- und Jugendmedienforschung**: Der Fokus liegt auf Hochschulbildung (DCE, BJET) und allgemeiner Erwachsenenbildung. Die konkrete Aneignung von KI und digitalen Plattformen durch Kinder und Jugendliche ist kein Gegenstand.
*   **Konstruktive, experimentelle oder künstlerische Ansätze in der pädagogischen Praxis mit Technologie**: Der Diskurs ist überwiegend kritisch-analytisch oder instrumentell (Literacy-Messung), weniger gestalterisch oder interventionsforschend.

---

### Cluster: `medienpaed` — Medienpädagogik

_Artikel:_ 40  ·  _Jaccard:_ 0.19

#### Mistral Large ($0.0140, 12,955c, cache=0%, 77.2s)

# Trendbeobachtung: Medienpädagogik (2024–2026)

## Überblick
Das Zeitfenster 2024–2026 zeigt eine klare Fokussierung der deutschsprachigen Medienpädagogik auf **Extended Reality (XR) und Künstliche Intelligenz (KI)** als zentrale Gegenstände. Auffällig ist die Dominanz von **praxisnahen Erprobungen** (z. B. VR im Sportunterricht, XR im Musikunterricht) gegenüber theoretischen Grundlagenreflexionen. Während *MedienPädagogik* fast ausschließlich empirische Studien und Praxisberichte veröffentlicht, steuert *BJET* stärker konzeptuelle und methodisch elaborierte Beiträge bei (z. B. Skalenentwicklung zu AI Literacy, Metaanalysen). Thematisch verschiebt sich der Diskurs von "Digitalisierung als Tool" hin zu "Digitalität als Erfahrungsraum" – mit besonderem Interesse an **Leiblichkeit, Ästhetik und Agency**.

---

## Konsolidierende Diskurse

### 1. **XR als ästhetisch-leiblicher Erfahrungsraum**
XR-Technologien (VR, AR, 360°-Videos) werden nicht mehr als bloße Werkzeuge, sondern als **Bildungsmedien** verhandelt, die neue Formen der Selbst- und Welterfahrung ermöglichen. Im Zentrum steht die Frage, wie immersive Technologien **ästhetische Bildung** (Kunst, Musik, Sport) transformieren – etwa durch:
- **Körperliche Selbstwahrnehmung**: VR als "geschützter Raum" für schamfreie Bewegungsexploration ([7] Rudi et al. 2026) oder als Medium für "gestische Plastik" ([15] Hickfang et al. 2026).
- **Performative Agency**: VR ermöglicht neue Rollenidentitäten (z. B. "Being Composer" in [6] Feneberg 2026) und kollaborative Kreativprozesse ([14] Bruns/Rotsch 2026).
- **Hybride Räume**: Die Verschränkung von physischer und virtueller Realität wird als pädagogische Herausforderung diskutiert ([21] Wiesche et al. 2026; [23] Sträter et al. 2026).

**Belege**:
- [7] Rudi et al. (2026): VR als Raum für wertfreie Körpererfahrung im Tanzunterricht.
- [14] Bruns/Rotsch (2026): XR-Producing im Musikunterricht als kollaborative Praxis.
- [17] Wiesche et al. (2026): Theoretische Rahmung von XR als Medium ästhetischer Erfahrung.
- [16] Zgraggen et al. (2026): Metaverse als gestaltbarer Raum für kulturelle Bildung.

**Charakteristik**:
Die Beiträge arbeiten an einer **postdigitalen Ästhetik**, die XR nicht als Simulation, sondern als **eigenständige Wirklichkeit** begreift (vgl. [18] Dierich-Hoche/Brenne 2026). Methodisch dominieren **qualitative Fallstudien** und **Design-Based Research** (z. B. [16]), die Technologieeinsatz mit pädagogischen Zielen verknüpfen.

---

### 2. **KI-Literacy: Operationalisierung und kritische Reflexion**
KI wird zunehmend als **Bildungsgegenstand** greifbar gemacht – nicht nur als Werkzeug, sondern als **soziales Phänomen**, das Kompetenzen jenseits technischer Bedienung erfordert. Zwei Stränge prägen den Diskurs:
- **Skalenentwicklung**: Scheibenzuber et al. ([1] 2026) differenzieren zwischen **instrumentellen** (z. B. KI nutzen) und **kritisch-reflexiven** KI-Skills (z. B. Deepfakes erkennen) und entwickeln ein **szenariobasiertes Messinstrument** (SAILS).
- **Kritische Medienpädagogik**: Rainer ([8] 2026) plädiert für eine **hegemoniekritische KI-Bildung**, die Machtstrukturen (z. B. "Datenreligion") sichtbar macht. Rezensionen ([19] Tully 2026; [30] Zweig 2025) betonen die Notwendigkeit **niedrigschwelliger Aufklärung**.

**Belege**:
- [1] Scheibenzuber et al. (2026): SAILS-Skala zur Messung von AI Literacy.
- [8] Rainer (2026): Hegemoniekritik als Methode der KI-Bildung.
- [36] Rappa et al. (2026): KI als Unterstützung für Lernende mit Behinderung (Agency-Perspektive).
- [37] Le et al. (2026): KI-Literacy-Training für Lehramtsstudierende (Design-Based Research).

**Charakteristik**:
Der Diskurs verschiebt sich von **technischer Kompetenz** hin zu **soziokultureller Einbettung** von KI. Auffällig ist die **Divergenz zwischen empirischer Operationalisierung** (z. B. [1]) und **theoretischer Kritik** (z. B. [8]), die selten aufeinander Bezug nehmen.

---

### 3. **Agency in digitalen Lernumgebungen**
Das Konzept der **Agency** (Handlungsfähigkeit) wird zum Schlüsselbegriff, um Lernprozesse in digitalen Kontexten zu beschreiben. Drei Perspektiven zeigen sich:
- **Lernende als Gestalter:innen**: XR und KI werden als Räume verhandelt, in denen Lernende **eigene Wirklichkeiten konstruieren** ([16] Zgraggen et al. 2026; [14] Bruns/Rotsch 2026).
- **Lehrkräfte als Gatekeeper**: Studien zu **Digital Divide** ([12] Frohn/Piezunka 2026) und **digitalen Kompetenzen von Lehramtsstudierenden** ([9] Hinzke/Ellermeyer 2026) zeigen, wie Agency durch institutionelle Strukturen begrenzt wird.
- **KI als Akteur**: Beiträge wie [39] Xing et al. (2026) analysieren, wie **KI-Agenten** Agency von Lernenden beeinflussen (z. B. durch Autoritätszuschreibungen).

**Belege**:
- [9] Hinzke/Ellermeyer (2026): Habituelle Dispositionen von Lehramtsstudierenden.
- [12] Frohn/Piezunka (2026): Lehrkräfteperspektiven auf Digital Divide.
- [36] Rappa et al. (2026): KI und Agency von Lernenden mit Behinderung.
- [39] Xing et al. (2026): Interaktionsmuster zwischen Lernenden und KI-Agenten.

**Charakteristik**:
Agency wird **relational** gedacht – als Wechselspiel zwischen Subjekt, Technologie und Institution. Methodisch dominieren **qualitative Studien** (z. B. [9]) und **Mixed-Methods-Ansätze** (z. B. [39]).

---

## Differenzierungen und offene Spannungen

### 1. **XR: Emanzipation vs. Normierung**
Während einige Beiträge XR als **Medium der Selbstermächtigung** feiern (z. B. [7] Rudi et al. 2026: VR als Raum für schamfreie Körpererfahrung), warnen andere vor **neuen Normierungszwängen**:
- Przybylka/Lehnhoff ([2] 2026) zeigen, wie VR im Sportunterricht **Bewegungsoptimierung** reproduziert – analog zur videobasierten Analyse.
- [15] Hickfang et al. (2026) problematisieren, dass VR oft als **Rezeptionsmedium** genutzt wird, statt kreative Potenziale zu entfalten.

**Kontroverse**:
Die Spannung zwischen **Befreiungspotenzial** (z. B. inklusive Teilhabe in [3] Weißelstein et al. 2026) und **Disziplinierung** (z. B. [2]) bleibt unaufgelöst.

---

### 2. **KI: Instrument vs. Gegenstand der Kritik**
Der Diskurs zu KI oszilliert zwischen **pragmatischer Nutzung** und **fundamentaler Kritik**:
- **Pragmatisch**: [36] Rappa et al. (2026) zeigen, wie KI Lernende mit Behinderung unterstützt; [37] Le et al. (2026) entwickeln KI-Literacy-Trainings für Lehrkräfte.
- **Kritisch**: [8] Rainer (2026) fordert eine **hegemoniekritische Medienpädagogik**, die KI als Machtinstrument analysiert.

**Leerstelle**:
Es fehlt eine **Synthese** beider Perspektiven – etwa: Wie kann KI *kritisch* genutzt werden?

---

### 3. **Postdigitale Ästhetik: Leiblichkeit vs. Virtualität**
Die Beiträge zu XR und ästhetischer Bildung ([17] Wiesche et al. 2026; [18] Dierich-Hoche/Brenne 2026) diskutieren, wie **leibliche Erfahrung** in virtuellen Räumen möglich ist. Dabei zeigen sich zwei Positionen:
- **Körper als Interface**: [18] argumentiert, dass VR eine **erweiterte Leiblichkeit** ermöglicht (z. B. durch "responsive Mensch-Maschinen-Interaktion").
- **Körper als Abwesenheit**: [21] Wiesche et al. (2026) problematisieren, dass VR **soziale Interaktionen verflacht** (z. B. Nähe-Distanz-Regulation).

**Frage**:
Wie lässt sich **leibliche Präsenz** in digitalen Räumen denken – als Erweiterung oder als Verlust?

---

## Methodische Beobachtungen

### 1. **Szenariobasierte Messinstrumente**
Die Entwicklung von **Skalen** zur Erfassung digitaler Kompetenzen nimmt zu:
- [1] Scheibenzuber et al. (2026): SAILS-Skala für AI Literacy (szenariobasierte Selbstauskunft).
- [24] Rütti-Joy et al. (2026): Skalen zur Messung virtueller Einsamkeit.

**Trend**:
Verstärkter Einsatz von **kontextualisierten Items** (z. B. Szenarien) statt abstrakter Kompetenzbeschreibungen.

---

### 2. **Design-Based Research (DBR)**
Mehrere Beiträge nutzen **DBR** zur Entwicklung pädagogischer Konzepte:
- [16] Zgraggen et al. (2026): Iterative Entwicklung einer XR-App für kulturelle Bildung.
- [37] Le et al. (2026): KI-Literacy-Training für Lehramtsstudierende.

**Charakteristik**:
DBR ermöglicht die **Verschränkung von Theorie und Praxis**, bleibt aber oft **lokal begrenzt** (z. B. Einzelschulen).

---

### 3. **Qualitative Heuristiken**
In der XR-Forschung dominieren **qualitative Methoden**:
- [4] Rudi et al. (2026): Qualitative Heuristik nach Kleining.
- [23] Sträter et al. (2026): Leitfadeninterviews zu Körpererfahrungen in VR.

**Auffälligkeit**:
Kaum **quantitative Studien** zu XR – Ausnahmen sind [1] (Skalenentwicklung) und [34] Hu et al. (2026, Metaanalyse zu VR und Perspektivübernahme).

---

### 4. **Kollaborative Formate**
Zwei Beiträge nutzen **Mehrautor:innen-Kollaborationen** mit explizit **diskursivem Charakter**:
- [10]/[28] Schenk et al. (2026): "Schreib-Streit-Gespräch" zu Normativität in der Medienpädagogik.
- [17] Wiesche et al. (2026): Vier Autor:innen aus Kunst, Musik und Sport diskutieren XR als ästhetisches Medium.

**Funktion**:
Diese Formate dienen der **Theorieentwicklung durch Dialog** – ein Novum in der deutschsprachigen Medienpädagogik.

---

## Ausreißer und Einzelgänger

### 1. **Komplexitätswissenschaft in der Bildung** ([31] Durak et al. 2026)
- **Thema**: Metaanalyse zu Anwendungen von **Complexity Science** in der Bildung (z. B. Systemdenken).
- **Ausreißer**: Der Beitrag steht **quer** zum restlichen Diskurs, da er **theoretische Grundlagen** (nicht Technologie) fokussiert.
- **Relevanz**: Zeigt eine **Lücke** – die Medienpädagogik könnte von systemtheoretischen Ansätzen profitieren, nutzt sie aber kaum.

---

### 2. **"Dream Machine": Künstlerische Utopien im urbanen Raum** ([5] Brönnecke/Washausen 2026)
- **Thema**: Studierende entwerfen mit XR-Technologien **ästhetische Utopien** für urbane Räume.
- **Ausreißer**: Einziger Beitrag mit **explizit künstlerisch-forschendem Ansatz** – verbindet Medienpädagogik mit **Stadtsoziologie** und **Postwachstumsdebatten**.
- **Relevanz**: Zeigt, wie XR **gesellschaftliche Gestaltungsräume** eröffnen kann – jenseits von Schule.

---

### 3. **Gendered Organizations in der Digitalität** ([13] Vollmar 2026)
- **Thema**: Wie verändern sich **geschlechtsspezifische Ungleichheiten** in digitalen Organisationen?
- **Ausreißer**: Einziger Beitrag mit **explizit gender- und organisationstheoretischer Perspektive**.
- **Relevanz**: Medienpädagogik diskutiert selten **strukturelle Ungleichheiten** – hier wird eine Brücke zu **Organisationspädagogik** geschlagen.

---

## Absenzen

### 1. **Kritische Datenpädagogik**
- **Fehlend**: Beiträge, die **Datenpraktiken** (z. B. Learning Analytics, Predictive Policing) als **Bildungsgegenstand** analysieren.
- **Kontext**: Während KI als Thema präsent ist, fehlt eine **kritische Auseinandersetzung mit Daten** als Machtinstrument (vgl. [8] Rainer 2026, der "Datenreligion" erwähnt, aber nicht vertieft).

---

### 2. **Globale Ungleichheiten**
- **Fehlend**: Studien zu **Digital Divide jenseits des Globalen Nordens** (Ausnahme: [33] Pachori et al. 2026 zu DIKSHA in Indien).
- **Kontext**: Die deutschsprachige Medienpädagogik bleibt **eurozentrisch** – globale Perspektiven (z. B. zu EdTech in Afrika) fehlen.

---

### 3. **Postkoloniale Medienpädagogik**
- **Fehlend**: Reflexionen über **koloniale Kontinuitäten** in digitalen Technologien (z. B. KI-Trainingsdaten, XR-Design).
- **Kontext**: Während [8] Rainer (2026) Hegemoniekritik übt, bleibt eine **postkoloniale Perspektive** aus.

---

### 4. **Ökologische Nachhaltigkeit**
- **Fehlend**: Beiträge zu **Umweltauswirkungen** digitaler Technologien (z. B. Energieverbrauch von KI, E-Waste).
- **Kontext**: Obwohl [5] Brönnecke/Washausen (2026) das **Anthropozän** thematisieren, fehlt eine **medienpädagogische Antwort** auf ökologische Krisen.

---

## Fazit: Drei zentrale Bewegungen
1. **Von der Digitalisierung zur Postdigitalität**:
   Der Diskurs verschiebt sich von "Wie nutzen wir Technologie?" zu "Wie verändert Technologie unsere Wahrnehmung von Welt und Selbst?" – besonders sichtbar in den Beiträgen zu **XR als ästhetischem Medium** ([17], [18]).

2. **KI als soziales Phänomen**:
   KI wird nicht mehr nur als Tool, sondern als **Gegenstand kritischer Reflexion** verhandelt ([1], [8]). Die Spannung zwischen **Nutzung** und **Kritik** bleibt jedoch unaufgelöst.

3. **Agency als Schlüsselkonzept**:
   Agency wird zum **Leitbegriff**, um Lernprozesse in digitalen Räumen zu beschreiben – sowohl für Lernende ([36]) als auch für Lehrkräfte ([12]). Die Frage, wie Agency **institutionell ermöglicht** werden kann, bleibt offen.

**Offene Fragen**:
- Wie lässt sich die **Kluft zwischen empirischer Operationalisierung** (z. B. AI Literacy) und **kritischer Theorie** (z. B. Hegemoniekritik) überbrücken?
- Welche **methodischen Innovationen** (z. B. partizipative Designs) braucht die Medienpädagogik, um postdigitale Erfahrungsräume zu erforschen?
- Wie kann Medienpädagogik **strukturelle Ungleichheiten** (Geschlecht, Klasse, Globaler Süden) stärker in den Blick nehmen?

#### MiMo ($0.0210, 11,406c, recycled)

# Trendbeobachtung: Medienpädagogik (2024–2026)

## Überblick

Das analysierte Fenster umfasst 40 Beiträge aus zwei Journals — der britisch-international ausgerichteten *BJET* (11 Beiträge) und der deutschsprachigen *MedienPädagogik* (29 Beiträge) —, sämtlich aus dem Jahr 2026. Beim ersten Durchgang fällt eine gravierende Diskurs-Segmentierung auf: Die beiden Journals arbeiten weitgehend an unterschiedlichen Gegenständen, mit unterschiedlichen Methoden und theoretischen Referenzen. Innerhalb von *MedienPaed* dominiert ein einziges Thema — XR/VR in körperästhetischen Bildungskontexten — in geradezu monothematischer Dichte. *BJET* wiederum ist geprägt von empirischen Untersuchungen zu GenAI in Lehr-Lern-Kontexten. Die Schnittmenge zwischen beiden Diskursen ist gering.

---

## Konsolidierende Diskurse

### 1. XR/VR in körperästhetischer Bildung — das MedienPaed-Kernthema

Mit mindestens 13 von 29 MedienPaed-Beiträgen handelt es sich um das dominante Cluster des gesamten Fensters. Die Beiträge untersuchen den Einsatz von VR, 360°-Video und XR-Technologien ausnahmslos in Fächern, die auf leiblich-sinnliche Erfahrung zielen: Sport, Tanz, Musik und bildende Kunst. Nicht einer dieser Beiträge behandelt VR als Instrument kognitiver Wissensvermittlung oder als Verwaltungs-/Organisationstool — es geht durchgehend um Bewegung, Wahrnehmung, Körpererfahrung und ästhetisches Handeln.

- *Von der videobasierten zur VR-basierten Bewegungsanalyse* — Przybylka & Lehnhoff, 2026 (id: 3a8f8e9b9a1d)
- *Virtual Reality im Förderschwerpunkt Körperliche und motorische Entwicklung* — Weißelstein et al., 2026 (id: 629f4caa2d4a)
- *Einsatz von 360°-Videotechnologie in kreativen Bewegungskontexten* — Rudi et al., 2026 (id: 5ae42c712a56)
- *Playing Composer – Performing Composer – Being Composer?* — Feneberg, 2026 (id: 3817b37c000a)
- *‹Es ist, als wäre ich in meiner eigenen Welt›* — Rudi et al., 2026 (id: e4057832900f)
- *Mit der VR-Brille ins Orchesterkonzert* — Feneberg & Malmberg, 2026 (id: 010ab8bc90fb)
- *Von der Bewegung zur gestischen Plastik* — Hickfang et al., 2026 (id: 65298f6ab803)
- *Ästhetische Erfahrung und XR* — Wiesche, Brönnecke, Przybylka & Feneberg, 2026 (id: 7c179322b1b3)
- *XR-Producing im Musikunterricht* — Bruns & Rotsch, 2026 (id: 92c1897640a5)
- *Nähe und Distanz als sportpädagogisches Thema im hybriden Raum* — Wiesche et al., 2026 (id: 5847dddc3fd0)
- *Erfahrungsräume erweitern: Kämpfen in Virtual Reality* — Sträter et al., 2026 (id: 51bc470d7128)
- *Die virtuelle Realität (VR) als gestaltbarer Raum* — Dierich-Hoche & Brenne, 2026 (id: bfac3892e1b8)
- *Dream Machine* — Brönnecke & Washausen, 2026 (id: 2559fb92116e)

Dieses Cluster zeichnet sich durch eine konsistente theoretische Rahmung aus: Die Beiträge referenzieren durchgehend Konzepte der *Leiblichkeit*, der *ästhetischen Erfahrung* (Brandstätter), der *Kultur der Digitalität* (Stalder) und des *postdigitalen* Paradigmas. Bemerkenswert ist, dass die Beiträge nicht bloß Potenzialanalyse betreiben, sondern mehrheitlich auf die Spannung zwischen Optimierungsnorm und kreativer Offenheit zielen — etwa die Kritik an der einseitigen Ausrichtung auf Bewegungsnormierung bei Przybylka/Lehnhoff oder die Betonung wertfreier Körpererkundung bei Rudi et al. (2026, id: e4057832900f). Einige Autoren sind mehrfach vertreten (Rudi, Feneberg, Wiesche, Brönnecke, Przybylka), was auf ein produktives Netzwerk innerhalb der sport-, kunst- und musikpädagogischen Medienforschung schließen lässt.

### 2. GenAI und KI-Literacy im Bildungskontext — das BJET-Kernthema

In der *BJET* bilden GenAI-bezogene Untersuchungen das zentrale Cluster (7 von 11 Beiträgen). Anders als in MedienPaed steht hier nicht die ästhetisch-leibliche Dimension, sondern die Frage im Vordergrund, wie Lernende und Lehrende mit generativen KI-Systemen umgehen — hinsichtlich Kompetenz, Agency, Bewertung und emotionaler Bewältigung.

- *SAILS: Scenario-Based AI Literacy Scale* — Scheibenzuber et al., 2026 (id: eb6257c786d7)
- *Learner agency in revising GenAI-generated statements of purpose* — Jiang et al., 2026 (id: c7f8b66bf713)
- *GenAI supporting pre-service teachers' emotional labour* — Nguyen & Barbieri, 2026 (id: 6b1b74a7b738)
- *GenAI for students with disability* — Rappa et al., 2026 (id: 5e0eeed796ba)
- *AI literacy training for teacher education students* — Le et al., 2026 (id: 220a60e74e0f)
- *GenAI teachable agent and student agency* — Xing et al., 2026 (id: 43aa0401c989)
- *GenAI-supported formative assessment* — Webb & Galamba, 2026 (id: 245803dfa959)

Innerhalb dieses Clusters differenziert sich die Perspektive: Scheibenzuber et al. instrumentalisieren AI-Literacy psychometrisch und trennen zwischen *instrumentellen* und *kritisch-reflexiven* KI-Kompetenzen. Jiang et al. und Xing et al. fokussieren auf *learner agency* in Mensch-KI-Interaktionen. Nguyen & Barbieri rücken die emotionale Dimension (emotional labour) ins Zentrum. Webb & Galamba argumentieren pädagogisch-didaktisch für GenAI als Werkzeug formativer Assessment-Praxis. Einzig die Rezension bei Tully (id: ea8383ccee44) in MedienPaed greift das KI-Thema auf — eine echte Lücke zwischen den Diskursen.

---

## Differenzierungen und offene Spannungen

### Agency: differente Rahmungen in MedienPaed vs. BJET

Der Begriff der *Agency* taucht in beiden Journals auf, wird aber fundamental unterschiedlich gerahmt. In *BJET* ist Agency ein lernpsychologisches Konstrukt, das operationalisierbar und messbar wird (vgl. Xing et al. id: 43aa0401c989; Jiang et al. id: c7f8b66bf713; Rappa et al. id: 5e0eeed796ba) — die Frage lautet: *Wie viel Agency zeigt der Lernende im Umgang mit KI?* In *MedienPaed* hingegen wird Agency (wo sie auftaucht) relational und subjekttheoretisch gefasst, eingebettet in Fragen der Hegemoniekritik (Rainer, id: d1e7be866563) oder der Selbstbestimmung im Digitalen (Schwenke et al. / Schreibgespräch, id: 010ab8bc90fb). Eine explizite Verschränkung beider Perspektiven fehlt.

### VR: zwischen Optimierung und Offenheit

Innerhalb des MedienPaed-VR-Clusters besteht eine offene Spannung zwischen zwei Positionen: Einige Beiträge untersuchen VR primär als Instrument der Bewegungsoptimierung und Leistungssteigerung (Przybylka/Lehnhoff; Weißelstein et al.), andere betonen das Potenzial von VR als *offenem Erfahrungsraum* für kreative, wertfreie, selbstreflexive Körperarbeit (Rudi et al., id: e4057832900f; Feneberg, id: 3817b37c000a; Brönnecke/Washausen, id: 2559fb92116e). Wiesche et al. (id: 7c179322b1b3) versuchen theoretisch zu vermitteln, indem sie XR nicht als Technologie, sondern als *Bildungsmedium* rahmen — eine Position, die implizit gegen den rein funktionellen Einsatz argumentiert.

### Digital Divide: Befund vs. Intervention

Frohn & Piezunka (id: ed0382de3f85) kartieren den Digital Divide aus Lehrkräfteperspektive mittels Bourdieus Kapitaltheorie und dem Konzept des *Digitalen Kapitals* — eine differenzierte, strukturell argumentierende Analyse. Dem gegenüber steht Neuberger et al. (id: 9b837c66111b), die mit quasi-experimentellem Design die Wirksamkeit analoger vs. digitaler Leseförderung untersuchen und dabei auf subgruppendifferenzielle Effekte stoßen (z.B. dass häufige digitale Mediennutzer:innen *negativ* auf digitale Leseförderung reagieren). Beide befassen sich mit Bildungsgerechtigkeit im Digitalen, arbeiten aber auf完全不同 unterschiedlichen Analyseebenen — die eine strukturell-qualitativ, die andere interventionistisch-quantitativ.

---

## Methodische Beobachtungen

**Deutliche Methodentrennung zwischen den Journals.** *MedienPaed* ist geprägt von qualitativen Verfahren: Interviews (Weißelstein et al.; Sträter et al.; Wiesche et al., id: 5847dddc3fd0), Gruppendiskussionen (Hinzke/Ellermeyer; Wiesche et al.), qualitativer Inhaltsanalyse (Wiesche et al., id: 5847dddc3fd0), qualitativer Heuristik (Rudi et al., id: 5ae42c712a56), Fallstudien (Feneberg; Zgraggen et al.). *BJET* dominiert mit psychometrischen Skalen (Scheibenzuber et al.), Meta-Analysen (Hu et al.), Eye-Tracking (Huangfu et al.), konfirmatorischer Faktorenanalyse (Rütti-Joy et al.), Mixed-Methods (Pachori et al.) und Large-N-Analyse von Textdaten (Xing et al.: 117.000 Utterances).

**Kollaborative Formate in MedienPaed.** Der *Schreibgespräch*-Beitrag (Schenk et al., id: 010ab8bc90fb / id: b3a0141f2159) markiert ein methodisches/wissenschaftstheoretisches Format, das in der englischsprachigen Educational-Technology-Forschung kaum vorkommt: ein dialogisches, polyphones Textverfahren, das Normativität und Positionalität der Forschenden selbst zum Thema macht.

**Reviews als Diskursmarker.** MedienPaed enthält mehrere Rezensionen (Tully zu KI-Buch; Brown zu post-digitalem Erzählen), die anzeigen, dass das Feld Begriffsarbeit leistet und Rezeption als wissenschaftliche Praxis pflegt — ein Format, das in der BJET nicht vorkommt.

---

## Ausreißer und Einzelgänger

- **Dertinger et al.** (*Neue Diskurse, veränderte Arbeitsbedingungen — aber weiterhin prekäre Lage*, id: 977ae8063c8b): Eine arbeitsmarktpolitische Befragung von Medienpädagogik-Wissenschaftler:innen in Qualifikationsphasen. Der einzige Beitrag, der das Feld selbst zum Gegenstand macht — weder medienpädagogisch inhaltlich noch bildungstechnologisch, sondern soziologisch-selbstreflexiv.

- **Durak et al.** (*The landscape of complexity science in education*, id: 0f938609621c): Ein Scoping Review zur Komplexitätswissenschaft in der Bildungsforschung. Thematisch kein medienpädagogischer Beitrag, sondern ein metatheoretischer Überblick, der in der BJET als breit gefasstem Educational-Technology-Journal Platz findet, aber im engeren medienpädagogischen Diskurs nicht verankert ist.

- **Vollmar** (*Gendered Organizations reloaded*, id: 0455a6a0ff53): Verbindet Organisationspädagogik mit Digitalität und Geschlechterforschung über eine praxistheoretische Rahmung. Thematisch zwischen Medienpädagogik und Organisationsforschung angesiedelt — ein Beitrag, der andeutet, dass die Digitalisierung von Organisationen ein medienpädagogisches Thema werden *könnte*, aber bisher kaum ist.

---

## Absenzen

- **Soziale Medien / Plattformpädagogik** fehlt nahezu vollständig. Kein Beitrag behandelt TikTok, Instagram, YouTube oder Plattformdynamiken als pädagogischen Gegenstand — eine bemerkenswerte Lücke angesichts der Alltagsrelevanz sozialer Medien für die Zielgruppen der Medienpädagogik.
- **Spiele/Game-Based Learning** taucht nur am Rande auf (einmal im Zusammenhang VR-Komponieren bei Feneberg, id: 3817b37c000a) — Gamification wird lediglich in Dierich-Hoche/Brenne (id: bfac3892e1b8) als Fortbildungselement erwähnt.
- **KI in MedienPaed** ist eine gravierende Lücke. Während *BJET* das Thema prominent besetzt, erscheint in *MedienPaed* lediglich eine Rezension — wobei die Gramsci-Hegemoniekritik (Rainer, id: d1e7be866563) und das XR-KI-Modell (Autenrieth/Schenk, id: 113b75917b91) als theoretische Anknüpfungspunkte vorhanden wären. Das deutschsprachige medienpädagogische Feld scheint die KI-Debatte noch nicht als eigenen Gegenstand etabliert zu haben.
- **Cyberbullying, Datenschutz, digitale Sicherheit** — klassische Themen der Medienpädagogik — sind im vorliegenden Korpus nicht vertreten.
- **Post-COVID-Digitalisierung** wird nur in zwei Beiträgen als Kontext erwähnt (Frohn/Piezunka; Dertinger et al.), was darauf hindeutet, dass die Pandemie als diskurstreibendes Ereignis im Medienpädagogischen abebbt.

---

### Cluster: `erziehungswiss` — Erziehungswissenschaftliche Journals

_Artikel:_ 40  ·  _Jaccard:_ 0.19

#### Mistral Large ($0.0136, 14,697c, cache=0%, 86.3s)

# Trendbeobachtung: Erziehungswissenschaftliche Journals (2024–2026)

## Überblick
Das Fenster umfasst 40 Beiträge aus vier deutschsprachigen und internationalen Journals (*EthicsEd*, *Discourse*, *PCS*, *ZfE*) zwischen 2024 und 2026. Auffällig ist die starke Präsenz **ethisch-philosophischer Reflexionen** (v. a. in *EthicsEd*), die sich mit ökologischen Krisen, posthumanistischen Perspektiven und der Neubestimmung von Bildungszielen befassen. Parallel dazu dominieren in der *ZfE* **empirisch-quantitative Studien** zu digitalen Kompetenzen, Sprachbildung und schulischer Praxis – oft mit Fokus auf Messbarkeit und Interventionsforschung. *Discourse* und *PCS* zeigen eine **kulturtheoretische und machtkritische Ausrichtung**, die Bildung als vernetztes, materiell-diskursives Gefüge analysiert.

---

## Konsolidierende Diskurse

### 1. **Ökologische Bildung und postanthropozentrische Ethik**
Ein zentraler Cluster formiert sich um die **Neubestimmung von Bildung angesichts ökologischer Krisen**, wobei klassische Konzepte wie *Bildung* oder *Flourishing* radikal dezentriert werden. Die Beiträge arbeiten mit **posthumanistischen, dekolonialen und degrowth-orientierten Theorien** und plädieren für eine Abkehr von anthropozentrischen Bildungszielen.

- **Rudolph et al. (2026, #25)**: *"Beyond colonial-capitalist logics: reimagining the aims of education through degrowth and reviving the commons"*
  - Kritik an "growthism" und "alienation" als treibende Kräfte der Klimakrise; Forderung nach einer Bildung, die Commons und Degrowth als ethische Praxis verankert.
- **Wolbert (2026, #26)**: *"Mutual flourishing as an ideal aim of education"*
  - Ersetzt "human flourishing" durch "mutual flourishing" (inspiriert von Kimmerer/Haraway) und betont ökologische Interdependenz als Bildungsziel.
- **Felton (2026, #31)**: *"Responsibility with the Other: Plant Ethics and Education at the End of the World"*
  - Entwickelt eine **pflanzenethische Perspektive**, die Verantwortung als "Antwortfähigkeit" gegenüber nicht-menschlichen Akteuren fasst.
- **Posada & Surian (2026, #36)**: *"Hope and agency for reimagining education towards just and habitable futures"*
  - Propagiert eine *Critical Transformative Ecopedagogy* (CTE), die dekoloniale Epistemologien und politische Emotionen integriert.
- **Murris & Castillo (2026, #39)**: *"Responding to the ‘small’: thinking-with Karen Barad and Emmanuel Levinas about death and dying"*
  - Kombiniert Barads Agential Realism mit Levinas’ Ethik der Alterität, um kindliche Auseinandersetzungen mit Sterblichkeit als **posthumanistische Praxis** zu lesen.

**Charakteristika**:
- **Begriffliche Verschiebung**: Von "Nachhaltigkeit" zu "ökologischer Gerechtigkeit" (*justice-to-come*, #39) und "planetarer Bildung" (#25).
- **Methodische Innovation**: Einsatz von **trioethnography** (#40) und **Community of Philosophical Enquiry (CoPE)** (#39) als partizipative Forschungsformate.
- **Kontroverse**: Die Beiträge teilen die Kritik an technokratischen Lösungen (z. B. "net-zero"-Narrative, #36), divergieren aber in der Radikalität der Forderungen – von reformistischen Ansätzen (#38) bis zu systemischer Transformation (#25).

---

### 2. **Kritische Online Reasoning (COR) und digitale Kompetenzen**
Ein zweiter Cluster bündelt **empirische Studien zu digitalen Kompetenzen**, insbesondere zur Fähigkeit, online Informationen kritisch zu bewerten. Die Beiträge stammen fast ausschließlich aus der *ZfE* und zeigen eine **starke Standardisierung** des Forschungsfelds, das sich um das Konstrukt *Critical Online Reasoning* (COR) organisiert.

- **Mehler et al. (2026, #15)**: *"Linguistic features of student responses as indicators of performance in critical online reasoning tasks"*
  - Nutzt **computerlinguistische Analysen** (Syntax, Semantik), um COR-Leistungen vorherzusagen.
- **Martin de los Santos et al. (2026, #12)**: *"The relation between critical online reasoning skills of first-semester university students and their epistemological beliefs"*
  - Korreliert COR mit epistemologischen Überzeugungen (EBs) und zeigt **domänenspezifische Unterschiede** (z. B. stärkere Effekte in Medizin als in Physik).
- **Hartig et al. (2026, #16)**: *"Rating procedures to evaluate generic critical online reasoning in an open Internet environment"*
  - Entwickelt **Bewertungskriterien für GEN-COR** (Generic Critical Online Reasoning) und trennt *Online Information Acquisition* (OIA) von *Reasoning* (REAS).
- **Maur et al. (2026, #11)**: *"Exploring browsing patterns in domain-specific critical online reasoning: an eye-tracking study"*
  - Zeigt mittels **Eye-Tracking**, dass Hochleister*innen systematischer scrollen und abstrakte Textpassagen länger fixieren.

**Charakteristika**:
- **Konvergenz um COR**: Das Konstrukt wird als **neuer Standard** etabliert, mit klaren Operationalisierungen (#16) und domänenspezifischen Adaptionen (#12).
- **Methodische Dominanz**: **Quantitative Verfahren** (Metaanalysen, Regressionsanalysen, Eye-Tracking) überwiegen; qualitative Ansätze fehlen.
- **Implizite Kontroverse**: Während die Studien COR als **messbare Kompetenz** behandeln, bleibt unklar, ob damit nicht eine **neoliberale Anpassung an digitale Arbeitsmärkte** befördert wird (vgl. kritische Perspektiven in #29 zu KI).

---

### 3. **Ruralität, Prekarität und Bildung als Assemblage**
Ein dritter Cluster untersucht **Bildung in prekären Kontexten** (ländliche Räume, Migration, digitale Arbeitsmärkte) und nutzt **poststrukturalistische und netzwerktheoretische Ansätze**, um Bildung als vernetztes Gefüge zu analysieren.

- **Díaz-Romanillos (2026, #1)**: *"The rural school as network and assemblage: fragility, agency, and educational futures"*
  - Analysiert ländliche Schulen in Spanien als **Akteur-Netzwerke** (ANT), die trotz struktureller Prekarität soziale Kohäsion ermöglichen.
- **Domingo (2026, #3)**: *"Promise, gate, constraint: the recruitment rhetoric of online English schools targeting Filipino teachers"*
  - Dekonstruiert die **multimodale Rhetorik** von Online-Sprachschulen als "promise-gate-constraint"-Mechanismus, der prekäre Arbeitsverhältnisse normalisiert.
- **Jamal Al-Deen (2026, #4)**: *"Unsettling inclusion: refugee-background students and the cultural politics of regional schooling"*
  - Zeigt, wie **Inklusion als Machttechnologie** funktioniert, die Geflüchtete zu "hörbaren" Subjekten macht – oder eben nicht.
- **Ergin (2026, #6)**: *"Reimagining sound and affect: challenging traditional meaning-making in early childhood education assemblages"*
  - Erweitert den Assemblage-Ansatz um **affektive und klangliche Dimensionen** in der frühen Kindheit.

**Charakteristika**:
- **Theoretische Prägung**: Starke Rezeption von **Deleuze/Guattari** (#1, #6) und **ANT** (#1, #3); Fokus auf **Macht-Wissen-Komplexe** (#3, #4).
- **Gegenstandsverschiebung**: Von "Bildung in der Krise" zu **Bildung *als* Krise** – Prekarität wird nicht als Defizit, sondern als **konstitutives Moment** analysiert (#1).
- **Methodische Vielfalt**: Kombination aus **Diskursanalyse** (#3), **Interviews** (#4) und **postqualitativen Ansätzen** (#6).

---

## Differenzierungen und offene Spannungen

### 1. **KI in der Bildung: Zwischen Naturalisierung und Kritik**
Zwei Beiträge in *EthicsEd* behandeln KI, kommen aber zu **radikal unterschiedlichen Schlussfolgerungen**:

- **Hou (2026, #29)**: *"Natural intelligence, not artificial: a Confucian reframing of generative AI in higher education"*
  - **Position**: KI als "natural intelligence" – eingebettet in menschliche Kreativität und moralische Verantwortung (Konfuzianismus).
  - **Implikation**: KI soll als **Werkzeug der Selbstkultivierung** (*xue yi cheng ren*) genutzt werden.
- **Kritische Einordnung**: Fehlende Auseinandersetzung mit **Machtasymmetrien** (z. B. Datenkolonialismus) oder **epistemischer Gewalt** durch KI-Systeme.

**Kontrast**:
- Die COR-Studien (#11, #12, #15, #16) behandeln KI **implizit** als Bedrohung (z. B. durch Misinformation), ohne jedoch eine **ethische Reflexion** anzuschließen.

---

### 2. **Trauma-Pädagogik: Zwischen Schutz und Herausforderung**
- **Kerswell (2026, #28)**: *"Beyond safe spaces: restoring purpose and responsibility in education"*
  - **Kritik**: Trauma-informierte Pädagogik kann zu **Überprotektion** führen und demokratische Bildung untergraben.
  - **Alternative**: Adlerianische Psychologie als Rahmen für **Verantwortungsübernahme** und "courage".
- **Sukodoyo et al. (2026, #33)**: *"Bullying as a moral failure in education: integrating care ethics, loving-kindness, and self-compassion"*
  - **Position**: Trauma-Pädagogik als **ethische Pflicht**; Fokus auf **loving-kindness** (Buddhismus) und Care Ethics.

**Spannung**:
- **Schutz vs. Herausforderung**: Während #28 vor einer **Therapeutisierung von Bildung** warnt, sieht #33 in Trauma-Pädagogik einen **Weg zu mehr Gerechtigkeit**.

---

### 3. **Sprachbildung: Zwischen Systemkritik und Systemanpassung**
- **Hartung et al. (2026, #13)**: *"Aufgabenprofile von Sprachbildungsbeauftragten"*
  - **Empirischer Befund**: Sprachbildung wird oft auf **kommunikative und konzeptionelle Tätigkeiten** reduziert; Umsetzung und Evaluation bleiben aus.
  - **Implikation**: Sprachbildung als **verteilte Führung** scheitert an strukturellen Barrieren.
- **Henschel & Heppt (2026, #10)**: *"Kompetenzeinschätzungen von Grundschullehrkräften zum sprachbildenden Unterrichten"*
  - **Fokus**: **Individuelle Kompetenzen** von Lehrkräften und deren Zusammenhang mit Schüler*innenleistungen.
  - **Ergebnis**: Fortbildungen verbessern subjektives Wissen, aber **kein Effekt auf Schüler*innenkompetenzen**.

**Divergenz**:
- #13 analysiert Sprachbildung als **institutionelles Problem** (Macht, Ressourcen), während #10 sie als **individuelle Kompetenzfrage** behandelt.

---

## Methodische Beobachtungen

### 1. **Quantitative Dominanz in der ZfE**
- **Häufige Verfahren**:
  - **Latente Profilanalysen** (#9, #13) zur Typenbildung (z. B. Schulleitungsprofile, Sprachbildungsbeauftragte).
  - **Regressionsanalysen** (#10, #12) zur Prüfung von Prädiktoren (z. B. epistemologische Überzeugungen → COR).
  - **Eye-Tracking** (#11) und **computerlinguistische Analysen** (#15) als **neue Datenquellen**.
- **Kritikpunkt**: Fast alle Studien arbeiten mit **Selbstauskünften** (#10, #12) oder **standardisierten Tests** (#11, #15), was die **Validität der Messungen** infrage stellt.

### 2. **Kollaborative Mehrautor*innen-Texte**
- **Trend**: Zunahme von **5+ Autor*innen** (z. B. #9, #11, #15, #16), besonders in COR-Studien.
- **Hintergrund**: **Großprojekte** (z. B. *Projekt COR* an deutschen Universitäten) erfordern interdisziplinäre Teams (Psychologie, Linguistik, Informatik).
- **Ausnahme**: *EthicsEd*-Beiträge sind meist **Einzelautor*innen** (#25, #26, #29), was auf eine **stärkere theoretische Prägung** hindeutet.

### 3. **Postqualitative und netzwerktheoretische Ansätze**
- **Innovation**: Beiträge in *Discourse* und *EthicsEd* nutzen **Assemblage-Theorie** (#1, #6), **Agential Realism** (#39) oder **trioethnography** (#40).
- **Beispiel**: #39 kombiniert **Levinas’ Ethik** mit **Barads Physik** und analysiert kindliche LEGO-Spiele als **ontologische Praxis**.
- **Grenze**: Diese Ansätze bleiben **theorieintensiv** und haben wenig Anschluss an empirische Bildungsforschung (z. B. keine Verbindung zu COR-Studien).

---

## Ausreißer und Einzelgänger

### 1. **Seo (2026, #2)**: *"Persistent solitude in virtual worlds: paradoxes of materiality"*
- **Thema**: **Levinas’ Solitude-Konzept** in digitalen Räumen; Analyse von Avataren als **Flucht vor Einsamkeit**.
- **Besonderheit**: Einziger Beitrag, der **digitale Materialität** philosophisch reflektiert – ohne Bezug zu COR oder KI.
- **Methode**: **Autoethnografie** und **phänomenologische Reflexion**.

### 2. **Kölsch (2026, #18)**: *"Kollaboration und Rechtfertigung"*
- **Thema**: **Ethnografie mündlicher Prüfungen** in der Geschichtswissenschaft; Fokus auf **kollektive Notengebung**.
- **Besonderheit**: Einziger Beitrag, der **Bewertungspraktiken** als **soziale Praxis** analysiert – jenseits von Kompetenzmessung.
- **Theorie**: **Bewertungssoziologie** (Boltanski/Thévenot) und **Adlerianische Psychologie**.

### 3. **Szawiel (2026, #27)**: *"Avant-garde pedagogies and academic freedom"*
- **Thema**: **Historische Analyse** der sowjetischen Kunstschulen *Svomas-Vkhutemas* (1918–1927) als **Gegenmodell zu neoliberaler Hochschulpolitik**.
- **Besonderheit**: Einziger Beitrag mit **historischer Perspektive**; nutzt **Lyotards "Performativität"** als kritischen Rahmen.

---

## Absenzen

1. **Klassische Themen der Erziehungswissenschaft**:
   - **Schulreformdebatten** (z. B. Ganztagsschule, Inklusion) fehlen fast vollständig.
   - **Soziale Ungleichheit** wird nur in **Migrationskontexten** (#4) oder **ländlichen Räumen** (#1) behandelt, nicht aber in urbanen Settings.
   - **Lehrkräftebildung** taucht nur als **Kompetenzmessung** (#10, #14) auf, nicht als **professionstheoretische Reflexion**.

2. **Theoretische Leerstellen**:
   - **Bourdieu** wird kaum rezipiert (Ausnahme: #3 zu symbolischer Gewalt in Rekrutierungsdiskursen).
   - **Feministische Theorie** (z. B. Haraway) wird nur in **posthumanistischen Kontexten** (#25, #39) genutzt, nicht aber für Analysen von Geschlechterverhältnissen in Bildung.
   - **Neomarxistische Ansätze** (z. B. Althusser, Gramsci) fehlen – trotz der starken Kritik an Kapitalismus (#25, #36).

3. **Regionale Lücken**:
   - **Afrika** und **Lateinamerika** werden nur in **dekolonialen Kontexten** (#25, #36) erwähnt, nicht aber als empirische Forschungsfelder.
   - **Osteuropa** taucht nur in der historischen Studie zu *Svomas-Vkhutemas* (#27) auf.

---

## Fazit: Drei Bewegungen im Feld
1. **Ökologische Wende**: Bildung wird zunehmend als **planetare Praxis** gedacht (#25, #26, #36), wobei **posthumanistische und dekoloniale Theorien** die Debatte dominieren.
2. **Digitalisierung als Messbarkeitsprojekt**: COR etabliert sich als **neues Kompetenzparadigma** (#11–#16), das jedoch **ethisch unreflektiert** bleibt.
3. **Prekarität als analytische Kategorie**: Bildung in Krisenkontexten (ländliche Räume, Migration, digitale Arbeit) wird nicht mehr als Defizit, sondern als **konstitutives Moment** analysiert (#1, #3, #4).

**Offene Fragen**:
- Wie lassen sich die **theoretisch radikalen Ansätze** (z. B. #25, #39) mit der **empirischen Standardisierung** (z. B. COR) verbinden?
- Warum fehlen **kritische Perspektiven auf Digitalisierung** in der *ZfE*, obwohl *EthicsEd* hier starke Impulse setzt?
- Wird die **ökologische Bildung** zum neuen Mainstream – oder bleibt sie ein Nischendiskurs?

#### MiMo ($0.0199, 10,948c, recycled)

# Trendbeobachtung: Erziehungswissenschaftliche Journals (2024–2026)

## Überblick

Das analysierte Fenster umfasst 40 Beiträge aus vier Journals (*EthicsEd*, *Discourse*, *PCS*, *ZfE*), ausschließlich aus dem Jahr 2026. Die Verteilung ist stark schief: *EthicsEd* und *ZfE* dominieren mit je 15 bzw. 20 Beiträgen, *Discourse* liefert vier, *PCS* einen. Auffällig beim ersten Durchgang: *EthicsEd* bewegt sich fast geschlossen in Richtung ökologisch-posthumanistischer Bildungstheorie; die *ZfE* ist dagegen ein Reservoir empirisch-quantitativer Bildungsforschung mit Schwerpunkten auf Sprachbildung und digitalem_REASONING. Zwischen diesen beiden Polen — philosophisch-spekulativ auf der einen, psychometrisch-deskriptiv auf der anderen — klafft eine bemerkenswerte Lücke: Es gibt kaum Beiträge, die Brücken zwischen diesen Modi schlagen.

---

## Konsolidierende Diskurse

### 1. Klimakrise als Leitproblem der Bildungsethik (*EthicsEd*)

Das auffälligste Cluster: Mindestens acht Beiträge in *EthicsEd* arbeiten an der Frage, wie Bildung auf die ökologische Krise antworten kann — und warum bisherige Antworten (Nachhaltigkeitsbildung, Kompetenzrahmen) dafür unzureichend sind.

- Rudolph et al. – *Beyond colonial-capitalist logics* (2026, id=25): Degrowth und Commons als Gegenentwurf zu wachstumslogischen Bildungszielen.
- Wolbert – *Mutual flourishing* (2026, id=26): Ersetzt „human flourishing" durch ein Verhältnis von Mensch-und-Mehr-als-Mensch (Haraway, Kimmerer).
- Felton – *Responsibility with the Other: Plant Ethics* (2026, id=31): Verantwortung *mit* Pflanzen statt *für* die Umwelt.
- Rucker – *The logic of modern education revisited* (2026, id=34): Rückgriff auf die deutsche *Allgemeine Pädagogik* und den Begriff der *Zucht*, um die ethische Dimension des Bildungsbegriffs gegen die Klimakrise zu reaktivieren.
- Posada & Surian – *Hope and agency* (2026, id=36): Critical Transformative Ecopedagogy als Synthese aus Wygotski, Freire und dekolonialer Analyse.
- Fancourt et al. – *Mediating between advocacy and freedom of thought* (2026, id=38): Narrativ-ethischer Ansatz, um den Spannungsfeld zwischen Nachhaltigkeitsadvocacy und Gedankenfreiheit aufzulösen.
- Murris & Castillo – *Responding to the 'small'* (2026, id=39): Barad und Levinas als Denkwerkzeuge für Kinderphilosophie im Zeichen ökologischer Krisen.
- Sánchez Tyson et al. – *'Reforesting' environmental education* (2026, id=40): Trioethnografie eines MSc-Programms, Arendts Natalität als Konzept der Neuanfänge.

**Was den Cluster auszeichnet:** Die Beiträge arbeiten nicht an einer einheitlichen Programmatik, sondern an einer *konvergenten Diagnose*: Gängige Nachhaltigkeitsbildung reproduziere kolonial-kapitalistische Logiken. Die Gegenentwürfe reichen von explizit dekolonialen Frameworks (Posada & Surian) über spekulativ-posthumanistische Ethiken (Felton, Murris & Castillo) bis zu einer Rückgewinnung klassischer deutscher Pädagogikbegriffe (Rucker). Der Cluster markiert eine klare Abgrenzung von technokratischen und kompetenzorientierten Zugängen — ein programmatischer *Neuanfang*, der sich als solcher auch rhetorisch inszeniert.

### 2. Critical Online Reasoning (COR) — ein methodisches Großprojekt in der *ZfE*

Vier Beiträge in der *ZfE* bilden ein kohärentes Forschungsprogramm zur digitalen Informationskompetenz von Studierenden.

- Maur et al. – *Exploring browsing patterns in COR* (2026, id=11): Eyetracking-Analyse, low-performer fixieren länger auf illustrativen Textpassagen.
- Martin de los Santos et al. – *COR skills and epistemological beliefs* (2026, id=12): Epistemologische Überzeugungen als Prädiktor für COR-Leistung (N=1939).
- Mehler et al. – *Linguistic features of student responses* (2026, id=15): Computerlinguistische Merkmale (Modus, Syntax) als Leistungsindikatoren.
- Hartig et al. – *Rating procedures for generic COR* (2026, id=16): Assessment-Entwicklung für offene Internetsuchen.

**Was den Cluster auszeichnet:** Hier konsolidiert sich eine messmethodisch ambitionierte Perspektive auf digitale Mündigkeit. Die Beiträge sind überwiegend quantitativ, teilweise mit NLP-Verfahren, und operieren innerhalb eines gemeinsamen konzeptionellen Rahmens. Auffällig: Die epistemologische Dimension wird betont (Martin de los Santos et al.), die linguistische Dimension wird ausgebaut (Mehler et al.), und die Blickbewegungsdaten fügen eine kognitive Ebene hinzu (Maur et al.). Das ist ein konzertierter Zugriff auf einen Gegenstand — und methodisch der am stärksten vernetzte Cluster der Stichprobe.

### 3. Sprachbildung als Querschnittsaufgabe (*ZfE*)

Mehrere *ZfE*-Beiträge behandeln Sprachbildung und Mehrsprachigkeit — als Kompetenzfrage, als Organisationsaufgabe und als Entwicklungsphänomen.

- Henschel & Heppt – *Kompetenzeinschätzungen sprachbildendes Unterrichten Mathematik* (2026, id=10): Lehrkräfte-Selbsteinschätzungen, positiver Zusammenhang mit Fortbildung, kein Effekt auf Schülerkompetenzen.
- Hartung et al. – *Aufgabenprofile Sprachbildungsbeauftragte* (2026, id=13): Vier Typen von Sprachbildungsbeauftragten, Latent Class Analysis.
- Li et al. – *CLIL and language development* (2026, id=19): Meta-Analyse (28 Studien, 52.235 Teilnehmende), CLIL zeigt upper-medium Effekt.
- Odermann & Mertins – *Semantisches Bewusstsein und Bilingualismus* (2026, id=22): Bilinguale Vorschulkinder erkennen Mehrdeutigkeiten früher.

**Was den Cluster auszeichnet:** Der Fokus liegt auf der Schnittstelle zwischen Sprache und Fachlernen — ein in der deutschsprachigen Bildungsforschung etabliertes Thema. Bemerkenswert ist die methodische Bandbreite (Meta-Analyse, LCA, Experimentalstudie, Survey), die eine Verdichtung empirischer Evidenz andeutet. Gleichzeitig fällt auf, dass keiner der Beiträge *Diskursanalyse* oder *Machtverhältnisse* im Sprachbildungsprozess thematisiert — das Feld arbeitet hier primär im Modus der Optimierung von Unterrichtspraxis.

---

## Differenzierungen und offene Spannungen

### Bildungsbegriff gegen die Krise — aber welcher?

Innerhalb des ökologischen Clusters in *EthicsEd* gibt es eine implizite Spannung darüber, *woher* die theoretischen Impulse kommen sollen. Rucker (id=34) greift explizit auf die deutsche Tradition der *Allgemeinen Pädagogik* zurück und reaktiviert die *Zucht* als Bildungsform — eine Geste, die in der angelsächsischen Diskussion ungewöhnlich ist. Dem gegenüber stehen die posthumanistischen und dekolonialen Ansätze (Posada & Surian, Rudolph et al., Murris & Castillo), die den anthropozentrischen Kern des klassischen Bildungsbegriffs grundsätzlich infrage stellen. Diese Spannung wird nicht explizit ausgetragen, aber sie markiert eine offene Frage: Ist der Bildungsbegriff selbst das Problem — oder seine Rettung die Antwort?

### Discomfort: Politisierung vs. Entgrenzung

Zembylas (*PCS*, id=7) und Kerswell (*EthicsEd*, id=28) greifen beide affective Regime in Bildungsinstitutionen auf, arbeiten aber gegenläufig: Zembylas zeigt, wie Institutionen *autorisiertes* Unbehagen fördern und *unautorisiertes* unterdrücken — eine Analyse, die auf politische Sichtbarmachung zielt. Kerswell dagegen kritisiert die therapeutische Überformung pädagogischer Verhältnisse (trauma-informed pedagogy) und plädiert für eine Rückkehr zu Mut, Beitrag und Verantwortung nach Adler. Beide diagnostizieren eine Schieflage im Umgang mit Verletzlichkeit, aber die normativen Richtungen divergieren: der eine will das Politische im Affect sichtbar machen, der andere den Affect aus dem Politischen herausführen.

---

## Methodische Beobachtungen

- **Methoden-Clear-cut zwischen den Journals:** Die *ZfE* ist fast vollständig quantitativ-empirisch (LPA, Regression, Eyetracking, Meta-Analyse, RCT, NLP). *EthicsEd* ist fast vollständig philosophisch-konzeptuell. *Discourse* bewegt sich dazwischen mit qualitativen und diskursanalytischen Verfahren (MCDA, Interviews, Interaktionsanalyse). Die methodischen Welten berühren sich kaum.

- **Computerlinguistische Verfahren** tauchen in der *ZfE* bei Mehler et al. (id=15) auf — ein Pilotprojekt, das grammatikalische Merkmale studentischer Texte als Leistungsindikatoren nutzt. Dies ist innerhalb der Stichprobe singulär, verweist aber auf eine mögliche methodische Erweiterung des Feldes.

- **Multi-Autor-Kollaborationen** sind in der *ZfE* Standard (4–8 Autor\*innen keine Seltenheit, vgl. Selcik et al., Maur et al., Hartig et al.), in *EthicsEd* überwiegen Einzelautor\*innen oder Zweierteams. Das korreliert mit der empirischen vs. konzeptionellen Ausrichtung.

- **Trioethnografie** als Verfahren taucht bei Sánchez Tyson et al. (id=40) auf — eine seltene, auf das Format zugeschnittene Methode, die Reflexivität und Kollaboration verbindet.

---

## Ausreißer und Einzelgänger

- **Seo – *Persistent solitude in virtual worlds*** (id=2, *EthicsEd*): Philosophisch anspruchsvoller Text zu Levinas, Nietzsche und Haraway, der Virtual Reality als Ort einer existenziellen Einsamkeit liest. Innerhalb des ökologischen Clusters nicht verankert, aber konzeptionell mit der posthumanistischen Sensibilität der anderen Beiträge verbunden.

- **Szawiel – *Avant-garde pedagogies and academic freedom*** (id=27, *EthicsEd*): Historische Rekonstruktion sowjetischer Kunstschulen (Svomas-Vkhutemas) als Gegenbild zur performativen Universität. Thematisch und methodisch (historisch-archivarisch) alleinstehend.

- **Domingo – *Recruitment rhetoric of online English schools*** (id=3, *Discourse*): Multimodale CDA der Rekrutierungsstrategien japanischer Online-Sprachschulen, die philippinische Lehrkräfte anwerben. Ein Beitrag zur politischen Ökonomie digitaler Arbeit — in der Stichprobe ohne Anschluss.

- **Arning – *Open Science / IFLA*** (id=20, *ZfE*): Eher institutional-praktisch als forschungsorientiert; ein Plädoyer für Open Access, das den üblichen *ZfE*-Modus (empirische Studie) verlässt.

---

## Absenzen

- **Digitale Bildung/EdTech** ist auffällig unterrepräsentiert: Nur Hou (id=29) behandelt Generative KI, und zwar ausschließlich aus konfuzianischer Perspektive. Keine empirische Studie zu KI im Bildungskontext, keine mediendidaktische Analyse — obwohl dies 2025/26 das beherrschende Thema der öffentlichen Bildungsdebatte ist.

- **Geschlecht, Sexualität, Queer-Theorie** fehlen nahezu vollständig. Kein einziger Beitrag greift Gender als analytische Kategorie systematisch auf (einzelne Abstracts nennen es als OpenAlex-Concept, aber ohne inhaltliche Relevanz).

- **Rassismuskritik / Critical Race Theory** taucht nur am Rand auf (Jamal Al-Deen zu Geflüchteten, Posada & Surian dekolonial) — als systematisches Analyserahmenwerk fehlt es.

- **Frühkindliche Bildung** ist mit nur einem Beitrag (Ergin, id=6) vertreten, obwohl es in der deutschsprachigen Erziehungswissenschaft ein expandierendes Feld ist.

- **Keine Debattenkultur sichtbar:** Kein Beitrag referenziert einen anderen desselben Journals aus demselben Jahrgang. Die Texte stehen nebeneinander, nicht miteinander im Gespräch.

---
