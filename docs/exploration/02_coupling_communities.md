# Bibliografische Kopplungs-Communities im MOJO-Korpus

**Erzeugt von** `journal_bot.corpus_explore.coupling` (rein algorithmisch, kein LLM). **Handlung:** strukturieren + verankern. Zwei Artikel sind gekoppelt, weil sie **dasselbe Werk zitieren** (belegte geteilte Zitation), nicht über Text-Ähnlichkeit — darum spricht die Struktur als Befund. **Kein** Relevanz-Urteil über Artikel.

## Konditionierung

Der Korpus ist die vollständige Erhebung einer **personalisierten Journal-Watchlist**. Die Kopplungsstruktur ist die *dieses kuratierten Stroms* — der Diskurs, wie er den User erreicht —, **nie** neutrale Feld-Struktur.

## Methode

Kantengewicht = Σ idf(r) über geteilte Referenzen mit Korpus-df ∈ [2, 50] (vielzitierte Werke als "Zitations-Stoppwörter" gekappt); Kante nur ab 2 geteilten solchen Referenzen. Community-Detection: Louvain (Auflösung 1.0, Seed 42, deterministisch). **cross-field** = Community spannt ≥ 2 thematische Diskursräume mit je ≥ 25% Anteil (Sprach-Raum "deutsche" ausgenommen).

**Daten:** 14683 ref-tragende Artikel (2016–2026); koppelnde Referenzen: 64193. **Graph:** 12034 Knoten, 84036 Kanten. **Louvain:** 81 Communities (Modularität 0.708); davon 17 mit ≥ 20 Artikeln (unten).

## Communities (≥ 20 Artikel, nach Größe)

### C1 — 1554 Artikel · 23 Journals · Jahr-Median 2023 (IQR 2020–2025) · **cross-field**

**Journals** (Konz. größtes 42%): BDS 42%, STHV 28%, AIandSoc 21%, LMT 2%, EPT 1%, JAC 1%

**Diskursräume** (Mehrfach-Mapping, Summe > 100%): Digitale Kultur 96%, Resilienz & Nachhaltigkeit / Environmental Humanities 71%, Medienpädagogik 4%, Erziehungswissenschaftliche Journals 2%, Bildungstheorie und -philosophie 2%, Deutschsprachige Journals 1%, Ästhetische und kulturelle Bildung 1%

**Topics** (sauberes Vokabular): Ethics and Social Impacts of AI (25%), Privacy, Security, and Data Protection (7%), Digital Economy and Work Transformation (5%), Social Media and Politics (5%), Innovative Human-Technology Interaction (5%), Information Systems Theories and Implementation (4%), Ethics in Clinical Research (4%), Geographies of human-animal interactions (4%)

**Geteilte Referenzbasis** (within-Community / global zitiert):

- CRITICAL QUESTIONS FOR BIG DATA, 2012 — 121/1554 der Community (8%), korpusweit 176×
- Automating Inequality: How High-Tech Tools Profile, Police, and Punish the Poor, 2018 — 78/1554 der Community (5%), korpusweit 148×
- Algorithms of oppression how search engines reinforce racism — 78/1554 der Community (5%), korpusweit 132×
- The Black Box Society, 2015 — 76/1554 der Community (5%), korpusweit 136×
- Sorting Things Out, 1999 — 72/1554 der Community (5%), korpusweit 103×
- Situated Knowledges: The Science Question in Feminism and the Privilege of Partial Perspective, 1988 — 67/1554 der Community (4%), korpusweit 148×
- Big Data, new epistemologies and paradigm shifts, 2014 — 67/1554 der Community (4%), korpusweit 90×
- The Ethnography of Infrastructure, 1999 — 62/1554 der Community (4%), korpusweit 75×

### C2 — 1264 Artikel · 28 Journals · Jahr-Median 2021 (IQR 2018–2024) · **cross-field**

**Journals** (Konz. größtes 21%): JEE 21%, EPT 17%, SAE 10%, PCS 8%, RAeE 8%, Discourse 7%

**Diskursräume** (Mehrfach-Mapping, Summe > 100%): Bildungstheorie und -philosophie 46%, Resilienz & Nachhaltigkeit / Environmental Humanities 29%, Ästhetische und kulturelle Bildung 27%, Digitale Kultur 26%, Erziehungswissenschaftliche Journals 23%, Medienpädagogik 3%, Deutschsprachige Journals 1% · 2 ohne Mapping

