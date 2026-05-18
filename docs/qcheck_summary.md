# Q-Check MiMo vs Opus — Konsolidierter Befund

**Datum:** 2026-05-16
**Methode:** MiMo neu gefahren gegen vorhandene Opus-Datensätze (articles.db, summaries.json) bzw. recycled Opus-trends aus `cost_test_sarah_v2_mimo_cached.json`. Side-by-Side-Reports siehe `docs/qcheck_{assessment,summarize,trends}.md`.
**Q-Check-Kosten (Dev-Key):** $1.17

## TL;DR — Empfehlung pro Operation

| Operation | n | Konkordanz | Faktor MiMo/Opus | Empfehlung |
|---|---:|---|---:|---|
| Assessment | 50 | **70 %** Verdict-Match, 4/20 `lesenswert` → `scannen` | ~1/2 (mit Cache) | **Opus bleibt** |
| Summarize | 5 | Jaccard keys=0.45, thinkers=0.59, **methods=0.17** | ~1/7 | **Opus bleibt, methods kritisch** |
| Trends | 3 | term-Jaccard 0.20–0.26, vergleichbare Länge, finish=stop | **~1/10** | **MiMo wird Default** |

## Cache-Befund (Aufklärung)

- MiMo-Cache via OpenRouter **funktioniert** mit `tool_choice='auto'` + `cache_control: ephemeral` — Hit-Rate 88–99 % nachweisbar.
- Voraussetzung: Frischer/aktiver API-Key. Der alte mojo-Key war beim Wochenlimit auf eine cache-lose Provider-Route gefallen — daher 0 % im ersten Q-Check-Block.
- TTL ist ~5 Minuten: nach Lücke (Cluster-Wechsel oder Wartezeit) fällt Cache auf 0 zurück. Q-Check #33–50 (nach mehrminütiger Pause) wieder 0 %.
- Bei Trends: 99.6–99.8 % Cache-Hit, weil das System-Prompt-Format zwischen den drei Cluster-Calls identisch geblieben ist und die Lücken klein waren.

## Assessment — Detail

Stichprobe: 50 Artikel, stratifiziert (20 lesenswert + 15 scannen + 15 ignorieren), 19 Journals.

### Konfusionsmatrix (Opus → MiMo)

| Opus ↓ | ignorieren | scannen | lesenswert | Σ |
|---|---:|---:|---:|---:|
| ignorieren | 12 | 3 | 1 | 16 |
| scannen | 2 | 9 | 4 | 15 |
| lesenswert | 0 | 4 | 14 | 18 |

(Die ursprüngliche Stichprobe hatte 20 lesenswert; 2 wurden aus der DB nicht gefunden, ergo 18.)

### Mismatch-Richtungen

