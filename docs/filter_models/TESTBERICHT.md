# Testbericht — MOJO 2.0 Relevanzfilter-Evaluation (50 Iterationen)

| | |
|---|---|
| **Projekt** | MOJO 2.0 — algorithmischer Relevanzfilter für eingehende Zeitschriftenartikel |
| **Testgegenstand** | 50 Filtermodell-Entwürfe (Triage „relevant für Benjamins Werk?"), gemessen + hart kritisiert |
| **Datum** | 2026-05-31 |
| **Datengrundlage** | 461 gelabelte Artikel (`backtest_data/features_gold.parquet`), Ground Truth = `user_verdict` |
| **Mess-Harness** | `scripts/fm_eval.py` (StratifiedKFold-OOF, seed-gemittelt); reproduzierbare Endbilanz `scripts/iter_50_scorecard.py` |
| **Artefakte** | `docs/filter_models/iter_01..50_*.md` (Entwurf+Messung+Kritik), `scripts/iter_01..50_*.py` (lauffähig), `00_PLAN.md` (Ledger+Vorschriften) |
| **Status** | Abgeschlossen, 50/50 |

---

## Kurzfassung

Getestet wurde, ob ein **algorithmischer** Filter entscheiden kann, welche eingehenden Artikel für
Benjamin Jörissens Werk relevant sind — gemessen gegen sein eigenes Urteil (`user_verdict`), nicht gegen
Diskursraum-Zugehörigkeit (die Korrektur eines Ur-Fehlers, siehe §1).

**Befund in einem Satz:** Der Algorithmus ist ein brauchbarer **Vorfilter, Sortierer und Erder — aber
kein Entscheider.** Auf dem ehrlichen Maßstab (blinder Screening-Strom) erreicht das beste Modell **M-E**
eine keep-AUC von **0.666 ± 0.009**; es kann **~22 % des Stroms sicher verwerfen** (ohne ein einziges
„lesenswert" zu verlieren) und den Rest nach Relevanz vorsortieren (LES-Recall ≈ 62 % bei 20 % gesichtetem
Material). Aber es gibt **kein Score-Band, in dem der Algorithmus sicher genug ist, um automatisch zu
surfacen** — das bleibt der LLM/Volltext-Lektüre vorbehalten (der LLM-Agent schlägt den Algorithmus auf
blinder Triage klar: 88 % vs 38 % LES-Recall).

**Die fünffach bestätigte Grenze:** Bibliometrie plateauft; der Hebel ist Inhalt; aber selbst reicher
Inhalt verfehlt die **theoretische Wahlverwandtschaft im fremden disziplinären Vokabular** (15 von 79
„lesenswert"-Artikeln sind algorithmisch irreduzibel — u. a. Benjamins eigenes Barad/Whitehead-Terrain).
Generative, nicht-referenzielle Relevanz ist algorithmisch nicht greifbar. Das ist keine behebbare
Modellschwäche, sondern die Definition des Problems — und die **empirische Begründung** für die
dokumentierte 2.0-Linie: Volltext-LLM-Eskalation für die unsichere Restmenge, substitutiv-geerdete
Einträge ohne Konfabulation für den Rest.

---

## 1. Testgegenstand & Fragestellung

**Was getestet wurde:** Kann ein algorithmisches Modell aus Metadaten (Abstract, Concepts, Referenzen,
Journal, Autoren) zuverlässig bestimmen, ob ein neuer Artikel für Benjamin **lesenswert / scannenswert /
ignorierbar** ist?

**Die zentrale Korrektur (Ur-Fehler des Tages):** Ein früherer Ansatz erdete Relevanz in der
**Diskursraum-Zugehörigkeit** eines Artikels. Das ist zirkulär (Journals *definieren* die Diskursräume
über `journal.clusters` — ein per-Artikel-LLM-Urteil über die Zugehörigkeit ist tautologisch) UND
orthogonal zur eigentlichen Frage („relevant *für Benjamins Arbeit*"). Sämtliche 50 Iterationen zielen
daher konsequent auf `user_verdict`, geerdet in Benjamins Œuvre (own_coupling, bezugsautoren,
Inhaltsähnlichkeit gegen die eigenen Publikations-Summaries).

---

## 2. Methodik

- **Ground Truth:** `user_verdict`, 3 effektive Klassen (siehe §3). Schreibendes Choke-Point-Prinzip.
- **Ehrlicher Maßstab:** Alle Headline-Zahlen auf dem **blinden Screening-Strom** (`selection_mode =
  'screening'`, n = 120) — der einzige selektions-unverzerrte Teil. Zahlen auf „alle Quellen" sind durch
  intentional-positive Selektion (citation/complementarity/…) aufgebläht und werden stets als solche
  markiert.
- **Validierung:** StratifiedKFold-**Out-of-Fold** (kein In-Sample-Leak); Headline-Metriken über **5 Seeds
  gemittelt** mit Standardabweichung (keine Glücksseed-Punktwerte).
- **Metriken:** keep-AUC, LES-Recall@K, keep-Precision, macro-F1 (3-Klassen), ECE (Kalibrierung).
- **Reproduzierbarkeit:** `.venv/bin/python scripts/iter_50_scorecard.py` reproduziert die gesamte
  Endbilanz in einem Lauf.
- **Methodische Leitplanken:** 16 positive Vorschriften (P1–P16) aus der Auswertung aller Tagesfehler;
  siehe Anhang A und `00_PLAN.md` §B.

---

## 3. Datengrundlage

| Merkmal | Wert |
|---|---|
| Gelabelte Artikel gesamt | 461 |
| Klassen | ignorieren 273 (59 %), scannen 109 (24 %), lesenswert 78–79 (17 %), pflichtlektüre 1 (effektiv leer) |
| Blinder Strom (screening) | n = 120, davon keep 25, lesenswert 8 |
| keep-Basisrate | gesamt 41 %, blinder Strom **21 %** |
| Abstract-Verfügbarkeit | 381/461 (83 %) mit Abstract (Pfad A), 80 ohne (Pfad B) |

**Selection-Bias (zentral für die Interpretation):** 65 % der „lesenswert" stammen aus intentional-
positiven Quellen (citation/complementarity/mixed/trigger/similarity), nur 17 % aus blindem Screening.
Jede Zahl auf „alle Quellen" ist daher optimistisch verzerrt; die blind-Strom-Zahlen sind der Realtest.

---

## 4. Testmatrix — alle 50 Iterationen

Phasen: **A** Boden/Ehrlichkeit (01–08) · **B** Inhalt & Erdung (09–24) · **C** operatives Modell (25–35) ·
**D** Stabilität & Korrektur (36–38) · **E** Stresstests & Synthese (39–50).

| # | Slug | Kennzahl | Kern-Befund |
|---|------|----------|-------------|
| 01 | floor_single_signals | keep-F1 0.312 | Bibliometrie sieht nur **19 %** der Treffer → Recall muss aus Inhalt kommen |
| 02 | content_axis | AUC 0.66 (M7) | Inhalt trägt, aber ungeerdet schwach |
| 03 | family_ablation | F1 0.514 | own+content > ALL; Trigger-Features = Rauschen |
| 04 | tree_model | F1 0.514 | HistGBM schlägt LogReg nicht — der Lerner ist nicht der Hebel |
| 05 | per_journal_prior | F1 0.490 | **„Bar 0.603" war In-Sample-Leak; ehrlicher Boden 0.544/0.589** |
| 06 | selection_bias | F1 0.459 (blind) | **Headline durch Selection-Bias aufgebläht; blind keep-F1 ≈ 0.46** |
| 07 | calibrated_threshold | F1 0.357 (scr) | Blind: keep-F1 max 0.357 → taugt nur als Vorfilter + LLM |
| 08 | prefilter_coverage | — | Vorfilter spart nur ~10 % bei 95 % Recall (frühere „50–60 %" widerlegt) |
| 09 | perwork_embedding | AUC 0.691 | Per-Werk-max ≈ global → Profil-Hypothese trägt für keep nicht |
| 10 | cascade_veto_up | F1 0.514 | Biblio-Veto feuert blind nur 1×/120 → wirkungslos |
| 11 | error_anatomy | — | Blind-verfehlte LES signalfrei; Relevanz **konzeptuell**, nicht biblio/lexikalisch |
| 12 | rich_perwork | AUC 0.690 | Reicher Summary-Text hebt 2/4 verfehlte LES (AfD 36→94 %) — komplementär |
| 13 | content_combo | AUC 0.728 | **Kombi bricht 0.69-Decke; blind rich 0.632 ≫ global 0.517** — Œuvre-Erdung trägt |
| 14 | full_model_rich | F1 0.493 | AUC-Gewinn überträgt sich nicht auf 3-Klassen — Ranking ≠ Entscheidung |
| 15 | engineered_mean | F1 0.492 | 3-Klassen-Decke strukturell; als Ranker blind rich 0.632 / 68 % R@50 % |
| 16 | operative_ranker | AUC 0.709 | Blind R@10 % 20 % vs M7 4 % (5×); Biblio-Veto = Präzisionsanker |
| 17 | grounded_bezug | — | Substitutive Komponente konkret, aber **blind 0 %** → Enrichment, nicht Filter |
| 18 | bezugsautoren_layer | — | bez-direkt: keeper 21→37 %; breite Kopplung = Rauschen, verworfen |
| 19 | entry_composer | — | **Substitutiver Komponist: 0 ungrounded Behauptungen** (vs LLM 55,9 %) |
| 20 | named_thinkers | AUC 0.591 | Erste Achse, die blind erreicht (28 %); fängt Queer-Kin↔Haraway |
| 21 | combined_enrichment | — | **Selbstkorrektur: gehärtet blind 8 % (nicht 28 %)**; Kombi keeper 46 % |
| 22 | temporal_drift | — | `year` = Bias-Leck → ausschließen, screening-only messen |
| 23 | abstract_robustness | AUC 0.532–0.684 | **43 % blind abstract-los → Ranker dort ≈ Zufall** |
| 24 | calibration | ECE .044/.201 | Gesamt gut, **blind lügt** (Basisraten-Shift) → Rang statt Prozent |
| 25 | journal_prior_eb | AUC 0.711 | **EB-Journal-Prior stärkstes blindes Signal**, nicht zirkulär; Gate killt Serendipität |
| 26 | ensemble_serendipity | AUC 0.702 | Ensemble R@20 % 44 %, **begräbt aber Serendipitäts-keeper** → lift-only-Fix |
| 27 | per_cluster | AUC 0.648 | **Profil-Topologie widerlegt: der Hebel war reicher TEXT, nicht Topologie** |
| 28 | author_identity | AUC 0.509 | Koautor zu selten; bezugsautor-Match zirkulär (Leak gefangen) |
| 29 | rich_ablation | AUC 0.648 | **summary_de trägt**; key_terms/thinkers allein < Titel → Opus-Summary nötig |
| 30 | abstract_enrichment | — | OpenAlex-Backfill rettet **0/81** abstract-lose → braucht Volltext-Fetch |
| 31 | operating_point | — | **Modell M-C: @20 % Sichtung 62 % LES-Recall (M7: 12 %)** |
| 32 | vs_agent | — | **LLM-Agent schlägt M-C klar (88 % vs 38 %)** → Algo ersetzt LLM nicht |
| 33 | cascade_cost | — | Kaskade @30 %: 70 % Kosten gespart, LES-Recall 88→62 % |
| 34 | two_path | — | **Alle 8 blind-LES in Pfad A; Pfad B (43 %) 0 LES** |
| 35 | cost_model | — | M-E Pfad-A-only $1.96/100 (43 % billiger, 0 LES verloren) |
| 36 | seed_stability | — | **Korrektur: M-C-AUC 0.66 ± 0.01 (nicht 0.702-Glücksseed)** → Spannen |
| 37 | per_verortung | — | **Blinder Fleck: Kern überbedient (87 %), Frontier begraben (37–43 %)** |
| 38 | balanced_ranker | AUC 0.620 | Per-Verortung-Balance hebt Frontier (+14 pp) auf Kosten Kern — Werte-Trade |
| 39 | complementarity | — | **Triage-Falle: complementarity-keeper Ø-Rang 57 % vs citation 86 %** |
| 40 | journal_holdout | AUC 0.690 | **Journal-Prior generalisiert nicht** (+0.000 auf ungesehenen); rich-sim trägt 96 % |
| 41 | temporal_holdout | AUC 0.632 | **Cross-Year-Split unzulässig** (year ≈ selection_mode); Intra-Strom stabil |
| 42 | ablation | AUC 0.736 | **Komplementarität: rich_sim trägt AUC, Biblio-Veto trägt Top-K-Recall** |
| 43 | grounded_coverage | — | **Härtester Produkt-Befund: grounded Bezug blind fast leer (keeper 4 %, LES 0 %)** |
| 44 | bez_signal | AUC 0.666 | **bezugsautoren = Bezug-Lieferant, kein Relevanz-Hebel** (Veto schadet) |
| 45 | trigger_rule | — | **(A) Autoren-Match 100 % Precision behalten; (B) Ref-Overlap blind 0.4× Lift (negativ)** |
| 46 | confidence_bands | — | **3-Zonen: DROP 22 % (0 LES), KEEP 0 %, LLM 75 %** — Algo verwirft, surft nie |
| 47 | hardcases | — | **15/79 LES irreduzibel** (theoret. Verwandtschaft, fremdes Vokabular) |
| 48 | calibration | ECE 0.088→0.047 | M-E **isotonisch kalibrierbar** zur echten Wahrscheinlichkeit |
| 49 | pathb_fallback | AUC 0.532 | **Pfad B blind = Metadaten-Rauschen** → direkt Volltext holen |
| 50 | synthese | AUC 0.666 | **Finale M-E-Spezifikation + Scorecard** |

---

## 5. Ergebnisse nach Themenfeld

### 5.1 Bibliometrie plateauft (Iter 01, 03, 10, 40, 44, 45)
Reine Referenz-/Zitations-Signale sehen nur **19 %** der Treffer (Iter 01) und feuern auf dem blinden
Strom fast nie. Der EB-Journal-Prior ist das stärkste *bibliometrische* Einzelsignal (Iter 25), aber er
**generalisiert nicht** auf ungesehene Journals (Iter 40: +0.026 bei bekannten, **+0.000** bei neuen —
reine Memorisierung). Referenz-Overlap (bezugsautoren, Trigger-Werke) ist **kein Relevanz-Hebel**: als
Veto schadet er (zieht False Positives hoch) oder ist auf dem blinden Strom sogar negativ (Trigger-Ref-
Overlap 0.4× Lift, Iter 45). **Lehre: Was ein Artikel zitiert, taugt zum Bezug-Text, nicht zum
Relevanz-Urteil** (zweifach unabhängig belegt, Iter 44+45).

### 5.2 Der Hebel ist reicher Inhalt — nicht Topologie (Iter 09, 12, 13, 27, 29, 42)
Per-Werk-Embedding und Profil-Topologie bringen im Aggregat nichts über den globalen Schwerpunkt (Iter 09,
27). Was die 0.69-Decke bricht, ist **reicher Text**: die Opus-`summary_de` der eigenen Publikationen als
Ähnlichkeitsanker (Iter 13: blind rich 0.632 ≫ global 0.517; Iter 29: summary_de trägt, key_terms/thinkers
allein schlechter als Titel). Die Ablation (Iter 42) zeigt **Komplementarität, nicht Redundanz**: rich_sim
trägt die globale AUC (+0.041), das Biblio-Veto trägt die Top-K-Präzision — keine Komponente ist
streichbar.

### 5.3 Algorithmus vs. LLM — der Algorithmus ersetzt das LLM nicht (Iter 31, 32, 46)
Das operative Modell **M-C** sortiert blind gut (LES-Recall 62 %@20 %, vs M7 12 %, Iter 31). Aber der
**LLM-Agent schlägt es klar** (88 % vs 38 % LES-Recall@16 %, Iter 32). Konsequent zeigt die Confidence-
Band-Analyse (Iter 46): es gibt **kein Score-Band mit ≥80 % keep-Precision** auf dem blinden Strom — der
Algorithmus ist nie sicher genug, um automatisch zu surfacen. Sein einziger sicherer Akt ist die billige
Ablehnung von ~22 %.

### 5.4 Kosten & Kaskade (Iter 08, 33, 34, 35)
Als Vorfilter spart der Algorithmus bei 95 % Recall nur ~10 % (Iter 08); die Kaskade @30 % spart 70 %
Kosten, kostet aber LES-Recall (88→62 %, Iter 33). Der **Zwei-Pfad-Befund** (Iter 34) ist wertvoller: alle
8 blind-LES liegen in Pfad A (abstract-reich); Pfad B (43 %, abstract-los) hat 0 LES → LLM nur auf Pfad A =
gleiche Qualität bei 43 % weniger Calls (Iter 35: $1.96/100 Artikel, 43 % billiger, 0 LES verloren). Der
Hauptwert ist **Qualität, nicht Ersparnis**.

### 5.5 Erdung ≠ Relevanz — der substitutive Komponist (Iter 17, 19, 43, 44, 45)
Der substitutive Komponist erzeugt Einträge mit **0 ungegründeten Behauptungen** (vs 55,9 % beim alten
LLM-Kommentar, Iter 19) — das eigentliche 2.0-Motiv. **Aber** (härtester Produkt-Befund, Iter 43): auf dem
blinden Strom ist der zitations-basierte grounded Bezug **fast leer** (keeper 4 %, LES **0 %** geerdet) —
die Anker konzentrieren sich im bekannten Backfill und fehlen genau dort, wo Entdeckung zählt. Das
begründet, warum der Anker **inhaltlich** (Volltext) kommen muss, nicht aus dem Zitationsgraph.

### 5.6 Robustheit & Kalibrierung (Iter 22, 24, 40, 41, 48, 49)
- **Journal-Holdout (40):** Prior memoriert, generalisiert nicht — aber Watchlist ist fix, also realer
  Produktions-Lift mit dokumentiertem Cold-Start.
- **Temporal (41):** Cross-Year-Split unzulässig (`year` ≈ selection_mode); Intra-2026-Strom stabil; Drift
  ist ein Wartungsthema (Summaries neu einbetten), kein Architektur-Problem.
- **Kalibrierung (48):** roh ECE 0.088 → **isotonisch-OOF 0.047** mit monotoner Reliabilitätskurve → M-E
  darf eine echte keep-Wahrscheinlichkeit ausgeben (Kalibrator auf Produktions-Strom nachziehen).
- **Pfad B (49):** ohne Abstract ist rich-sim reines Rauschen (AUC 0.532) → direkt Volltext holen.

### 5.7 Die harte Grenze hat ein Gesicht (Iter 11, 37, 39, 47)
**15 von 79 „lesenswert"** sind algorithmisch irreduzibel (tief gereiht + kein Anker, Iter 47). Es sind
keine thematisch fernen Artikel, sondern **theoretische Wahlverwandtschaften im Vokabular angrenzender
Disziplinen** — Barad, Whitehead, posthumane Agency, Überwachungskritik, dekoloniale Epistemologie,
ästhetische Geste, ausgedrückt in HCI-/Kognitions-/Fan-Studies-/Assessment-Sprache. Smoking Gun:
„Gesture-ing in drawing via Whitehead and Barad" (Benjamins Kernterrain) auf nur 36 %-Rang. Der
complementarity-Pool (Iter 39) bestätigt es: komplementäre keeper Ø-Rang 57 % vs offensichtliche 86 %.

---

## 6. Konsolidierte Scorecard (verifiziert, `iter_50_scorecard.py`)

> Maßstab: **blinder Screening-Strom**, seed-gemittelt (5 Seeds), out-of-fold. „alle Quellen" nur zur
> Einordnung (Selection-Bias).

| Kennzahl | Wert |
|---|---|
| keep-Basisrate (blind / gesamt) | 21 % / 41 % |
| **keep-AUC blinder Strom** | **0.666 ± 0.009** |
| keep-AUC alle Quellen (verzerrt) | 0.736 ± 0.002 |
| rich-only blind (fest) | 0.632 |
| **LES-Recall @20 % / @30 % (blind)** | **62 % / 65 %** |
| sicher-DROP-Band (0 LES verloren) | **22 % ± 6 pp** (= −22 % LLM-Calls bei 100 % Recall) |
| sicher-KEEP-Band (≥80 % Precision) | **0 %** (Algo surft nie allein) |
| Kalibrierung roh → isotonisch-OOF (ECE) | 0.10 → **0.05** |
| Pfad A blind (Abstract): rich-AUC, LES | 0.684, 8/8 |
| Pfad B blind (kein Abstract): rich-AUC, LES | 0.532, 0/8 |
| irreduzible Hard-Case-LES | 15 / 79 |
| 3-Klassen-Decke (Opus) / ehrlicher Boden | macro-F1 0.679 / 0.544 |
| LLM-Agent vs M-C (LES-Recall blind) | **88 % vs 38 %** |

---

## 7. Empfohlene Architektur — Modell M-E

**Kern-Ranker** (Iter 14/26/42):
```
mc = z( z(rich_sim) + 0.5 · z(max(0, pj − G)) )      # rich_sim + Journal-Prior-Lift
score = where(biblio, 1 + mc, mc)                     # Biblio-Veto-Up
```
`rich_sim` = max. Ähnlichkeit gegen die 53 Opus-Summaries (summary_de + key_terms + named_thinkers);
`pj` = Empirical-Bayes-Journal-Prior (Shrinkage k = 5, nur-Lift, nie Veto-down); `biblio` = own_coupling ≥ 1
∨ citation ≥ 1.

**Zwei-Pfad-Routing** (Iter 34/49): Pfad A (Abstract) → scoren; Pfad B (kein Abstract) → kein Metadaten-
Urteil, direkt OA-PDF-Volltext holen, dann wie A.

**Drei-Zonen-Operating-Point** (Iter 46): sicher-DROP (~22 %, auto-ignorieren) · unsicher (~75 %,
→ Volltext-LLM, nach Score vorsortiert) · sicher-KEEP (leer — nie automatisch surfacen).

**Wert-Eskalationen** (konfigurierbar via `profile.json`): Trigger-Autoren-**Match** (MacGilchrist/Jarke/
Chun, 100 % Precision) immer hochstufen. Ref-Overlap **nicht** als Veto.

**Erdungs-/Komponisten-Schicht** (getrennt vom Ranker): faktentreue Bezüge wo Anker; sonst ehrlich
„relevant — Begründung über Lektüre"; **nie konfabuliert**.

**Kalibrierung** (Iter 48): isotonische OOF-Abbildung Score → keep-Wahrscheinlichkeit, auf dem
Produktions-Strom nachgezogen.

**Rollen-Fazit:** M-E ist **Vorfilter + Sortierer + Erder**, kein Entscheider — exakt die dokumentierte
2.0-Linie (1.x-LLM-Runs bleiben erhalten, MOJO 2.0 = algorithmischer Vorfilter + Volltext-Eskalation).

---

## 8. Validitätsgrenzen (Threats to Validity)

1. **Kleine LES-Zahl blind (n = 8):** alle blind-Strom-LES-Recall-Zahlen ruhen auf 8 Positiven —
   Spannen sind breit, Einzel-Artikel verschieben Prozente. Konsequent als Spannen berichtet, nie als
   Punktwerte.
2. **Selection-Bias:** 65 % der LES aus intentional-positiven Quellen → „alle Quellen"-Zahlen optimistisch;
   nur die blind-Zahlen sind belastbar.
3. **Pfad-B-Label-Artefakt (Iter 49):** „0 LES auf Pfad B" könnte „konnte nicht beurteilt werden"
   heißen, wenn der Ground Truth abstract-basiert vergeben wurde — stärkt die Volltext-Empfehlung.
4. **bezugsautoren-Zirkularität (Iter 28/44):** die DB ist aus Gold-Erstautoren geseedet → Coverage-Zahlen
   auf „alle Quellen" verzerrt; die blind-Zahlen (2–4 %) sind die unverzerrten.
5. **Journal-Konzentration:** AIandSoc stellt 147/461 (32 %) → Journal-Holdout-Folds unbalanciert (AUC
   bleibt robust, Journal-Verteilung selbst watchlist-verzerrt).
6. **rich_sim-Modell:** all-MiniLM-L6-v2 (offline, generisch) — ein domänenstärkeres Embedding könnte die
   Vokabular-Lücke (Iter 47) teils schließen; **zu messen, nicht zu projizieren**.

---

## 9. Offene Arbeit (gemessen, nicht projiziert)

- Eigenwerk-Repräsentation reichern: Volltext-Summaries statt Titel, theoretische Quellen explizit
  (adressiert Iter-47-Vokabular-Lücke — Effekt **zu messen**).
- bezugsautoren-DB über das Gold hinaus skalieren (Erdungs-Coverage ↑; Triage bleibt unberührt).
- Kalibrator auf Produktions-Strom (Basisrate 0.21) nachziehen.
- Summaries um Diskursraum-Label erweitern (sauberere Frontier-Balance, Iter 38).
- Ground Truth additiv wachsen lassen; Pfad-B-Label-Artefakt prüfen (Iter 49).

---

## 10. Reproduzierbarkeit & Artefakt-Index

```bash
# Gesamte Endbilanz in einem Lauf reproduzieren:
.venv/bin/python scripts/iter_50_scorecard.py

# Einzelne Iteration nachvollziehen (Beispiel):
.venv/bin/python scripts/iter_47_hardcases.py
```

| Artefakt | Pfad |
|---|---|
| Mess-Harness | `scripts/fm_eval.py` |
| rich-sim-Cache | `backtest_data/rich_sim.parquet` (Build: `scripts/_build_rich_sim.py`) |
| Iterations-Skripte | `scripts/iter_01..50_*.py` |
| Iterations-Dokumentation | `docs/filter_models/iter_01..50_*.md` |
| Plan + Vorschriften + Ledger | `docs/filter_models/00_PLAN.md` |
| Finale Architektur-Spezifikation | `docs/filter_models/iter_50_synthese.md` |
| Endbilanz-Skript | `scripts/iter_50_scorecard.py` |
| Datengrundlage | `backtest_data/features_gold.parquet` (461 × 33) |

---

## Anhang A — Methodische Vorschriften (P1–P16, Kurzform)

Aus der Auswertung aller Tagesfehler, ausschließlich **positiv** formuliert (Vollform in `00_PLAN.md` §B):

P1 Ziel = `user_verdict` (nicht Diskursraum) · P2 jede Achse gegen das Œuvre erden · P3 Provenienz/Leak/
Bias jeder Zahl prüfen · P4 gemessenes Artefakt vor jeder Behauptung · P5 out-of-fold validieren ·
P6 Evidenz pro Aussage · P7 Klassen-/Basisraten explizit · P8 neutrale Kriterien · P9 auf der
dokumentierten Linie bleiben · P10 Selbstkorrektur dokumentieren · P11 Anweisung/Wert vor Modell-
Präferenz · P12 Kosten transparent · P13 offline/billig als Default · P14 messen statt projizieren ·
P15 ehrliche Spannen statt Decke/Boden-Rhetorik · P16 geerdete Begründung statt Konfabulation.

---

*Bericht erzeugt am 2026-05-31 als Konsolidierung der 50-Iterationen-Serie. Alle Zahlen aus den
referenzierten, lauffähigen Skripten verifiziert.*
