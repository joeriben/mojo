# MOJO 2.0 — Konzept-Skizze

**Stand**: 24. Mai 2026 — am Ende von Iter 10 des algorithmischen Backtests.

**Adressat**: Benjamin Jörissen. Diese Skizze setzt Benjamins explizite Architektur-
Setzung um:

> "Die ganzen LLM-Auswertungen sind NUR dann hilfreich wenn sie a) Text valide meinen
> Forschungsfeldern zuordnen, und v.a. b) wenn sie VOLLTEXTE analysieren. Nacherzählen
> von Abstracts ist verbranntes Geld."

Plus der ursprüngliche Iter-10-Phase-4-Wunsch: "Schritt 4 wäre zu prüfen wie MoJo
funktionieren würde wenn es nicht LLM-basierte Abstract selber schreibt sondern ein
Coding-LLM verwendet, um ständig mitzulernen und auf User zugeschnittene Heuristiken
anzupassen/zu entwickeln."

---

## 1. Empirische Basis (Iter 1–10)

| Datum | Befund | Konsequenz |
|---|---|---|
| Iter 1–9 | Algorithmische Triage plateauft bei **0.607 F1** (M9_Cascade_TunedBase). Gap zu Opus 4.6: 0.072 F1 / 4.8 pp Agreement. | Bibliometrische Pipeline funktioniert für ~89 % der Opus-Performance. |
| Iter 7→8 | Per-Journal-Threshold mit Shrinkage liefert in-sample +0.013 F1, kollabiert unter Per-Fold-CV auf -0.072 F1. | Kein weiteres Threshold-Tuning bei n=461. |
| Iter 9 | Auch ein-Parameter-Bias-Adjust für AIandSoc instabil schätzbar. | Plateau ist hart. |
| Iter 9 Hard-Case | 30 wrong-LES haben f_citation_hit=0.00, f_coauthor=0.03 — null bibliometrisches Signal. | "Strukturell unerreichbar" über Metadaten allein. |
| Iter 10 | 2nd-Trigger-Coupling-Netz auf OpenAlex (374 Trigger-Works, 9 836 Refs, 620 ≥2-coupled IDs) liefert per-class Mean-Ratios 5–22× LES/IGN — aber **wrong-LES (0.77) ≈ wrong-IGN (0.67)**. | Auch Bibliometrie 2. Ordnung trennt die Hard-Cases nicht. Bibliometrie-Plateau bestätigt. |
| Iter 11 | Zweiseitiges Bibliographic-Coupling über 109 lokale Zotero-PDFs (367 DOIs aus Refs-Sections, 275 OA-Wolke). LES-Hit-Rate 26.9 % vs IGN 2.2 % (12× Ratio). M9_Cascade_TunedBase 0.597→0.586 F1 (−0.011), M9_Cascade_PerJournalBase ±0. **wrong-LES (0.057) ≈ wrong-IGN (0.083)** — identische Plateau-Signatur wie Iter 10. | Aber: **+5.2 pp LES-Recall** als Veto-Up-Regel praktisch wertvoll. |

**Schlussfolgerung**: Die diskriminative Information für die wrong-LES sitzt nicht
mehr in Metadaten (Refs, Authors, Journals, Concepts, Topics, Embeddings über
Abstracts) — selbst nicht im zweiseitigen Coupling über Benjamins eigene
Cited-Sources-Wolke. Sie sitzt im **Text selbst** — in der Begriffsverwendung,
in der Methodik-Diskussion, in der disziplinären Selbstverortung der
Einleitung/Conclusio.

---

## 2. Zwei Architektur-Verschiebungen

### 2.1 Von Abstract-Triage zu Volltext-Validierung

**Heute (MOJO 1.x)**:
```
Article (title + abstract)
  → DeepSeek-Screening (25er-Batch, $0.001/article)
  → Opus-Assessment (Abstract-Lektüre, $0.04–0.10/article)
  → Digest-Entry (Opus erzählt Abstract nach)
```

