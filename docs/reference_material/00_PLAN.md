# Plan — Optimierung des Referenzmaterials (MOJO 2.0)

## Auftrag (Phasen)
1. **JETZT:** Qualität des Referenzmaterials messen (User-Volltexte, User-Projekte, User-Profile) →
   **10 Strategien** zu dessen Optimierung entwerfen, jede **adversarial selbst kritisieren** und
   **iterativ verbessern**.
2. **DANACH:** Anhand des optimierten Referenzmaterials alle algorithmischen Strategien neu testen, neue
   entwerfen.
3. **DANN:** Kombinierte, begründete Algo-LLM-Strategien entwerfen.

Melden nur bei einer konkreten Referenzmaterial-Aufgabe, die ich selbst nicht erledigen kann (Zotero
läuft bereits).

**Warum dieser Auftrag:** Die 50 Filtermodell-Iterationen liefen auf der richtigen Achse (`user_verdict`,
am Werk geerdet), aber das **Erdungs-Material selbst** war dünn — und genau das limitierte jedes Signal
(Iter 43: grounded Bezug blind 4 %; Iter 47: theoretische Verwandtschaft im fremden Vokabular unsichtbar).
Erst das Referenzmaterial verbessern, dann neu testen.

---

## §A — Qualitätsbefund (gemessen, `/tmp/refmat_diag*.py`)

### Achse 1: User-Volltexte (`own_refs.db`, n=156 bereinigte Publikationen)
> **Korrektur 2026-05-31:** Tabelle auf den **bereinigten** Korpus umgestellt. Die ursprünglichen
> „n=161" enthielten **5 leere Phantom-Stubs** (titellose AI&Society-DOIs aus `QM7TZT44`, von Benjamin als
> „keine meiner Publikationen" bestätigt). Sie sind purged + der Build ist gehärtet (siehe
> `strat_01_fulltext_gap.md`). Die 5 waren die einzige Kontamination dieser Achse — Beleg: discourse-Label
> springt nach Purge auf **100 %** (die 5 Unlabeled waren genau die Stubs).

| Merkmal | Wert (bereinigt) | Befund |
|---|---|---|
| Volltext extrahiert (>500 chars) | **90/156 (58 %)** | 66 fehlen, **überwiegend pre-2018** (48/66 Fundament) |
| Volltext-Länge (wo vorhanden) | median 57 465 chars | gut; aber **1 Ausreißer 4,17 Mio chars** (Sammelband → Strat 03 Rollen-Trennung) |
| Refs extrahiert | 90/156 (58 %) | an Volltext gekoppelt |
| pub_refs aufgelöst zu OpenAlex-ID | **770/6 244 (12 %)** | **kritischer Engpass** — `own_coupling` verhungert (Stubs hatten 0 Refs, daher unverändert) |
| Publikationen mit ≥1 aufgelöster Ref | 62/156 (40 %) | Kopplungs-Universum künstlich winzig |
| DOI-Coverage | 24/156 (15 %) | erklärt durch Buch-Profil (bookSection + book); −5 vs. Rohstand = die DOI-tragenden Stubs |
| discourse-Label | **156/156 (100 %)** | nach Purge vollständig |

**unaufgelöste Refs haben `ref_text`** (APA-Strings) → auflösbar via Title-Search (nicht verloren).

### Achse 2: User-Projekte (`projects.json`, n=5)
| Projekt | desc | connected_publications | relevance_shifts |
|---|---|---|---|
| Cultural Resilience | 448 ch | 6 | 7 |
| MetaKuBi | 268 ch | 6 | 7 |
| AI4ArtsEd | 321 ch | 3 | 7 |
| ComeArts | 461 ch | 3 | 6 |
| DiäS-KuBi | 327 ch | 4 | 7 |

**Reich strukturiert (Verknüpfungen + relevance_shifts befüllt) — aber in keinem Erdungssignal genutzt.**
Niedrig hängende Frucht.

### Achse 3: User-Profil
- `summaries.json`: **53/156 Pubs (34 %)** (bereinigt), since_year=2018 → **103 ohne Summary, davon 85 pre-2018.**
  Felder reich (summary_de ~1169 ch median, key_terms, named_thinkers, methods, cases_examples). Aber das
  **Fundament-Werk ist für `rich_sim` unsichtbar.**
- `profile.json`: dünn (areas = ein Freitext-String; triage_topics 10; trigger patterns). Die
  5 Verortungen nicht strukturiert verankert; Profil-Modellierung (Per-Werk-Embedding/Cluster) skizziert,
  nie gebaut (Memory `project_profile_modelling`).
- `bezugsautoren.db`: 221 seeds, **ALLE role=first_author** (zirkulär aus Gold-Erstautoren, Iter 28/44).

---

## §B — Positive Vorschriften (R1–R8)
Übernommen + erweitert aus P1–P16 der Filtermodell-Serie. Ausschließlich positiv.

