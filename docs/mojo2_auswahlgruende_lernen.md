# Auswahlgründe lernen (Entwicklungsaufgabe)

**Datum**: 2026-07-18.
**Status**: vorgemerkt, nicht begonnen.
**Anspruch**: MOJO muss die Art von Erkenntnis, die bisher nur ein Assistent im
Dialog erzeugt hat, am Ende **selbst** erzeugen. Nutzer\*innen werden dafür
niemanden haben.

---

## Problem

Die Begründung, *warum* ein Text zur Prüfung vorgelegt wird, stützt sich derzeit
auf thematische Ähnlichkeit zu den Kurzfassungen des Eigenwerks. Themenlabels
(OpenAlex-Topics, Concepts) beschreiben aber **Gegenstände**, nicht deren
theoretische Verfasstheit. Damit ist die Repräsentation unterbestimmt: derselbe
Gegenstand, in lösungsorientierter oder in theoretisch begründeter Bearbeitung,
erhält dasselbe Label.

Empirisch (gerechnet am 2026-07-18 über `articles.db`, 913 Nutzerentscheidungen):

- **1 838 kontrollierte Paare** — gleiche Zeitschrift, mindestens ein geteiltes
  OpenAlex-Topic, gegenläufiges Nutzerurteil (`lesenswert`/`pflichtlektuere`
  gegen `ignorieren`).
- Verteilt auf 13 Zeitschriften, stark ungleich: AI & Society 1 057,
  Zeitschrift für Erziehungswissenschaft 343, MedienPädagogik 154, weiter
  abfallend. **Ohne Schichtung lernt ein Verfahren vor allem über eine
  Zeitschrift.**
- Beispiel aus AI & Society, identisches Themenlabel, gegenläufiges Urteil:
  behalten „Communicative surrogates and the ethics of LLM-mediated
  communication"; verworfen „Development and validation of the Generative AI
  Self-Efficacy Scale", „Who lets AI take over? Cross-national variation in
  willingness to delegate", „Resource allocation by algorithms".
- Die Labels selbst sind teils fehlerhaft (ein Paar entstand über das geteilte
  Topic „Consumer behavior in food and health" bei einem Text über
  Erziehungswissenschaft seit 1990). **Labels taugen zum Auffinden von Paaren,
  nicht als Repräsentation.**

Kontrollierte Paare sind das eigentliche Lernsubstrat: eine Entscheidung über
ein Paar isoliert die trennende Variable, hundert Entscheidungen über
unverbundene Texte tun das nicht.

---

## Kategorien, keine Achsen

Auswahlgründe sind **Kategorien**, keine Zweipol-Skalen. Das ist keine
Formulierungsfrage, sondern bestimmt die Datenstruktur.

Belegbar an den Gründen, die bei anderen Nutzer\*innen zu erwarten sind —
Methodenqualität, Region, Aktualität, ob der eigene Name vorkommt: keiner davon
hat einen Gegenpol, auf dem jemand symmetrisch liegen könnte. Sie treffen zu
oder nicht, mehrere zugleich, und sie sind nicht ineinander überführbar. Eine
Achsen-Repräsentation würde eine Symmetrie unterstellen, die es nicht gibt, und
sie würde jede Kategorie zwingen, sich einen Gegenpol zu erfinden.

## Zwei Ebenen: Kategorie und Wert

Die Software braucht beides getrennt, sonst wird nutzerspezifischer Inhalt zur
Struktur:

- **Kategorie** = *Art* des Auswahlgrundes. Wenige, allgemein, für alle
  Nutzer\*innen dieselben Slots. Auslieferbar.
- **Wert** = was eine konkrete Person in dieser Kategorie sucht oder verwirft.
  Nutzerspezifisch, ausschließlich aus deren Entscheidungen gewonnen. **Nicht**
  auslieferbar.