**MOJO 2.0**:
```
Article-Metadata (OpenAlex/RSS)
  → Algorithmischer Vorfilter (PerJournalBase Cascade, gratis, 0.600 F1)
       ─ p_ignorieren ≥ 0.80 → IGNORIERT (kein LLM-Call)
       ─ Veto-Up-Regeln (alle gleichberechtigt, LES setzen):
            • f_citation_hit_count ≥ 1   (Item zitiert Benjamin direkt)
            • f_trigger_author_match ≥ 1 (MacGilchrist/Jarke/Chun)
            • f_own_coupling_union ≥ 1   (Iter 11: shared cited source mit
              Benjamin's eigener 275er Refs-Wolke; +5.2 pp LES-Recall ohne
              SCAN-Noise — Begründung siehe §1 Iter-11-Zeile)
       ─ Rest → in Volltext-Pipeline
  → Volltext-Retrieval (siehe §3)
       ─ Wenn kein Volltext erreichbar → "unzuordenbar" (Abstract bleibt als Fallback,
         aber wird transparent als Fallback markiert)
  → Volltext-LLM (siehe §4)
       ─ valide disziplinäre Zuordnung gegen Benjamins 5 Verortungen
       ─ inhaltliche Bewertung auf Basis der Volltext-Argumentation
  → Digest-Entry mit nachvollziehbarer Begründung (Stellen-Verweise, nicht
    Paraphrase)
```

**Wichtig zu Iter 11 / `f_own_coupling_union`**: Diese Variable im LogReg-Mix
des Cascade-Stacks zu führen verschlechtert F1 um −0.011 (vor allem
SCAN-Verlust −0.028) — siehe `feedback_iter11_two_sided_coupling.md`. Sie
gehört **als binäre Veto-Up-Regel auf den Cascade-Output**, nicht als
zusätzliches Trainings-Feature. Implementierung minimal:
`if predicted != "lesenswert" and f_own_coupling_union >= 1: predicted = "lesenswert"`.

**Empirische Validierung der Veto-Up-Regel** (gold-set N=460, 3-Klassen-Macro):

| Variante                              | Macro-F1 | LES-Recall | LES-Prec |
|---------------------------------------|----------|------------|----------|
| Cascade_PerJournalBase (raw)          | 0.601    | 65.4 %     | 48.6 %   |
| **Cascade_PerJournalBase + Veto-Up**  | **0.592**| **67.9 %** | 45.3 %   |
| Cascade_TunedBase (raw)               | 0.588    | 60.3 %     | 53.4 %   |
| Cascade_TunedBase + Veto-Up           | 0.577    | 62.8 %     | 48.5 %   |

Veto-Up tauscht ca. 2.4 pp LES-Precision gegen 2.5 pp LES-Recall. Für den
Vorfilter-Use-Case ist Recall der relevante Tradeoff: ein falsch-positives LES
kostet einen Volltext-LLM-Call (~$0.30), ein falsch-negatives LES kostet eine
verpasste Reading-Empfehlung. Recall-Optimierung ist hier *richtig*; der
F1-Verlust ist ein Artefakt der gleichgewichteten Metrik.

**Citation/Trigger-Veto** (`f_citation_hit_count ≥ 1 ∨ f_trigger_author_match ≥ 1`)
produziert auf dem gold-set 0 zusätzliche Flips über `own_coupling≥1` hinaus —
beide Signale sind im Cascade bereits absorbiert. Trotzdem als Veto behalten,
weil sie für *neue* (nicht-gold) Items unabhängige Garantien sind, sobald die
Cascade-Schwellen sich verschieben.

### 2.2 Von monolithischer LLM-Triage zu Coding-LLM-Heuristik-Loop

**Heute**: Jeder Artikel kostet einen oder mehrere LLM-Calls. Heuristiken sind
hardcoded in `signals.py` und werden manuell gepflegt.

**MOJO 2.0**: Ein **Coding-LLM** beobachtet Benjamins Feedback-Stream (LES/SCAN/IGN
auf einzelne Articles) und entwickelt fortlaufend Python-Heuristiken (Features,
Regeln, Schwellen), die in den algorithmischen Vorfilter wandern. Der Anteil der
Articles, die LLM-Triage brauchen, sinkt mit der Zeit.

