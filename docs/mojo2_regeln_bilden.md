# Auswahlregeln in MOJO bilden — Spezifikationsentwurf

Nicht eingebaut. Vorlage zur Durchsicht.

## Die Aufgabe

Die Auswahlkriterien sind **empirisch aus dem Material zu ermitteln, das auf der
Plattform anfällt** — nicht aus Wortlisten im Quelltext und nicht aus
Selbstauskunft, die jemand in einen Prompt kopiert. Und das Ermitteln ist eine
Aufgabe von MOJO für seine Nutzer, nicht eine Analyse, die ein Assistent einmal
außerhalb durchführt.

Damit fällt beides weg, was ich bisher gebaut habe: die Marker-Regex (trifft
semantische Verhältnisse nicht) und der Regelblock in `agent.py` (schreibt einen
bestimmten Nutzer in den Quelltext).

## Woraus die Regeln entstehen

Das Material liegt in MOJO und wächst jede Woche:

| Quelle | Umfang heute | was sie trägt |
|---|---|---|
| Urteile in der Oberfläche | 913 | die Entscheidung selbst |
| Memos des Nutzers | 53 | sein Vokabular für den Grund |
| überstimmte Agent-Begründungen | 217 | ein ausgesprochener Grund und sein Widerruf |
| Abstract, Themen, Zeitschrift, Kanal | vollständig | der Gegenstand, über den entschieden wurde |

Der Kanal ist dabei Pflichtangabe jeder Auswertung: die Behalten-Quote schwankt
über ihn von 15 % (Screening) bis 85 % (Zitationsfund). Wer ihn nicht festhält,
misst den Beschaffungsweg und nennt es Kriterium.

## Wie ein Regelvorschlag entsteht

**Nicht** durch Anpassung eines Gewichtsvektors und **nicht** durch Wortlisten.
Durch kontrastierendes Lesen:

1. **Kontrastpaare bilden.** Zwei Artikel, bei denen Zeitschrift und Kanal
   gleich sind und ein Thema geteilt wird, aber das Urteil gegenläufig ausfiel.
   Damit sind Gelegenheit, Beschaffungsweg und Gegenstand konstant — was übrig
   bleibt, ist der Grund. (Auf dem heutigen Bestand: ~1 800 solcher Paare.)
2. **Lesen lassen.** Ein Modell bekommt eine Gruppe solcher Paare plus die Memos
   des Nutzers und benennt, was die Ja-Seite von der Nein-Seite trennt — in
   **seinem** Vokabular, das in den Memos steht. Nicht »empirisch-quantitativ«,
   sondern »reduktionistische Tool-Perspektive«, wenn er das so nennt.
3. **Als typisierte Regel an einem Platz formulieren.** Siehe nächster
   Abschnitt: der Typ und die Position sind Teil der Regel, nicht Auslegung.

## Regeltypen und Reihenfolge

Eine Regel ist kein freier Satz, sondern ein Satz mit **Typ** und **Platz**.
Ohne beides entstehen Scheinwidersprüche: »dekoloniales öffnet« und »niemals
Richtung Gesundheitsversorgung« widersprechen sich nur, wenn man sie als
ungeordnete Menge liest. Geordnet ist der Fall bei der ersten Regel entschieden
und die Öffnung erreicht ihn nie.

| Typ | wirkt | aufhebbar |
|---|---|---|
| **terminale Sperre** | verwirft endgültig | nein — keine Öffnung greift |
| **aufhebbare Sperre** | verwirft | ja — durch eine spätere Öffnung |
| **Öffnung** | hebt eine aufhebbare Sperre auf »vertieft prüfen« | — |
| **Verengung** | hebt den Maßstab in einem Bereich | — |
| **Kalibrierung** | misst gegen eine benannte Bezugsgröße | — |

Für die vom Nutzer bereits benannten Regeln ergibt das:

```
1  terminale Sperre   Gesundheit, Versorgung, Pflege, Care, Urban Planning
2  aufhebbare Sperre  psychologisch + quantitativ + kompetenzorientiert
                      (psychoanalytisch fällt NICHT darunter)
3  Öffnung            politisch, fachpolitisch, dekolonial
                      → hebt 2 und bloße Fremdheit auf »vertieft prüfen«
4  Verengung          im Kernfeld entscheidet der Zugriff, nicht die Nähe
5  Kalibrierung       Medienpädagogik gegen das Werkprofil
```

