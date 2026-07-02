# Strategie 02 — Refs-Auflösung 12 % → höher (der größte Erdungshebel)

## Ist-Zustand (gemessen, `/tmp/s2.py` + `/tmp/s2probe.py`)
- pub_refs: 6 244 gesamt, **nur 770 (12 %) zu OpenAlex-ID aufgelöst.** `own_coupling` (das bibliometrische
  Erdungssignal) verhungert daran (Iter 43: blind 4 %).
- resolution_state: **5 421 `text_unresolved`** (versucht, gescheitert), 484 text_resolved, 286 doi_resolved.
  → Der Resolver lief, aber die **Text-Trefferquote war ~8 %.**
- 99 % der Unaufgelösten haben `ref_text` (APA-Strings) → Rohmaterial vorhanden, nichts verloren.
- Resolver-Code existiert (`text_resolve.py`, `resolve.py`, `oa_titles.py`).

## Strategie v1
Unaufgelöste `ref_text` per OpenAlex-Title-Search auflösen.

## Live-Probe v1 (15 Refs) → 27 % konfidente Treffer — aber die Fehler sind diagnostisch
| Ref-Anfang | OpenAlex Top-Hit | Urteil |
|---|---|---|
| „Abdilla, A., Arista, N., Baker…" | „**Abundant intelligences: placing AI within Indigenous knowledge**" | korrekt, aber meine Metrik = 0.00 |
| „Ernst, W. (2013). Digital memory…" | „Digital Memory and the Archive" | echter Treffer |
| „Cramer (2014). What is post-digital?" | „The qualitative content analysis process" | echte OpenAlex-Fehlausgabe |
| „Gabrys (2018). Becoming planetary. E-Flux" | (no result) | echte OpenAlex-Lücke (e-flux ungeindext) |