- **R1** Jede Coverage-/Qualitäts-Zahl wird **gemessen** (Skript), nie angenommen (P4).
- **R2** Optimierung wird am **nachgelagerten Ziel** validiert (Erdungssignal für `user_verdict`), nicht
  nur an Coverage-Prozenten — sonst optimiert man Coverage um ihrer selbst willen (P14).
- **R3** **Kostenkontrolle:** vor jedem LLM-Batch (z. B. Summarization) Einzelkosten-Verifikation an 2–3
  Items, Kosten zeigen, erst dann skalieren ($43-Vorfall). In der Design-Phase Kosten **analytisch
  schätzen** (Tokenzahl × Preis), nicht durch Probe-Batches verbrennen.
- **R4** Erweiterungen **additiv-idempotent, multi-source, versioniert** (Memory `feedback_mojo2_reframe`).
- **R5** Das **pre-2018-Fundament nicht ausschließen** — `since_year=2018` macht die Wurzel-Werke blind;
  Volltext/Summary-Strategien decken bewusst die Frühphase ab.
- **R6** **Keine theoretische Verortung interpretieren** (CLAUDE.md): Denker/Begriffe nur **faktisch
  extrahieren** (explizit genannt/zitiert), nicht deuten.
- **R7** Ehrliche Spannen, Ausreißer und Grenzen benennen, nicht glätten (P15).
- **R8** Adversariale Selbstkritik je Strategie ist Pflicht; jede Strategie wird mindestens **v1 → v2**
  iteriert.

---

## §C — Die 10 Strategien (nach Hebel sortiert)

| # | Slug | Achse | Hebel (gemessene Lücke) |
|---|------|-------|--------------------------|
| 01 | fulltext_gap | Volltext | 66 fehlende Volltexte (48 pre-2018-Fundament, nur 1 mit DOI) über Zotero-Pipeline schließen |
| 02 | ref_resolution | Volltext | Refs-Auflösung 12 %→? via Title-Search auf `ref_text` (5 474 unaufgelöst) |
| 03 | fulltext_clean | Volltext | Normalisierung: 4,17-Mio-Ausreißer, Header/Footer, Hyphenation |
| 04 | summary_coverage | Profil | Summary-Coverage 53→156 (Priorität: 85 pre-2018), kosten-kontrolliert |
| 05 | concept_extraction | Profil | Denker/Begriffe faktisch extrahieren (Vokabular-Brücke, Iter 47) — ohne Deutung (R6) |
| 06 | project_anchor | Projekte | `projects.json` als Embedding-/Kopplungs-Erdungssignal aktivieren |
| 07 | project_fulltext | Projekte | Projekt-Anträge/-Beschreibungen als Volltext (ggf. Benjamin-Aufgabe) |
| 08 | profile_modelling | Profil | Per-Werk-Embedding + Soft-Cluster + Topologie (gesketchte Stage 0) |
| 09 | lexicon | Profil | Denker-/Begriffs-Lexikon konsolidieren (Voll-Name-Disambiguation, Iter 20/21) |
| 10 | unified_index | Integration | Einheitlicher, versionierter, additiv-idempotenter Referenz-Index |

---

## §D — Ledger

| # | Slug | Ist-Zustand (gemessen) | Strategie-Kern + v2-Iteration | Status |
|---|------|------------------------|-------------------------------|--------|
| — | Qualitätsbefund | §A | Drei Achsen vermessen; Engpässe: Refs 12 %, Volltext 58 %, Summaries 33 %, Projekte ungenutzt. **+ 5 leere Phantom-Stubs purged (161→156), Build gehärtet** | ✅ |
| 01 | fulltext_gap | **66** ohne Volltext (bereinigt), 48 pre-2018, **nur 1 mit DOI** (De Gruyter, real seins) | **Beschaffung über Zotero-Pipeline, nicht Extraktion.** Korrektur 2026-05-31: „5 eigene AI&Society-DOIs" war Konfabulation = leere Stubs (purged, Build gehärtet). VPN ist systemweit; „Client Challenge" war Bot-Erkennung auf naiven urllib, kein Zugangsproblem. → OA/Zotero-Fetch + optional pre-2018-Attachments | ✅ |
| 02 | ref_resolution | 770/6244 (12 %) aufgelöst, 5421 text_unresolved, 99 % haben ref_text | Probe: naiv 27 %, Fehler = Parsing+Konfidenz (False Negatives), nicht OpenAlex. v2: APA-Parse → Titel-Query → Jahr+Autor-Kreuzprüfung; e-flux/dt. als ehrliche Decke | ✅ |
| 03 | fulltext_clean | Top-3 „Volltexte" = **Herausgeberbände** (4,17 Mio/1,4 Mio/868k chars) | Rollen-Kontamination, nicht OCR. v2: authored/edited trennen, Hrsg.-Bände nicht als Eigentext embedden, Längen-Norm, dann putzen | ✅ |
| 04 | summary_coverage | 53/156 (34 %), 103 fehlen, **nur 37 mit Volltext**; ~$16/37 (~$45/103) | Kosten-Alarm (≈$43-Vorfall). v2: **erst gratis messen ob Volltext-Embedding Summary ersetzt**, dann ggf. 37 mit Einzelkosten-Verifik. | ✅ |
| 05 | concept_extraction | Barad/Whitehead/Haraway **vorhanden**, aber Formen fragmentiert, 70 % Long-Tail | Iter-47-Brücke buildbar. v2: faktisch (R6), kanonisiert, gewichtet, als Denker-Overlap-Signal (Iter-45-Vorbehalt) | ✅ |
| 06 | project_anchor | projects.json reich, ungenutzt | **Probe: blind-AUC 0.410 (< Zufall!)** — Grant-Prosa ≠ Relevanz. v2: auf connected_publications ankern + Achse als Routing umdeuten | ✅ |
| 07 | project_fulltext | keine Anträge lokal; **relevance_shifts dicht+kuratiert** | v2: Projekte = **vorwärtsgerichtete Frontier-Erdung** (Iter 37/38); relevance_shifts als Anker, Anträge optional | ✅ |
| 08 | profile_modelling | **Cluster schwach (Silhouette 0.06)**, ÄKB-Dominanz 18/53 | Hard-Cluster verworfen. v2: Per-Werk-kNN + discourse-Soft-Membership; Material-Rebalancing (S1/S4) vor Ranker-Fix | ✅ |
| 09 | lexicon | 400 Formen, **11 Nachnamen-Kollisionen** (Gibson/Krämer/Böhme) | Surname-Merge fatal (Iter 20/21 belegt). v2: OpenAlex-Autor-ID-Disambig., full-name, kuratiertes versioniertes Lexikon | ✅ |
| 10 | unified_index | Material auf **6 unverbundenen Stores** | Kein neuer Store (Over-Eng.). v2: `own_refs.db` als bestehenden Hub erweitern (role/embedding/soft/FK), zuletzt nach Material | ✅ |

