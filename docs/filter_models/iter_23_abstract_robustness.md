# Iter 23 — Robustheit gegen fehlende Abstracts

## Anforderung
Der rich-Ranker (Iter 16) beruht auf Titel+Abstract+Konzepten. Realer OJS/RSS-Strom liefert oft keinen
Abstract. Wie viele Gold-Artikel sind abstract-arm, wie stark bricht der Ranker dort ein, trägt ein
Titel+Konzepte-Fallback?

## Messung (`iter_23_abstract_robustness.py`)
Abstract-Verfügbarkeit: **<50 Zeichen: 81 (18 %)**, voll (≥200): 380 (82 %).
**Screening-Strom ohne Abstract: 51/120 = 43 %.**

rich-Ranker keep-AUC, stratifiziert:
| Teilmenge | n | rich (m. Abstract) | rich_noabs (Titel+Konzepte) |
|---|---|---|---|
| voll-Abstract (≥200) | 380 | 0.701 | 0.652 |
| abstract-arm (<200) | 81 | 0.610 | 0.622 |
| **screening voll** | 69 | **0.684** | 0.697 |
| **screening arm** | 51 | **0.532** | 0.545 |

## Harte Kritik
- **Die Hälfte des realen Stroms ist abstract-los — und genau dort versagt der Ranker (P15, P3):**
  43 % des screening-Stroms hat keinen Abstract; dort fällt die rich-AUC auf **0.532** (≈Zufall),
  gegenüber **0.684** auf abstract-reichen screening-Artikeln. Das ist ein **operativer Showstopper-
  Caveat** für Iter 16: die dort gefeierte blinde Ranking-Leistung gilt im Wesentlichen für den
  abstract-reichen Teil. Hätte ich nur die aggregierte screening-AUC (0.632) berichtet, wäre verschleiert
  geblieben, dass sie auf einer Mischung aus „gut (0.684)" und „nutzlos (0.532)" beruht.
- **Der Fallback rettet es nicht (P6):** Titel+Konzepte (rich_noabs) ist auf abstract-armen Artikeln
  statistisch gleichauf (0.545 vs 0.532) — kein echter Gewinn. OpenAlex-`concepts`/`topics` sind zu grob,
  um die fehlende Abstract-Semantik zu ersetzen. Es gibt also keinen rein-textuellen Notnagel.
- **Konkrete Konsequenz für die Architektur (P7):** Abstract-Verfügbarkeit ist eine **Vorbedingung** des
  Rankers, kein Detail. Die Pipeline muss abstract-arme Artikel **vor** dem Ranking anreichern
  (OpenAlex/Crossref/Unpaywall-Abstract bzw. OA-Volltext holen — die Infrastruktur dafür existiert laut
  Memory bereits, §2.5 escalation/fulltext) oder sie auf einen **anderen Pfad** routen
  (bibliometrisch-präzise Treffer + Eskalations-Flag), statt ihnen einen Zufalls-Score zu geben.
- **Ehrlich über n:** screening-arm AUC 0.532 steht auf 51 Artikeln mit wenigen keepern — verrauscht.
  Die *Richtung* (abstract-arm ≪ abstract-voll) ist über beide Strata (gesamt 0.610<0.701, screening
  0.532<0.684) konsistent und damit belastbar; die exakte 0.532 nicht.

## → nächste Iteration
Iter 24: **Kalibrierungs-Ehrlichkeit** des Keep-Rankers — wenn der Komponist (Iter 19) einen Score-Hinweis
gibt („rankt im oberen X %"), stimmt die implizierte keep-Wahrscheinlichkeit? Isotonic-kalibrierte
P(keep) auf dem screening-Strom, Reliability-Check (sagt „70 %" auch ~70 % Treffer?), getrennt für
abstract-voll/arm. Ein Score, der lügt, ist schlimmer als keiner.