**Topics** (sauberes Vokabular): Environmental Education and Sustainability (18%), Posthumanist Ethics and Activism (12%), Art Education and Development (12%), Global Educational Policies and Reforms (6%), Children's Rights and Participation (6%), Geographies of human-animal interactions (5%), Indigenous and Place-Based Education (5%), Climate Change Communication and Perception (4%)

**Geteilte Referenzbasis** (within-Community / global zitiert):

- A Thousand Plateaus: Capitalism and Schizophrenia, 1989 — 103/1264 der Community (8%), korpusweit 226×
- Meeting the Universe Halfway, 2007 — 70/1264 der Community (6%), korpusweit 226×
- Staying with the Trouble, 2016 — 57/1264 der Community (5%), korpusweit 127×
- Vibrant Matter, 2010 — 55/1264 der Community (4%), korpusweit 89×
- OA:W4285719527 — 52/1264 der Community (4%), korpusweit 444×
- Meeting the Universe Halfway Quantum Physics and the Entanglement of Matter and Meaning, 2006 — 48/1264 der Community (4%), korpusweit 90×
- Posthumanist Performativity: Toward an Understanding of How Matter Comes to Matter, 2003 — 44/1264 der Community (3%), korpusweit 119×
- Canadian Journal of Environmental Education, 2001 — 41/1264 der Community (3%), korpusweit 47×

### C3 — 1174 Artikel · 28 Journals · Jahr-Median 2021 (IQR 2018–2024) · **cross-field**

**Journals** (Konz. größtes 22%): EPT 22%, PCS 13%, DIME 11%, Discourse 10%, SAE 9%, REPCS 9%

**Diskursräume** (Mehrfach-Mapping, Summe > 100%): Bildungstheorie und -philosophie 61%, Erziehungswissenschaftliche Journals 42%, Digitale Kultur 28%, Ästhetische und kulturelle Bildung 25%, Resilienz & Nachhaltigkeit / Environmental Humanities 8%, Medienpädagogik 4%, Deutschsprachige Journals 1% · 3 ohne Mapping

**Topics** (sauberes Vokabular): Global Education and Multiculturalism (16%), Critical Race Theory in Education (14%), Educator Training and Historical Pedagogy (12%), Global Educational Policies and Reforms (11%), Art Education and Development (9%), Critical and Liberation Pedagogy (5%), Indigenous and Place-Based Education (4%), Diverse Music Education Insights (4%)

**Geteilte Referenzbasis** (within-Community / global zitiert):

- The Cultural Politics of Emotion, 2014 — 39/1174 der Community (3%), korpusweit 63×
- OA:W4285719527 — 38/1174 der Community (3%), korpusweit 444×
- Decolonizing Methodologies: Research and Indigenous Peoples, 2000 — 37/1174 der Community (3%), korpusweit 48×
- 8 Decolonizing Methodologies: Research and Indigenous Peoples, 2024 — 35/1174 der Community (3%), korpusweit 40×
- Teaching to transgress: education as the practice of freedom, 1995 — 35/1174 der Community (3%), korpusweit 91×
- 1. Toward a Theory of Culturally Relevant Pedagogy, 1995 — 34/1174 der Community (3%), korpusweit 56×
- Research Is Ceremony: Indigenous Research Methods, 2008 — 31/1174 der Community (3%), korpusweit 43×
- Feeling Power: Emotions and Education, 1999 — 30/1174 der Community (3%), korpusweit 40×

### C4 — 1164 Artikel · 22 Journals · Jahr-Median 2022 (IQR 2020–2025)

**Journals** (Konz. größtes 78%): AIandSoc 78%, BDS 6%, EPT 4%, BJET 3%, STHV 2%, PDSE 1%

**Diskursräume** (Mehrfach-Mapping, Summe > 100%): Digitale Kultur 92%, Resilienz & Nachhaltigkeit / Environmental Humanities 9%, Bildungstheorie und -philosophie 6%, Medienpädagogik 6%, Erziehungswissenschaftliche Journals 2%, Ästhetische und kulturelle Bildung 1%, Deutschsprachige Journals 1% · 1 ohne Mapping

**Topics** (sauberes Vokabular): Ethics and Social Impacts of AI (43%), Neuroethics, Human Enhancement, Biomedical Innovations (16%), Psychology of Moral and Emotional Judgment (11%), Artificial Intelligence in Healthcare and Education (9%), Explainable Artificial Intelligence (XAI) (7%), Embodied and Extended Cognition (7%), AI in Service Interactions (6%), Social Robot Interaction and HRI (6%)

**Geteilte Referenzbasis** (within-Community / global zitiert):

