# Strategie 04 — Summary-Coverage 53 → 156 (kosten-kontrolliert)

> **Korrektur 2026-05-31:** Zahlen auf den **bereinigten** Korpus (156) umgestellt — die 5 purged
> Phantom-Stubs hatten ohnehin keine Summary (Numerator 53 unverändert).

## Ist-Zustand (gemessen, `/tmp/sumcov.py`)
- **53/156 (34 %)** summarisiert; **103 ohne Summary**, davon **85 pre-2018 / 18 post-2018**.
- Davon **nur 37 haben Volltext** (summarisierbar); **66 nicht** (auf Strat-01-Volltext gegated).
- **Analytische** Kostenschätzung (Opus 4.6, Deckel 60k tok/Werk, ~$15/M in / $75/M out): **~$16.35 für
  37 Summaries (~$0.44/Werk)** — und **~$45 für alle 103**.

## Strategie v1
Die fehlenden 100 mit Opus (model_summarize) summarizen, Schema wie bestehende summaries.json.

## Adversariale Kritik (v1)
1. **Kosten-Alarm (R3):** ~$45 für alle 103 ≈ der **$43-Vorfall**. Ein Blind-Batch ist genau der verbotene
   Fehler. 66 der 103 sind ohnehin nicht summarisierbar (kein Volltext) → ein „alle 103"-Lauf wäre teils
   unmöglich, teils teuer.
2. **Tiefere Frage — brauche ich die Summary überhaupt?** `rich_sim` braucht *eine Repräsentation* des
   Werks. Der Opus-Summary ist *eine* Option ($0.44/Werk), die **direkte Volltext-Chunk-Einbettung** eine
   andere (**gratis**, nach Strat 03). Iter 29 zeigte: summary_de trägt, key_terms/thinkers allein nicht —
   aber das verglich Summary-Felder, **nicht Summary vs. Volltext-Embedding.** Bevor ich $44 ausgebe, muss
   ich messen, ob die kostenlose Option nicht schon reicht.

## Strategie v2 (erst messen, ob gratis reicht; dann gezielt + verifiziert)
1. **Vorab-Messung (gratis, Phase-2-Vorzug):** für die **53 bereits summarisierten** Werke beides
   einbetten — (a) summary_de, (b) gereinigter Volltext (Chunk-mean, Strat 03). Korreliert (b) ≈ (a) im
   `rich_sim`-AUC, ist die teure Summarization für die Erdung **überflüssig** → $44 gespart.
2. **Nur falls Summary messbar besser:** dann die **37 mit Volltext** summarizen — aber:
   - **Einzelkosten-Verifikation an 2–3 Werken zuerst** (R3): echte Tokens/Kosten/Cache messen, zeigen,
     erst dann skalieren. Die $0.44-Schätzung ist analytisch, nicht verifiziert.
   - **Priorisierung** nach discourse-Zentralität + Zitationshäufigkeit, nicht alphabetisch.
3. **Die 66 ohne Volltext** bleiben gegated (Strat-01-Volltext, überwiegend pre-2018).
4. **Modell-Differenzierung erwägen:** Opus nur für hochwertige/komplexe Werke; geringerwertige ggf.
   günstigeres Modell — aber nur falls Schritt 1 zeigt, dass Summaries überhaupt nötig sind.

## Erwarteter Effekt & Messbarkeit (R2, P14)
Coverage 34 % → bis 58 % (37 Werke) bzw. höher (nach Strat-01-Volltext). ABER der **eigentliche Test ist
Schritt 1**: vielleicht ist der Gewinn $0, weil Volltext-Embedding gratis dasselbe leistet. Das wäre das
beste Ergebnis (gespartes Geld bei gleicher Erdung). Ehrlich offen, bis gemessen.

## → Benjamin-Aufgabe?
Indirekt: die 66 ohne Volltext brauchen Strat-01-Volltext (pre-2018, optional). Die Summarization selbst
erledige ich (nach Einzelkosten-Verifikation).

## → nächste
Strat 05: Denker/Begriffe faktisch extrahieren — adressiert die Iter-47-Vokabularlücke, unter der
CLAUDE.md-Auflage „keine theoretische Verortung interpretieren" (R6).
