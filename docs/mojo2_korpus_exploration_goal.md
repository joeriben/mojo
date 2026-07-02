# /goal — Algorithmische Erschließung des MOJO-Korpus

*Rahmen: [`docs/mojo_2_grundorientierung.md`](mojo_2_grundorientierung.md) — additiv zu MOJO 1.x, §4-Erhalt, keine 1.x-Pfade anfassen.*

## Auftrag
MOJO soll die in seinem Korpus verborgene Struktur und Bewegung — Zusammenhänge zwischen den Datensätzen, Trends nach Jahr, Thema und Feld — **rein algorithmisch** erschließen, damit Frontier-LLM-Token den irreduziblen Fällen vorbehalten bleiben und Konfabulation eingegrenzt wird. Beides ist dasselbe von zwei Seiten: der un-verankerte Token ist zugleich Kostenpunkt und Konfabulationsleck.

Gebaut werden **Methoden, die zu MOJO gehören** — additiv zu 1.x, wiederholbar auf frischen Daten —, keine einmaligen Analysen. Die so erschlossenen Erkenntnisse sind MOJOs Ausgabe an den User.

Algorithmen reichen als **Vorbereiter, Strukturierer, Erder** weit; als **Entscheider** sind sie gedeckelt. „Weitestgehende Durchdringung" heißt darum maximal *strukturieren und verankern*, nicht maximal *urteilen*.

## Der Korpus
18.543 Artikel · 31 kuratierte Journals · 2010–2026 (dicht ab 2016).
Abdeckung: OpenAlex-Topics 97 % · Concepts 97 % · Jahr ~100 % · DOI 98 % · Referenzen ~80 % · Abstracts 84 %.
Validierungs-Anker: 505 User-Gold-Verdikte (sauber, klein) + 16.787 Agent-Verdikte (verrauschte Kontrastschicht).

Der Korpus ist die vollständige Erhebung einer **personalisierten Watchlist** — ein rausch-armes Abbild des Diskurses, *wie er den User erreicht*, nie neutrale Feld-Wahrheit. Jede Methode trägt diese Konditionierung (Watchlist-Komposition, Zeitfenster, Begriffsvokabular) in ihrer Ausgabe mit.

## Disziplin der Methoden
Bindend für jede gebaute Fähigkeit:

- **Handlung etikettiert.** Jede Stufe wird nach ihrer Handlung benannt — *eliminieren / strukturieren / verankern / priorisieren*. Nur geerdete Handlungen sprechen als Befund; ähnlichkeits-basierte Stufen lenken nur Aufmerksamkeit, urteilen nie.
- **Within-Journal-Dekomposition.** Die Journal-Volumina sind ungleich und zeitlich dynamisch; alle Journals wurden retrospektiv gefetcht (→ `year` nutzen, nie `fetched_at`). Jede Anteils-Trend-Aussage muss within-journal dekomponiert werden (gleichgewichtet über Journals mit ausreichender Belegung in beiden Fenstern), sonst überzeichnet der reine Korpus-Anteil die Bewegung. Der naive Korpus-Anteil darf nicht als Ausgabe erzeugbar sein.
- **Topics vor Concepts.** `openalex_topics` sind sauber; `openalex_concepts` tragen systematische False-Friends und gelten erst nach Normalisierung als Befund.
- **Mikro-LLM nur gekäfigt.** Kleine/lokale LLM sind ein Add-on zur Algo-Schicht, kein Frontier-Ersatz, und nur an Schaltstellen zugelassen, die den Zulassungstest erfüllen: (a) geschlossene Ausgabe (Enum/Schema, am Aufrufrand validiert), (b) verankerte Eingabe (lokalisierte Stelle + Features), (c) vom Algorithmus vor-verengter Geltungsbereich. Sonst bleibt die Stelle Algorithmus oder Frontier-Eskalation. Auch das billige Modell konfabuliert — die Disziplin trägt hier die ganze Last.

## Zu bauende Fähigkeiten
1. **Themen-Trajektorien** — Topics × Jahr, within-journal-dekomponiert; die Confound-Kontrolle ist der einzige Pfad.
2. **Bibliografische Kopplungs-Communities** — Cluster der ref-tragenden Artikel nach geteilter Referenzbasis, quer zu Journal und Vokabular; gegen die 7 Diskursräume gehalten.
3. **Cross-Feld-Diffusion (Lag)** — Topic × Journal/Diskursraum × Jahr: ein Thema erscheint in Feld A und erreicht Feld B *n* Jahre später.
4. **Concept-Normalisierung** — False-Friend-Rauschen quantifizieren und an einer Mikro-LLM-Schaltstelle (geschlossene Ausgabe merge/keep/relabel) bereinigen.
5. **Methoden-Signal-Karte** — jede Fähigkeit gegen die 505 Gold- und 16.787 Agent-Verdikte kontrastieren: welche Verfahren tatsächlich Signal tragen.
6. **Integration** — die tragenden Fähigkeiten in MOJOs Lauf verankern (additiv zu 1.x).

## Scope
Jetzt die **intrinsische** Korpus-Struktur (datensatz-interne Zusammenhänge und Trends). Später additiv die SARAH-gestützte, strukturierte Eigenwerk-Seite (Bezug Struktur-zu-Struktur statt Vektor-zu-Vektor).