- The global landscape of AI ethics guidelines, 2019 — 80/1164 der Community (7%), korpusweit 129×
- Superintelligence: paths, dangers, strategies, 2015 — 64/1164 der Community (5%), korpusweit 81×
- I.—COMPUTING MACHINERY AND INTELLIGENCE, 1950 — 59/1164 der Community (5%), korpusweit 103×
- The ethics of algorithms: Mapping the debate, 2016 — 54/1164 der Community (5%), korpusweit 91×
- AI4People—An Ethical Framework for a Good AI Society: Opportunities, Risks, Principles, and Recommendations, 2018 — 53/1164 der Community (5%), korpusweit 84×
- The Ethics of AI Ethics: An Evaluation of Guidelines, 2020 — 51/1164 der Community (4%), korpusweit 71×
- Minds, brains, and programs, 1980 — 43/1164 der Community (4%), korpusweit 74×
- OA:W4285719527 — 39/1164 der Community (3%), korpusweit 444×

### C5 — 1102 Artikel · 27 Journals · Jahr-Median 2021 (IQR 2019–2024) · **cross-field**

**Journals** (Konz. größtes 23%): EERJ 23%, Discourse 19%, LMT 17%, EPT 10%, PCS 7%, PDSE 6%

**Diskursräume** (Mehrfach-Mapping, Summe > 100%): Erziehungswissenschaftliche Journals 52%, Digitale Kultur 34%, Medienpädagogik 27%, Bildungstheorie und -philosophie 20%, Resilienz & Nachhaltigkeit / Environmental Humanities 8%, Deutschsprachige Journals 3%, Ästhetische und kulturelle Bildung 2%

**Topics** (sauberes Vokabular): Global Educational Policies and Reforms (29%), Global Education and Multiculturalism (14%), Digital Education and Society (11%), Educator Training and Historical Pedagogy (8%), Teacher Education and Leadership Studies (7%), Higher Education Governance and Development (6%), Online Learning and Analytics (6%), Youth Education and Societal Dynamics (5%)

**Geteilte Referenzbasis** (within-Community / global zitiert):

- The teacher's soul and the terrors of performativity, 2003 — 64/1102 der Community (6%), korpusweit 111×
- Digital education governance: data visualization, predictive analytics, and ‘real-time’ policy instruments, 2015 — 48/1102 der Community (4%), korpusweit 59×
- Editorial: the datafication of education, 2019 — 44/1102 der Community (4%), korpusweit 50×
- Machine behaviourism: future visions of ‘learnification’ and ‘datafication’ across humans and digital technologies, 2019 — 43/1102 der Community (4%), korpusweit 55×
- Big Data in Education: The digital future of learning, policy and practice, 2017 — 43/1102 der Community (4%), korpusweit 71×
- Introduction: Critical studies of digital education platforms, 2021 — 39/1102 der Community (4%), korpusweit 43×
- Automation, APIs and the distributed labour of platform pedagogies in Google Classroom, 2020 — 37/1102 der Community (3%), korpusweit 38×
- Discipline and Punish, 2007 — 35/1102 der Community (3%), korpusweit 95×

### C6 — 1030 Artikel · 26 Journals · Jahr-Median 2022 (IQR 2020–2024) · **cross-field**

**Journals** (Konz. größtes 57%): BJET 57%, JRTE 15%, MedienPaed 9%, AIandSoc 5%, ZfE 2%, LMT 2%

**Diskursräume** (Mehrfach-Mapping, Summe > 100%): Digitale Kultur 82%, Medienpädagogik 69%, Erziehungswissenschaftliche Journals 20%, Deutschsprachige Journals 12%, Bildungstheorie und -philosophie 5%, Resilienz & Nachhaltigkeit / Environmental Humanities 2%, Ästhetische und kulturelle Bildung 1%

**Topics** (sauberes Vokabular): Innovative Teaching and Learning Methods (25%), Online Learning and Analytics (24%), Educational Games and Gamification (18%), Online and Blended Learning (16%), Virtual Reality Applications and Impacts (11%), Visual and Cognitive Learning Processes (9%), Intelligent Tutoring Systems and Adaptive Learning (7%), Impact of Technology on Adolescents (6%)

**Geteilte Referenzbasis** (within-Community / global zitiert):

