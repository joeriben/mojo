# MOJO Profil-Modellierungs-Komponente (Sketch)

**Datum**: 2026-05-25.
**Status**: vorgemerkt (eigene §X-Komponente, nicht in §2.6 oder Trigger-Auswahl gepresst).
**Trigger**: Benjamins Methodik-Reflexion bei der OS-Schulden-Diskussion zu
Trigger-Autoren:

> "Das ändert sich natürlich mit den Jahren und den Profilen innerhalb derer
> ich schreibe. D.h. nicht alle Artikel einfach zusammenschmeissen und dann
> ranken. Das ist schon subtiler. Eigentlich müsste man ein Embedding pro
> Artikel machen; es sind ja keine Haufen sondern Abhängigkeitsnetze die
> Formen ergeben (wenn auch an den Rändern unscharfe)."

---

## Problem

Alle aktuellen MOJO-Aggregationen über die Eigenwerk-Basis (`corpus.json`,
`summaries.json`, `own_refs.db`) sind **globale Haufen**:

- `named_thinkers`-Häufigkeit über alle 53 Summaries (Reckwitz 16, Foucault 11, …)
- `pub_refs`-Häufigkeit über alle 78 Eigenwerke mit Refs
- Diskursraum-Buckets sind 7 hartgrenzige Multi-Label-Mengen — zu grob

Empirischer Befund (siehe ChatLog 2026-05-25, OS-Schulden-Audit Stage):

| Person          | named_thinkers global | per Diskursraum (max%) |
|-----------------|----------------------|----------------------|
| Reckwitz        | 16 pubs (Rank 1)     | medienpaed 67%        |
| Macgilchrist    | 6 pubs (Rank 18)     | digitale_kultur 33%   |
| Chun            | 2 pubs (Rank 76)     | bildungstheorie 33%   |
| Jarke           | 1 pubs (Rank 161)    | (zu wenig Match)      |

Reckwitz/Latour/Barad sind **theoretische Quellen** (in Eigenwerken bereits
verarbeitet). Trigger-Autoren (Macgilchrist/Jarke/Chun) sind **kollegial-
aktuelle Stimmen** im Diskursraum — strukturell andere Kategorie. Eine
naive Häufigkeits-Aggregation reproduziert die Trigger-Liste nicht.

Pro Diskursraum-Aggregation ist die richtige Größenordnung, aber zu grob:
Macgilchrist konzentriert sich in `digitale_kultur` (33%), `kulturwiss_other`
(33%), `erziehungswiss` (29%), `resilienz` (25%) — vier Räume, also kein
sauberer Single-Cluster. 7 hartgrenzige Diskursräume sind nicht das, was
Benjamins methodische Intuition meint mit „Abhängigkeitsnetze die Formen
ergeben".

## Lösungs-Skizze: Profil-Modellierungs-Komponente

Drei Eigenschaften, die die Komponente haben muss:

1. **Pro-Artikel-Positionierung** statt Bucket-Zuordnung. Jeder Eigenwerk-
   Artikel bekommt einen Vektor in einem semantischen Raum.
2. **Soft-Cluster / kontinuierliche Topologie**. Ein Eigenwerk gehört nicht
   zu „1 Diskursraum" oder „k Diskursräumen", sondern hat eine **Nachbar-
   schafts-Struktur** mit allen anderen Eigenwerken. Ränder unscharf.
3. **Zeitliche Drift**. Profile verschieben sich. Der Vektorraum bildet
   Verschiebungen ab; Cluster können entstehen/zerfallen/migrieren.

### Stage 0 — Embeddings pro Eigenwerk

**Input pro Pub**:
- Variante A (preisgünstig, deckt 53/161): `summary_de + key_terms +
  named_thinkers + methods + cases_examples` aus `summaries.json`.
- Variante B (vollständig, deckt ~107/161 mit Volltext): pdftotext-Output
  aus `own_refs.db` plus o.g. Metadaten als prefix.

**Modell-Optionen**:
- Lokal: `sentence-transformers/distiluse-base-multilingual-cased-v2`
  (deutsch+englisch, ~500MB, offline, kostenlos).
- API: OpenAI `text-embedding-3-small` (~$0.0002/1k tokens, alle 161 Pubs
  unter $0.10).
- OpenRouter: `voyage-multilingual-2` o.ä.

**Output**: `own_refs/embeddings.parquet` mit Spalten
`canonical_id, model_id, vector (float32[d]), created_at`.

**Persistenz-Disziplin**: idempotent, additiv-inkrementell (analog
own_refs/build.py). Re-Build nur bei Modell-Wechsel oder neuen Pubs.

### Stage 1 — Cluster-Diagnose (visualisierbar)

