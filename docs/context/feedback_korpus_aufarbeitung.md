# Korpus-Aufarbeitungs-Diagnose: Benjamins eigene Publikationen

**Datum**: 2026-05-24.

**Trigger (Benjamins Reframe-Frage a vor Iter 11)**:
> "Wie gut sind meine Texte eigentlich aufgearbeitet, und z.B. in Bezug auf die
> Diskursfelder?"

Antwort auf Basis Iter 11a-Inventar (161 Items, Collection "Benjamin's publications",
key QM7TZT44) + Iter 11b-Refs-Extraktion + heuristischer Diskursklassifikation
(venue+title substring-patterns, multi-label, V3).

## Aufarbeitungs-Bilanz

| Kategorie       | N    | mit PDF       | ≥10 cits      | ≥1 DOI in Refs |
|-----------------|------|---------------|---------------|----------------|
| **GESAMT**      | 161  | **109 (68 %)**| **68 (42 %)** | **49 (30 %)**  |
| vor 2010        |  39  |  24 (62 %)    |  13 (33 %)    |   1  (3 %)     |
| 2010–2019       |  64  |  45 (70 %)    |  23 (36 %)    |  18 (28 %)     |
| 2020+           |  53  |  40 (75 %)    |  32 (60 %)    |  30 (57 %)     |
| ohne Jahr       |   5  |   0           |   0           |   0            |

- **PDF-Coverage steigt monoton** (62 % → 75 %), aber 5 noch leere Records
  (alle 2026er AI&Society-Items, nur DOI eingetragen).
- **DOI-Refs-Extraktion ist der echte Bottleneck**: 30 % im Mittel, mit
  scharfem Knick vor 2010 (3 %) — typisch für pre-DOI-Sammelband-Literatur
  (Wulf, Foucault, etc.) und gescannte Buchkapitel.
- **Refs-Coverage post-2020 deutlich besser** (57 % DOI vs 28 % davor) durch
  OA-Publication, strukturierte Springer/Routledge-PDFs.

## Diskursfelder-Verteilung (Multi-Label, V3-Heuristik)

| Diskursraum                          | N (%)         | mit PDF | ≥10 cits | ≥1 DOI |
|--------------------------------------|---------------|---------|----------|--------|
| **aesthetische_kulturelle_bildung**  | **71 (44 %)** | 47      | 30       | 27     |
| **digitale_kultur**                  | **51 (32 %)** | 38      | 25       | 21     |
| **medienpaed**                       | **43 (27 %)** | 32      | 20       | 17     |
| **bildungstheorie**                  | **29 (18 %)** | 24      | 15       |  5     |
| erziehungswiss                       | 22 (14 %)     | 14      | 11       |  8     |
| **resilienz**                        | **20 (12 %)** | 16      |  9       | 12     |
| kulturwiss_other                     |  8 (5 %)      |  6      |  4       |  2     |

→ alle 161 Items klassifiziert, 0 unklassifiziert; 39 Items mehrfach-getaggt
(meist ÄKB+Resilienz oder ÄKB+Digital).

**Diskurs × Jahr-Bucket (N / mit-PDF)**:

| Diskursraum            | vor 2010 | 2010-2019 | 2020+   |
|------------------------|----------|-----------|---------|
| ÄKB                    | 7/3      | 29/21     | 35/23   |
| digitale_kultur        | 12/9     | 14/13     | 20/16   |
| medienpaed             | 10/7     | 24/16     | 9/9     |
| bildungstheorie        | 12/9     | 13/11     | 4/4     |
| erziehungswiss         | 4/0      | 9/5       | 9/9     |
| resilienz              |  -       | 4/2       | 16/14   |

