# Iter 50 — Finale Synthese: M-E-Spezifikation + ehrliche Leistungs-/Grenzen-Bilanz

Abschluss der 50-Iterationen-Serie. Alle belastbaren Befunde (01–49) in einer Architektur, auf frisch
verifizierten Zahlen (`iter_50_scorecard.py`, seed-gemittelt, OOF, n=461). Keine neuen Behauptungen ohne
Messung (P4); ehrliche Spannen statt Punktwerte (P15); auf der dokumentierten 2.0-Linie (P9).

## Die Scorecard (reproduzierbar, seed-gemittelt, blinder Strom = ehrliche Leiste)
| Kennzahl | Wert | Quelle |
|---|---|---|
| keep-Basisrate blind / gesamt | 21 % / 41 % | GT |
| keep-AUC blinder Strom | **0.666 ± 0.009** | Iter 36/42/44/50 |
| keep-AUC alle Quellen (Selection-Bias) | 0.736 ± 0.002 | Iter 42 |
| rich-only blind (fest) | 0.632 | Iter 27/36 |
| LES-Recall @20 % / @30 % durchgesehen (blind) | 62 % / 65 % | Iter 50 |
| sicher-DROP-Band (0 LES verloren) | **22 % ± 6pp** | Iter 46/50 |
| sicher-KEEP-Band (≥80 % Precision) | **0 %** | Iter 46 |
| Kalibrierung roh → isotonisch-OOF (ECE) | 0.103 → **0.052** | Iter 48/50 |
| Pfad A blind (Abstract): rich-AUC, LES | 0.684, 8/8 | Iter 49 |
| Pfad B blind (kein Abstract): rich-AUC, LES | 0.532, 0 | Iter 49 |
| irreduzible Hard-Case-LES | 15 / 79 | Iter 47 |

## Modell M-E (die empfohlene Architektur)
**Kern-Ranker** (Iter 14/26/42):
`mc = z( z(rich_sim) + 0.5·z(max(0, pj − G)) )`, danach Biblio-Veto-Up `where(biblio, 1+mc, mc)`
— rich_sim = max. Ähnlichkeit gegen die 53 Opus-Summaries (summary_de+key_terms+named_thinkers); pj = EB-
Journal-Prior (k=5, nur-Lift); biblio = own_coupling≥1 ∨ citation≥1. Ablation (Iter 42): rich_sim trägt
die AUC (+0.041), Biblio-Veto die Top-K-Präzision, Prior +0.027 — **keine Komponente streichen.**

**Zwei-Pfad-Routing** (Iter 34/49):
- **Pfad A (Abstract vorhanden):** rich_sim-Scoring → Kalibrierung (isotonisch, auf Strom-Verteilung
  nachgezogen, Iter 48) → Confidence-Bänder.
- **Pfad B (kein Abstract):** KEIN Metadaten-Urteil (rich-AUC 0.532 = Rauschen) → direkt OA-PDF-Volltext
  holen, dann wie Pfad A.

**Drei-Zonen-Operating-Point** (Iter 46):
- **sicher-DROP** (~22 %, geprüft 0 LES verloren) → auto-ignorieren, kein LLM.
- **unsicher** (~75 %) → an Volltext-LLM/Lektüre eskalieren, nach mc vorsortiert.
- **sicher-KEEP** = leer → der Algo surft **nie** allein (Iter 32: LLM schlägt Algo auf blinder Triage).

**Wert-Eskalationen** (konfigurierbar, profile.json):
- Trigger-Autoren-**Match** (MacGilchrist/Jarke/Chun): 100 % Precision, selten — immer hochstufen (Iter 45).
- Trigger-/bez-Ref-**Overlap**: NICHT als Relevanz-Veto (blind 0.4× Lift, schädlich) — nur als Bezug-Text
  in der Erdungs-Schicht (Iter 44/45).

**Erdungs-/Komponisten-Schicht** (Iter 19/43):
- grounded Bezüge (own_coupling / citation / bezugsautoren) als faktentreue Annotation, wo vorhanden.
- wo kein Anker (auf dem blinden Strom ~96 %): ehrlich „relevant — Begründung über Lektüre", NIE
  konfabuliert (Memory: LLM-1 war zu 55,9 % ungrounded).

