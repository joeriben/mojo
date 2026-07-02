# Iter 10 — Cascade-Komposition: own+content-Basis + Bibliometrie-Veto-up

## Anforderung
Dokumentierte Cascade-Idee (Memory project_adversarial_blindspot, feedback_iter13): schwaches
Basismodell (own+content LogReg, Iter 03 = 0.514) mit **hochpräzisem** Biblio-Veto-up kombinieren —
wo `own_coupling≥1` ODER `citation≥1` feuert (Iter 01: Präzision 0.83–1.0), hochstufen. Ehrlich auf
`user_verdict` (OOF CV), gesamt **und** screening-only.

## Messung (`iter_10_cascade_veto_up.py`, OOF 5-fold, class_weight balanced)
Veto feuert: **42 gesamt, nur 1 im blinden screening-Strom**; davon 83 % echt-keep.

| | macro-F1 | keep-F1 | LES-Rec | keep-Prec |
|---|---|---|---|---|
| **GESAMT** Basis own+content | 0.514 | 0.605 | 0.532 | 0.547 |
| + Veto→scannen | 0.514 | 0.605 | 0.532 | 0.547 |
| + Veto→lesenswert | 0.508 | 0.605 | **0.582** | 0.547 |
| **SCREENING** Basis | 0.444 | 0.384 | 0.500 | 0.292 |
| + Veto→scannen / →lesenswert | 0.444 | 0.384 | 0.500 | 0.292 |

## Harte Kritik
- **Veto→scannen = exakter No-Op (P6):** 0 Änderung in *allen* Metriken. Wo die Bibliometrie feuert,
  sagt das Basismodell **bereits keep**. Die hochpräzisen Treffer sind im own+content-Modell schon
  drin → das Veto fügt nichts hinzu. Direkte Bestätigung von Memory feedback_iter13 („wo STRONG
  feuert, sind alle bereits LES, 100 % redundant") — jetzt auf `user_verdict` reproduziert.
- **Veto→lesenswert ist ein schlechter Tausch:** +5 pp LES-Recall (0.532→0.582), aber −0.6 pp macro-F1
  (drückt korrekte *scannen* fälschlich auf *lesenswert*). Recall gegen Genauigkeit erkauft, nicht geschenkt.
- **Der vernichtende Befund (P15):** im **blinden** Strom feuert das Veto **genau 1×** (von 120). Der
  gesamte sichtbare Nutzen der Cascade (42 Treffer) lebt im **intentional-positiven** Pool — exakt der
  Selection-Bias aus Iter 06. Auf dem echten Entdeckungs-Strom ist die dokumentierte Veto-up-Cascade
  **praktisch wirkungslos**. Das ist die schärfere, ehrlichere Lesart des „Plateaus": nicht nur
  redundant, sondern auf dem relevanten Strom abwesend.
- **Konsequenz:** Bibliometrie-Veto-up ist als Recall-Hebel für blinde Entdeckung **erledigt**. Was
  bleibt, ist allein der Inhalt — und der sitzt bei AUC 0.69 (Iter 02/09). Phase C muss den Inhalt
  *erden* (geteilte Referenzen mit konkretem benanntem Eigenwerk), nicht weitere Score-Achsen stapeln.

## → nächste Iteration
Iter 11: Fehleranalyse statt neues Modell — **wo** scheitert das own+content-Modell auf dem blinden
Strom? Welche der 8 screening-LES verfehlt es, und teilen die verfehlten überhaupt *irgendein*
geerdetes Signal (Ref/Autor/Konzept)? Das entscheidet, ob Phase C (geerdete Bezüge) das Defizit
treffen kann oder ob die Hard-Cases strukturell signalfrei sind (Memory feedback_ground_truth: 72 Items
wo Algo+Opus beide falsch).
