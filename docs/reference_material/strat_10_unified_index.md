# Strategie 10 — Einheitlicher, versionierter Referenz-Index (Integration)

## Ist-Zustand (gemessen, §A)
Das Referenzmaterial ist auf **6 unverbundene Stores** verstreut: `own_refs.db` (Volltext+Refs),
`summaries.json` (53 Summaries), `bezugsautoren.db` (Autoren-Werke), `projects.json` (5 Projekte),
`profile.json` (Verortungen/Trigger), `backtest_data/rich_sim.parquet` (Embedding-Cache). Kein Store kennt
den anderen; Joins laufen ad-hoc über Titel-Präfix-Matching (fehleranfällig, vgl. die S4-Summary-vs-pub-
Zuordnung über `title[:50]`).

## Strategie v1
Einen neuen, umfassenden Referenz-Index-Store bauen, der alle Achsen vereint (Werke, Refs, Embeddings,
Lexikon, Projekte, Profil) mit einheitlichem Schema.

## Adversariale Kritik (v1)
**Verstößt gegen „kein Over-Engineering" (CLAUDE.md).** Ein neuer Grand-Unified-Store ist verfrühte
Abstraktion: er dupliziert `own_refs.db` (das bereits die kanonische Werk-Identität + Volltext + Refs
hält), erzwingt eine Migration und Schema-Churn, und das eigentliche Problem (12 % Refs, 56 % Volltext) löst
er **nicht** — es ist ein Sortier-, kein Beschaffungs-Problem. Ein schöner Index über dünnes Material bleibt
dünn.

## Strategie v2 (minimal-invasiv: `own_refs.db` ist bereits der Hub)
1. **`own_refs.db` als bestehenden Hub erweitern**, nicht ersetzen — die Werk-Identität (canonical_id) ist
   schon kanonisch. Idempotent ergänzen (R4):
   - `role` (authored/edited, Strat 03) · `embedding` (Per-Werk-Vektor-Cache, Strat 08) ·
     `discourse_soft` (Verteilung statt Label) · stabiler `summary_ref` (FK statt Titel-Präfix-Join, behebt
     die fehleranfällige `title[:50]`-Zuordnung).
2. **Lexikon (Strat 09) + Projekt-Anker (Strat 06/07) als eigene kleine Tabellen** in `own_refs.db`, mit
   FK auf publications — keine neue DB.
3. **Provenienz + Version pro Record (R4):** `source` (zotero/folder/oa), `schema_version`,
   `last_built_at` — additiv, idempotent, multi-source, re-runnable (`mojo refs build`).
4. **Ein Reader-Interface** (`own_refs/index.py` existiert bereits) als einzige Bezugsquelle für die
   Filtermodelle (Phase 2) — statt 6 ad-hoc-Joins. Das ist die einzige echte Integrations-Arbeit.
5. **Validierungs-Tests:** Idempotenz (2× build = identisch), Join-Korrektheit (summary_ref vs Titel-Match),
   keine verwaisten FKs.

## Erwarteter Effekt & Messbarkeit (R2)
Ein konsistenter, versionierter Zugriff auf alle Achsen ohne neue Infrastruktur — die Filtermodelle (Phase
2) lesen aus einer Quelle statt aus 6. Messbar: Join-Fehlerrate (Titel-Präfix vs FK), Idempotenz-Test grün.
**Aber ehrlich:** der Index ist Hygiene, kein Erdungs-Gewinn — der Gewinn kommt aus Strat 01/02/04 (mehr/
besseres Material). Index zuletzt, nachdem das Material steht — sonst indexiert man Lücken.

## → Benjamin-Aufgabe?
Nein — Schema-Erweiterung + Reader, selbst erledigbar.

## → Phasen-Abschluss
Alle 10 Strategien entworfen + adversarial v1→v2 iteriert. Konsolidierung + priorisierte Reihenfolge +
gesammelte Benjamin-Aufgaben im Ledger (00_PLAN.md §D) und im Phasen-1-Abschluss.