- Using thematic analysis in psychology, 2006 — 50/1030 der Community (5%), korpusweit 354×
- Mind in Society: The Development of Higher Psychological Processes, 1978 — 47/1030 der Community (5%), korpusweit 159×
- School Engagement: Potential of the Concept, State of the Evidence, 2004 — 45/1030 der Community (4%), korpusweit 68×
- Critical Inquiry in a Text-Based Environment: Computer Conferencing in Higher Education, 1999 — 38/1030 der Community (4%), korpusweit 48×
- The Power of Feedback, 2007 — 35/1030 der Community (3%), korpusweit 60×
- Effectiveness of virtual reality-based instruction on students' learning outcomes in K-12 and higher education: A meta-analysis, 2013 — 34/1030 der Community (3%), korpusweit 36×
- Becoming a Self-Regulated Learner: An Overview, 2002 — 33/1030 der Community (3%), korpusweit 39×
- A systematic review of immersive virtual reality applications for higher education: Design elements, lessons learned, and research agenda, 2019 — 32/1030 der Community (3%), korpusweit 33×

### C7 — 725 Artikel · 20 Journals · Jahr-Median 2021 (IQR 2019–2024)

**Journals** (Konz. größtes 66%): ZfE 66%, EERJ 7%, BJET 6%, JRTE 5%, MedienPaed 4%, DIME 3%

**Diskursräume** (Mehrfach-Mapping, Summe > 100%): Erziehungswissenschaftliche Journals 85%, Deutschsprachige Journals 72%, Digitale Kultur 12%, Medienpädagogik 11%, Bildungstheorie und -philosophie 5%, Resilienz & Nachhaltigkeit / Environmental Humanities 1%, Ästhetische und kulturelle Bildung 1%

**Topics** (sauberes Vokabular): Sociology and Education Studies (18%), Education Methods and Technologies (13%), Early Childhood Education and Development (10%), Teacher Education and Leadership Studies (9%), Educational Assessment and Improvement (9%), School Choice and Performance (8%), Motivation and Self-Concept in Sports (8%), Parental Involvement in Education (8%)

**Geteilte Referenzbasis** (within-Community / global zitiert):

- Stichwort: Professionelle Kompetenz von Lehrkräften, 2006 — 73/725 der Community (10%), korpusweit 98×
- Cutoff criteria for fit indexes in covariance structure analysis: Conventional criteria versus new alternatives, 1999 — 55/725 der Community (8%), korpusweit 123×
- Professionelle Kompetenz von Lehrkräften. Ergebnisse des Forschungsprogramms COACTIV, 2011 — 45/725 der Community (6%), korpusweit 48×
- Handbuch der Forschung zum Lehrerberuf, 2011 — 44/725 der Community (6%), korpusweit 47×
- OA:W4285719527 — 43/725 der Community (6%), korpusweit 444×
- Multiple Imputation for Nonresponse in Surveys, 1987 — 42/725 der Community (6%), korpusweit 45×
- Beyond Dichotomies, 2015 — 41/725 der Community (6%), korpusweit 46×
- Visible Learning: A Synthesis of Over 800 Meta-Analyses Relating to Achievement, 2008 — 38/725 der Community (5%), korpusweit 48×

### C8 — 665 Artikel · 17 Journals · Jahr-Median 2022 (IQR 2020–2023)

**Journals** (Konz. größtes 67%): MedienPaed 67%, merz 17%, ZfE 7%, BJET 2%, AIandSoc 2%, LMT 1%

**Diskursräume** (Mehrfach-Mapping, Summe > 100%): Deutschsprachige Journals 91%, Medienpädagogik 88%, Erziehungswissenschaftliche Journals 9%, Digitale Kultur 7%, Bildungstheorie und -philosophie 1%, Resilienz & Nachhaltigkeit / Environmental Humanities 1%, Ästhetische und kulturelle Bildung 1%

**Topics** (sauberes Vokabular): Sociology and Education Studies (40%), Education Methods and Technologies (21%), Child Development and Digital Technology (14%), Impact of Technology on Adolescents (13%), Linguistic Education and Pedagogy (9%), Social Media and Politics (9%), Digital literacy in education (7%), Innovation, Technology, and Society (5%)

**Geteilte Referenzbasis** (within-Community / global zitiert):

- Medienbildung - Eine Einführung, 2009 — 52/665 der Community (8%), korpusweit 68×
- OA:W4285719527 — 38/665 der Community (6%), korpusweit 444×
- Zur Entstehung und Entwicklung zentraler Begriffe bei der pädagogischen Auseinandersetzung mit Medien, 2011 — 28/665 der Community (4%), korpusweit 31×
- Strategie der Kultusministerkonferenz "Bildung in der digitalen Welt", 2018 — 28/665 der Community (4%), korpusweit 35×
- Orientierungsrahmen für die Entwicklung von Curricula für medienpädagogische Studiengänge und Studienanteile, 2017 — 25/665 der Community (4%), korpusweit 26×
- Medienpädagogik und digitaler Kapitalismus. Für die Stärkung einer gesellschafts- und medienkritischen Perspektive, 2017 — 25/665 der Community (4%), korpusweit 27×
- Von der Mediatisierung zur tiefgreifenden Mediatisierung, 2018 — 22/665 der Community (3%), korpusweit 26×
- Muster, 2019 — 21/665 der Community (3%), korpusweit 25×