Beide Verschiebungen greifen ineinander: Volltext-LLM-Calls sind teuer (Größenordnung
$0.10–0.50/article statt $0.01), also muss der Vorfilter immer besser werden, und
zwar **nicht** durch mehr Metadaten-Features (Plateau bewiesen), sondern durch
Heuristiken, die aus Benjamins kuratierender Aufmerksamkeit lernen.

### 2.3 Adversariale / differenzierende Heuristiken (Blind-Spot-Detektion)

**Bisheriger Bias der gesamten Pipeline**: alle Signale messen *Ähnlichkeit* zu
Benjamins existierendem Werk (citation_hit, ref_overlap_authored, own_coupling,
concept_overlap, embedding_similarity). Das findet zuverlässig, was zur Fortsetzung
des bisherigen Zitations- und Themenprofils gehört — aber genau deshalb auch nicht,
was *adversarial* relevant ist: Autor*innen/Themen, die in Benjamins Feld
einflussreich sind, die er aber **selbst nicht zitiert**.

**Adversariale Set-Differenzen** (Kandidaten-Features, alle aus existierenden Daten
berechenbar):

| Feature                                      | Konstruktion                                                                                                                                                          | Bedeutung                                                            |
|----------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------|
| `f_adv_author_in_trigger_not_own`            | `len(article.authors ∩ (cited_by_trigger_authors \ cited_by_benjamin))` mit `cited_by_X = Autor*innen, die in X's Bibliografie ≥3× als Ref vorkommen`                | Article schreibt jemand, den deine Trigger-Autor*innen lesen, du nie |
| `f_adv_author_in_a_journal_not_own`          | `len(article.authors ∩ (cited_by_a_journals_in_discourse[d] \ cited_by_benjamin))` pro Diskursraum d                                                                  | Article schreibt jemand, den die A-Journals des Feldes lesen, du nie |
| `f_adv_ref_in_trigger_not_own`               | `len(article.refs ∩ (trigger_cited_refs \ benjamin_cited_refs))`                                                                                                       | Article zitiert Quellen, die deine Trigger zitieren, du nicht        |
| `f_adv_topic_overrep_trigger_underrep_own`   | `Σ_topic_in_article  log(p(topic\|trigger_corpus) / p(topic\|own_corpus))`  mit  `clipped Smoothing`                                                                  | Article hat Themenprofil typisch für Trigger-Korpus, atypisch für dich |
| `f_adv_concept_blind_spot`                   | OpenAlex-Concepts: `concept ∈ top_50_concepts(trigger_corpus_in_discourse) − top_50_concepts(own_corpus_in_discourse)`                                                | Konzept-Cluster, in dem dein Feld arbeitet, ohne dich                |

**Datenbasis ist da**:
- 374 Trigger-Works mit refs (aus Iter 10 Phase 1a).
- 275 OA-Wolke aus Benjamins eigenen 109 PDFs (aus Iter 11).
- Per-Discourse-Top-Authors/Journals als Heuristiken (aus Iter 10 Phase 3).
- OpenAlex-Topics + Concepts pro Article in articles.db.

**Wie diese Features in die Cascade einfließen** (Korrektur 2026-05-24 nach
Benjamins Reframe — adversariale Heuristiken sind **algorithmische Set-Operationen**,
keine LLM-Prompt-Vorbereitung):

```
Article passes Cascade-Vorfilter (kein hard IGN)
  ↓
  Veto-Up- und Veto-Down-Regeln werden direkt auf den Cascade-Output angewandt
  (analog zu f_own_coupling_union ≥ 1 in §2.1):

  Veto-Up auf LES, wenn:
    f_adv_author_in_trigger_not_own ≥ 2  (mehrere Trigger-Autor-Lektüren)
    ∨ f_adv_ref_in_trigger_not_own ≥ 3   (deutliche Referenz-Überlappung mit
                                          Trigger-Bibs, die du nicht zitierst)

  Veto-Down auf IGN, wenn:
    article ist im flachen Vorfilter SCAN und
    ALLE f_adv_* = 0 und ALLE Ähnlichkeits-Signale niedrig
    → kein adversarialer und kein konventioneller Anschluss → IGN
```

