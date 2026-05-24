# Backtest: Algorithmische Heuristiken vs. LLM-Triage

**Anlass** (2026-05-24): Benjamin beobachtet beim Browsen von AI & Society, dass Abstracts auf der Plattform schnell scannbar sind — und fragt, ob der LLM-Aufwand der aktuellen Triage gegenüber guten algorithmischen Verfahren wirklich gerechtfertigt ist. Diese Notiz hält Plan und Setup für den Backtest fest.

## Ausgangsbefund

Auswertung der Konfusionsmatrix gegen 461 user_verdicts (Stand 2026-05-24):

| | n |
|---|---:|
| Gesamt user_verdicts | 461 |
| Agent-User-Agreement | **71.6%** (330/461) |
| Verpasste LESENSWERT (Agent → User-Korrektur) | 22 + 6 = 28 |
| Falsch-Positive in "scannen" (User → ignorieren) | 54 |
| Bestätigte Agent-"ignorieren" (richtig wegsortiert) | 214/254 = 84% |

**Befund**: der LLM-Triage erreicht 71.6% Übereinstimmung mit Benjamins Urteil. Die billige Vorsortierung in "ignorieren" funktioniert (84% Bestätigung), die teure "scannen"-Klasse ist die Müllkippe (43% Agreement).

**Frage**: Wie viel von diesen 71.6% Agreement schafft ein algorithmischer Ansatz ohne LLM? Wenn ≥60%, dann ist der LLM für die Filter-Aufgabe Overkill und sollte nur noch auf die finalen ~5% angesetzt werden.

## Methodische Disziplin — was ist erlaubt

Die Verfahren dürfen ausschließlich **non-LLM-Daten** verwenden. Sonst wäre die Aussage "schlägt der Algorithmus den LLM?" zirkulär.

**Erlaubt:**
- `articles.{title, abstract, openalex_abstract, authors_json, doi, year, journal_short}` (Publisher/OpenAlex)
- `articles.{crossref_refs, openalex_refs, openalex_topics, openalex_concepts}` (Bibliometrie-Services)
- `articles.citation_hits_json` (eigener Citation-Tracker via Vornamen+DOI-Match — kein LLM)
- `corpus.json.{authored_all, publications}` (Zotero-Export inkl. Original-Abstracts + extrahierte Fulltexts)
- `projects.json` (vom User formuliert)

**Verboten:**
- `summaries.json` (Opus-generierte Summaries der eigenen Publikationen)
- `articles.agent_verdict` / `agent_entry_json` (Agent-Output) — nur als Vergleichs-Baseline am Schluss
- `articles.selection_mode` / `discourse_indicator` / `signal_group` / `suggested_subgroup` (vom Screening-LLM gesetzt)

Bug-Anekdote (2026-05-24): Erste Version von `load_corpus_texts()` zog `summaries.json` als Korpus-Profil für TF-IDF/Embedding — Benjamin hat den Methodik-Fehler sofort gefangen. Korrigiert: nur noch `corpus.json/publications` + `authored_all`-Titel + `projects.json`.

## Datenlage (alle in articles.db verfügbar)

| Asset | n / Coverage |
|---|---:|
| Artikel total | 18,212 |
| Mit Crossref-Refs | 14,071 (77%) |
| Mit OpenAlex-Refs | 14,416 (79%) |
| Mit OpenAlex-Concepts | 17,728 (97%) |
| Mit OpenAlex-Topics | 17,736 (97%) |
| Mit citation_hits (zitieren Benjamin) | 162 |
| Mit User-Verdict (Goldstandard) | **461** |

User-Verdict-Verteilung: 273 ignorieren / 109 scannen / 78 lesenswert / 1 pflichtlektüre.
Class-Balance ratio ~3.5 : 1.4 : 1.

## Selection Bias (offen dokumentiert)

