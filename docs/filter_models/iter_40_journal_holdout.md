# Iter 40 — Journal-Holdout: generalisiert der Journal-Prior?

## Anforderung
Ehrlichkeitsbefund aus dem Ledger: die „Bar" hatte einen Per-Journal-Leak (Prior aus denselben Zeilen
gelernt, gegen die getestet wird). StratifiedKFold mischt jedes Journal über Train/Test. Harter Test:
**GroupKFold nach Journal** — jedes Test-Journal ist im Train ungesehen, der Prior fällt auf den globalen
Schnitt G zurück (max(0, pj−G)=0). Wie viel des Prior-Lifts überlebt auf wirklich neuen Journals?

## Messung (`iter_40_journal_holdout.py`, alle Quellen)
Journal-Landschaft im Gold: **26** unique Journals, 4 Singletons, Top = AIandSoc (147 Artikel).

| Modell | keep-AUC |
|---|---|
| rich-only | 0.690 |
| M-C, StratifiedKFold (Journal **bekannt**) | **0.716** |
| M-C, GroupKFold (Journal **ungesehen**) | **0.690** |

- 100 % der GroupKFold-Test-Zeilen fielen auf G zurück → Prior-Beitrag dort **exakt 0**.
- Prior-Beitrag bekannt: **+0.026**; davon auf neue Journals generalisiert: **+0.000**.

## Harte Kritik
- **Der Journal-Prior ist Memorisierung, keine Generalisierung (P3, P15):** der +0.026-Lift ist
  *vollständig* ein Effekt bekannter Journals. Auf einem genuin neuen Journal trägt er **null** —
  das M-C kollabiert dort sauber auf rich-only (0.690). Der frühere „Bar"-Leak-Verdacht ist damit
  *quantifiziert*: der Prior leakt nicht im Sinne falscher Zahlen, aber er ist ein
  **Erinnerungs-, kein Lern**-Signal. Ehrlich benannt, nicht als generalisierbare Trennschärfe verkauft.
- **Aber die Produktions-Nuance kehrt das Urteil um (P11, P16):** die Scout-Watchlist ist **fix**
  (~49 Journals, hier 26 im Gold). Eingehende Artikel stammen fast immer aus **bekannten** Journals —
  also ist das StratifiedKFold-Szenario (Prior verfügbar, +0.026) das **realistische**, und GroupKFold
  das pessimistische Rand-Szenario, das nur beim *Hinzufügen* eines neuen Journals zur Watchlist eintritt.
  Der +0.026 ist also ein **real nutzbarer** Produktions-Lift — solange man weiß, dass ein neu
  aufgenommenes Journal erst Historie sammeln muss, bevor sein Prior greift (Cold-Start).
- **Konsequenz: Cold-Start explizit behandeln (P6):** ein neu zur Watchlist hinzugefügtes Journal startet
  mit Prior=G (neutral) — korrekt, kein Schaden, aber auch kein Lift. Erst nach ~5+ bewerteten Artikeln
  (Shrinkage-k=5) wird der Prior aussagekräftig. Das gehört in die M-E-Spezifikation als bekannte
  Eigenschaft, nicht als Bug.
- **Der eigentliche Hebel bleibt rich-sim (P6):** 0.690 von 0.716 (96 %) der M-C-Trennschärfe kommt aus
  dem Content (rich_sim), nur 0.026 aus dem Journal-Prior. Bestätigt die Serien-Linie (Iter 27/36):
  **Inhalt trägt, Bibliometrie/Journal-Herkunft schmückt.** Investition gehört in bessere Content-
  Erdung (Per-Werk-Summaries, geerdete Bezüge), nicht in feinere Journal-Statistik.
- **Caveat (P3):** 26 Journals, AIandSoc dominiert mit 147/461 (32 %). GroupKFold mit einem so dominanten
  Cluster verschiebt viel Masse in einen Fold; die AUC-Zahl ist robust (rich-only ist fold-invariant),
  aber die Journal-Verteilung ist selbst selektions-verzerrt (Watchlist-Schwerpunkt KI&Gesellschaft).

## → nächste Iteration
Iter 41: **Temporal-Holdout** — train auf älteren, test auf neueren Artikeln (Publikationsjahr). Prüft
Drift-Robustheit: bleibt rich-sim über die Zeit stabil, oder driftet Benjamins Relevanz-Signatur so,
dass ein auf Vergangenheit kalibriertes Modell die Gegenwart schlechter trifft? (Validitätsfrage, P3.)