→ Die Set-Differenzen sind das **eigentliche algorithmische Werkzeug**, nicht
Vor-Material für einen LLM-Prompt. Volltext-LLM-Calls bleiben die *teure
Ausnahme* (§4) für Items, die nach allen Cascade-Regeln noch unklar sind, nicht
das Default-Ziel der adversarialen Pipeline.

**Implementierungs-Reihenfolge**:
1. **Refs-Pipeline produktiv** machen (lift aus `scripts/iter11_extract_own_refs.py`
   + `iter11_resolve_refs_to_openalex.py` in `journal_bot/refs_pipeline.py`,
   multi-source + idempotent-inkrementell, siehe `HANDOVER.md` §1).
2. **`scripts/build_adversarial_sets.py`** — vorberechnete Mengen
   `cited_by_trigger_authors`, `cited_by_benjamin_per_year` (aus produktivem
   Refs-Index), `cited_by_a_journals_per_discourse[d]`. Wöchentlicher Cache.
3. **`f_adv_*` in `signals.py`** analog zu den Iter-10-Heuristiken.
4. **Validierung auf Gold-Set** (kostengünstig, kein LLM): treffen
   `f_adv_*` ≥ Schwelle die 35 wrong-LES überproportional?
5. **Veto-Up/Veto-Down-Regeln in der Cascade** wenn Validierung positiv.
6. **Optional**: adversariale Trefferanzeige als *Kontext-Mitlauf* im
   Volltext-LLM-Prompt für die Restmenge, die §4 erreicht — aber nicht als
   Trigger der LLM-Eskalation.

**Warum das eine eigene Architektur-Komponente ist (nicht nur ein weiteres
LogReg-Feature)**: Ähnlichkeits-Heuristiken sind im Cascade absorbierbar — das
hat das Plateau bei 0.60 F1 bewiesen. Adversariale Heuristiken sind *strukturell
anders*: sie sollen *nicht* Benjamins bisheriges Zitationsverhalten reproduzieren,
sondern es kontrastieren. Im LogReg-Mix würden sie als Anti-Signal wirken — sie
gehören als **eigenständige Veto-Regeln** auf den Cascade-Output (analog zur
`f_own_coupling_union`-Regel in §2.1).

---

## 3. Volltext-Layer (`fulltext_store`)

**Eingabe**: Article-Metadata (DOI, OpenAlex-ID, URLs).

**Pipeline**:

1. **OA-Detection**:
   - `openalex.work.primary_location.pdf_url` (oft direkt)
   - `openalex.work.oa_location.pdf_url` (oft kuratierter)
   - Unpaywall-API als Fallback (auch bei OpenAlex-Lücken)
2. **PDF-Download**:
   - httpx mit User-Agent + 30s-Timeout
   - Cache in `.fulltext_cache/{openalex_id}.pdf`
   - Größen-Limit: 50 MB
3. **Text-Extraktion**:
   - `pdfplumber` (besser als pypdf für mehrspaltige akademische Layouts)
   - Sektion-Heuristik: Headings via Font-Size-Cluster, Schwellen für Abstract/
     Introduction/Methods/Results/Discussion/References
4. **Volltext-Struktur** (`{openalex_id}.json`):
   ```json
   {
     "openalex_id": "W...",
     "source": "openalex_oa_pdf",     // oder "unpaywall_pdf", "html_scrape", "manual"
     "fetched_at": "2026-05-24T...",
     "char_count": 42137,
     "sections": {
       "abstract": "...",
       "introduction": "...",
       "methods": "...",
       "results": "...",
       "discussion": "...",
       "references_text": "..."
     },
     "extraction_quality": {
       "n_pages": 18,
       "sections_detected": ["abstract", "introduction", "discussion"],
       "missing_sections": ["methods", "results"],
       "ocr_used": false
     }
   }
   ```
5. **Fallback-Strategie**:
   - Wenn OA-PDF nicht erreichbar: HTML-Scrape der Landing-Page (für Open-HTML-
     Journals wie e-flux, zkmb.de, viele OJS-Installationen)
   - Wenn auch das scheitert: Abstract-only mit Flag `extraction_quality.fallback=true`
