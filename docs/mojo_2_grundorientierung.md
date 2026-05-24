# MOJO 2.0 — Grundorientierung

**Stand**: 2026-05-24 — bestätigt von Benjamin nach Iter 11.
**Zweck**: Dauerhaftes Orientierungsdokument. Jeder Coding-Assistent, der an
MOJO 2.0 arbeitet, liest dieses Dokument vor `HANDOVER.md` und prüft eigene
Entwürfe gegen die hier festgehaltenen Konturen. Drifts (siehe §6) sind
historisch wiederholt aufgetreten.

---

## §1 Was MOJO 1.x ist (Plattform, in Produktion)

MOJO ist ein persönlicher Forschungsassistent, kein generisches Triage-Tool.
Aufgabe: aus ~49 wissenschaftlichen Zeitschriften (RSS / OJS / OpenAlex / HTML)
wöchentlich ~300 neue Artikel ziehen, gegen den publizierten Eigenkorpus des
Researchers (heute 160+ Pubs in Zotero-Collection `QM7TZT44`) bewerten, und
in Digest-Einträge und diskursraum-weise Trend-Analysen rendern.

Stabile produktive Bausteine:

- `mojo fetch` — RSS/OJS/OpenAlex/HTML-Fetcher mit Crossref/OpenAlex-Enrichment,
  schreibt nach `articles.db` (Stand 17.601 Artikel).
- `mojo digest` — zweistufige Triage: DeepSeek-Screening in 25er-Batches mit
  cache-disziplinierter Hard-Abort-Regel (nur cache-kritische Modelle, nicht
  DeepSeek), Opus-Assessment mit ~98 % Cache-Hit zu ~$0.049/Artikel. Trigger-
  Autoren (MacGilchrist, Jarke, Chun) eskalieren tier-unabhängig zu Opus.
- `mojo trends` — diskursraum-weise (7 Räume in `diskursraeume.json`), seit
  Q-Check auf MiMo statt Opus (~9× günstiger, qualitäts-neutral).
- `mojo scout` — Multi-Linsen-Positionalitäts-Report (Spannungen als
  Forschungsinstrument), Volllauf 2026-05 von Benjamin als „hervorragend"
  validiert.
- Citation-Tracker gegen `authored_all` (alle 160 Pubs, Vornamen-Initial-
  Disambiguation, nicht nur Nachname).
- A/B/C-Tier-Logik je Journal, weil Opus-für-alle zu teuer wäre.

Datenebenen, die zusammenspielen:

- `articles.db` — was gefunden wurde
- `corpus.json` — Volltexte ab `SINCE_YEAR` (74 Pubs ab 2018) + `authored_all`
  (160 Stubs)
- `summaries.json` — 53 Opus-Kondensate, ~28k Tokens, als Such-Index im
  Agent-Toolkit (`read_publication`)
- `projects.json` — 5 aktive Forschungsprojekte als eigene Ebene
- `diskursraeume.json` — Cluster-Mapping mit Journal-Zuordnung

Werk-explizierende LLM-Runs (Opus-Agent + Tool-Use über die eigenen
Volltexte) sind der Kern dessen, was MOJO 1.x von einem generischen Triage-
System unterscheidet — sie lesen Werkbezüge live aus dem Eigenkorpus heraus,
statt nur Abstracts zu paraphrasieren.

---

## §2 Wo der algorithmische Backtest steht (Iter 1–11)

Die 11-stufige Evaluationspipeline in `scripts/` (kein Produktionscode) testet
Algorithmen gegen ein 461er Gold-Set aus `articles.db`. Befund:

- M9_Cascade_TunedBase plateauft seit Iter 7 bei **0.600–0.607 F1**.
- Iter 10 (Trigger-Coupling über 374 Trigger-Works → 9.836 Refs → 620 coupled
  IDs, also 2nd-Degree-Netz) bestätigt das Plateau: 0.600 F1.
- Iter 11 (zweiseitiges Coupling über 109 Eigen-PDFs → 275 OpenAlex-IDs aus
  Eigenwerk-Refs) bestätigt es zum vierten Mal: 0.586 F1 als LogReg-Feature.

Die strukturelle Diagnose, die MOJO 2.0 motiviert:

- Das **Eigenwerk-Coupling-Signal ist da** — per Klasse 12× LES/IGN-Ratio —
  verpufft aber in der LogReg-Aggregation. Als **Veto-Up-Regel**
  (`f_own_coupling_union ≥ 1` → LES) bringt es dagegen +5,2 pp LES-Recall.
- **Opus ist kein verlässlicher Goldstandard**: 35 wrong-LES, bei denen
  Algorithmus *und* Opus beide falschliegen.
- Das **461er Gold-Set hat Selection-Bias**: 65 % der LES aus intentional-
  positiven Quellen (Citation/Trigger/Complementarity), nur 17 % aus Blind-
  Screening. Der Complementarity-Pool (41 % des Sets, 16 % LES) ist die
  Triage-Falle, in der weder Algo (58 %) noch Opus (62 %) zuverlässig sind.

Konsequenz: weiteres LogReg-Tuning ist Selbstbeschäftigung. Der Hebel liegt
in besseren/wachsenden Refs-Daten und algorithmischen Set-Operationen darauf.

---

## §3 Was MOJO 2.0 ist — und was nicht

**Nicht**: „MOJO 1.x plus Volltext-LLM". Frühere Sketches sind in diese Richtung
gedriftet (`mojo_2_volltext_sketch.md` in der Erstfassung). Das ist explizit
korrigiert.

**Sondern**: die bestehende algorithmische Cascade plus drei zusammenhängende
Verschärfungen.

### §3.1 Wachsende, multi-source Refs-Datenbasis

Statt 109-PDF-Snapshot. Quellen sind Zotero-Collections *und* freie Ordner
(FAUbox, Archiv) gleichberechtigt, additiv-idempotent re-importierbar. „Bessere
Triage" heißt: mehr/sauberere Refs → schärfere Set-Operationen. Konkrete
Implementierung: `journal_bot/own_refs.py` (siehe HANDOVER §1).

### §3.2 Adversariale Heuristiken als Set-Operationen

Z. B. `cand.refs ∩ (trigger_refs \ benjamin_refs)` als Veto-Up-/Veto-Down-Regel
direkt in der Cascade. **Nicht** als LLM-Anker-Prompt. Korrigiert am
2026-05-24 in `project_adversarial_blindspot_heuristics.md`.

### §3.3 Volltext-LLM als Eskalations-Slot für ≤ 10 % Restmenge

Nachdem Cascade + Coupling-Veto + adversariale Vetos eine Hard-Case-Schicht
isoliert haben. **Nicht** als Default für alle Items. Refs-Extraktion bleibt
auch in dieser Eskalation algorithmisch: pdftotext + Header-Regex + DOI-Pattern
+ Citation-Splitting + Free-Text-Resolution gegen OpenAlex. LLM liest keine
Volltexte für Refs.

---

## §4 MOJO-1.x-Erhalt und Kombinations-Vorbehalt (zentrale Festlegung)

**Code-seitiger Erhalt** (verbindlich):

- Sämtliche LLM-Runs aus MOJO 1.x, die Kernthesen erschließen und Werkbezüge
  explizieren — Opus-Agent mit Tool-Use über `corpus.json`, Diskursraum-Trends,
  Multi-Linsen-Scout — bleiben **code-seitig vollständig erhalten und
  API-kompatibel**.
- Funktionen dürfen *schlafen* (nicht aufgerufen werden), wenn die
  algorithmische Cascade einen Lauf abdeckt. Sie dürfen **nicht** entfernt,
  umbenannt, signaturell verändert oder durch Wrapper „algorithmifiziert"
  werden.
- 2.0-Module sind **additiv**, nicht ersetzend. Neue Cascade-Veto-Regeln,
  neue Refs-Pipelines, neue Set-Features haken sich ein, ohne bestehende
  Aufrufpfade umzustellen.

**Kombinations-Vorbehalt** (offen):

- Benjamin wertet erst aus, wie die rein algorithmischen 2.0-Läufe am Ende
  performen. Erst danach wird entschieden, ob bestehende werk-explizierende
  LLM-Runs in den 2.0-Pfad re-eingehängt werden (Kombinations-Architektur).
- Daher muss 2.0 so gebaut sein, dass solche Re-Einhängungen ohne API-Bruch
  möglich bleiben: 1.x-Aufrufpfade existieren, Datenformate sind weiter lesbar,
  Eingabe/Ausgabe-Konventionen stabil.

