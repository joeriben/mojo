# Strategie 03 — Volltext-Normalisierung & Rollen-Trennung

## Ist-Zustand (gemessen, `/tmp/s3.py`)
- 90 Volltexte, median 57 465 chars, p90 **694 096** — stark rechtsschief.
- **Top-3 sind Sammelbände, die Benjamin herausgab:** „Jahrbuch Medienpädagogik 18" (**4 171 305 chars**),
  „Medialität und Subjektivation" (1 429 534), „Schlüsselwerke der Identitätsforschung" (867 884).
- Extraktions-Artefakte mild: Ligaturen ~0, nonascii 0.5–1.2 % (normal für Deutsch), aber **5 313
  Worttrennungen** (`-\n`) im größten, 577 Seitenumbrüche → Hyphenation/Header-Müll vorhanden.

## Strategie v1
Volltexte normalisieren: De-Hyphenation, Header/Footer/Seitenumbruch-Strip, Ligatur-Fix.

## Adversariale Kritik (v1)
**v1 putzt Symptome, übersieht den Kategoriefehler.** Das eigentliche Problem ist nicht OCR-Müll (der ist
mild), sondern **Rollen-Kontamination:** ein 4,17-Mio-Zeichen-Sammelband ist zu 95 % der Text *anderer*
Autoren. Ihn als „Benjamins Werk" in `rich_sim` zu embedden, misst den Schwerpunkt des **ganzen Feldes**,
nicht Benjamins Position — exakt der Aggregations-Trugschluss aus der Profil-Modellierungs-Memory
(`project_profile_modelling`: globaler Haufen reproduziert das Profil nicht). De-Hyphenation eines
falsch-attribuierten Textes macht ihn nicht richtig.

## Strategie v2 (Rollen-Trennung zuerst, dann putzen)
1. **authored vs edited trennen:** über `corpus.json/authored_all` + Zotero-creatorType (editor vs author).
   Herausgeberschaften werden **nicht** als Eigentext embedded.
2. **Bei Herausgeberbänden nur Benjamins eigenen Beitrag** (Einleitung/eigenes Kapitel) extrahieren, falls
   als Sektion identifizierbar; sonst den Band für `rich_sim` ausschließen, aber seine **Referenzen
   behalten** (die kuratierte Lit-Auswahl eines Hrsg. ist erdungs-relevant — als eigener Signaltyp
   „kuratierte Bibliographie", nicht als Eigentext).
3. **Längen-Normalisierung:** pro Werk auf Embedding-Fenster segmentieren (Chunk-mean), damit kein
   Einzelwerk den Schwerpunkt dominiert (ein 700k-Werk darf nicht 12× so viel wiegen wie ein 57k-Werk).
4. **Dann erst** De-Hyphenation (`-\n`→''), Seitenumbruch/Running-Header-Strip, Whitespace-Norm.

## Erwarteter Effekt & Messbarkeit (R2)
Sauberere, fair gewichtete Eigenwerk-Repräsentation → `rich_sim` misst Benjamins Position statt des
Feld-Mittels. Messbar nachgelagert (Phase 2): ändert die Rollen-Trennung den blinden `rich_sim`-AUC und
verschiebt sie den Iter-37-Schwerpunkt (ÄKB-Dominanz war evtl. teils ein Sammelband-Artefakt)?
**Zu messen, nicht zu behaupten.**

## → Benjamin-Aufgabe?
Nein — authored/edited steht in corpus.json/Zotero, selbst erledigbar.

## → nächste
Strat 04: Summary-Coverage 53→161 — und die Rollen-Trennung aus Strat 03 ist Voraussetzung (keine
Herausgeberbände summarizen wie Eigentexte). Kosten-kontrolliert (R3).