**Stand: Phase 1 abgeschlossen — 10/10 Strategien entworfen + adversarial v1→v2 iteriert.**

### Priorisierte Reihenfolge (nach Hebel × Selbst-Erledigbarkeit)
1. **Strat 02** (Refs 12 %→?) — größter Erdungshebel, selbst erledigbar, kostenlos. **Sofort.**
2. **Strat 03** (Rollen-Trennung) — billig, behebt Embedding-Kontamination, Voraussetzung für 04/08.
3. **Strat 04-Schritt-1** (gratis-Messung: ersetzt Volltext-Embedding die Summary?) — vor jeder Ausgabe.
4. **Strat 09 + 05** (Lexikon disambiguiert → Denker-Overlap) — kostenlos, Iter-47-Brücke.
5. **Strat 08, 06/07** (Profil-kNN, Projekt-Routing/Frontier) — kostenlos, je nach Messung.
6. **Strat 10** (Index) — zuletzt, nachdem Material steht.
7. **Strat 01 + 04-Rest** — gegated auf **Benjamin-Aufgaben** (unten).

### Gesammelte Benjamin-Aufgaben (legitimer Melde-Trigger)
> **Korrektur 2026-05-31:** Der frühere Haupt-Trigger („deine 6 eigenen DOI-Artikel im Browser laden")
> war falsch — er beruhte auf 5 konfabulierten AI&Society-„Eigenartikeln", die in Wahrheit leere
> Phantom-Stubs waren (purged, Build gehärtet). Es bleiben nur **optionale, nicht-blockierende** Aufgaben:
- **Optional/niedrig — pre-2018-Fundament:** hochwertige Buchkapitel ohne DOI/PDF, die nur du als Datei
  hast, als Attachment in die Zotero-Collection „Benjamin's publications" (`QM7TZT44`) hängen → Re-Build
  zieht sie automatisch. (Das systemweite VPN gibt dem normalen Fetch ohnehin institutionellen Zugang.)
- **Optional/Hygiene:** die 5 titellosen AI&Society-DOIs (itemIDs 43704–43708) aus `QM7TZT44` entfernen —
  code-seitig bereits neutralisiert, also nicht nötig, nur sauberer.
- Optional/niedrig: Projekt-Antrags-PDFs, falls leicht zur Hand (geringer Relevanz-Wert, gemessen S6).

**→ Kein blockierender Melde-Trigger offen.** Die Referenzmaterial-Optimierung läuft selbst-erledigbar
weiter (Strat 02/03/04-Messung/05/06/07/08/09/10), Phasen 2 & 3 anschließend.

---

## §E — Phasen 2 & 3 (Vorschau)
- **Phase 2:** Mit optimiertem Material die Filtermodell-Serie (M-C/M-E) neu messen — verschiebt bessere
  Erdung die ehrliche Leiste (blind keep-AUC 0.666)? Neue algorithmische Strategien auf den neuen Signalen.
- **Phase 3:** Begründete Algo-LLM-Kombinationen — Algo als Vorfilter/Erder, LLM als geerdete Volltext-
  Eskalation (Iter 32/47), jetzt auf reicherem Referenzmaterial.