**Praktische Konsequenzen für 2.0-Code**:

- `journal_bot/corpus.py` bleibt orthogonal zu `journal_bot/own_refs.py`.
  Keine Migration von `corpus.json` auf `own_refs.db`.
- `journal_bot/agent.py` (Opus-Tool-Use), `journal_bot/digest.py`,
  `journal_bot/trends.py`, `journal_bot/scout.py` werden nicht refaktoriert.
- Neue CLI-Befehle ergänzen, vorhandene unverändert lassen.
- Wenn ein neues Modul ein bestehendes API überschneidet (z. B. ein
  Refs-Lookup, der heute über `corpus.py` liefe): neuer Endpunkt, nicht
  Umleitung des alten.

---

## §5 Wie dieses Dokument zu verwenden ist

1. **Vor jedem MOJO-2.0-Sprint** lesen, eigenes Verständnis (Plattform +
   Stand + 2.0-Konturen + §4) vor der nächsten Aufgabe abprüfen.
2. **HANDOVER.md** liest sich danach — der Handover beschreibt den nächsten
   konkreten Schritt, dieses Dokument den Rahmen.
3. **Wenn die nächste Aufgabe gegen §3 oder §4 verstößt**: STOP. Erst diesen
   Konflikt benennen, dann erst weiter.
4. **Wenn ein Drift aus §6 droht**: STOP, korrigieren, dann weiter.

---

## §6 Anti-Drift in sechs Punkten (Drifts, in die frühere Sessions gelaufen sind)

1. **LLM-Volltext-Vision** verkaufen statt algorithmische Cascade-Verschärfung
   bauen. — Volltext-LLM ist Eskalation für ≤ 10 % Restmenge.
2. **„Adversarialer Anker-Prompt"** statt Set-Operationen `(A \ B) ∩ C` auf
   den persistierten Refs. — Set-Operationen.
3. **OpenAlex-Schema-Recherche neu starten**, obwohl
   `scripts/iter11_resolve_refs_to_openalex.py` Logik + Polite-Pool-Cache
   bereits hat. — Porten, nicht neu denken.
4. **Code in `scripts/`**, weil dort die Backtest-Logik liegt. — `journal_bot/`,
   MOJO wird Open Source.
5. **Single-Source-Variante als „erstmal MVP"**. — Multi-source ist
   konstitutiv.
6. **Heredoc-Pipes** für Analysen oder Tests. — Alles als Scripts/Module,
   sonst nicht reproduzierbar.

Ergänzend für 2.0-spezifische Drifts:

7. **1.x-Funktionen entfernen oder ersetzen**, weil sie scheinbar von neuen
   Modulen abgelöst werden. — Erhalten, kompatibel, schlafen lassen
   (siehe §4).
8. **Optimistische Projektionen** auf Basis von Einzeltests. — Erst Vollläufe
   und Backtest, dann Schlüsse.

---

## §7 Verweise

- `HANDOVER.md` — aktueller §1-Auftrag (`journal_bot/own_refs.py`), Reihenfolge
  der Folgeschritte, Akzeptanzkriterien.
- `docs/mojo_2_volltext_sketch.md` — detaillierte Architektur-Skizze, am
  2026-05-24 durchgängig auf §3 dieses Dokuments korrigiert.
- `docs/context/MEMORY.md` — Index über aufgebauten Arbeitskontext.
- `docs/context/feedback_mojo2_reframe_algorithmic.md` — die drei Reframes,
  Quelle für §3.
- `docs/context/feedback_mojo1_erhalten_kompatibel.md` — die §4-Festlegung
  als Feedback-Memory.
- `docs/context/project_adversarial_blindspot_heuristics.md` — Set-Operationen
  als Cascade-Erweiterung, Quelle für §3.2.
- `docs/context/feedback_iter11_two_sided_coupling.md` /
  `feedback_iter10_bibliometrie_erschoepft.md` /
  `feedback_algorithmic_triage_plateau.md` — Backtest-Befund, Quellen für §2.
- `docs/context/feedback_ground_truth_qualitaet.md` — Selection-Bias-Diagnose,
  Quelle für §2.
- `CLAUDE.md` / `AGENTS.md` — Coding-Assistent-Briefing.
