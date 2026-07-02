# Iter 37 — Per-Verortung-Fairness: der disziplinäre blinde Fleck

## Anforderung
Bedient M-C alle disziplinären Verortungen gleich? Fairness-Diagnostik (NICHT Relevanz-Signal):
blind-keeper über `journal_clusters` den Diskursräumen zuordnen, mittlerer M-C-Perzentil-Rang pro Raum.

## Messung (`iter_37_per_verortung.py`, blinder Strom)
| Diskursraum | Artikel | keeper | Ø keeper-Rang |
|---|---|---|---|
| aesthetische_kulturelle_bildung | 17 | 5 | 88 % |
| medienpaed | 31 | 7 | 87 % |
| deutsche | 24 | 8 | 86 % |
| erziehungswiss | 23 | 1 | 82 % |
| bildungstheorie | 8 | 1 | 82 % |
| **digitale_kultur** | 57 | **12** | **37 %** |
| **resilienz** | 13 | 3 | **43 %** |

## Harte Kritik
- **Ein systematischer disziplinärer blinder Fleck — und er trifft die Frontier (P15, P8 — der schärfste
  Synthese-Befund):** M-C reiht die keeper der **Kern**-Heimaten (ÄKB 88 %, medienpaed 87 %, deutsche
  86 %) weit oben, aber die keeper in **digitale_kultur (37 %)** und **resilienz (43 %)** weit unten.
  digitale_kultur ist mit 12 keepern der **bestbesetzte** Raum — das Defizit ist also gut belegt, kein
  Kleinstichproben-Artefakt. Der Scout würde genau die STS-/Posthumanismus-/Datafizierungs-Funde
  begraben.
- **Die Ursache verbindet die ganze Serie (P6):** (1) die rich-Summary-Repräsentation ist ÄKB-dominiert
  (71 ÄKB-Publikationen vs 20 resilienz, 46 digitale_kultur) → der Content-Schwerpunkt lehnt zum Kern,
  Frontier-Artikel matchen schwächer; (2) die digitale_kultur-Journals (AIandSoc, BDS, DCE) haben
  mittlere/niedrige keep-Raten → journal-prior-lift hilft nicht; (3) es ist exakt die konzeptuell-
  relevante-aber-bibliometrisch-ferne Region aus Iter 11 (Queer Kin, Surveillance Capitalism). Drei
  unabhängige Befunde zeigen auf dieselbe Wunde.
- **Das widerspricht dem Scout-Zweck frontal (P11, P16):** digitale_kultur + resilienz sind nicht
  Randgebiete, sondern Benjamins **wachsende Kante** (Cultural Resilience Programme 2020–2029, AI4ArtsEd,
  MetaKuBi). Ein Ranker, der den etablierten Kern überbedient und die Frontier begräbt, **zementiert die
  Vergangenheit** und unterläuft genau den Entdeckungswert. Das ist gravierender als eine AUC-Schwäche —
  es ist eine inhaltliche Schieflage.
- **Konkrete Konsequenz (P7):** der Content-Schwerpunkt muss **per-Verortung balanciert** werden (nicht
  ÄKB-gewichtet) — z. B. pro Diskursraum ein eigener Eigenwerk-Schwerpunkt und Artikel gegen den *seines*
  Raums ranken (nicht den globalen ÄKB-lastigen). ODER ein expliziter Frontier-Bonus für digitale_kultur/
  resilienz. Das ist die EINE Stelle, wo die in Iter 27 verworfene per-Cluster-Topologie doch zählt:
  nicht für Aggregat-AUC, aber für **disziplinäre Fairness**. (Iter 27 hatte nur Aggregat-AUC getestet —
  hier zeigt sich der per-Cluster-Wert auf einer anderen Achse.)
- **Ehrlich über n (P3):** resilienz 3 / erziehungswiss 1 / bildungstheorie 1 keeper sind dünn; die
  82–88 %-Werte dort sind verrauscht. Belastbar ist der digitale_kultur-Befund (12 keeper, 37 %) und der
  Kontrast Kern-vs-Frontier. Die Richtung steht, die Einzel-Prozente der dünnen Räume nicht.

## → nächste Iteration
Iter 38: den **per-Verortung-balancierten Ranker** testen — Artikel gegen den Eigenwerk-Schwerpunkt
*seines* Diskursraums ranken statt gegen den globalen ÄKB-lastigen. Hebt das den digitale_kultur/
resilienz-Rang, ohne den Kern zu beschädigen? Das ist die direkte Reparatur des blinden Flecks aus Iter 37.