6. **Paywall-Behandlung**:
   - Markieren als `requires_manual_fetch` — eigene UI-Liste, in der Benjamin
     Articles per Klick zur Bibliotheks-Anfrage / SciHub-/Buch-Anschaffung schicken
     kann.
7. **Caching-Disziplin**:
   - PDFs gehören NICHT ins Git (gross), separates Verzeichnis ausserhalb des Repos
     oder `.gitignore`.
   - Geistige Eigentum: Verwendung nur für Benjamins persönliche Forschungs-Triage.
     Keine Weiterverbreitung, kein Upload zu Drittsystemen, Speicherung lokal.

**Erwarteter OA-Hit-Rate**:
- Bildungs-/Medien-Pädagogik-Journals: ~50–70 % OA (viele Diamond-OA-Journals,
  hoher Anteil deutscher Open-Access-Tradition)
- AI/Medien-Studien englischsprachig (AI & Society, Convergence, Big Data &
  Society): ~70–80 % (Funding-Mandate)
- Theorie/Bildungstheorie: niedrig (~30–50 %, viele paywalled Springer/Routledge)
- Insgesamt: ~50–60 % erwartbare OA-Coverage, der Rest braucht Bibliothek/manuell.

---

## 4. Volltext-LLM-Schicht (Eskalation, nicht Default)

**Kritische Korrektur 2026-05-24 (Benjamin-Reframe)**: Dieser Abschnitt
beschrieb Volltext-LLM ursprünglich als Default-Triage für „die ~10–20 %, die
der Vorfilter durchlässt". Das ist falsch. Volltext-LLM bleibt **Eskalation
für die Restmenge nach allen Cascade-Regeln** (Vorfilter + own_coupling-Veto
+ adversarial Veto + andere algorithmische Filter), höchstens 5–10 % der
Items. Die unten beschriebenen Prompts und Output-Schemas gelten für genau
diese Eskalations-Restmenge. Wer mehr als 10 % der Items hier hinroutet, hat
die Architektur missverstanden (siehe HANDOVER.md §5).

**Prinzip für die Eskalations-Calls**: Nicht "Zusammenfassung schreiben",
sondern **strukturierte Validierung mit Stellen-Verweisen**.

### 4.1 Disziplinäre Zuordnung (Benjamins Forderung (a))

**Frage an das LLM**:
> "Lies den vollen Text. Welche Theorie-Tradition(en) verwendet der Artikel
> operativ (= als analytisches Werkzeug, nicht als zitierten Hintergrund)? Welche
> Begriffe werden definiert/verwendet vs. nur beiläufig genannt? Wo verortet sich
> der Artikel im Methodik-/Diskussions-Teil selbst disziplinär?"

**Mapping**: Antwort wird gegen Benjamins 5 Verortungen geprüft:
1. Allgemeine Pädagogik / Bildungstheorie
2. Posthumanismus / STS / Resilienz
3. Medienbildung / Medienpädagogik
4. Pädagogische Medienforschung / Medienwissenschaft
5. Kulturwissenschaft / Ästhetik

**Output-Schema**:
```json
{
  "disciplinary_placement": {
    "primary": "medienpaed",
    "secondary": ["digitale_kultur"],
    "confidence": "high",  // "high" / "medium" / "low" / "unzuordenbar"
    "evidence": [
      {
        "verortung": "medienpaed",
        "anchor_quote": "...Volltext-Zitat (max 200 Zeichen)...",
        "section": "introduction",
        "char_offset": 1834
      }
    ],
    "warning_if_low_confidence": "..."
  }
}
```

**Wenn confidence=low oder unzuordenbar**:
→ Artikel wird auf "nicht-kanonisch" gesetzt. KEIN normales Digest-Entry, sondern
ein Eintrag "Randfund — disziplinär unklar, hier ist der Stellen-Verweis", den
Benjamin manuell entscheidet.

### 4.2 Inhaltliche Bewertung (Benjamins Forderung (b))