- **4× `lesenswert` → `scannen`** (MiMo verfehlt 4 von 18 lesenswert-Artikeln; 22 % False-Skip-Rate)
- 4× `scannen` → `lesenswert` (MiMo eskaliert; weniger schlimm — bedeutet Zusatz-Lektüre)
- 3× `ignorieren` → `scannen` (MiMo großzügiger)
- 2× `scannen` → `ignorieren` (MiMo zu hart)
- 1× `ignorieren` → `lesenswert` (False-Positive, EERJ #25)

### Beispielfall: schwerer Mismatch

`#25 EERJ` – Opus = `ignorieren`, MiMo = `lesenswert`. Inhaltliche Prüfung notwendig (siehe `docs/qcheck_assessment.md`).

### Kosten

- MiMo gesamt (50 Calls): **$1.23**
- davon mit Cache (88–96 %, Calls 8–32): avg $0.012/Call
- davon ohne Cache (TTL expired, Calls 33–50): avg $0.038/Call
- Opus aus DB-Originallauf: $1.40
- Faktor auf Wochenlast: ~1/2 (Opus-Cache war im Originallauf bei 91 %, dadurch nur leicht teurer als MiMo cold).

### Verdict

**Opus bleibt für Assessment.** 30 % Drift-Rate und insbesondere 22 % False-Skip auf `lesenswert` sind für die pädagogische Kernoperation nicht akzeptabel — das sind die Artikel, die in den Digest gehören und auf die der Assistant Dich aufmerksam machen soll.

## Summarize — Detail

5 Publikationen aus `summaries.json` (Opus-generiert) → MiMo neu gefahren.

### Konkordanz pro Pub

| pub_id | keys J | thinkers J | methods J |
|---|---:|---:|---:|
| IGPFC4IP | 0.35 | 0.28 | 0.33 |
| 3W9X5QLZ | 0.33 | 0.53 | 0.12 |
| KGZXSKKC | **0.76** | **0.79** | 0.10 |
| 6WYG2HJG | 0.30 | **0.86** | **0.00** |
| VNFHZFKN | 0.50 | 0.50 | 0.29 |
| **avg** | **0.45** | **0.59** | **0.17** |

### Beobachtungen

- **`methods` ist konstant das schwächste Feld** (avg 0.17, einmal 0.00). MiMo formuliert Methoden mit anderen Begriffen — z. B. „qualitative content analysis" statt „inhaltsanalytisches Verfahren", oder schreibt Methoden gar nicht raus.
- `named_thinkers` und `key_terms` sind teilweise erstaunlich nah (KGZXSKKC, 6WYG2HJG), aber mit hoher Varianz.
- MiMo summaries sind **inhaltlich verständlich**, aber nicht identitäts-erhaltend gegenüber Opus.

### Kosten

- MiMo gesamt (5 Pubs): **$0.118**
- Opus-Original (aus summaries.json, je Pub geschätzt $0.05–0.13): ~$0.49
- Faktor ~1/4 bis 1/7

### Verdict

**Opus bleibt, aber methods-Lücke ernst.** Wenn die `methods`-Listen aus `summaries.json` als Suchindex oder für Such-Disambiguation genutzt werden (z. B. „Welche Pubs nutzen ethnographische Methoden?"), dann ist MiMo's 0.17-Jaccard ein klares Risiko. Vor einer Migration auf MiMo: erst hand-validieren, ob die `methods` für die downstream-Suche überhaupt entscheidend sind.

## Trends — Detail

3 Cluster (digitale_kultur, medienpaed, erziehungswiss), je 40 Artikel.
Opus aus `cost_test_sarah_v2_mimo_cached.json` recycled; MiMo neu mit `max_tokens=32000`.

### Output

| Cluster | Opus chars | MiMo chars | term-Jaccard |
|---|---:|---:|---:|
| digitale_kultur | 9 653 | 9 518 | 0.20 |
| medienpaed | 9 681 | 11 406 | 0.24 |
| erziehungswiss | 10 831 | 10 948 | 0.26 |

- Vergleichbare Länge, alle finish=stop, keine Truncation
- Term-Overlap 0.20–0.26: unterschiedliche Diskurs-Pointierung, aber dieselben Cluster-Themen
- **MiMo-Cache 99.6–99.8 %** — System-Prompt-Layout konstant über die 3 Calls

### Kosten (Q-Check-Stichprobe — 40 Artikel pro Cluster!)

- MiMo gesamt (3 Cluster × 40 Artikel): **$0.057**
- Opus-Original: $0.53
- Faktor ~1/9 — **gilt nur für die Q-Check-Stichprobengröße**

### Korrektur: Produktionsmessung am 2026-05-16

Nach Umstellung (`MODEL_TRENDS=xiaomi/mimo-v2.5-pro`, `MAX_TOKENS_TRENDS=32000`) wurde Cluster `erziehungswiss` mit echtem Vollvolumen (**746 Artikel**, 262.775 input-Tokens) gefahren:

- **Kosten gemessen: $0.555** (nicht $0.02 wie aus dem Q-Check hochgerechnet)
- **Cache greift nicht**: `cache_write=0`, `cached_read=512` (<0.2 %). Der Trends-System-Prompt ist nur **~700 Tokens**, liegt damit unter der Cache-Mindestschwelle (Anthropic/MiMo: 1024–4096). `cache_control: ephemeral` ist im aktuellen Trends-Setup ein no-op.
- **Faktor MiMo/Opus realistisch**: ~1/3 bei Vollvolumen (Opus cold geschätzt $1.44/Cluster), **nicht 1/9**. Bei 7 Clustern pro Trend-Welle: ~$4 MiMo vs ~$10–14 Opus cold.
- **Q-Check-Hochrechnung war falsch**, weil 40-Artikel-Stichproben den User-Content-Anteil klein hielten und dort offenbar implicit caching durch identische Prefixe griff. Bei voller Artikel-Vielfalt pro Cluster greift dieser Mechanismus nicht.

### Verdict (aktualisiert)

**MiMo bleibt Default für Trends**, aber die Spar-Bilanz ist deutlich kleiner als ursprünglich behauptet:
- ~$0.55/Cluster MiMo vs ~$1.44/Cluster Opus cold = Faktor ~1/3
- Vollvolumen-Outputs sind vollständig (finish=stop), Qualität laut Q-Check-Stichprobe akzeptabel
- Empfohlen: profile.json kann via `model_trends` jederzeit auf Opus zurückgeschaltet werden, falls qualitativer Vergleich auf Produktionsdaten das nahelegt
- Cache-Strategie für Trends ist ein eigenes Thema (System-Prompt zu klein für ephemeral cache).

## Mistral Medium 3.5 — Side-Note gegen die 5 Mismatches

Am 2026-05-16 zusätzlich getestet, ob Mistral Medium 3.5 (nativ via api.mistral.ai, $1.50 in / $7.50 out per Mtok) das Assessment-Problem ohne Prompt-Tuning anders löst als MiMo. n=5 — qualitativ.

| # | Opus | MiMo v1 | MiMo v2 patched | Mistral 3.5 |
|---|---|---|---|---|
| 10 | lesenswert | scannen | scannen | scannen |
| 22 | lesenswert | scannen | scannen | **lesenswert** ✓ |
| 25 | ignorieren | lesenswert | scannen | lesenswert |
| 44 | lesenswert | scannen | **lesenswert** ✓ | scannen |
| 48 | lesenswert | scannen | **lesenswert** ✓ | **lesenswert** ✓ |

- Mistral 3.5 matched Opus in 2/5 — gleiche Quote wie MiMo+Patches, komplementäre Verteilung. Mistral fixt den Black-Box-Fall (#22, User-hochrelevant), den MiMo selbst mit Patches verfehlt. MiMo+Patches fixt im Gegenzug den Citation-Hit (#44), den Mistral verfehlt.
- Cultural-Resilience-Falle (#25): Beide fallen rein.
- **Kosten:** $0.049/Call (0 % Cache über alle 5 Calls — Mistrals implicit caching greift entweder nicht im Usage-Report oder bei diesem Prompt-Shape nicht). Im Vergleich: Opus mit Cache $0.028/Call. **Mistral 3.5 ist ohne Cache teurer als Opus mit aktivem Cache.**
- **Verdict:** Mistral 3.5 ist für MOJO uninteressant — weder Qualitätsvorteil noch Kostenvorteil. Rohdaten: `docs/qcheck_mistral_med35.{json,md}`, Skript: `scripts/qcheck_mistral_med35.py`.

## Patch-Test Round 2 (verworfen)

Am 2026-05-16 wurde mit `scripts/qcheck_mimo_promptv2.py` getestet, ob drei chirurgische Outro-Regeln (Citation-Trigger, Schlüsselbegriff-Anschluss, Cultural-Resilience-Negativabgrenzung) die Konkordanz von MiMo gegen Opus verbessern. Test-Set: 5 Mismatches + 3 Kontrollen aus dem Hauptlauf, n=8.

Resultat: 2/5 Mismatches in Richtung Opus verschoben (#44, #48), 1/3 Kontrollen regressed (#6: ignorieren → scannen). **Bei n=8 ist das nicht von statistischer Streuung zu unterscheiden** — die Patches werden NICHT in `agent.py` integriert. Rohdaten in `docs/qcheck_mimo_promptv2.{json,md}` für Doku-Zwecke aufgehoben.

Falls die Frage „Kann MiMo Opus im Assessment ersetzen?" je wieder gestellt wird: erst vollen Mismatch-Pool (alle 15 Mismatches aus Hauptlauf) + entsprechend große Kontrollgruppe testen, n ≥ 30. Erst dann lässt sich entscheiden, ob die hier gefundenen Effekte real sind oder Rauschen.

## Was im Code anschließend zu tun ist

1. **`trends.run` auf MiMo umstellen** (Task #4) — Provider-Konfig setzen, `max_tokens=32000` für MiMo erzwingen, Empty-Response-Failsafe hinzufügen.
2. **`summarize.run` bleibt Opus**, methods-Lücke später untersuchen.
3. **`agent.run_agent` (assessment) bleibt Opus**. Outro-Patches verworfen (siehe oben).
4. `mimo.supports_anthropic_cache=True` (in `multi_provider.py`) ist korrekt — Cache funktioniert nachgewiesen.
5. **OpenRouter weekly key limit** für regulären MOJO-Lauf prüfen — der alte Key ($10/Woche) ist eng kalibriert für eine Digest-Woche und reicht möglicherweise nicht für ein produktives MOJO + parallele Experimente.

## Schlussfolgerung: wo ist der größte Kostenhebel?

Nach Q-Check + Produktions-Smoketest (2026-05-16): der größte Hebel ist **NICHT der Modellwechsel**, sondern **Cache-Hygiene auf dem bestehenden Opus-Assessment**.

| Hebel | Größenordnung | Risiko |
|---|---|---|
| Cache-Hit-Rate hoch halten (>80 % auf assess/verify) | $0.10 → $0.028 pro Artikel = **Faktor 3–4** | keiner, Quality bleibt Opus |
| Trends auf MiMo statt Opus | $1.70 → $0.55 pro Cluster = Faktor ~1/3 | minimaler Quality-Drift |
| Assessment auf MiMo (verworfen) | wäre ~1/9, aber 30 % Verdict-Drift | zu hoch |
| Mistral 3.5 Assessment (verworfen) | kein netto-Vorteil (siehe oben) | mittel |

**Konkret implementiert (Task #9, 2026-05-16):**
- Pro Welle wird am Ende ein Cache-Hit-Rate-Report ausgegeben (`run_batch_digest` → `_finalize_with_cache_report`). Sichtbar im CLI- und Web-Output, sowohl bei Erfolg als auch bei Abbruch.
- `mojo cache-report --days N [--endpoint …] [--model …]` zeigt historischen Trend pro Endpoint/Modell. Cache-kritische Endpoints (`batch_screen`, `run_agent`, `assess`, `verify`) bekommen ein ⚠-Flag, wenn die Hit-Rate unter 80 % fällt.
- Implementation: neue Funktionen `cache_hit_stats()`, `format_cache_report()`, `wave_marker()` in `journal_bot/llm_log.py`. Token-gewichtete Hit-Rate (nicht call-gewichtet) — Tests in `tests/test_llm_log.py::CacheHitStatsTests`.

Wenn die Hit-Rate auf assess/verify unter 80 % fällt, ist das die Ursache jedes Kostenanstiegs — nicht das Modell. Das Reporting macht diesen Hebel jetzt sichtbar.

## Rohdaten

- `docs/qcheck_assessment.json` + `docs/qcheck_assessment.md` (50 Artikel side-by-side)
- `docs/qcheck_summarize.json` + `docs/qcheck_summarize.md` (5 Pubs side-by-side)
- `docs/qcheck_trends.json` + `docs/qcheck_trends.md` (3 Cluster side-by-side)
- Script: `scripts/qcheck_mimo_vs_opus.py`
- Stichprobe: `scripts/qcheck_assessment_ids.json`