- UMAP 2D-Projektion → Scatter-Plot mit Jahresfarben + Diskursraum-Markern.
  Zeigt, ob die hartgrenzigen Diskursräume mit der Embedding-Topologie
  übereinstimmen oder davon abweichen.
- HDBSCAN o.ä. für **Soft-Cluster**, aber wichtiger als harte Cluster:
  **k-Nearest-Neighbor-Strukturen**. Pro Pub die 5–10 ähnlichsten Eigenwerke.
- Pro Soft-Cluster oder pro NN-Region: dominante `key_terms`,
  `named_thinkers`, `ref`-Autoren (aus `own_refs.db` mit Backfill).

**Diagnose-Ausgabe**: Markdown-Report `output/profile_clusters.md` mit
Cluster-Profilen (Top-Begriffe, Top-Personen, repräsentative Eigenwerke,
Zeitspanne, Diskursraum-Dominanz).

### Stage 2 — Topologie-basierte Trigger-Auswahl

- Pro Region des Eigenwerk-Embedding-Raums: diskursiv-naheliegende externe
  Autor*innen über (a) Autor-Embeddings aus OpenAlex, (b) Autor-Coupling
  zu Eigenwerk-Refs in der Region, (c) Diskursraum-A-Journal-Co-Occurrence.
- **Differenz-Heuristik** (analog §2.2 adversarial-blindspot): bevorzuge
  Autor*innen, die in der Region **prominent**, in den globalen Top-Theorie-
  Quellen aber **niedrig** sind. Das schließt Reckwitz/Latour/Barad aus.
- **Trennschärfe-Filter** (Jandrić-Test): OpenAlex-Author-Works/Jahr unter
  Schwelle.
- Output: pro Region 5–10 Trigger-Kandidaten mit Begründung; User editiert
  und finalisiert in `profile.json["trigger_authors"]`.

## Anschluss-Komponenten in MOJO, die davon profitieren würden

| Komponente | Aktueller Zustand | Mit Profil-Modell |
|---|---|---|
| Trigger-Auswahl | hartcoded Macgilchrist/Jarke/Chun, manuell editierbar | per-Region-Vorschläge + Validierung |
| Cascade-Vorfilter (§2.1/§2.2) | globale IDF-Schwellen | per-Cluster-Schwellen (verschiedene Profile haben verschiedene Refs-Dichte) |
| Digest-Sortierung | Journal-Tier + Verdict | Artikel-zu-User-Profil-Distanz im Embedding-Raum |
| Diskursraum-Trends | 7 hartgrenzige Räume | kontinuierliche Topologie, Drift sichtbar machen |
| Eskalations-Selektion (§2.5) | PrioScore aus IDF-Signalen | + Cluster-Zugehörigkeit als Signal |
| Wrong-LES-Diagnose | LLM-Volltext-Assess | + Region-Kontext im Prompt ("dieser Artikel liegt in der Region X Deiner Arbeit") |

## Bewusste Nicht-Ziele

- **Kein Ersatz** für `summaries.json` und `corpus.json`. Die LLM-
  Profilbildung bleibt der Wahrheits-Anker. Embeddings sind eine
  **zusätzliche** Topologie-Schicht.
- **Kein Ersatz** für die hartgrenzigen Diskursräume in `diskursraeume.json`.
  Die bleiben als User-explizite Kategorien für Trends/Digest erhalten.
- **Kein automatisches Trigger-Set**. Stage 2 produziert Kandidaten; finale
  Entscheidung bleibt User-Entscheidung (gleicher Punkt wie bei Benjamins
  intuitiver Auswahl Macgilchrist/Jarke/Chun).

## Reihenfolge — wann implementieren?

Aktuelle MOJO-2.0-Roadmap (§2.1–§2.6) ist näher an der Cascade-Triage. Die
Profil-Modellierung ist orthogonal — kann **nach** §2 angegangen werden, ohne
§2 zu blockieren. OS-Schulden #3+#4 (Trigger-Autoren konfigurierbar) werden
pragmatisch über editierbare `profile.json`-Listen gelöst, **bevor** Stage 0
gebaut wird.

## Nächste konkrete Aufgabe (wenn die Komponente angegangen wird)

1. Modell-Wahl entscheiden (lokal vs. API).
2. `scripts/embed_eigenwerke.py` als Einmal-Ingest (Stage 0).
3. `scripts/profile_cluster_diagnose.py` als visuell ausgewerteter Sanity-
   Check (Stage 1).
4. Erst danach Stage 2 angehen.

## Verankerung

- Memory-Eintrag `project_profile_modelling.md` (kurz, mit Verweis hierhin).
- Diese Datei `docs/mojo_profile_modelling_sketch.md` ist die methodische
  Begründung.
- ROADMAP.md bekommt einen §X-Eintrag, der hierauf zeigt.