### C9 — 657 Artikel · 22 Journals · Jahr-Median 2022 (IQR 2020–2024) · **cross-field**

**Journals** (Konz. größtes 56%): PDSE 56%, EPT 22%, AIandSoc 5%, LMT 4%, BJET 3%, PCS 1%

**Diskursräume** (Mehrfach-Mapping, Summe > 100%): Digitale Kultur 71%, Medienpädagogik 63%, Bildungstheorie und -philosophie 26%, Erziehungswissenschaftliche Journals 5%, Resilienz & Nachhaltigkeit / Environmental Humanities 3%, Ästhetische und kulturelle Bildung 2%, Deutschsprachige Journals 0% · 1 ohne Mapping

**Topics** (sauberes Vokabular): Digital Education and Society (53%), Misinformation and Its Impacts (9%), Higher Education Practises and Engagement (9%), Neuroethics, Human Enhancement, Biomedical Innovations (8%), COVID-19 and Mental Health (6%), Digital Media and Philosophy (5%), Ethics and Social Impacts of AI (4%), Global Educational Policies and Reforms (4%)

**Geteilte Referenzbasis** (within-Community / global zitiert):

- Postdigital science and education, 2018 — 178/657 der Community (27%), korpusweit 243×
- Postdigital Education in Design and Practice, 2018 — 63/657 der Community (10%), korpusweit 84×
- Postdigital Dialogue, 2018 — 62/657 der Community (9%), korpusweit 83×
- What Does the ‘Postdigital’ Mean for Education? Three Critical Perspectives on the Digital, with Implications for Educational Research and Practice, 2019 — 55/657 der Community (8%), korpusweit 95×
- OA:W4253722997 — 46/657 der Community (7%), korpusweit 47×
- Learning in the Age of Digital Reason, 2017 — 41/657 der Community (6%), korpusweit 43×
- The Digital University, 2017 — 38/657 der Community (6%), korpusweit 41×
- OA:W4206803701 — 38/657 der Community (6%), korpusweit 48×

### C10 — 520 Artikel · 26 Journals · Jahr-Median 2020 (IQR 2018–2023) · **cross-field**

**Journals** (Konz. größtes 42%): EPT 42%, EthicsEd 24%, PCS 6%, AIandSoc 5%, Discourse 4%, REPCS 3%

**Diskursräume** (Mehrfach-Mapping, Summe > 100%): Bildungstheorie und -philosophie 80%, Erziehungswissenschaftliche Journals 37%, Resilienz & Nachhaltigkeit / Environmental Humanities 26%, Digitale Kultur 15%, Ästhetische und kulturelle Bildung 8%, Medienpädagogik 4%, Deutschsprachige Journals 2%

**Topics** (sauberes Vokabular): Philosophy, Ethics, and Existentialism (21%), Digital Media and Philosophy (11%), Global Educational Policies and Reforms (9%), Education and Critical Thinking Development (8%), Digital Education and Society (7%), Critical Theory and Philosophy (7%), Global Education and Multiculturalism (7%), Critical and Liberation Pedagogy (6%)

**Geteilte Referenzbasis** (within-Community / global zitiert):

- Taking care of youth and the generations, 2010 — 32/520 der Community (6%), korpusweit 35×
- OA:W4285719527 — 31/520 der Community (6%), korpusweit 444×
- OA:W4207046476 — 28/520 der Community (5%), korpusweit 46×
- Towards an Ontology of Teaching, 2019 — 28/520 der Community (5%), korpusweit 32×
- OA:W4231877591 — 27/520 der Community (5%), korpusweit 65×
- The Beautiful Risk of Education, 2014 — 25/520 der Community (5%), korpusweit 44×
- OA:W4239627609 — 23/520 der Community (4%), korpusweit 36×
- Beautiful Risk of Education, 2015 — 23/520 der Community (4%), korpusweit 42×

### C11 — 499 Artikel · 27 Journals · Jahr-Median 2021 (IQR 2019–2023) · **cross-field**

**Journals** (Konz. größtes 24%): BJET 24%, JRTE 17%, LMT 16%, MedienPaed 5%, Discourse 5%, BDS 4%

