# Ground-Truth-Qualität: Diagnose des 461er Backtest-Sets

**Datum**: 2026-05-24.

**Trigger (Benjamins Reframe-Frage c vor Iter 11)**:
> "wie gut ist überhaupt die Ground truth?"

Antwort auf Basis SQLite-Analyse `articles.db` × `features_gold.parquet` ×
`predictions_iter11_full.parquet`.

## Klassen-Verteilung (Benjamins user_verdict, n=461)

| Klasse          | N    | %      |
|-----------------|------|--------|
| ignorieren      | 273  | 59.2 % |
| scannen         | 109  | 23.6 % |
| lesenswert      |  78  | 16.9 % |
| pflichtlektuere |   1  |  0.2 % |

→ **pflichtlektuere ist effektiv leer** (1 Annotation). Alle Modell-Vergleiche
sollten 3-Klassen-Macro-F1 ohne PFL rechnen — exklusiv PFL liefert konsistente
Zahlen mit Iter-1–10-Log.

## Selection-Bias: Wie kamen die 461 ins Set?

| selection_mode  | N    | %      | LES   | LES-Rate | Bedeutung                                |
|-----------------|------|--------|-------|----------|------------------------------------------|
| complementarity | 187  | 40.6 % | 30    | 16.0 %   | Mainstream, „ergänzt Benjamins Portfolio"|
| screening       | 120  | 26.0 % |  8    |  6.7 %   | RSS/OAI/Crossref-Volllauf                |
| similarity      | 110  | 23.9 % |  5    |  4.5 %   | semantisch ähnliche Items                |
| citation        |  22  |  4.8 % | 18    | 81.8 %   | Item zitiert Benjamin oder umgekehrt     |
| mixed           |  20  |  4.3 % | 15    | 75.0 %   | Mehrere Selection-Signale                |
| trigger         |   2  |  0.4 % |  2    | 100.0 %  | Trigger-Autor (MacGilchrist/Jarke/Chun)  |

**78 LES verteilt:** 38 % complementarity, 23 % citation, 19 % mixed, 10 %
screening, 6 % similarity, 3 % trigger.

→ **65 % aller LES sind aus „intentional"-positiven Quellen**
(citation/mixed/trigger/complementarity). Nur 17 % LES (13 von 230) stammen aus
„blind screening" (screening+similarity). Das ist *strukturelle* Auswahl-
verzerrung, *kein* Annotations-Fehler.

## Triage-Schwierigkeit per Selection-Mode

| Mode            | N    | Algo-Agree    | Opus-Agree    | Interpretation               |
|-----------------|------|---------------|---------------|------------------------------|
| trigger         |   2  | 100 %         | 100 %         | trivial                      |
| citation        |  22  |  81.8 %       |  90.9 %       | leicht                       |
| screening       | 120  |  75.8 %       |  80.0 %       | moderat                      |
| similarity      | 110  |  68.2 %       |  72.7 %       | moderat                      |
| mixed           |  20  |  45.0 %       |  85.0 %       | Opus dominiert (Multi-Signal)|
| complementarity | 187  |  57.8 %       |  61.5 %       | **HÄRTESTE Klasse**          |

→ **Der Complementarity-Pool ist die Triage-Falle**: 41 % des Sets, 38 % der
Algo-Fehler, 38 % der Opus-Fehler. Hier liegt die Information die nicht im
*bisher genutzten* Citation-Graph oder Metadaten sitzt. Antwort dafür ist
primär eine **breitere algorithmische Refs-/Set-Operations-Schicht**
(adversariale Heuristiken auf Trigger-Refs ∖ Benjamin-Refs etc., siehe
`project_adversarial_blindspot_heuristics.md`); für die Restmenge, die auch
dort unklar bleibt, kommt Volltext-LLM als gezielte Eskalation
(≤10 % der Items, siehe `feedback_mojo2_reframe_algorithmic.md`).

## Fehler-Overlap Algo (M9_Cascade) vs Opus

| Cell                | N   | %     |
|---------------------|-----|-------|
| Beide richtig       | 244 | 52.9 %|
| Beide falsch        |  72 | 15.6 %|
| Nur Algo richtig    |  59 | 12.8 %|
| Nur Opus richtig    |  86 | 18.7 %|

