# Strategie 09 — Denker-/Begriffs-Lexikon konsolidieren (disambiguiert)

## Ist-Zustand (gemessen, `/tmp/s9.py`)
- 400 Roh-Formen → naiv kanonisiert (Nachname+Initial) **350** (nur 12 % gemerged). Top sauber:
  Jörissen B 25, Reckwitz A 16, Cramer F 11, Foucault M 11, Latour B 10, Haraway D 9, Barad K 8.
- **11 echte Nachnamen-Kollisionen** (gleicher Nachname, verschiedene Personen):
  - **Gibson:** „James J. Gibson" (ökolog. Wahrnehmungspsych.) vs „William Gibson" (Cyberpunk-Autor)
  - **Krämer:** „Sybille Krämer" (Medienphilosophin) vs „Franz Krämer"
  - **Böhme:** „Gernot Böhme" (Atmosphären-Ästhetik) vs „Jeanette Böhme" (Erziehungswiss.)
  - **Adorno:** „Adorno" vs „Theodor W. Adorno" (gleiche Person — muss gemerged werden)
  - „Engel": teils bare-surname „Engel", teils Birgit/Juliane Engel (ambig)

## Strategie v1
named_thinkers auf Nachnamen normalisieren und als Profil-Lexikon nutzen.

## Adversariale Kritik (v1)
**Nachnamen-Merge ist nachweislich fatal (Iter 20/21 jetzt am Lexikon belegt):** er würde William Gibson
mit James Gibson, Sybille mit Franz Krämer, Gernot mit Jeanette Böhme verschmelzen — die einen sind
Benjamins Bezugsfeld (Medienphilosophie/Ästhetik), die anderen nicht. Ein Lexikon mit solchen Fehl-Merges
ist schlimmer als keins: es erzeugt Pseudo-Treffer (ein Artikel, der William Gibson zitiert, würde als
„nah an Benjamins James-Gibson-Bezug" markiert). Zugleich braucht „Adorno"/„Theodor W. Adorno" einen
echten Merge — Nachname-Initial trennt das fälschlich.

## Strategie v2 (OpenAlex-disambiguiert, full-name, kuratiert)
1. **Disambiguierung über OpenAlex-Autor-ID**, nicht Nachname: jeder Denker → Autor-Entität (Suche
   Name → Autor-ID; bei Mehrdeutigkeit über Ko-Vorkommen/Disziplin auflösen). Gibson-Problem gelöst, weil
   James J. und William verschiedene OpenAlex-IDs haben.
2. **Bare-surname-Mentions** („Adorno", „Engel") per **Kontext** auflösen (welcher Vorname kommt im selben
   Werk/Korpus vor) oder explizit als „unaufgelöst" markieren — nicht raten.
3. **Frequenz-gewichtetes, kuratiertes Artefakt** `lexicon.json`: {Autor-ID, kanonischer Name, Frequenz,
   Werke, Recency}. Plus ein Begriffs-Lexikon (key_terms, dedupliziert: „subjektivierung"/„subjektivation"
   zusammenführen — semantische, nicht String-Dedup).
4. **Wiederverwendbar + versioniert (R4):** das Lexikon erdet Strat 05 (Denker-Overlap-Signal), die
   Trigger-Autoren-Pflege (profile.json) und die Digest-Annotation — ein Artefakt, drei Verbraucher.
5. **Pre-2018-Erweiterung:** wächst mit S4 (mehr Summaries) — dann erscheinen die Frühphasen-Denker
   (Deleuze etc., in Strat 05 als fehlend gemessen).

## Erwarteter Effekt & Messbarkeit (R2)
Ein sauberes, disambiguiertes Denker-/Begriffs-Profil ohne Pseudo-Merges. Direkt messbar: Disambiguierungs-
Quote (wie viele der 350 → eindeutige OpenAlex-ID) und manuelle Stichprobe auf Fehl-Merges (Ziel: 0
Gibson-Fehler). Nachgelagert: speist das Denker-Overlap-Signal (Strat 05), dessen Relevanz-Wert in Phase 2
getestet wird (Iter-45-Vorbehalt).

## → Benjamin-Aufgabe?
Nein — disambiguierbar über OpenAlex (kostenlos). Bei hartnäckig ambigen Bare-Surnames evtl. kurze
Bestätigung, aber nicht blockierend.

## → nächste
Strat 10: einheitlicher, versionierter, additiv-idempotenter Referenz-Index — die Integration aller
Achsen (Volltext, Refs, Projekte, Profil, Lexikon).
