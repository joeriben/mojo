# Strategie 08 — Profil-Modellierung (Stage 0): Per-Werk-Embedding statt Haufen

## Ist-Zustand (gemessen, `/tmp/s8.py`)
Memory `project_profile_modelling`: Embedding pro Eigenwerk + Soft-Cluster + Topologie statt globaler
Aggregation. Probe auf den 53 Summaries:
- **Harte Cluster schwach:** Silhouette k=3..7 nur **0.06–0.08** → das Œuvre ist eine **kontinuierliche
  Wolke**, kein diskretes Cluster-Set (bestätigt Iter 27 auf Material-Ebene).
- **Aber Struktur vorhanden:** Ø-Ähnlichkeit zum eigenen Cluster-Schwerpunkt **0.786** vs. globalem **0.710**
  (+0.076). k=5-Cluster sind interpretierbar und bilden auf die Verortungen ab:
  Medienbildung (n=10) · **ÄKB (n=18)** · ÄKB/Resilienz-international (n=8) · Resilienz (n=6) ·
  digitale-Kultur/ÄKB (n=11).
- **ÄKB-Dominanz (18/53 + ÄKB-nahe 2,4):** erklärt den Iter-37-Blindfleck auf **Material-Ebene** — der
  Œuvre-Schwerpunkt ist ÄKB-lastig, weil das *summarisierte* Korpus ÄKB-lastig ist (das pre-2018-
  Bildungstheorie-Fundament fehlt, S4).

## Strategie v1
Werke per KMeans (k=5 = Verortungen) hart clustern, Artikel gegen Cluster-Schwerpunkte ranken.

## Adversariale Kritik (v1)
- **Harte Cluster sind aufgezwungen, nicht gefunden:** Silhouette 0.06 heißt, KMeans schneidet eine Wolke
  willkürlich; bei n=53 sind die Grenzen instabil (seed-abhängig).
- **Der dominante ÄKB-Cluster ist ein Sampling-Artefakt:** er spiegelt, *welche* Werke summarisiert wurden
  (post-2018), nicht Benjamins wahres Profil. Hart darauf zu ranken zementiert den Iter-37-Blindfleck.
- **k=5 = Verortungen ist eine Annahme, keine Messung:** die Daten stützen kein sauberes k.

## Strategie v2 (Soft-Membership + Per-Werk-Primitiv + Rebalancing)
1. **Per-Werk-Embedding als Primitiv**, nicht Cluster-Label. Ähnlichkeit eines Artikels = **kNN/Top-m
   gegen einzelne Werke** (kontinuierliche Topologie), nicht gegen einen Cluster-Schwerpunkt. Das vermeidet
   sowohl den globalen Haufen (Iter 27) als auch die instabilen harten Cluster.
2. **Soft-Membership statt Hard-Cluster:** jedes Werk bekommt eine *Verteilung* über die Verortungen (aus
   discourse_json, das zu 97 % vorhanden ist — verlässlicher als KMeans), nicht ein Label. Die Verortungen
   kommen damit aus Benjamins kuratiertem discourse-Label, nicht aus einem Silhouette-0.06-KMeans.
3. **Rebalancing-Kopplung an S1/S4:** die ÄKB-Schieflage ist materialbedingt — pre-2018-Volltexte/Summaries
   (S1/S4) rebalancieren das Profil an der Quelle, statt es per Ranker-Gewicht (Iter 38) nachträglich zu
   biegen. **Material-Fix vor Ranker-Fix.**
4. **Recency-Gewicht:** neuere Werke höher gewichten (Lehrstuhl-Shift Richtung ÄKB/Resilienz ist real,
   Memory `feedback_korpus_aufarbeitung`) — aber konfigurierbar, weil das die Frontier-vs-Kern-Werte-
   Entscheidung berührt.

## Erwarteter Effekt & Messbarkeit (R2)
Eine stabilere, kuratiert-geerdete Profil-Repräsentation (discourse-Soft-Membership + Per-Werk-kNN), die
nicht auf instabilen Clustern ruht. Phase 2: schlägt Per-Werk-kNN den globalen `rich_sim` (Iter 27 sagte
nein für AUC — aber das war OHNE die Rollen-Trennung aus Strat 03 und OHNE pre-2018-Rebalancing). Ehrlich
offen: vielleicht bestätigt sich Iter 27 erneut, dann ist die einfachere globale Repräsentation richtig.

## → Benjamin-Aufgabe?
Nein — discourse_json + Embeddings vorhanden. (Rebalancing hängt indirekt an Strat-01-PDFs.)

## → nächste
Strat 09: Denker-/Begriffs-Lexikon konsolidieren — Voll-Namen-Disambiguation (Strat 05 zeigte
Fragmentierung) als kuratiertes, wiederverwendbares Profil-Artefakt.