→ **Die 72 „beide falsch"-Cases sind die echten Hard-Cases**. Sie entsprechen
strukturell den 35 wrong-LES und 33 wrong-IGN, die Iter 7–11 als Plateau-Quelle
identifiziert haben.

→ **86 „nur Opus richtig" vs 59 „nur Algo richtig"** = Opus hat 27 unique
korrekte Calls mehr als Algo. Das ist genau der 0.09-F1-Gap zwischen 0.588
(Algo nach Iter-11-Penalty) und 0.677 (Opus 3-class macro).

## 3-Klassen-Macro-F1 (excl pflichtlektuere, n=460)

| Klassifikator             | Macro-F1 |
|---------------------------|----------|
| Opus (agent_verdict)      | 0.677    |
| M9_Cascade_TunedBase      | 0.588    |
| Gap                       | +0.090   |

(Gap vor Iter-11-Coupling-Features: 0.072. Iter 11 LogReg-Mischen verschlechtert
F1 um −0.011, deshalb steigt der Gap. Mit Veto-Up-Regel statt LogReg-Feature
würde das aufgehoben.)

## Methodische Grenzen / Was wir NICHT haben

- **Kein Inter-Rater-Reliability**: 100 % der Annotationen sind von Benjamin.
  By design (persönlicher Filter), aber Cohen's-κ-Vergleich nicht möglich.
- **Kein Test-Set außerhalb des Annotations-Pools**: alle 461 sind annotiert.
  Train/Test-Splits sind 5-Fold-CV innerhalb desselben Selection-Bias.
- **Kein Verdict-Update-Log**: wenn Benjamin nach Tagen umentscheidet (z.B.
  weil er den Artikel später als Quelle braucht), gibt es kein Re-Labeling.
- **pflichtlektuere als 4. Klasse ist nicht trainierbar** (1 Sample). Faktisch
  3-Klassen-System.

## Implikationen für MOJO 2.0

**Korrektur 2026-05-24**: MOJO 2.0 ist algorithmisch-first; Volltext-LLM ist
Eskalation für ≤10 % Restmenge, nicht Default-Triage (siehe
`feedback_mojo2_reframe_algorithmic.md`).

1. **Komplementaritäts-Pool ist der primäre Adressat für die breitere
   algorithmische Refs-/Set-Operations-Schicht**: dort sitzt der Mehrwert über
   Algo+Opus hinaus. Screening/Similarity (230 Items, 13 LES) können mit dem
   0.588-Algo-Vorfilter (LES-Recall ~60 % mit Veto-Up) zu ~80–90 % auf
   SCAN/IGN abgeschoben werden, ohne LES-Verlust. Adversariale Veto-Regeln
   (`f_adv_*` aus Trigger-Refs ∖ Benjamin-Refs) müssen direkt in die Cascade,
   nicht in einen LLM-Prompt.
2. **Citation/Trigger-Items immer auf LES escalieren** (`f_citation_hit ≥ 1` ∨
   `trigger_author ≥ 1` ∨ `f_own_coupling_union ≥ 1`) → das ist die
   Veto-Up-Regel aus Iter 11 und die Blaupause für weitere algorithmische
   Veto-Up/Veto-Down-Regeln.
3. **Das echte Bewertungsrisiko liegt bei den 72 „beide falsch"-Cases** —
   erst durch algorithmische adversariale Set-Features (Trigger-Autoren/Refs
   ∖ Eigenwerk) angreifen; für die Restmenge, die auch dort unklar bleibt,
   ist Volltext-LLM mit Anker-Zitaten die gezielte Eskalation. Ein
   Vergleichs-Backtest *algorithmisch erweitert vs Volltext-LLM* auf genau
   diesen 72 Items wäre der nächste Validitäts-Check.
4. **Ground-Truth ist für ihren Zweck (3-Klassen-Triage-Validierung) belastbar.**
   Selection-Bias ist transparent (per `selection_mode` rekonstruierbar) und
   muss bei Modellvergleichen explizit berichtet werden — nicht „getunt weg".

## Daten

- `articles.db` (39 cols, `selection_mode` als Bias-Tracker)
- `backtest_data/features_gold.parquet` (461 × 33 Features)
- `backtest_data/predictions_iter11_full.parquet` (alle Modellvarianten)