**Diskursräume** (Mehrfach-Mapping, Summe > 100%): Digitale Kultur 73%, Medienpädagogik 49%, Erziehungswissenschaftliche Journals 32%, Bildungstheorie und -philosophie 11%, Deutschsprachige Journals 9%, Resilienz & Nachhaltigkeit / Environmental Humanities 6%, Ästhetische und kulturelle Bildung 5%

**Topics** (sauberes Vokabular): Teaching and Learning Programming (24%), Child Development and Digital Technology (21%), Literacy, Media, and Education (16%), Educational Games and Gamification (11%), Social Media and Politics (10%), Innovative Teaching and Learning Methods (9%), Misinformation and Its Impacts (8%), Impact of Technology on Adolescents (7%)

**Geteilte Referenzbasis** (within-Community / global zitiert):

- Computational thinking, 2006 — 47/499 der Community (9%), korpusweit 70×
- Mindstorms: Children, Computers, And Powerful Ideas, 1980 — 32/499 der Community (6%), korpusweit 48×
- Scratch, 2009 — 25/499 der Community (5%), korpusweit 25×
- Computational Thinking in K–12, 2013 — 23/499 der Community (5%), korpusweit 25×
- Review on teaching and learning of computational thinking through programming: What is next for K-12?, 2014 — 21/499 der Community (4%), korpusweit 23×
- The Maker Movement in Education, 2014 — 20/499 der Community (4%), korpusweit 26×
- OA:W4285719527 — 20/499 der Community (4%), korpusweit 444×
- Using thematic analysis in psychology, 2006 — 20/499 der Community (4%), korpusweit 354×

### C12 — 419 Artikel · 25 Journals · Jahr-Median 2020 (IQR 2018–2023) · **cross-field**

**Journals** (Konz. größtes 25%): Discourse 25%, PCS 20%, EPT 15%, EERJ 15%, DIME 4%, REPCS 3%

**Diskursräume** (Mehrfach-Mapping, Summe > 100%): Erziehungswissenschaftliche Journals 66%, Bildungstheorie und -philosophie 40%, Digitale Kultur 16%, Medienpädagogik 7%, Ästhetische und kulturelle Bildung 7%, Resilienz & Nachhaltigkeit / Environmental Humanities 4%, Deutschsprachige Journals 3%

**Topics** (sauberes Vokabular): Global Education and Multiculturalism (18%), Global Educational Policies and Reforms (14%), Social and Cultural Dynamics (8%), Youth Education and Societal Dynamics (8%), Multilingual Education and Policy (8%), Children's Rights and Participation (7%), Educator Training and Historical Pedagogy (6%), Higher Education Governance and Development (5%)

**Geteilte Referenzbasis** (within-Community / global zitiert):

- Handbook of Theory and Research for the Sociology of Education., 1987 — 34/419 der Community (8%), korpusweit 79×
- Outline of a Theory of Practice, 1977 — 26/419 der Community (6%), korpusweit 43×
- An Invitation of Reflexive Sociology, 1993 — 24/419 der Community (6%), korpusweit 36×
- Distinction: A Social Critique of the Judgement of Taste., 1985 — 21/419 der Community (5%), korpusweit 37×
- Using thematic analysis in psychology, 2006 — 21/419 der Community (5%), korpusweit 354×
- OA:W4285719527 — 20/419 der Community (5%), korpusweit 444×
- Distinction: A Social Critique of the Judgement of Taste*, 2018 — 20/419 der Community (5%), korpusweit 35×
- The Dialogic Imagination: Four Essays, 1981 — 19/419 der Community (5%), korpusweit 35×

### C13 — 365 Artikel · 18 Journals · Jahr-Median 2020 (IQR 2018–2023) · **cross-field**

**Journals** (Konz. größtes 44%): BJET 44%, JRTE 29%, MedienPaed 7%, LMT 5%, AIandSoc 4%, ZfE 3%

**Diskursräume** (Mehrfach-Mapping, Summe > 100%): Digitale Kultur 83%, Medienpädagogik 58%, Erziehungswissenschaftliche Journals 36%, Deutschsprachige Journals 11%, Bildungstheorie und -philosophie 3%, Resilienz & Nachhaltigkeit / Environmental Humanities 1%, Ästhetische und kulturelle Bildung 1%

**Topics** (sauberes Vokabular): Online and Blended Learning (25%), Gender and Technology in Education (18%), Digital literacy in education (16%), Child Development and Digital Technology (14%), Innovative Teaching and Learning Methods (14%), Technology Adoption and User Behaviour (14%), Impact of Technology on Adolescents (13%), Education and Technology Integration (11%)

**Geteilte Referenzbasis** (within-Community / global zitiert):