Die 461 user_verdicts sind kein randomisiertes Sample aus den 18k. Benjamin hat sie durch UI-Browsing erzeugt, dominant aus AIandSoc (32%), MedienPaed (11%), BDS (9%). Heißt: die Heuristik wird auf dieser Verteilung über-optimiert. Für ein produktiv eingesetztes Verfahren wäre ein Random-Sample über alle Journals nötig — aber für die Grundsatzfrage "schlägt Algorithmus den LLM?" reicht das vorhandene Sample.

## Die 8 Verfahren

Spektrum bewusst breit: Rule-based → Bibliometrie → Bag-of-Words → Embeddings → ML.

| # | Verfahren | Input | Logik | Erwartung |
|---|---|---|---|---|
| M1 | **Citation-Hit-Only** | citation_hits_json | ≥1 hit → lesenswert, sonst ignorieren | Hoher Precision, niedriger Recall |
| M2 | **Trigger-Author-Only** | authors_json ∩ Trigger-Liste | Match → lesenswert | Niedriger Recall, aber hochpräzise |
| M3 | **Citation+Trigger (OR)** | M1 ∨ M2 | Disjunktion | Mittel-Recall, gute Precision |
| M4 | **Topic/Concept-Jaccard** | openalex_topics/concepts ∩ Korpus-Profil | Jaccard ≥ θ → lesenswert | Mittlerer Recall, mittlere Precision |
| M5 | **Reference-Overlap mit Trigger-Nachbarschaft** | crossref_refs ∩ aggregierte Refs (Trigger-Artikel + authored_all) | Threshold auf Overlap-Count | Stark für Diskurs-Nachbarschaft |
| M6 | **TF-IDF Abstract → Korpus** | abstract gegen summaries.json + projects.json | Cosine über Vocabulary | Keyword-Treffer, sprachunsensibel |
| M7 | **Sentence-Embedding Cosine** | abstract embedding (multilingual MiniLM) gegen Korpus-Embeddings | Cosine, k-NN | Semantische Ähnlichkeit, beste Recall-Hoffnung |
| M8 | **Combined Features + ML** | Alle numerischen Features aus M1–M7 | LogReg + GradientBoosting, 5-fold CV auf user_verdicts | Sollte den Agent übertreffen wenn überhaupt möglich |

## Tools

Installiert ins `.venv` (2026-05-24):
- numpy 2.2.6, pandas 2.3.3, scikit-learn 1.7.2
- sentence-transformers 5.5.1 (für M7, multilingual-MiniLM)
- tabulate 0.10.0, pyarrow 24.0.0

## Skript-Struktur

```
scripts/
  backtest_extract_features.py    # baut features.parquet aus articles.db
  backtest_methods.py             # 8 Verfahren als Klassen mit .predict()
  backtest_run.py                 # Cross-Val, Metriken, Report
docs/
  backtest_algorithmic_v1.md      # Report-Output
```

## Metriken

Pro Verfahren auf 461 user_verdicts:
- **Precision/Recall/F1 pro Klasse** (ignorieren / scannen / lesenswert)
- **Top-5%-Precision**: wenn das Verfahren einen Score liefert, sind die Top-5% wirklich LESENSWERT?
- **Recall der 28 vom Agent verpassten LESENSWERT**: fängt der Algorithmus, was der LLM verfehlt?
- **Overall Agreement vs. Goldstandard**: vergleichbar mit Agent-Baseline 71.6%

## Erwartete Aussagen am Ende

- "M_i erreicht X% Agreement vs. Goldstandard, Agent erreicht 71.6%."
- "Für die Filterung 'ignorieren' reicht M_j, der LLM ist Overkill."
- "Für die 1% LESENSWERT bleibt der LLM unersetzlich, weil M_k nur Y% Recall erreicht."
- Oder: "M_8 erreicht 80%+ Agreement → der LLM kann komplett abgelöst werden."

## Offene Punkte

- Embedding-Modell: erst MiniLM (klein, schnell), bei schlechtem Recall mE5-base
- Random-Sample für Negativklasse über 18k bleibt offen (für saubere False-Positive-Rate über alle Diskursräume)
- Wenn M8 stark abschneidet: separater Test auf einem Hold-out-Journal (z.B. nur PDSE), um Selection-Bias zu prüfen
