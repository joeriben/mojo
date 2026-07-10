# A/B-Test Phase-2-Agent-Lektüre: z-ai/glm-5.2 vs. google/gemini-3.5-flash

**Datum:** 2026-07-10
**Skript:** `scripts/_glm52_vs_gemini_agent_ab.py` (fixe Artikel-ID-Liste im Skript)
**Rohdaten:** `scripts/out/glm52_vs_gemini_ab_2026-07-10.json` (40 Records, beide Arme)
**Auftrag:** A/B nur auf der Agent-Stufe (Verdikt-Empfehlung); das Batch-Screening (MODEL_SCREEN = deepseek/deepseek-v3.2) blieb unangetastet und wurde nicht aufgerufen.

_n=20 pro Arm — orientierend, keine Statistik. user_verdicts sind selektiv gewachsen
(geurteilt wurde historisch nur, was Screening/Agent überhaupt vorgelegt haben)._

---

## Zusammenfassung

1. **Tool-Use-Kompatibilität: GLM-5.2 besteht.** Der historische Befund „GLM scheitert am Tool-Protokoll" (DEVLOG, GLM 5.1: 7× read_publication, aber nie ein verwertbarer submit) reproduziert sich mit GLM-5.2 **nicht**: 20/20 Läufe liefen bis zum finalen `submit_digest_entry` durch, 0 Exceptions, 0 leere Antworten, 0 Verifikations-Fallbacks [gerechnet]. **Aber:** In 3/20 Artikeln (= 3 der 7 Artikel mit befüllten `bezuege`) emittierte GLM das `bezuege`-Feld als JSON-**String** statt als Array, und dieser String ist wegen unescapeter deutscher Anführungszeichen (`„…"` mit ASCII-`"` als Schlusszeichen) **nicht reparabel parsebar** — die Bezugs-Texte sind als Fließtext lesbar, aber strukturell verloren. Das aktuelle UI-Rendering (`render_markdown`) würde an diesen Einträgen brechen. Gemini: 0/20 Formatfehler [gerechnet].
2. **LES-Recall gleichauf, Ausreißer-Verhalten unterschiedlich.** Auf den 6 echten user-lesenswert-Artikeln treffen beide 4/6 als keep [gerechnet] — beide verfehlen dieselben zwei (GenAI-Systematic-Review/BJET, Social-Scoring/BDS → je „scannen"). GLM irrt systematisch nach oben (4 von 7 user-ignorieren → „scannen", 0 false-keeps), Gemini nach beiden Seiten (5/7 ignorieren exakt, aber 1 false-keep „lesenswert" auf user-ignorieren) [gerechnet]. Recall-orientiert ist GLMs Fehlerrichtung die verträglichere [Einschätzung].
3. **Ökonomie: GLM ~40 % billiger, aber ~3× langsamer.** Ø $0.0402 vs. $0.0667 pro Artikel; Latenz Ø 33.8 s vs. 11.5 s [gerechnet]. Der GLM-Kostenvorteil kommt wesentlich aus dem Cache (85–89 % Cache-Hit-Rate via OpenRouter, Gemini in diesem Fenster nur 0–15 %) — und das trotz mehr als doppelt so vieler Phase-2-Verifikationen (7 vs. 3) [gerechnet].
4. **Konfabulations-Check negativ (gut):** In beiden Armen wurde **jede** in `bezuege` zitierte pub_id vorher tatsächlich per `read_publication` gelesen (GLM 8/8, Gemini 4/4 strukturell auswertbare Bezüge) [gerechnet].

**Gesamtkosten des Tests: $2.14** (llm_calls-Ledger, Fenster ab 20:00 UTC; inkl. Smoke-Calls < $0.001) [gerechnet] — Budget-Deckel $5 eingehalten, Abbruchschwellen nie ausgelöst.

---

## Testdesign

- **Modus:** Beide Arme im produktiven Routing der Agent-Stufe: `assess_then_verify`-Pipeline (Phase 1 Assessment ohne Tools, 1 Iteration; Phase 2 Verifikation mit `read_publication` nur bei `candidate_reads`). Das ist der Pfad, über den `batch_digest.run_batch_digest()` heute **alle** A-/B-Tier-Artikel schickt (`digest.process_article(mode="assess_verify")`); die alte Unterscheidung „B-Tier ohne Tools" existiert im produktiven Wochenlauf nicht mehr.
- **Einziger Unterschied zwischen den Armen:** der `model`-Parameter. Prompts (ASSESSMENT_OUTRO, Verifikations-Kontext), Tools, max_iterations-Logik, Enrichment identisch. profile.json und settings.py unverändert.
- **Kein B-Tier-no-tools-Zusatzlauf:** Der Auftrag sah ihn nur für den Fall vor, dass GLM-Tool-Use bricht. Er brach nicht (0/20 Abbrüche) — der Zusatzarm wurde daher nicht gefahren (Budget-Disziplin).
- **Reihenfolge:** je Modell erst 3 Artikel mit Kosten-Checkpoint (GLM Ø $0.081, Gemini Ø $0.059 — beide unter der $0.15-Schwelle), dann der Rest.
- **Modell-ID verifiziert:** 1-Token-Smoke via `llm_client.build_client()` — `z-ai/glm-5.2` existiert und antwortet über OpenRouter ($0.00005; Hinweis: GLM ist Reasoning-Klasse, die 5 Tokens gingen in `reasoning_tokens`). Keine Ausweich-Varianten nötig.

### Stichprobe (20 Artikel, 12 Journals, fest im Skript)

| # | article_id (kurz) | Journal | user_verdict | Abstract |
|---|---|---|---|---|
| 1 | eaab8fbec1 | BJET | lesenswert | ok |
| 2 | de4ac5cbc1 | AIandSoc | lesenswert | ok |
| 3 | 283be25245 | MedienPaed | lesenswert | ok |
| 4 | 59b41fadc6 | ZfE | lesenswert | ok |
| 5 | e8a2c291f8 | BDS | lesenswert | ok |
| 6 | 910d8402db | CompCult | lesenswert | ok |
| 7 | 5600ea9e78 | MedienPaed | pflichtlektuere | ok — **Sonderfall, s. u.** |
| 8 | af6f9705f1 | AIandSoc | scannen | ok |
| 9 | 721e8ae04e | BDS | scannen | ok |
| 10 | a61faadb88 | REPCS | scannen | ok |
| 11 | 598d79c944 | EthicsEd | scannen | ok |
| 12 | ac3bc611f5 | JRTE | scannen | ok |
| 13 | 74f223f51f | MedienPaed | scannen | **abstract-arm (0 Zeichen)** |
| 14 | b756f0c8e6 | AIandSoc | ignorieren | ok |
| 15 | b56e34a4cf | BJET | ignorieren | ok |
| 16 | 9c28670eeb | Discourse | ignorieren | ok |
| 17 | 10e1538360 | EERJ | ignorieren | ok |
| 18 | 285f36c132 | PDSE | ignorieren | ok |
| 19 | 45972f0bbd | ZfE | ignorieren | ok |
| 20 | 167708764b | AIandSoc | ignorieren | **abstract-arm (0 Zeichen)** |

Volle IDs in `SAMPLE` im Skript. `pflichtlektuere` existiert genau 1× in der ganzen DB (805 user_verdicts) und wurde deshalb mit aufgenommen; er entpuppte sich als **Eigenpublikation des Forschers** (beide Modelle erkannten korrekt pub H2C4LUW8) — im Produktionslauf würde `match_own_publication` diesen Artikel **vor** der Agent-Stufe abfangen. Die Zeile misst also einen degenerierten Fall (s. Qualitativ).

---

## Ergebnistabelle (beide Arme, tools-Modus = produktives Routing)

| Metrik | **glm-5.2** | **gemini-3.5-flash** |
|---|---|---|
| Läufe mit finalem Digest-Eintrag | 20/20 | 20/20 |
| Exceptions / leere Antworten / Retries | 0 / 0 / 0 | 0 / 0 / 0 |
| Format-Defekte im Tool-Output | **3/20** (bezuege als String, inner-JSON irreparabel) | 0/20 |
| Exakt (4 Klassen) vs. user_verdict | 11/20 (55 %) | 12/20 (60 %) |
| Binär keep(les+pflicht)/rest | 15/20 (75 %) | 14/20 (70 %) |
| LES-Recall echte lesenswert (n=6) | 4/6 | 4/6 |
| LES-Recall inkl. Own-Pub-Sonderfall (n=7) | 5/7 | 4/7 |
| False-Keeps auf user-ignorieren (n=7) | 0 | 1 |
| Exakt auf user-ignorieren | 3/7 (4× „scannen") | 5/7 |
| Phase-2-Verifikation ausgelöst | 7/20 | 3/20 |
| read_publication-Calls gesamt | 19 | 4 |
| Ø Agent-Iterationen | 1.9 | 1.4 |
| Kosten Σ / Ø / median pro Artikel | $0.805 / **$0.040** / $0.020 | $1.334 / $0.067 / $0.054 |
| Latenz Ø / median | 33.8 s / 23.2 s | **11.5 s / 10.0 s** |
| Tokens Ø in / out / cached-read | 69 235 / 2 682 / 60 077 | 40 968 / 1 266 / 4 568 |
| Cache-Hit-Rate (assess / verify, llm_calls) | 89 % / 84 % | 15 % / 0 % |

Alle Zahlen [gerechnet] aus `scripts/out/glm52_vs_gemini_ab_2026-07-10.json` bzw. `llm_calls` (articles.db). Kosten-Kreuzcheck Shard-Summen vs. Ledger: identisch auf 4 Nachkommastellen ($0.8049/$1.3336).

Externe Plausibilisierung: der produktive Gemini-Bestand (605 Artikel, assess+verify in llm_calls) liegt bei Ø $0.0611/Artikel — nahe an den hier gemessenen $0.0667 [gerechnet].

### Verdikt-Matrix pro Artikel

| # | user | glm-5.2 | gemini-3.5-flash |
|---|---|---|---|
| 1 | lesenswert | scannen | scannen |
| 2 | lesenswert | lesenswert | lesenswert |
| 3 | lesenswert | lesenswert | lesenswert |
| 4 | lesenswert | lesenswert | lesenswert |
| 5 | lesenswert | scannen | scannen |
| 6 | lesenswert | lesenswert | lesenswert |
| 7 | pflichtlektuere (Own-Pub) | **pflichtlektuere** | **ignorieren** |
| 8 | scannen | scannen | ignorieren |
| 9 | scannen | lesenswert | lesenswert |
| 10 | scannen | lesenswert | lesenswert |
| 11 | scannen | lesenswert | scannen |
| 12 | scannen | scannen | scannen |
| 13 | scannen (abstract-arm) | scannen | scannen |
| 14 | ignorieren | scannen | **lesenswert** |
| 15 | ignorieren | ignorieren | ignorieren |
| 16 | ignorieren | scannen | ignorieren |
| 17 | ignorieren | ignorieren | ignorieren |
| 18 | ignorieren | scannen | scannen |
| 19 | ignorieren | ignorieren | ignorieren |
| 20 | ignorieren (abstract-arm) | scannen | ignorieren |

Auf den 2 abstract-armen Fällen: beide treffen #13 (scannen); #20 trifft Gemini exakt (ignorieren), GLM hält ihn recall-schützend auf „scannen" mit expliziter Kein-Abstract-Begründung [gerechnet].

---

## Protokoll-Robustheit im Detail

**Historischer Kontext:** DEVLOG-Benchmark (Full-Agent, gleicher Prompt-Stack): „GLM 5.1 | (kein Output) | 7× read_pub | $0.150 | 53s | Scheitert am Tool-Protokoll". Der Modus damals: Endlos-Lesen ohne verwertbaren submit.

**GLM-5.2 heute:** Kein einziger Lauf ohne submit. Der Agent-Loop (OpenAI-kompatible tool_calls via OpenRouter) funktionierte durchgängig, inklusive Mehrfach-Iterationen mit Tool-Results als Kontext. **Verbleibender Defekt:** In 3 von 7 Fällen mit befüllten Bezügen kam `"bezuege"` als String:

```
"bezuege": "[{\"pub_id\": \"XTJR5DRD\", ... Jörissen diskutiert hier, wie „digital designs" die Bedingungen ..."
```

Doppelter Schaden: (a) String statt Array (der vorhandene Double-Encode-Guard in `agent.py` greift nur für das **gesamte** args-Objekt, nicht pro Feld); (b) im String stehen deutsche Anführungszeichen, deren schließendes Zeichen als ASCII-`"` emittiert wurde — `json.loads` scheitert daher auch bei nachträglicher Reparatur (getestet: alle 3 irreparabel ohne Quote-Heuristik) [gerechnet]. Betroffen: Artikel #3, #4, #9 — alle drei GLM-Phase-2-Läufe mit deutschsprachigen Bezugs-Texten und Zitaten. Verdict/Kernthese/Begründung blieben in allen 3 Fällen intakt und auswertbar.

**Konsequenz für einen etwaigen Umstieg** [Einschätzung]: GLM-5.2 wäre erst produktionsreif mit einem per-Feld-Repair (String-bezuege → Parse-Versuch → bei Scheitern als Fließtext-Fallback rendern statt crashen) — oder man akzeptiert ~15 % Artikel mit unstrukturiertem Bezugs-Block. Das ist ein lösbarer Harness-Fix, kein Protokoll-K.o. wie bei 5.1.

**Gemini-3.5-flash:** 0 Format-Defekte, 0 Exceptions. Ein Lauf (#9) brauchte 4 Iterationen in der Verifikation (mehrfache reads), blieb aber sauber.

---

## Qualitative Stichprobe (Konfabulations-Prüfung)

Objektiver Check zuerst: **kein** Bezug in beiden Armen zitiert eine pub_id, die nicht vorher per `read_publication` geladen wurde (GLM 8/8, Gemini 4/4 strukturierte Bezüge) [gerechnet]. Die Prompt-Regel „NEVER cite from the summaries" wurde auf der bezuege-Ebene eingehalten. Stichproben der Begründungen:

1. **#7 Own-Pub (‹Schule – Nicht-Schule – Nicht-Nicht-Schule›):** Beide erkennen die Eigenpublikation korrekt (H2C4LUW8, keine Konfabulation). GLM: „pflichtlektuere … zentral für MetaKuBi/ComeArts"; Gemini: „ignorieren … Lektüreempfehlung obsolet". Beide Lesarten sind vertretbar; die Zeile misst Policy-Divergenz bei Eigenpublikationen, nicht Urteilskraft [Einschätzung]. (Produktion filtert diesen Fall vor dem Agenten.)
2. **#14 Human Firewall (user=ignorieren):** Gemini eskaliert auf „lesenswert" mit Projekt-Bezügen (cultural_resilience, ai4artsed) — die Anknüpfung ist thematisch konstruiert, aber datengedeckt formuliert (kontrastierendes Resilienz-Modell, keine erfundenen Werk-Zitate). GLM bleibt bei „scannen" und benennt den Kontrast präziser als Diskurs-Beobachtung („Resilienz defensiv-operational, nicht als relationaler Bildungsprozess"). GLMs Zurückhaltung liegt näher am User-Urteil [Einschätzung].
3. **#1 GenAI-Systematic-Review (user=lesenswert, beide→scannen):** Beide begründen fast wortgleich: empirisch-kartierendes HCI/AIED-Review ohne ästhetisch-kulturelle Dimension. Der User-Grund für „lesenswert" (mutmaßlich Überblicks-Nutzwert) liegt außerhalb dessen, was der Prompt als Anregungspotenzial operationalisiert — ein Kalibrierungs-, kein Modell-Problem [Einschätzung].
4. **#2 Decolonial AI ethics (beide→lesenswert):** GLM belegt beide `erweitert`-Bezüge (L224MAYL Prompt Interception, 3W9X5QLZ Cultural Resilience) nach echten Volltext-Reads mit spezifischen, im gelesenen Text verankerten Formulierungen — kein Anzeichen für ungedeckte Werk-Behauptungen.
5. **#20 „Spot on" (abstract-arm, user=ignorieren):** GLM sagt explizit „ohne Abstract ist keine inhaltliche Einschätzung möglich → scannen zur Diskursübersicht" (ehrliche Unsicherheits-Markierung, aber Über-Behalten); Gemini zieht daraus „ignorieren" (exakter Treffer, aggressiver bei Datenarmut).

Konfabulations-Anfälligkeit: In den gelesenen Begründungen behauptet keines der Modelle Werk-Bezüge, die nicht durch mitgegebene Daten (Summaries-Index, Volltext-Reads, Citation-Hits) gedeckt wären. GLMs Bemerkenswert-Einträge referenzieren Werk-Konzepte aus dem Summary-Index (z. B. „Wahrnehmungskrisen", Jörissen/Klepacki/Flasche) — das ist durch die bemerkenswert-Regel des Prompts gedeckt (kein Volltext-Zwang) [Einschätzung].

---

## Abweichungen vom Auftrag

1. **Kein B-Tier-no-tools-Zusatzarm:** war konditional („wenn Tool-Use bei GLM bricht") — Bedingung nicht eingetreten.
2. **`llm_log.db`:** Der Auftrag nennt die Datei `llm_log.db`; MoJos Kosten-Ledger ist tatsächlich die Tabelle `llm_calls` **in articles.db** (`journal_bot/llm_log.py: LLM_LOG_DB = PROJECT_ROOT / "articles.db"`; die Datei `llm_log.db` im Repo-Root ist ein leeres Relikt). Geloggt wurde ordnungsgemäß über `record_llm_call` (Choke-Point, nicht umgangen) — d. h. es gab Schreibzugriffe auf articles.db, aber ausschließlich auf die `llm_calls`-Tabelle, nie auf `articles` (Lesezugriffe im Skript laufen über eine `mode=ro`-Connection; `store.update_agent_result` wird nirgends aufgerufen).
3. **`assess_then_verify` repliziert statt importiert:** identische Funktionsaufrufe mit identischen Argumenten (`run_agent` Phase 1/Phase 2 wie im Original), aber mit eigener try/except-Grenze zwischen den Phasen, damit ein Phase-2-Absturz das Phase-1-Ergebnis nicht verschluckt. An dem, was die Modelle sehen, ändert das nichts.
4. **Stichprobe 6+1+6+7 statt „~6/6/6–9":** die zusätzliche Zeile ist der einzige `pflichtlektuere`-Fall der DB; er erwies sich als Own-Pub-Sonderfall und wird in den Metriken getrennt ausgewiesen.
5. **Kein separater Latenz-Messpunkt pro LLM-Call:** Latenz wurde pro Artikel (Wall-Clock über alle Iterationen) gemessen, nicht pro Call — für den Vergleich der Arme ausreichend [Einschätzung].

## Einordnung

n=20 pro Arm, ein Testtag, ein Prompt-Stand. Die user_verdicts sind über Monate selektiv gewachsen und die exakten Agreement-Werte (55 %/60 %) sind deshalb keine Qualitätsmessung der Modelle gegen eine neutrale Wahrheit, sondern gegen ein historisch mitgeprägtes Urteilskorpus. Belastbar sind vor allem die Protokoll-Befunde (0 Abbrüche; 3/20 Format-Defekte bei GLM), die Kosten-/Latenz-Relationen und die Fehler-Richtungen (GLM über-behält, Gemini schneidet schärfer und produzierte den einzigen false-keep). Für eine Umstiegs-Entscheidung wäre ein Repair-Layer für GLMs bezuege-Strings Voraussetzung; danach spräche ökonomisch wenig gegen, latenzseitig einiges gegen GLM im interaktiven Betrieb — im nächtlichen Batch-Lauf ist Latenz nachrangig [Einschätzung].