- Technological Pedagogical Content Knowledge: A Framework for Teacher Knowledge, 2006 — 68/365 der Community (19%), korpusweit 112×
- Perceived Usefulness, Perceived Ease of Use, and User Acceptance of Information Technology, 1989 — 56/365 der Community (15%), korpusweit 107×
- User Acceptance of Information Technology: Toward A Unified View1, 2003 — 46/365 der Community (13%), korpusweit 87×
- Teacher Technology Change, 2010 — 38/365 der Community (10%), korpusweit 46×
- Technological Pedagogical Content Knowledge (TPACK), 2009 — 35/365 der Community (10%), korpusweit 37×
- Teacher beliefs and technology integration practices: A critical relationship, 2012 — 35/365 der Community (10%), korpusweit 45×
- Those Who Understand: Knowledge Growth in Teaching, 1986 — 32/365 der Community (9%), korpusweit 91×
- Addressing first- and second-order barriers to change: Strategies for technology integration, 1999 — 31/365 der Community (8%), korpusweit 36×

### C14 — 350 Artikel · 21 Journals · Jahr-Median 2021 (IQR 2019–2024) · **cross-field**

**Journals** (Konz. größtes 61%): JTE 61%, EPT 10%, PCS 6%, JAE 6%, EERJ 3%, AIandSoc 3%

**Diskursräume** (Mehrfach-Mapping, Summe > 100%): Bildungstheorie und -philosophie 88%, Resilienz & Nachhaltigkeit / Environmental Humanities 63%, Erziehungswissenschaftliche Journals 12%, Ästhetische und kulturelle Bildung 11%, Digitale Kultur 10%, Medienpädagogik 2%, Deutschsprachige Journals 0% · 1 ohne Mapping

**Topics** (sauberes Vokabular): Adult and Continuing Education Topics (45%), Critical and Liberation Pedagogy (18%), Global Educational Policies and Reforms (13%), Ego Development and Educational Practices (11%), Education and Critical Thinking Development (10%), Global Education and Multiculturalism (9%), Higher Education Practises and Engagement (6%), Innovative Education and Learning Practices (5%)

**Geteilte Referenzbasis** (within-Community / global zitiert):

- The Handbook of Transformative Learning: Theory, Research, and Practice, 2012 — 92/350 der Community (26%), korpusweit 98×
- Transformative Dimensions of Adult Learning, 1991 — 91/350 der Community (26%), korpusweit 113×
- Learning as Transformation: Critical Perspectives on a Theory in Progress, 2001 — 65/350 der Community (19%), korpusweit 78×
- Transformative Learning as a Metatheory, 2015 — 60/350 der Community (17%), korpusweit 67×
- Transformative Learning: Theory to Practice, 1997 — 46/350 der Community (13%), korpusweit 66×
- Transformative Learning as Discourse, 2003 — 44/350 der Community (13%), korpusweit 48×
- Transformative learning in practice: insights from community, workplace, and higher education, 2009 — 39/350 der Community (11%), korpusweit 40×
- Perspective Transformation, 1978 — 36/350 der Community (10%), korpusweit 38×

### C15 — 227 Artikel · 19 Journals · Jahr-Median 2021 (IQR 2019–2023) · **cross-field**

**Journals** (Konz. größtes 57%): ArtsEdPolRev 57%, PCS 11%, SAE 6%, EPT 5%, EERJ 5%, EthicsEd 4%

**Diskursräume** (Mehrfach-Mapping, Summe > 100%): Ästhetische und kulturelle Bildung 66%, Bildungstheorie und -philosophie 28%, Erziehungswissenschaftliche Journals 25%, Digitale Kultur 11%, Resilienz & Nachhaltigkeit / Environmental Humanities 4%, Medienpädagogik 3%, Deutschsprachige Journals 2% · 1 ohne Mapping

**Topics** (sauberes Vokabular): Diverse Music Education Insights (44%), Art Education and Development (30%), Teacher Education and Leadership Studies (23%), Educational Environments and Student Outcomes (10%), Early Childhood Education and Development (8%), Educator Training and Historical Pedagogy (6%), Global Education and Multiculturalism (6%), Creativity in Education and Neuroscience (5%)

**Geteilte Referenzbasis** (within-Community / global zitiert):

