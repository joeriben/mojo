# Iter 35 — Modell M-E: End-to-End-Spezifikation + Kosten-Bilanz

## Modell M-E (vollständige 2.0-Filter-Architektur)
```
Eingehender Strom
   │
   ├─ Abstract-Gate (Iter 23/34)
   │     ├─ Pfad A (abstract-reich, ~57%): rich-Content-Ranker (Titel+summary_de, Iter 29)
   │     │     + journal-prior-lift-only (Iter 26)  + Bibliometrie-Präzisions-Anker (Iter 16)
   │     │     → Reihung; LLM-Agent entscheidet (ganz Pfad A = 88% LES, oder Kaskade Top-30%)
   │     └─ Pfad B (abstract-arm, ~43%, 0 LES im Sample): deprioritisiert;
   │           Bibliometrie-Veto rettet gekoppelte; periodischer Sweep gegen Drift
   │
   ├─ Substitutiver Komponist (Iter 19): Abstract verbatim + Signale (RANG, nicht Prozent, Iter 24)
   │     + geerdete Bezüge (own-Ref ⊕ bez-direkt ⊕ named_thinker-hart, Iter 21) — ODER Leerstelle
   │     → NIE LLM-Erzählung/Konfabulation (Iter 17–19: 0 ungrounded Behauptungen)
   │
   └─ Eskalation (Iter 30/§2.5): signalfreie konzeptuelle LES (Iter 11) → Volltext-Fetch + LLM
```

## Kosten (echte Call-Kosten aus `llm_calls`, pro 100 blinde Artikel)
Gemini-assess $0.0343 · Opus-assess $0.0858 · DeepSeek-screen $0.0114.
| Betrieb | assess-Calls | $/100 | $/Artikel | LES |
|---|---|---|---|---|
| MOJO-1 assess-alle | 100 | $3.43 | 0.0343 | — |
| MOJO-1 screen→assess | 40 (+100 screen) | $2.51 | 0.0251 | — |
| **M-E Pfad-A-only** | 57 | **$1.96** | 0.0196 | **0 verloren** |
| M-E Pfad-A Kaskade @30 % | 17 | $0.59 | 0.0059 | −LES |
Einmal-Senke: Opus-Summaries 53× = $4.55 (amortisiert). rich-Ranker/Lauf: $0.00 (offline).

## Harte Kritik
- **Der Kosten-Fall für 2.0 hält — knapp und ehrlich (P16, P13):** M-E Pfad-A-only ($1.96/100) ist
  **43 % billiger** als assess-alle ($3.43) bei **0 LES-Verlust** und etwas billiger als MOJO-1s
  screen→assess ($2.51) — *ohne* den DeepSeek-Screening-Schritt (der Ranker ersetzt ihn). M-E ist also
  nicht teurer als der Status quo und liefert zusätzlich Reihung + geerdete Einträge. Aber: das ist
  **kein dramatischer Spareffekt** — die blinde Strom-Triage war nie der teure Posten (HANDOVER: der
  $43-Vorfall lag woanders). Ehrlich: der Kosten-Gewinn ist real, aber moderat; der Hauptwert ist
  Qualität (Reihung, Erdung), nicht Geld.
- **Die Kaskade ist verlockend billig ($0.59) und genau deshalb gefährlich (P15):** sie kostet LES
  (Iter 33). Ich liste sie, aber markiere sie als Kosten-Notnagel, nicht als Default — sonst optimiert
  jemand auf den $0.59 und verliert Pflichtlektüre. Default bleibt Pfad-A-voll.
- **Sicherheits-Disziplin eingebaut (P13, CLAUDE.md):** alle Varianten (Gemini $0.034/Art) liegen weit
  unter der $0.15-Abbruch-Schwelle. Die Spec schreibt **Einzelkosten-Verifikation** (2–3 Calls messen,
  zeigen, bestätigen) VOR jedem Batch fest — der $43-Vorfall darf sich nicht wiederholen. Kein blinder
  Pauschal-Lauf.
- **Opus-Summary-Senke ist ehrlich auszuweisen (P3):** die $4.55 sind real und einmalig — aber sie
  müssen bei jedem neuen Eigenwerk inkrementell nachgeführt werden (Memory feedback_mojo2_reframe:
  own_refs additiv-idempotent). Nicht „kostenlos", sondern „amortisiert + laufende kleine Pflege".
- **Was die Spec NICHT verspricht:** Vollständigkeit (LES-Decke 75–88 %, Iter 31/34), scharfe Triage
  (Decke strukturell, Iter 14), LLM-Ersatz (Iter 32). Sie verspricht: bessere **Reihung** am Kopf,
  **geerdete** Einträge ohne Konfabulation, **moderate** Kostenersparnis, **kontrollierte** Eskalation.

## → nächste Iteration
Iter 36: **Seed-/Split-Stabilität** der Headline-Zahlen — die zentralen Kennwerte (M-C blind-AUC,
LES-Recall@20 %, journal-prior-AUC) über mehrere CV-Seeds streuen lassen. Wie groß ist die
Konfidenz-Spanne bei n=120/25? Das beziffert, welche der Synthese-Zahlen belastbar sind und welche
Rauschen im Bereich ±X pp haben (Anti-Overclaim-Absicherung der gesamten Phase E).
