# Strategie 07 — Projekt-Material als FRONTIER-Erdung (vorwärtsgerichtet)

## Ist-Zustand (gemessen, S7-Check)
- **Keine Antrags-/Proposal-Dokumente lokal** (die `output/`-Treffer sind Digest-Einträge, keine Anträge).
- `projects.json` hat **keine** url/doi/grant_id/fulltext-Felder — nur description + relevance_shifts +
  connected_publications + funder/period.
- **`relevance_shifts` sind das dichteste, präziseste Material im ganzen Referenzsatz** und von Benjamin
  **kuratiert**, z. B. (Cultural Resilience): „Belonging (heritages, traditions, relatings, becomings),
  resourcefulness (Futurability)…", „ecological grief, mourning, loss, Anthropocene education often
  operate within Rootedness without…". Das beschreibt explizit, *welche Verschiebung* einen Artikel für
  das Projekt relevant macht.

## Strategie v1
Projekt-Antrags-Volltexte (BMBF-Anträge) beschaffen und als Erdungstext einbinden.

## Adversariale Kritik (v1)
- **Nicht verfügbar + unklarer Mehrwert:** Anträge liegen nicht lokal (Benjamin-Aufgabe), und
  Antrags-Prosa ist **Förder-Sprache** — S6 hat gemessen, dass Grant-Prosa als keep-Signal *unter* Zufall
  liegt (0.410). Ein vollständiger Antrag wäre vermutlich noch mehr davon.
- **Übersieht das Beste, was schon da ist:** die kuratierten `relevance_shifts` sind dichter und
  zielgenauer als jeder Antrag — sie zu ignorieren und stattdessen PDFs zu jagen wäre der falsche Hebel.

## Strategie v2 (Projekte als vorwärtsgerichtete Frontier-Erdung)
**Kernidee:** Publikationen erden die Vergangenheit (was Benjamin geschrieben hat); **Projekte/relevance_shifts
erden die Zukunft** (wohin sich seine Relevanz verschiebt). Das adressiert direkt den **Frontier-Blindfleck**
(Iter 37/38: das System begräbt digitale_kultur/resilienz, weil der rückblickende Œuvre-Schwerpunkt
ÄKB-dominiert ist).
1. **`relevance_shifts` als eigener Frontier-Anker** (nicht die Beschreibung): pro Projekt einen
   Forward-Looking-Embedding-Anker; gegen einen Artikel testen, ob er eine *kommende* Verschiebung trifft.
2. **Gewichtung Vergangenheit/Zukunft konfigurierbar** (profile.json): Benjamins Werte-Entscheidung aus
   Iter 38 (Kern vs. Frontier) wird hier zur Daten-Quelle, nicht nur zum Ranker-Gewicht.
3. **Antrags-Volltexte optional + niedrige Priorität:** nur falls Benjamin sie leicht bereitstellt; mit
   der ausdrücklichen Erwartung (gemessen an S6), dass sie als Relevanz-Signal **wenig** bringen und eher
   als Erdungs-Kontext für die LLM-Eskalation (Phase 3) taugen.

## Erwarteter Effekt & Messbarkeit (R2)
Ein vorwärtsgerichteter Anker, der die Frontier-Artikel (Iter 47: digitale_kultur/Überwachung) heben
*könnte* — zu MESSEN in Phase 2 gegen `user_verdict`, mit der Iter-45-Warnung (Overlap ≠ Relevanz) im Kopf.
Ehrlich offen, ob `relevance_shifts` als keep-Signal trägt oder (wie die Projekt-Beschreibung) nur
organisiert.

## → Benjamin-Aufgabe?
Optional/niedrig: Antrags-PDFs *falls leicht zur Hand*. **Nicht blockierend** — `relevance_shifts` genügen
für v2. (Die echte Benjamin-Aufgabe bleibt die Volltext-PDFs aus Strat 01.)

## → nächste
Strat 08: Profil-Modellierung (die gesketchte Stage 0) — Per-Werk-Embedding + Soft-Cluster + Topologie.
Free-Probe auf den 53 Summaries.
