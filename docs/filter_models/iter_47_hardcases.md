# Iter 47 — Die irreduziblen Hard-Cases, konkret benannt

## Anforderung
Die harte Grenze (Iter 11/39/43/46) nicht nur als Zahl, sondern als benennbare Artikel-Klasse: welche
LES reiht M-C tief (Rang < 50 %) UND fängt kein geerdeter Anker? Qualitative Diagnose — Titel, Journal,
Concepts, Abstract-Snippet.

## Messung (`iter_47_hardcases.py`)
**15 von 79 LES** sind irreduzibel (Rang < 50 % UND kein Anker). Ø rich-sim **0.35** vs. leicht erkannte
LES (Rang ≥ 75 %, n=40) **0.55** — und letztere zu **68 % geerdet**, die Hard-Cases zu 0 %.

Exemplare (Rang | rich-sim):
- **36 % | 0.37 — „Gesture-ing in drawing via Theory of Whitehead and Barad" (JAC, similarity)** — der
  Smoking Gun: Benjamins *Kernterrain* (ästhetische Bildung + Barad/Neuer Materialismus), tief gereiht.
- 22 % | 0.33 — „AI-enabled foraging… disrupting efficiency-driven sociotechnical imaginaries" (AIandSoc) — STS/Imaginaries.
- 36 % | 0.37 — „Human–AI relationships as designed relationality: a sociotechnical model" (AIandSoc) — Relationalität/Posthumanismus.
- 35 % | 0.37 — „AI and epistemic justice: a decolonial turn through indigenous knowledge" (AIandSoc) — dekoloniale Epistemologie.
- 22 % | 0.33 — „When machines join the moral circle: the persona effect of generative AI" (BJET) — Agency/Moral.
- 11 % | 0.28 — „SURVEILLANCE CAPITALISM IN SCHOOLS" (DCE, **concepts leer**) — Überwachungskritik + Datenarmut.

## Harte Kritik
- **Die Grenze hat ein Gesicht — und es ist Benjamins eigenes Terrain (P6, P16):** die irreduziblen
  Hard-Cases sind nicht thematisch fern, sondern **theoretisch/konzeptuell verwandt** (Barad, Whitehead,
  posthumane Agency, Relationalität, Überwachungskritik, dekoloniale Epistemologie, ästhetische Geste) —
  **ausgedrückt im Vokabular angrenzender Disziplinen** (HCI, Kognitionswissenschaft, Fan Studies,
  formatives Assessment, STS-Pädagogik). Genau die Verwandtschaft, die einen Menschen sofort aufhorchen
  lässt, ist für das generische Embedding (all-MiniLM) unsichtbar, weil die *Oberflächen-Wörter* anders
  sind. Und es gibt keine Zitations-Brücke (kein Anker). **Weder Bibliometrie noch Oberflächen-Embedding
  greift — nur das Lesen des Arguments.**
- **Das ist die empirische Begründung der gesamten 2.0-Architektur (P9, P16):** warum Volltext-LLM-
  Eskalation? Weil die wertvollsten Treffer (theoretische Wahlverwandtschaft unter fremder Oberfläche)
  per Konstruktion das sind, was Abstract-Embedding und Zitationsgraph verfehlen. Warum schafft selbst
  Opus nur ~62 % auf dem complementarity-Pool (Memory)? Weil die Relevanz im *Argument* steckt, nicht in
  Stichworten. Iter 47 zeigt die Artikel, an denen das wahr wird — kein abstraktes „Plateau", sondern
  ein Stapel konkreter Paper.
- **Zwei verschiedene Versagensgründe, nicht einer (P6):** (1) **Vokabular-Lücke** (der Barad/Whitehead-
  Artikel, die Relationalitäts-Paper) — Relevanz da, Embedding blind; behebbar durch *reichere Eigenwerk-
  Repräsentation* (Volltext-Summaries statt Titel, theoretische Quellen explizit). (2) **Datenarmut** (der
  Surveillance-Capitalism-Artikel: concepts leer, rich 0.28) — kein Signal, weil keine Metadaten; behebbar
  nur durch Volltext-Holung. Beide führen zu „tief gereiht", aber die Reparatur ist verschieden — pauschal
  „Modell schlecht" wäre falsch.
- **Bestätigt die Werte-Entscheidung aus Iter 38/46 (P11):** mehrere Hard-Cases sind Frontier
  (digitale_kultur/Überwachung) und ÄKB-mit-fremder-Oberfläche (K-pop-Bildung, Drawing/Barad) — genau die
  Zonen, die der balancierte Ranker (Iter 38) und das „nie-droppen"-Mittelband (Iter 46) schützen sollen.
  Die qualitative Analyse rechtfertigt rückwirkend, warum 100 % LES-Recall (großes LLM-Mittelband) die
  richtige Vorgabe ist: würde man hier hart droppen, verlöre man Benjamins eigenstes Material.
- **Selbstkritik (P3):** „Rang < 50 % & kein Anker" ist eine grobe Hard-Case-Definition; einige der 15
  sind Grenzfälle (Rang 44–48 %). Der Kern-Befund (Vokabular-Verwandtschaft ohne Oberflächen-/Zitations-
  Signal) gilt aber gerade für die *tiefsten* (11–25 %, der Barad-, Surveillance-, foraging-Cluster) —
  also nicht ein Artefakt der Schwelle.

## → nächste Iteration
Iter 48: **Kalibrierung / Reliabilitäts-Check** — taugt der M-E-Score als *Wahrscheinlichkeit* (ECE,
Reliabilitätskurve), oder nur als Rang? Entscheidet, ob die Confidence-Bänder (Iter 46) auf kalibrierten
Schwellen ruhen dürfen oder nur auf Perzentilen. Letzter Mess-Baustein vor der finalen Synthese (Iter 50).
