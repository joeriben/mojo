# Iter 17 — geerdeter Bezugs-Extraktor (substitutive Komponente)

## Anforderung
Das eigentliche 2.0-Motiv (feedback_llm_bezuege_konfabulation): nicht „wie relevant" (Score), sondern
**welcher konkrete Werk-Bezug** — als Ersatz für die LLM-Konfabulation (Audit: nur 12.7 % corroborated,
55.9 % ungrounded). Pro Artikel die geteilten Referenzen mit *benannten* Eigenpublikationen
(`own_refs.pub_refs` ∩ `articles.openalex_refs`). Diagnose: für wie viele keeper benennbar?

## Messung (`iter_17_grounded_bezug.py`)
Artikel mit OA-Refs: 384/461. Eigenpublikationen mit aufgelösten Refs: **62/161**.
| Gruppe | n | ≥1 konkreter Bezug |
|---|---|---|
| alle | 461 | 13 % |
| keeper (scan+les) | 188 | 21 % |
| LES (lesenswert) | 79 | **34 %** |
| **blind keeper (screening)** | 25 | **0 %** |
| IGN (ignorieren) | 273 | 7 % |

Konkrete Beispiele (verifizierbar, kein LLM):
- `[EduTheory]` „Predictive Curricula and the Foreclosure of Pedagogical Futures" ↔ geteilte Ref mit
  Benjamins **„Schule und Medialität" (2022)**
- `[AIandSoc]` „Hybrid epistemic practices … academic assemblages" ↔ **„Bildungstheoretische
  Strukturanalysen von hybriden, digital-materiellen …" (2024)**

## Harte Kritik
- **Die substitutive Mechanik funktioniert und erfüllt das 2.0-Ziel — für ihren Teilbereich (P16):**
  wo sie feuert, produziert sie einen **konkreten, verifizierbaren, nicht-konfabulierten** Bezug
  („teilt Referenz X mit deiner Publikation Y"). Genau das soll die LLM-Erzähler-Rolle ersetzen.
  Das diskriminiert auch: keeper 21 % vs IGN 7 % (3×), LES 34 %.
- **Aber sie ist genau dort leer, wo sie gebraucht wird (P15, der vernichtende Caveat):** **0 %** der
  blinden keeper haben einen benennbaren Bezug. Das bestätigt Iter 11 hart — der blinde Strom ist
  bibliometrisch ungeerdet. Als *Filter* ist der Bezugs-Extraktor damit untauglich; als *Anreicherung*
  des Digest-Eintrags (wenn vorhanden: benennen; wenn nicht: schweigen statt konfabulieren) ist er
  exakt richtig. Die Rolle ist Enrichment, nicht Triage — das muss klar getrennt bleiben.
- **Coverage ist datenlimitiert, nicht nur real (P3):** nur **62/161** Eigenpublikationen haben
  aufgelöste Refs (Pre-2010/DOI-Lücke, Memory feedback_korpus_aufarbeitung). Die 21 % keeper-Coverage
  ist also eine *Untergrenze* — mit vollständigerer Aufarbeitung der Eigenbibliografie steigt sie. Ich
  verkaufe die 21 % nicht als Decke, sondern als aktuellen Aufarbeitungs-Stand.
- **Ehrlich über die Richtung:** auch mit perfekter Aufarbeitung bliebe der blinde Strom (0 %) das
  Problem — geteilte Referenzen *können* dort nicht entstehen, wenn der Artikel Benjamins Quellen nicht
  zitiert (Iter 11: konzeptuell, nicht bibliografisch verwandt). Der Bezugs-Extraktor rettet die
  bibliometrisch-nahen keeper (das intentional-positive Umfeld), nicht die konzeptuell-fernen.

## → nächste Iteration
Iter 18: Coverage-Hebel **bezugsautoren.db** (208 Autoren, 6404 Werke mit `referenced_works_json`) —
zweite Erdungsschicht: teilt der Artikel Refs mit Werken von Autoren aus Benjamins direktem Umfeld
(nicht nur mit Benjamins eigenen Refs)? Memory project_bezugsautoren_db: halbiert ungrounded
(59 %→30 %). Hebt das die keeper-Coverage über die 62-Publikations-Decke — und bleibt blind trotzdem 0 %?