## Adversariale Kritik (v1)
**Die gemessenen 27 % unterschätzen das Mögliche dramatisch — der Engpass ist nicht OpenAlex, sondern
mein Verfahren:**
1. **Parsing-Fehler:** meine Titel-Heuristik (längstes Segment) griff bei APA-Refs die **Autorenliste**
   statt des Titels. OpenAlex fand das richtige Paper trotzdem (Top-Hit „Abundant intelligences…"), aber
   mein Wort-Overlap verglich Autoren↔Titel → 0.00 = **False Negative der Konfidenz-Metrik**, keine
   Resolutions-Lücke.
2. **Konfidenz-Metrik falsch:** Overlap(query, title) ist sinnlos, wenn query die Autoren sind. Die
   Kreuzprüfung muss **Jahr + Erstautor-Nachname** gegen den Kandidaten halten, nicht Query↔Titel.
3. **Echte Decke existiert aber:** e-flux, dt. Volkskunde/Kulturwissenschaft, alte Sammelbände sind in
   OpenAlex **genuin schlecht indexiert** — ein Teil bleibt prinzipiell unauflösbar (kein Over-Claim).

## Strategie v2 (strukturiertes Parsing + Kreuzprüfung + Fallback + ehrliche Decke)
1. **APA/Chicago strukturiert parsen:** Autoren / Jahr / **Titel** / Venue trennen (Regex auf „(JAHR).
   TITEL. VENUE"-Muster; Fallback `refextract`-artig). Query = **Titel-Feld**, nicht Rohstring.
2. **Konfidenz = Jahr-Match ∧ Erstautor-Nachname-Match ∧ Titel-Overlap ≥ 0.6** (drei-Faktor, statt
   einem). Eliminiert die „qualitative content analysis"-Fehlausgaben.
3. **Crossref-Fallback** für Treffer mit DOI-Spur (53 ref_doi sind teils abgeschnitten → reparieren).
4. **Self-Citation-Bonus:** Refs auf „Jörissen, B." gegen das eigene Korpus auflösen (own_refs hat die
   canonical_ids) — direkte Eigen-Kopplung.
5. **Ehrliche Rest-Decke:** e-flux/zkmb/dt.-kulturwiss. Quellen als `resolution_state='oa_absent'`
   markieren (nicht als Fehler) — sie sind der dokumentierte Sonderfall (CLAUDE.md: zkmb/e-flux nicht in
   OpenAlex).

## Erwarteter Effekt & Messbarkeit (R2, P14)
Text-Trefferquote von ~8 % auf geschätzt **40–65 %** (Spanne, weil die OpenAlex-Decke für dt./Kunst-Quellen
unbekannt ist) → pub_refs-Auflösung von 12 % Richtung 35–50 %, Publikationen mit ≥1 Ref deutlich über 39 %.
**Zu MESSEN in der Implementierung an einer 100er-Stichprobe (OpenAlex kostenlos, kein LLM)**, nicht zu
projizieren. Nachgelagert (Phase 2): hebt das `own_coupling` und die grounded-Bezug-Coverage (Iter 43)?

## Re-Test (gemessen 2026-05-31, bereinigter Korpus, `/tmp/s2_diag/garbage/probe/tierB.py`)
Der v2-Resolver ist **bereits implementiert** (`text_resolve.py`: APA-Parse → Titel-Query → Erstautor∧Jahr±1∧
Titel-Containment≥0.85). Die „12 %" sind sein Ergebnis. Re-Test der 5 421 `text_unresolved`:

| Kategorie | Anteil | Diagnose |
|---|---|---|
| **UNPARSEABLE** (Parser→None) | **2 038 (38 %)** | **Großteils gar keine Refs:** Seiten-Header („498 B. Jörissen and L. Klepacki"), Autoren-Bios, TOC-Zeilen, **und an Zeilen zerrissene Refs** („C., Stenzel, M. & Weidner, V. (2019)…" = Mitten-in-Autorenliste-Split). → **Extraktions-Problem (Strat 03), nicht Parser-Decke.** |
| **parseable, no OA-Treffer** | 3 383 (62 %) | Live-Probe (n=90) bricht das auf: |
| ↳ resolve bei Frisch-Lauf | ~10 % | **Stale Negativ-Cache** (2 967 `{}`-Einträge): OA-Abdeckung gewachsen / Cache vor Resolver-Iteration geschrieben. **Frei, risikolos rückholbar.** |
| ↳ no_candidates | ~39 % | OA-genuin-absent (Web/News/dt. Nischen-Print/e-flux). **Ehrliche Decke.** |
| ↳ weiter abgelehnt | ~50 % | Großteils Titel-Ratio **weit** unter Schwelle (andere Werke / Parse-Rauschen), **keine** Near-Misses. |

**Negativ-Befund (wertvoll): Schwellen-Relaxierung bringt fast nichts.** Eine getestete Tier-B-Regel
(Titel-Containment ≥0.78 **mit** Autor-Match ∧ Jahr±1 ∧ ≥4 Kandidaten-Tokens) akzeptierte auf 90 Refs
**+1 Treffer (~1 %)**. Das 0.85-Matching ist **gut kalibriert** — Lockern lohnt das False-Positive-Risiko
nicht (das die `own_coupling`-Erdung systematisch verschmutzen würde, vgl. Docstring-Warnung).

**Korrektur der v2-Projektion (40–65 %): zu optimistisch.** Die einzige freie, risikolose Anhebung ist der
**Frisch-Lauf** (Negativ-Cache leeren → Re-Resolve): ~10 % von 3 383 ≈ **+340 Refs**, also 12 % → **~18 %**.
Der Rest ist **strukturell gedeckelt**: OA-Abdeckung (~40 % absent) + Extraktions-Fragmentierung (Strat 03).
**Der größere verbleibende Hebel ist Strat 03 (Ref-Segmentierung beim Extrahieren)**, nicht der Resolver.

**Ausgeführt:** Negativ-Cache geleert + `mojo refs build` (Text-Resolve-Catch-up) → gemessene DB-Auflösung
siehe Lauf-Log. Schwelle bleibt unverändert (Messung sagt: nicht lohnend).

## → Benjamin-Aufgabe?
Nein — vollständig selbst erledigbar (OpenAlex Polite-Pool, kostenlos, idempotent, cachebar).

## → nächste
Strat 03: Volltext-Normalisierung — der 4,17-Mio-Zeichen-Ausreißer und OCR/Header-Müll verzerren sowohl
`rich_sim` als auch die Refs-Extraktion.