**Lehrstuhl-Profil-Shift sichtbar**:
- bildungstheorie: 12 → 13 → 4 (zurückgehend).
- medienpaed: 10 → 24 → 9 (Peak 2010er).
- ÄKB: 7 → 29 → 35 (durchgängig wachsend).
- resilienz: 0 → 4 → 16 (klare Post-2020-Bewegung, BMBF-MetaKuBi & Programme
  „Cultural Resilience").

## Lückenliste: 21 Diskurs-zentrale 2020+ Items mit unzureichender Aufarbeitung

Items aus ÄKB/Resilienz/MediaPed/DigitaleKultur, 2020+, ohne PDF oder mit
n_citations < 10:

- **5 × AI & Society 2026** (Cultural Resilience SI): nur DOI in Zotero, keine
  PDFs — sind aktuell in Production/Akzeptanz.
- **4 × International Journal for Research in Cultural, Aesthetic, and Arts
  Education** (2023–2026): Editorials/Vorworte und ein Springer-Item ohne PDF.
- **3 × Sammelband-Einleitungen/Vorworte** („Digitalisierung in der
  Kulturellen Bildung", „MusikmachDinge", „Wie viel Körper braucht die
  kulturelle Bildung").
- **Cultural Sustainability 2023 (Springer)**: zentral für Resilienz, n_cits=0.
- **Handbook of the Anthropocene 2023**: zentral für Resilienz, n_cits=0.
- **Palgrave Handbook of Embodiment and Learning 2022**: zentral für
  ÄKB+Resilienz, n_cits=0.
- **Cultural Sedimentations (Routledge 2020)**: zentral für ÄKB+Kulturwiss.

→ priorisierte Bezugsquellen: eigene IJRCAAE-Items über Open-Access-Zugriff
zur Journal-Website; FAUbox-Suche für angenommene Manuskripte;
Mit-Herausgeber/Verlag direkt für die 5 AI&Society-2026er.

## Implikation für MOJO 2.0 (algorithmische Refs-Pipeline)

**Korrektur 2026-05-24**: „MOJO 2.0" ist primär die **algorithmische**
Refs-/Coupling-Pipeline (`journal_bot/own_refs.py` produktiv, multi-source,
additiv-inkrementell — siehe `feedback_mojo2_reframe_algorithmic.md`), NICHT
ein Volltext-LLM-Vorfilter. Volltext-LLM bleibt Eskalation für ≤10 %
Restmenge.

1. **ÄKB + Resilienz sind die am besten dokumentierten Zukunftsdiskurse**
   (75 % PDF post-2020, 57 % mit DOIs). Algorithmische Refs-/Coupling-Features
   greifen dort am stärksten, weil die DOI-Dichte den OpenAlex-Resolve sauber
   trägt.
2. **bildungstheorie hat starkes PDF-Profil (24/29 = 83 %), aber schwaches
   DOI-Profil (5/29 = 17 %)** → Refs-Extraktion ist hier weniger zuverlässig,
   coupling-Features unterperformen.
3. **erziehungswiss vor 2010 (4 Items): 0 PDFs** → strukturelle Lücke; die
   alten ZfPaed-Print-Artikel sind nicht digitalisiert verfügbar.
4. Für `f_own_coupling_union` (siehe `feedback_iter11_two_sided_coupling.md`):
   die 275 OA-Wolke-IDs stammen überwiegend aus 49 Items mit ≥1 DOI in Refs,
   davon 30 (61 %) aus den post-2020-Diskursen ÄKB/Resilienz/digitale_kultur.
   → Coupling-Signal ist stark für Recent-Discourse, schwach für Bildungs-
   theorie-Klassik.

## Methodische Begrenzungen der Diskurszuordnung

- Heuristisches Substring-Matching auf Venue+Title; keine LLM-Klassifikation.
- Multi-Label, kein Hauptdiskurs ausgewiesen.
- 39 Items mehrfach-getaggt (ÄKB+Resilienz dominant) — diese Überlappung ist
  *inhaltlich korrekt*, nicht ein Fehler der Heuristik.
- Tag-Patterns sind in `discourse_classification.json` persistiert; Refinement
  durch LLM-Resort wäre kostenpflichtig, aber sinnvoll vor MOJO-2.0-Launch.

## Daten / Artefakte

- `backtest_data/own_bibliography/inventory.json` (161 Items)
- `backtest_data/own_bibliography/refs/{key}.json` (109 Refs-Extraktionen)
- `backtest_data/own_bibliography/refs_resolved.json` (275 OA-Wolke)
- `backtest_data/own_bibliography/discourse_classification.json` (Multi-Label)
