# Adversariale Heuristiken: Blind-Spot-Detektion als 3. MOJO-2.0-Säule

**Datum**: 2026-05-24.

**Trigger (Benjamin nach Iter 11 + Korpus-Diagnose + Ground-Truth-Diagnose)**:
> "es geht nicht nur um das Finden von Ähnlichem. Die verbesserte Ground Truth
> wird genauso hilfreich sein adversariale Heuristiken zu bauen ('Deine
> L1-Autoren / A-Journals zitieren v.a. Autor X mit Thema Y, die Du niemals
> zitierst obwohl im selben Themenfeld …') → hier wird die Kombi adversariale/
> differenzierende Heuristiken → LLM dann auch wirklich interessant, abgesehen
> von der Volltext-Auswertungs-Geschichte."

## Befund

Alle bisherigen MOJO-Signale messen **Ähnlichkeit zu Benjamins existierendem
Werk**:
- citation_hit, ref_overlap_authored, own_coupling (Iter 11)
- topic_overlap, concept_overlap
- embedding_similarity, TF-IDF
- 2nd-Trigger-Coupling (Iter 10)

Diese Pipeline findet zuverlässig, was die bisherige Linie *fortsetzt* — aber
genau deshalb auch nicht, was **adversarial relevant** ist: Autor*innen, Themen,
Konzept-Cluster, die in Benjamins disziplinärem Umfeld (Trigger-Autoren +
A-Journals des Diskursraums) prominent sind, in seinem eigenen Werk aber nicht
auftauchen.

→ Das ist der primäre **Blind-Spot-Detektor-Use-Case**. Und es ist die
Bedingung, unter der Volltext-LLM-Calls über reine Abstract-Paraphrase
hinausgehen — der LLM bekommt nicht „beurteile selbst die Relevanz", sondern
„prüfe diese vorbereitete differenzielle Frage am Volltext".

## Konkrete Feature-Kandidaten (alle aus existierenden Daten berechenbar)

| Feature                                      | Set-Konstruktion                                              |
|----------------------------------------------|---------------------------------------------------------------|
| `f_adv_author_in_trigger_not_own`            | `article.authors ∩ (cited_by_trigger \ cited_by_benjamin)`    |
| `f_adv_author_in_a_journal_not_own`          | `article.authors ∩ (cited_by_a_journals[d] \ cited_by_benjamin)` pro Diskursraum |
| `f_adv_ref_in_trigger_not_own`               | `article.refs ∩ (trigger_cited_refs \ benjamin_cited_refs)`   |
| `f_adv_topic_overrep_trigger_underrep_own`   | log(p(topic\|trigger) / p(topic\|own)) summiert über article-topics |
| `f_adv_concept_blind_spot`                   | top_50_concepts(trigger_corpus[d]) − top_50_concepts(own_corpus[d]) |

## Datenbasis ist bereits da

- **Trigger-Bibliografien**: 374 Trigger-Works mit refs (Iter 10 Phase 1a,
  `backtest_data/trigger_bibs/`).
- **Benjamin-Cited-Sources-Wolke**: 275 OA-Work-IDs aus 109 PDFs (Iter 11,
  `backtest_data/own_bibliography/refs_resolved.json`).
- **Per-Discourse-Heuristiken**: Top-Authors/Journals (Iter 10 Phase 3,
  `signals.py` plus `data/top_authors_per_discourse.json`).
- **OpenAlex-Topics/Concepts** pro Article in `articles.db`.

Was noch fehlt: `cited_by_a_journals_in_discourse[d]` — Liste der häufigsten
Refs in den A-Journals jedes Diskursraums. Einmaliger OpenAlex-Pull plus Cache.

## Integrations-Pfad in der Pipeline (Korrektur 2026-05-24)

**Frühere Version dieser Notiz hatte „→ Volltext-LLM-Pfad mit Anker-Prompt"
als Hauptmechanismus. Das war falsch fokussiert** (Benjamin-Reframe nach
HANDOVER-V2-Review). Adversariale Heuristiken sind **algorithmische
Set-Operationen** und gehören direkt in die Cascade als Veto-Up/Veto-Down —
analog zur `f_own_coupling_union`-Regel aus Iter 11.

```
Article passes Cascade-Vorfilter (kein hard IGN)
  ↓
  Veto-Up auf LES, wenn:
    f_adv_author_in_trigger_not_own ≥ 2
    ∨ f_adv_ref_in_trigger_not_own ≥ 3

  Veto-Down auf IGN, wenn:
    flacher Vorfilter sagt SCAN ∧ alle f_adv_* = 0 ∧ alle Ähnlichkeits-Signale
    niedrig
    → weder adversarialer noch konventioneller Anschluss
```

Volltext-LLM bleibt **gezielte Eskalation** für die Restmenge nach allen
Cascade-Regeln (höchstens 5–10 % der Items), NICHT Default-Ziel der
adversarialen Signale. Adversariale Trefferanzeige kann im Volltext-LLM-Prompt
als Kontext mitlaufen, ist aber nicht der primäre Mechanismus.

## Warum eigene Architektur-Komponente (nicht „nur ein weiteres LogReg-Feature")

- Ähnlichkeits-Heuristiken sind in den Cascade absorbierbar → Plateau bei
  0.60 F1 bewiesen (Iter 1–11).
- Adversariale Heuristiken sind **strukturell anders**: sie sollen Benjamins
  bisheriges Zitationsverhalten **kontrastieren**, nicht reproduzieren.
- Im LogReg-Mix würden sie als Anti-Signal wirken (Trefferquote zu Benjamins
  user_verdict ist a priori gering — der Witz ist ja, dass er sie *nicht*
  zitiert hat).
- → eigene Veto-Regeln auf den Cascade-Output, semantisch parallel zur
  bestehenden `f_own_coupling_union ≥ 1`-Regel. Eigene Spalte, deren Output
  **„Blind-Spot-Verdachtsgrad"** ist, nicht „LES-Wahrscheinlichkeit".

## Verbesserte Ground Truth = stärkere adversariale Signale

Aus `feedback_ground_truth_qualitaet.md`: 72 Items wo Algo+Opus beide falsch.
Davon sind die 35 wrong-LES (User: LES, beide: nicht-LES) genau jene Items, in
denen Benjamins Auge etwas sieht, was die Ähnlichkeits-Heuristiken nicht
finden. Wenn von diesen 35 ein nennenswerter Anteil Treffer auf adversariale
Signale wäre, hätten wir den ersten empirischen Beleg, dass die adversariale
Spalte die wrong-LES-Lücke schließt.

→ Vorgeschlagener Validierungs-Test (kostengünstig, vor Volltext-LLM-Bau):
„Wie viele der 35 wrong-LES hätten ≥1 `f_adv_*` ≥ Schwelle?" Wenn die Zahl
deutlich über 6 % (= Base-Rate der IGN-Klasse) liegt, ist der adversariale
Pfad empirisch belegt.

## Implementierungs-Reihenfolge (für die Phase nach §3-Volltext-Layer)

1. `scripts/build_adversarial_sets.py` — vorberechnete Mengen
   (`cited_by_trigger_authors`, `cited_by_benjamin`,
   `cited_by_a_journals_per_discourse[d]`), wöchentlicher Cache.
2. Neue `f_adv_*` Features in `signals.py` analog zu den Iter-10-Heuristiken.
3. **Vor-Bau-Validierung auf Gold-Set**: prüfen ob `f_adv_*` ≥ Schwelle
   die 35 wrong-LES überproportional trifft (Erwartung: 30–50 %).
4. Veto-Flag-Pfad „adversarial-flagged → Volltext-LLM-Slot in der
   Wochenbatch-Queue" (nicht Veto-Up auf LES).
5. Volltext-LLM-Prompt-Template mit adversarialem Anker im Volltext-LLM-Modul.

## Verankerung

- Konzeptiver Eintrag in `docs/mojo_2_volltext_sketch.md` §2.3.
- Memory `project_adversarial_blindspot_heuristics.md` (diese Datei).
