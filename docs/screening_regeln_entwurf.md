# Entwurf: Triage-Regeln für die grobe Vorprüfung

Ersetzt die beiden flachen Listen in `SCREENING_SUFFIX` (`journal_bot/agent.py`).
Nicht eingebaut, nicht gerechnet — Vorlage zur Durchsicht.

## Was jetzt dort steht und warum es der Fehler ist

```
"weitergeben" when:
- Topical overlap with the researcher's themes/positions
- Methodologically/phenomenally noteworthy for the observation field
- Cites Jörissen or cites works from the bibliography      ← unerfüllbar
"ignorieren" when:
- Obviously unrelated to the research
- Purely empirical/applied without theoretical connection
- Topically in a field without overlap (e.g. pure psychometrics, nursing didactics)
When in doubt: weitergeben.
```

Eine Feldliste, überall dieselbe, ohne Sperre und ohne Öffnung. Genau das
produziert die Begründung, die Benjamin mit „Kulturelle Resilienz" überstimmt
hat: *„weder Medienbildung, noch ästhetisch-kulturelle Bildung, noch
Digitalität → ignorieren"*. Die dritte Zeile verlangt außerdem etwas, das diese
Stufe nicht sehen kann — Titel und 500 Zeichen Abstract, kein
Literaturverzeichnis.

## Entwurf

```
=== SCREENING MODE ===
You receive a LIST of articles (title, journal, abstract excerpt).
For each article, decide which of THREE paths it takes:

[ID] weitergeben|vertiefen|ignorieren — reason in ≤15 words

Do NOT decide by topical overlap. A topic label does not tell you how a text is
constituted, and the constitution is what decides here. Apply the rules in this
order; a later rule can lift an earlier one only where it says so.

1. CLOSED SECTORS — ignorieren, and rule 3 does not lift this.
   Health care, health systems, clinical and therapeutic settings, nursing,
   care systems. Closed regardless of framing, method, or how digital the study
   is. A study on AI in nursing education is a nursing study.

2. CLOSED APPROACH — ignorieren.
   The combination of a psychological framing, a quantitative standard design,
   and a competence orientation. Any one alone is not enough; together they are
   the signature that is reliably dropped. Psychoanalytic work is NOT covered by
   this rule — it belongs to the opposite side (see rule 5).

3. THE OPENING — lifts rule 2 and any merely foreign topic to "vertiefen".
   A text from outside the research fields is NOT dropped when it carries a
   political, professional-political (the discipline's own institutional
   politics: curricula, teacher education, funding regimes, disciplinary
   self-understanding), or decolonial dimension. Foreign subject matter is
   tolerated on that condition. It does not lift rule 1.

4. INSIDE THE CORE FIELDS THE STANDARD TIGHTENS, it does not relax.
   Proximity is not a reason to pass something through. Within the researcher's
   own fields the question becomes how the phenomenon is taken up: as a cultural,
   aesthetic and subjectivating matter, or as equipment and its application.
   Avatars and virtual worlds: yes. VR headsets as devices: no. Same field,
   opposite outcome. When a core-field article treats its object as a tool whose
   effectiveness is to be established, it is NOT a find, it is the drop case.

5. TRADITION DECIDES INSIDE A NOMINAL FIELD.
   Classic mainstream psychology: practically never. Psychoanalytic work with
   cultural-studies connections: yes. The field name is the same; the tradition
   is what separates them. Read for the tradition, not the label.

6. MEDIA PEDAGOGY IS JUDGED NARROWLY.
   Anything media-pedagogical is measured against THIS researcher's
   understanding of media pedagogy, as set out in the profile block above — not
   against media pedagogy in general. A media-literacy-and-skills article is not
   media pedagogy in his sense.

When none of the rules speaks: weitergeben. Passing through costs one analysis;
missing costs the find.
No explanation, no introduction, just the lines.
```

## Was hier zur Entscheidung ansteht

**Kein Widerspruch — eine Reihenfolge.** Ich hatte hier einen Konflikt zwischen
»dekoloniales öffnet« und »niemals Richtung Gesundheitsversorgung« gemeldet. Den
gibt es nicht: die Sektorsperre steht an erster Stelle und ist terminal, der Fall
ist dort entschieden, die Öffnung erreicht ihn nie. Der Konflikt entsteht nur,
wenn man die Regeln als ungeordnete Menge liest und dann eine Auflösung sucht.
Die Reihenfolge ist Teil der Regel, nicht Auslegung — Typen und Plätze in
`mojo2_regeln_bilden.md`.

**Der dritte Weg ist neu.** Bisher kennt die Stufe nur `weitergeben|ignorieren`.
`vertiefen` heißt: nicht durchwinken, sondern in die Einschätzung mit dem
ausdrücklichen Auftrag, an der Öffnung zu prüfen. Das muss in `batch_screen()`
und im Aufrufer nachgezogen werden.

**Was noch fehlt und wo es herkäme.** Du sagst „den Rest hast Du in den Daten" —
`urban planning` hast du genannt, weitere gesperrte Sektoren stehen in den 607
Ablehnungen. Die kann ich dir als Kandidatenliste vorlegen: nach Themenfeldern
gruppiert, mit Anzahl und Behalten-Quote, damit du siehst, was sich als Sperre
anbietet. Ohne Rechnung geht das nicht, aber es ist eine Auszählung, keine
Regelfindung — entscheiden würdest du.

**Regel 6 hängt am Werkprofil.** Sie verweist auf den H7-Block im Systemprompt.
Der ist eingeschaltet und steht dort; ohne ihn hat die Regel keinen Bezug.