**Frage**:
> "Welche konkrete These/Befund/Methodendiskussion ist Anschluss-fähig an Benjamins
> aktuelle Forschungsprojekte (Cultural Resilience, MetaKuBi, AI4ArtsEd, ComeArts,
> DiäS-KuBi)? Belege mit Stellen-Verweis. Wenn nichts anschluss-fähig: sag das
> explizit."

**Output**:
```json
{
  "anschluss": [
    {
      "projekt": "ai4artsed",
      "anchor_quote": "...",
      "section": "discussion",
      "char_offset": 28401,
      "warum": "Argumentiert für eine Materialitäts-zentrierte Reflexion in
                generativen KI-Bildungssettings — direkte Anschlussfähigkeit
                an die AI4ArtsEd-Methodologie der ersten Förderphase."
    }
  ],
  "anschluss_count": 1
}
```

### 4.3 Vorteil gegenüber Abstract-Triage (für die Eskalations-Restmenge)

| Aspekt | Abstract-Triage (heute) | Volltext-Eskalation (MOJO 2.0, nur Restmenge) |
|---|---|---|
| Disziplinäre Trennschärfe | Schwach (thematische Oberfläche dominiert) | Hoch (Methodik-Sektion entscheidet) |
| Anschluss-Begründung | "scheint relevant für…" | Konkrete Stelle + Zitat |
| Kosten/Article | $0.01–0.10 | $0.10–0.50 |
| Skalierbarkeit | Alle Articles | Nur die ≤5–10 %, die nach allen Cascade-Regeln unklar bleiben |
| Kosten/Woche | ~$2–5 (300 Articles × $0.01) | ~$1–3 (10–15 Articles × $0.20) |

**Schlüssel-Erkenntnis**: Die produktive Refs-Pipeline plus die daraus
abgeleiteten Veto-Regeln (own_coupling, adversarial set-features) reduzieren
die Restmenge, die überhaupt Volltext-LLM braucht, auf ≤10 %. Der LLM ist
nicht "die Triage", sondern der Edge-Case-Resolver.

---

## 5. Coding-LLM als Developer-Werkzeug (NICHT als Triage-Komponente)

**Kritische Korrektur 2026-05-24**: Der Coding-LLM-Loop war ursprünglich als
„wöchentlich neue Heuristiken auto-deployen" konzipiert. Das wurde von Benjamin
nicht gefordert und entspricht nicht dem algorithmischen Reframe. Die folgende
Beschreibung gilt nur als **optionales Developer-Hilfsmittel**: ein LLM, das
*Code-Vorschläge* für die Veto-Regeln in `signals.py` macht, die der/die
Entwickler:in dann reviewt und commitet. Es ist KEIN Auto-Deployment-Pfad und
KEINE Triage-Komponente. Wenn dieser Loop nicht gebaut wird, fehlt nichts
Architektonisches.

**Setup (optional)**: Ein separater LLM-Pfad (Claude/GPT/Gemini im Coding-Modus,
MCP-fähig) bekommt periodisch (z. B. wöchentlich nach jedem Digest):

**Input**:
- Benjamins letzte 7 Tage Feedback (LES/SCAN/IGN auf Articles)
- Die Volltext-LLM-Ausgaben (mit Anker-Zitaten) dieser Articles
- Der aktuelle Stand von `signals.py` + `features_gold.parquet`
- Den Coupling-Network-Stand aus Iter 10

**Aufgabe**:
> "Schau die letzten 7 Tage Feedback an. Wo hat MOJO falsch entschieden? Welche
> wiederkehrenden Muster in den Anker-Zitaten findest du? Schlage 1–3 neue
> algorithmische Features oder Heuristiken vor, die du als kommentierte Python-
> Diffs gegen `signals.py`/`features_gold.parquet`-Builder formulierst. Erkläre,
> welches Hard-Case-Cluster du adressierst und wie wir die Heuristik gegen den
> 461-Gold-Backtest validieren."

**Workflow**:

```
Benjamin gibt Feedback (LES auf X, IGN auf Y)
   ↓
Coding-LLM-Run (wöchentlich, $1–3)
   ↓
Vorschlag: "Articles mit X-Begriff in Methods-Sektion + Y-Konzept in
            References → +1 für f_ai4artsed_anschluss"
   ↓
Validierung gegen 461-Gold-Backtest:
   - Wenn Verbesserung ≥ 0.005 F1 stabil über CV → autocommit ins
     Repo mit Provenienz-Kommentar
   - Wenn nicht → wird verworfen, geloggt
   ↓
Benjamin sieht im nächsten Digest weniger/passendere Articles
   ↓
neuer Feedback-Loop
```

**Provenienz-Pflicht**: Jede vom Coding-LLM generierte Heuristik bekommt einen
Kommentar:
```python
# AUTO-GENERATED 2026-05-31 by coding-llm v1.2
# Trigger: 4 wrong-IGN auf Articles mit "kritische Medienpädagogik" im Methods-Teil
# Validation: +0.007 F1 stable on 5-fold CV, n=461
def f_kritische_medienpaed_methods(article):
    ...
```

**Sicherheit**:
- Kein Auto-Deployment ohne CV-Validation
- Heuristiken, die mehr als 7 Tage keinen Beitrag bringen, werden vom Coding-LLM
  selbst zur Löschung vorgeschlagen
- Benjamin kann jede Heuristik im UI an/abschalten
- Tagestransparenz: "Diese Triage-Entscheidung wurde von Heuristiken X, Y, Z
  (autogen. 2026-05-31) und der Volltext-LLM-Bewertung beeinflusst"

---

## 6. Migrations-Pfad (korrigiert 2026-05-24, algorithmisch-zuerst)

| Schritt | Was | Aufwand | Wann |
|---|---|---|---|
| 1 | **Refs-Pipeline produktiv**: `journal_bot/own_refs.py` als multi-source + additiv-inkrementelles Modul (lift aus `iter11_extract_own_refs.py` + `iter11_resolve_refs_to_openalex.py`). Siehe HANDOVER §1. | 2–3 Tage | **als erstes** |
| 2 | **Cascade-Veto-Regel `f_own_coupling_union ≥ 1`** auf produktiven Refs-Index umstellen statt auf Iter-11-Snapshot | 0.5 Tag | nach Schritt 1 |
| 3 | **`scripts/build_adversarial_sets.py`** + `f_adv_*` Features in `signals.py`. Gold-Set-Validierung (35 wrong-LES). | 2 Tage | nach Schritt 2 |
| 4 | **Adversariale Veto-Up/Veto-Down-Regeln** in der Cascade, wenn Validierung positiv | 0.5 Tag | nach Schritt 3 |
| 5 | **Bessere Refs-Extraktion** (pdfplumber-Fallbacks, OCR für gescannte, Non-DOI-Resolution via Autor+Jahr+Titel-Match gegen OpenAlex) | 2–3 Tage | parallel zu 3–4 |
| 6 | **Volltext-Eskalations-Layer minimal**: OpenAlex-OA-PDF-Download + pdfplumber-Extraktion + JSON-Cache (für die Restmenge der Cascade) | 1–2 Tage | nach Schritt 4 |
| 7 | **Volltext-LLM-Eskalation für Restmenge** (≤10 % der Wochen-Articles): disciplinary_placement + anschluss-Felder mit Anker-Zitaten | 1 Tag (Pilot $4–10) | nach Schritt 6 |
| 8 | **Coding-LLM als optionales Developer-Tool** (siehe §5): nur wenn das Refs-Wachstum stabil genug ist, dass Vorschläge sinnvoll sind | 3–5 Tage, optional | dauerhaft optional |
| 9 | **Alte Abstract-Triage als Legacy-Fallback** für Articles ohne Volltext und ohne Refs | parallel | dauerhaft |

**Risiko-Punkte**:
- OA-Coverage könnte unter 40 % liegen → für viele Articles bleibt die
  Eskalation auf Abstract-only. Transparent flaggen, nicht faken.
- pdfplumber-Extraktion versagt bei manchen Verlags-PDFs. OCR-Fallback nur für
  Articles mit hohem Cascade-Score oder citation_hit ≥ 1.