- The teacher's soul and the terrors of performativity, 2003 — 14/227 der Community (6%), korpusweit 111×
- What Is Agency?, 1998 — 14/227 der Community (6%), korpusweit 28×
- The role of beliefs in teacher agency, 2015 — 14/227 der Community (6%), korpusweit 25×
- Agency and learning in the lifecourse: Towards an ecological perspective, 2007 — 12/227 der Community (5%), korpusweit 14×
- Is the edTPA the Right Choice for Evaluating Teacher Readiness?, 2015 — 12/227 der Community (5%), korpusweit 12×
- Teacher Agency, 2015 — 11/227 der Community (5%), korpusweit 18×
- OA:W4285719527 — 11/227 der Community (5%), korpusweit 444×
- Music education and the well-rounded education provision of the Every Student Succeeds Act: A critical policy analysis, 2017 — 11/227 der Community (5%), korpusweit 11×

### C16 — 103 Artikel · 13 Journals · Jahr-Median 2021 (IQR 2018–2023) · **cross-field**

**Journals** (Konz. größtes 27%): JRTE 27%, BJET 19%, AIandSoc 17%, LMT 17%, ZfE 5%, BDS 4%

**Diskursräume** (Mehrfach-Mapping, Summe > 100%): Digitale Kultur 86%, Medienpädagogik 37%, Erziehungswissenschaftliche Journals 37%, Bildungstheorie und -philosophie 7%, Deutschsprachige Journals 6%, Resilienz & Nachhaltigkeit / Environmental Humanities 6%, Ästhetische und kulturelle Bildung 3%

**Topics** (sauberes Vokabular): Impact of Technology on Adolescents (31%), Social Media and Politics (28%), Online and Blended Learning (23%), Literacy, Media, and Education (11%), Innovative Teaching and Learning Methods (10%), Innovative Human-Technology Interaction (10%), Child Development and Digital Technology (8%), Hate Speech and Cyberbullying Detection (6%)

**Geteilte Referenzbasis** (within-Community / global zitiert):

- How and Why Educators Use Twitter: A Survey of the Field, 2014 — 22/103 der Community (21%), korpusweit 26×
- Informal online communities and networks as a source of teacher professional development: A review, 2016 — 18/103 der Community (17%), korpusweit 19×
- Revisiting How and Why Educators Use Twitter: Tweet Types and Purposes in #Edchat, 2019 — 16/103 der Community (16%), korpusweit 16×
- Engagement through microblogging: educator professional development via Twitter, 2014 — 11/103 der Community (11%), korpusweit 12×
- “Together we are better”: Professional learning networks for teachers, 2016 — 11/103 der Community (11%), korpusweit 13×
- Twenty years of online teacher communities: A systematic review of formally-organized and informally-developed professional learning groups, 2018 — 10/103 der Community (10%), korpusweit 13×
- How and why are educators using Instagram?, 2020 — 10/103 der Community (10%), korpusweit 10×
- High-tech, hard work: an investigation of teachers’ work in the digital age, 2016 — 10/103 der Community (10%), korpusweit 26×

### C17 — 23 Artikel · 6 Journals · Jahr-Median 2024 (IQR 2019–2024) · **cross-field**

**Journals** (Konz. größtes 61%): BJET 61%, EERJ 22%, LMT 4%, EPT 4%, PCS 4%, PDSE 4%

**Diskursräume** (Mehrfach-Mapping, Summe > 100%): Medienpädagogik 70%, Digitale Kultur 70%, Erziehungswissenschaftliche Journals 26%, Bildungstheorie und -philosophie 9%

**Topics** (sauberes Vokabular): International Student and Expatriate Challenges (48%), Higher Education Governance and Development (43%), Global Education and Multiculturalism (39%), Higher Education Practises and Engagement (35%), Global Educational Policies and Reforms (22%), Online and Blended Learning (17%), Digital Education and Society (9%), Online Learning and Analytics (9%)

**Geteilte Referenzbasis** (within-Community / global zitiert):

- Conceptualizing Internationalization at a Distance: A “Third Category” of University Internationalization, 2020 — 10/23 der Community (43%), korpusweit 11×
- Internationalization at a Distance, 2016 — 7/23 der Community (30%), korpusweit 7×
- Internationalisation at a Distance and at Home: Academic and social adjustment in a South African distance learning context, 2019 — 6/23 der Community (26%), korpusweit 6×
- No human mobility: how is knowledge mobile in a context of internationalisation at a distance? a case study, 2023 — 6/23 der Community (26%), korpusweit 7×
- Infrastructures of immobility: enabling international distance education students in Africa to<i>not</i>move, 2019 — 5/23 der Community (22%), korpusweit 5×
- Redefining Internationalization at Home, 2015 — 4/23 der Community (17%), korpusweit 5×
- Conceptualising place and non-place in internationalisation of higher education research, 2023 — 4/23 der Community (17%), korpusweit 4×
- Internationalization in higher education: global trends and recommendations for its future, 2020 — 4/23 der Community (17%), korpusweit 8×