„Solutionistischer und mediennutzungsorientierter Zugriff statt
medientheoretisch begründetem" ist **kein Kategoriename**, sondern ein Wert.
Seine Kategorie heißt **theoretische Verfasstheit**. Genau diese Verwechslung
lag in der ersten Fassung dieses Dokuments: der Wert stand an der Stelle der
Kategorie, wodurch die Position eines einzelnen Nutzers zur Datenstruktur
geworden wäre.

## Kategorien (Struktur)

Ausgangsbestand, an dem entwickelt wird. Offen und erweiterbar:

| Kategorie | Erhebbar aus |
|---|---|
| theoretische Verfasstheit | Titel + Abstract, konditioniert aufs Werkprofil |
| Erkenntnisform | Titel + Abstract |
| Textsorte | Titel + Metadaten |
| Referenzrahmen | Titel + Abstract |
| Bezug zum eigenen Werk | `citation_hits`, `own_refs.db` (bereits im Code) |
| Methodenqualität | Abstract, ggf. Volltext |
| Herkunft/Region | Metadaten |
| Aktualität | Metadaten |

Die letzten drei sind bei diesem Nutzer **nicht belegt** — sie stehen hier, weil
sie bei anderen zu erwarten sind. Das ist der Test, ob die Kategorienebene
wirklich allgemein ist: sie muss Slots enthalten, die der Entwicklungsnutzer
leer lässt.

## Werte (Befund für *einen* Nutzer)

Aus einer Blindstichprobe (100 vom Screening verworfene Artikel, 18 zurückgeholt)
und den kontrollierten Paaren. **Nur** Startpunkt für die Erprobung an diesen
Daten, niemals Vorbelegung:

- **theoretische Verfasstheit** — verworfen: solutionistischer und
  mediennutzungsorientierter Zugriff; gesucht: medientheoretisch begründeter.
  *(Wortlaut des Nutzers. „VR", „E-Learning", „Mediennutzung in Familien" sind
  keine gemeinsame Thematik, sondern ein gemeinsamer Zugriff — das Thema ist
  nicht orthogonal zum Kriterium, es war nur zu grob beschrieben.
  „Solutionistisch" ist ein kritischer Begriff und darf nicht zu
  „lösungsorientiert" abgeschliffen werden.)*
  Weitere Ausprägungen derselben Kategorie in anderen Gegenstandsbereichen:
  Ästhetik in bildungstheoretisch formierender Funktion statt als Kunst- und
  Werkanalyse; subjektivierungs- und praxistheoretischer Zugriff statt Policy-
  und Steuerungsanalyse; Fach-Selbstverständigung über das Theorieprogramm statt
  über Methodenstandards.
- **Erkenntnisform** — verworfen: Wirkungsmessung, Evaluation,
  Steuerungsanalyse.
- **Referenzrahmen** — ein fremder Rahmen öffnet einen Text. *(Herkunft:
  kontrolliertes Paar — gleiche Zeitschrift, gleicher Jahrgang, gleiche
  Ausgangsfrage, einziger Unterschied der nicht-westliche Bezugsrahmen.)*
- **Textsorte** — verworfen: Dienstformate (Rezension, Neuerscheinungen,
  Linktipps, Nachruf).

**Die Kategorienliste ist Saatgut, kein Schema.** Der Inferenzschritt muss
Kategorien benennen können, die dort nicht stehen. Gäbe man dem Modell nur die
Liste zum Abhaken, fände es ausschließlich, was wir vorher erraten haben — und
„theoretische Verfasstheit" wäre so nie entstanden.

**Vokabular:** Werte werden im Wortlaut der Nutzerin geführt. Paraphrasen
verschieben die Bedeutung; die Abschleifung von „solutionistisch" zu
„lösungsorientiert" ist der dokumentierte Fall.

---

## Verfahren

1. **Paare finden** — kontrollierte Differenzen aus den Nutzerentscheidungen,
   nach Zeitschrift geschichtet. Fällt die gleiche Zeitschrift als Kontrolle
   aus (kleine Journalmengen), Kontrolle über das Thema allein — schwächer, und
   als schwächer auszuweisen.
2. **Inferieren** — Titel und Abstract beider Seiten lesen und benennen, was
   trennt, im Vokabular der Nutzerin. Konditioniert auf das Werkprofil aus der
   H7-Aggregation (Positionen, Quellen, Begriffe mit Zustimmungs-, Kontrast- und
   Vorbehaltskanten) — das ist die Datenlage, die theoretische Verfasstheit
   trägt und die Themenlabels nicht haben.
3. **Validieren** — jedes Kriterium gegen zurückgehaltene Paare prüfen. Was auf
   ungesehenen Paaren nicht trennt, fliegt raus. Das ist die Sperre gegen
   Konfabulation: ein Kriterium muss vorhersagen, nicht plausibel klingen.
4. **Zeigen** — was übrig bleibt, ist sichtbar, lesbar und korrigierbar, nicht
   ein verborgener Gewichtsvektor. Es liefert die Begründung, warum ein Text
   vorgelegt wird.

## Kaltstart

Bei null Entscheidungen hat das System nur das Werkprofil und muss das sagen,
statt Sicherheit zu simulieren. Der Rückfall darf **nicht** thematische
Ähnlichkeit sein — genau die trennt nachweislich nicht. Konstruktive Folge: die
ersten Vorlagen nicht zufällig ziehen, sondern gezielt als Paare (gleicher
Gegenstand, unterschiedliche Verfasstheit).

---

## Harte Randbedingungen

- **Kein Personen-Hardcoding.** Weder Namen noch Präferenzen einer konkreten
  Person im Code. Die nutzerspezifische Schicht liegt bereits richtig in
  Konfiguration (`journals.json`, `diskursraeume.json`, `profile.json`,
  `corpus.json`, `summaries.json`) — dabei bleibt es.
- **Keine geschlossene Kriterien-Taxonomie.**
- **Keine ausgelieferten Werte.** Kategorien sind Struktur und dürfen mit der
  Software kommen; Werte sind der Befund über eine konkrete Person und dürfen es
  nicht. Ausgeliefert wird das Verfahren, nicht sein Ergebnis.
- **Keine Paraphrase des Nutzervokabulars.** Werte werden im Wortlaut geführt.

### Offene Code-Schuld (konkret)

Erledigt am 2026-07-18 (die nutzersichtbaren Stellen):

- `journal_bot/research_agent.py:384` — `"zitiert Benjamin"` → „zitiert eigenes
  Werk".
- `journal_bot/research_agent.py:1663` — Intent-Token `"benjamins
  publikationen"` → `"meine publikationen"`.
- `journal_bot/cli.py:648` — Fehlermeldung nannte als Beispiel „QM7TZT44 für
  'Benjamin's publications'" → generische Beschreibung.

Offen, rein kosmetisch:

- `journal_bot/signals.py` — `benjamin_refs` in **vier Docstring-Zeilen**
  (517, 767, 1372 und eine Kommentarzeile) als Prosa-Bezeichnung des eigenen
  Referenz-Sets. Kein Bezeichner im Code, keine Laufzeitwirkung → bei
  Gelegenheit auf `own_refs` ziehen.
- Weitere Nennungen in Kommentaren und Docstrings (`signals.py`,
  `entry_composer.py`, `combine.py`, `bezugsautoren.py`, `batch_digest.py`)
  dokumentieren Entscheidungsherkunft und sind als Projekthistorie legitim —
  aber vor einer Open-Source-Veröffentlichung durchzusehen.

---

## Was nicht behauptet ist

Ob das Verfahren überträgt, ist **offen**. Es liegen die Daten genau eines
Nutzers vor. Prüfbar ist es an diesen; die Konstruktion muss so gebaut sein,
dass ein Scheitern sichtbar wird, statt sich hinter plausiblen Sätzen zu
verstecken.

Vor jedem Batch-Lauf gilt die Kostenregel: erst Einzelkosten an einer Handvoll
Paaren messen, zeigen, bestätigen lassen.