Die Ansicht muss den Typ deshalb mit vorschlagen und den Platz zeigen — eine
Sperre, die an der falschen Stelle steht, ist eine andere Regel.

## Wie ein Vorschlag geprüft wird, BEVOR er dem Nutzer gezeigt wird

Ein Vorschlag, der nur plausibel klingt, ist wertlos — die Konfabulationsgefahr
liegt genau hier. Deshalb wird jede Kandidatenregel vor der Vorlage gegen
**zurückgehaltene** Urteile gefahren, die bei ihrer Bildung nicht vorlagen:

- **wie oft sie überhaupt greift** (eine Regel, die 4 Artikel trifft, ist keine)
- **was sie auf der zurückgehaltenen Menge richtig und falsch macht**
- **welche eigenen Entscheidungen des Nutzers sie verletzt** — namentlich, mit
  Titel, damit er den Gegenfall selbst ansieht

Regeln, die auf der zurückgehaltenen Menge nichts tragen, werden gar nicht erst
vorgelegt. Was vorgelegt wird, trägt seine Zahlen sichtbar mit.

## Was der Nutzer sieht und tut

Eine Ansicht in MOJO, in Domänensprache — kein Regel-Editor, keine Schwellen,
keine Gewichte:

```
Vorschlag                                            greift bei   trifft
─────────────────────────────────────────────────────────────────────────
»Gesundheitsversorgung und Pflege verwerfe ich,        104 von      86 %
  unabhängig davon, wie digital die Studie ist.«          913

  Gebildet aus 12 Entscheidungen, darunter:
    ✗ »AI in nursing education: a competence framework«
    ✗ »Digital health literacy among caregivers«
  Dagegen spricht 1 Entscheidung von dir:
    ✓ »Decolonizing global health knowledge production«

  [ übernehmen ]  [ Wortlaut ändern ]  [ verwerfen ]  [ später ]
```

Der Gegenfall steht ausdrücklich dabei. Er ist der Ort, an dem der Nutzer die
Bedingung nachschärft — hier etwa: die Sperre gilt, außer bei dekolonialem
Zugriff. Genau diese Verfeinerung ist der Ertrag, und sie kommt von ihm.

## Wo die übernommenen Regeln liegen und wie sie wirken

- **Als Daten, nicht als Code.** Eine Regelliste beim Nutzer (neben
  `profile.json`), versioniert, mit Datum und dem Material, aus dem sie stammt.
  `journal_bot` liefert das Verfahren, kein einziger Nutzername steht darin.
- **In der groben Vorprüfung**, als geordneter Block: erst Sperren, dann
  Öffnungen, die Sperren aufheben, dann Verengungen im Kernfeld, dann
  Kalibrierungen gegen das Werkprofil. Die Reihenfolge ist Teil der Regel.
- **Mit drei Ausgängen statt zwei.** Die Öffnung braucht einen eigenen Weg:
  nicht durchwinken, sondern vertieft prüfen. Das zieht `batch_screen()` nach.
- **Rückgekoppelt.** Jede spätere Korrektur des Nutzers an einem Artikel, den
  eine Regel getroffen hat, wird dieser Regel zugeordnet. Eine Regel, deren
  Widerspruchsquote steigt, kommt von selbst wieder zur Durchsicht hoch.

## Was daran offen ist

- **Ab wann lohnt es sich?** Bei 913 Urteilen und 53 Memos ist die Ja-Seite
  dünn. Für einen neuen Nutzer mit 40 Urteilen wird MOJO keine Regel vorschlagen
  können. Es braucht eine Untergrenze, unter der die Ansicht sagt, was noch
  fehlt, statt Vorschläge zu erfinden.
- **Wie viele Regeln verträgt die Vorprüfung?** Sie sieht Titel und 500 Zeichen
  Abstract. Zwanzig Regeln in einem Prompt sind vermutlich schlechter als sechs.
- **Der Wortlaut gehört dem Nutzer.** Übernimmt er einen Vorschlag unverändert,
  steht mein Satz in seiner Regel. Die Änderungsmöglichkeit ist deshalb nicht
  Zierrat, sondern die Stelle, an der aus meinem Satz seiner wird.