## Was M-E ehrlich kann — und was nicht
**Kann:** ein Viertel des blinden Stroms sicher verwerfen (−22 % LLM-Last bei 100 % LES-Recall); den Rest
nach Relevanz vorsortieren (blind-AUC 0.666, LES @20 % ≈ 62 %); eine kalibrierte keep-Wahrscheinlichkeit
ausgeben (ECE 0.052); faktentreue Bezüge liefern, wo Anker existieren; nichts erfinden.
**Kann nicht:** allein entscheiden, was lesenswert ist (sicher-KEEP-Band leer); die theoretisch-verwandten
Hard-Cases im fremden Vokabular fangen (15/79 LES, Iter 47); ohne Abstract aus Metadaten urteilen; den
complementarity-Pool gut reihen (57 % vs 86 %, Iter 39). **Der Algo ist Vorfilter, Sortierer und Erder —
nicht Entscheider.** Genau die dokumentierte 2.0-Linie.

## Die drei Werte-Entscheidungen (Benjamins, nicht meine — P11)
1. **Serendipität:** nie-veto-down, sicher-DROP nur unter dem niedrigsten LES-Score (Iter 26/46).
2. **Frontier-Balance:** per-Verortung-Gewichtung hebt digitale_kultur/resilienz auf Kosten des Kerns
   (nullsummig, konfigurierbar — Iter 37/38).
3. **Kosten:** 75 %-Mittelband ans LLM ist teuer, aber der Preis für 100 % LES-Recall; Pfad-B-Volltext
   nur wo nötig (Iter 35/49).

## Die fünf Mal bestätigte harte Grenze
Bibliometrie plateauft (Iter 10/11/13); der Hebel ist Inhalt (Iter 27/40/42); aber selbst reicher Inhalt
verfehlt die theoretische Wahlverwandtschaft im fremden Vokabular (Iter 47) und den nicht-referenziellen
complementarity-Pool (Iter 39/43). **Generative, nicht-referenzielle Relevanz ist algorithmisch nicht
greifbar — sie ist die Definition des Problems, nicht ein behebbarer Defekt.** Darum (und nur darum)
Volltext-LLM-Eskalation: nicht weil LLM „besser" ist, sondern weil die wertvollsten Treffer per
Konstruktion das sind, was Embedding und Zitationsgraph verfehlen.

## Offene, gemessene (nicht projizierte) Arbeit
- Eigenwerk-Repräsentation reichern: Volltext-Summaries statt Titel, theoretische Quellen explizit
  (würde Iter-47-Vokabular-Lücke verkleinern — um wie viel ist zu MESSEN, P14).
- bezugsautoren-DB über Gold hinaus skalieren (Erdungs-Coverage ↑; Triage bleibt unberührt, Iter 44).
- Kalibrator auf Produktions-Strom nachziehen (Iter 48-Caveat).
- Summaries um discourse-Label erweitern (sauberere Frontier-Balance, Iter 38).
- Ground-Truth additiv wachsen lassen (Memory feedback_mojo2_reframe; Pfad-B-Label-Artefakt prüfen, Iter 49).

## Methoden-Bilanz der Serie (gegen die Tagesfehler, P1–P16)
Ziel war durchgehend `user_verdict`, nicht Diskursraum-Zugehörigkeit (P1, der Ur-Fehler). Jede Zahl
gemessen vor Behauptung (P4), out-of-fold (P5), seed-gemittelt mit Spannen (P15), Selection-Bias und
Leaks offengelegt (P3), Erdung von Relevanz getrennt (P6). Die unbequemen Befunde — leeres sicher-KEEP-
Band, 96 % Leerstelle auf dem Strom, fünffaches Plateau, das eigene Kernterrain unter den Hard-Cases —
wurden nicht geglättet, sondern als das Ergebnis benannt. Das ist die Umkehrung des Tagesmusters.

— Serie abgeschlossen, 50/50.