- Refs-Extraktion auf den Benjamin-eigenen PDFs (Schritt 1) versagt bei
  pre-2010er Texten mit 3 % DOI-Rate. Schritt 5 ist deshalb essentiell, nicht
  optional.
- Volltext-LLM kann halluzinieren → **Pflicht zur Anker-Zitat-Sektion +
  Char-Offset**.

---

## 7. Was MOJO 2.0 KEINE LLM-Calls mehr braucht

| Heutiger LLM-Call | MOJO 2.0 |
|---|---|
| Abstract-Screening DeepSeek auf alle ~300 Articles/Woche | gestrichen, ersetzt durch Cascade-Vorfilter + Refs-Veto-Regeln |
| Abstract-Triage Gemini 3.5 Flash auf ~150 A/B-Tier-Items | gestrichen für ≥90 % (durch Cascade + algorithmische Veto-Regeln), Rest geht in Volltext-Eskalation |
| Trend-Analyse Opus über alle Diskursräume | bleibt (anderer Use-Case, läuft monatlich nicht wöchentlich) |
| Trigger-Author-Escalation zu Opus | bleibt, aber für die ≤10 % Restmenge dann auf Volltext-Basis |

**Gewünschter End-Zustand** (Korrektur 2026-05-24): ≥90 % der wöchentlichen
Articles werden **rein algorithmisch** getriaged (Cascade + own_coupling-Veto
+ adversarial Veto + andere Refs-basierte Regeln, alle ohne LLM-Call). ≤10 %
gehen in die Volltext-Eskalation mit LLM. Das Refs-Wachstum (mehr eigene PDFs,
bessere Extraktion, Non-DOI-Resolution) verschiebt den algorithmischen Anteil
über Zeit nach oben, nicht nach unten.

---

## 8. Was diese Skizze NICHT klärt

- **UI** für die Volltext-Triage (Stellen-Verweis-Browser, Anchor-Highlights):
  separates Projekt, siehe `docs/ui_entwurf.md`.
- **Backtest-Methodik** für die Volltext-LLM-Schicht: braucht eigene Gold-Annotation
  (n≥50, Benjamin liest Volltext, vergleicht mit LLM-Output). Erst nach Schritt 3
  sinnvoll.
- **Privacy/IP**: Volltexte sind urheberrechtlich geschützt. Lokales Caching für
  persönliche Forschungsnutzung ist üblicherweise OK, aber für OpenSource-Release
  brauchen wir eine klare Trennung User-Daten vs. Code.

---

## 9. Offene Fragen für Benjamin

1. **OA-First oder OA-only**? Sollen paywalled Articles ohne Volltext-Validation
   im normalen Digest erscheinen (mit Flag) oder in eine separate "ungeprüft"-
   Sektion?
2. **Volltext-LLM-Kosten-Budget**: bei $0.20/Article × 30 Articles/Woche =
   $24/Monat. OK?
3. **Coding-LLM-Cadence**: wöchentlich nach jedem Digest, oder seltener
   (alle 2 Wochen)?
4. **Welche Volltext-Sektionen sind Pflicht** für eine valide Disziplinär-
   Zuordnung? Abstract+Introduction+Methods+Conclusion reicht meist; bei
   Theorie-Texten reicht Introduction+Conclusion; bei empirischen Texten
   braucht es Methods+Results.

---

**TL;DR (korrigiert 2026-05-24)**: MOJO 1.x triagiert Abstracts und stößt bei
0.607 F1 an die strukturelle Grenze der Metadaten-Information. MOJO 2.0 hebt
diese Grenze **algorithmisch** durch eine produktive, wachsende Refs-Pipeline
(`journal_bot/own_refs.py`, multi-source + additiv-inkrementell), aus der
weitere Veto-Up/Veto-Down-Regeln für die Cascade abgeleitet werden
(own_coupling-Erweiterung, adversariale Set-Operationen). LLM-Volltext-Calls
sind die **Ausnahme-Eskalation für ≤10 % Restmenge**, NICHT die Architektur.
Hebel für Verbesserung = mehr/bessere eigene Refs-Daten → schärfere
Set-Operationen → mehr Veto-Regeln. NICHT: mehr LLM-Calls.
