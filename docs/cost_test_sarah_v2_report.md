# SARAH-Stack vs Opus auf MOJO-Operationen — Ehrlicher Befund

**Datum:** 2026-05-16
**Fixture:** `scripts/cost_test_fixture.json` (20 Artikel, 5 Pubs, 3 Diskursräume)
**Roh-Daten:** `docs/cost_test_sarah_v2_mimo_cached.json` (n=20+5+3 pro Modell, Single-Shot, sequenziell)
**Test-Skript:** `scripts/test_sarah_v2.py`
**Code-Stand:** `journal_bot/multi_provider.py` mit `mimo.supports_anthropic_cache=True` (cache_control wird via OpenRouter durchgereicht — siehe SARAH-Pfad)

## TL;DR

> **Die Hypothese „MiMo-Cache greift via OpenRouter und macht MiMo 1/25 von Opus" ist empirisch falsch.**
> OpenRouter listet `input_cache_read=$0.20/Mtok` für `xiaomi/mimo-v2.5-pro`, akzeptiert auch
> `cache_control: ephemeral`, aber **0 von 20 Assessment-Calls liefern `cached_tokens > 0`**.
> Der Header wird stillschweigend ignoriert (oder die Provider-Implementierung steht aus).
>
> **Ohne** MiMo-Cache liegen die realen Faktoren bei: Assessment **1/1.6**, Summarize **1/6.9**, Trends **1/5.7**.
> Auf Wochenlast (25 Assessments + 5 Summarize + 3 Trends) hochgerechnet:
> **Opus $2.43 → MiMo $1.04 (–57 %, Faktor 1/2.3)** statt der behaupteten 1/25.

## Setup

| Aspekt | Konfiguration |
|---|---|
| Paarung | SARAH-konform: jede Operation gegen Opus als Goldstandard |
| Assessment | `opus` vs `mimo` (vorher Mistral verworfen — Verdict-Bias 20 %) |
| Summarize | `opus` vs `mimo` |
| Trends | `opus` vs `mimo` (MiMo `max_tokens=32000` per User-Direktive) |
| Cache-Strategie | Opus/MiMo: `cache_control: { type: 'ephemeral' }` via OpenRouter |
| Reihenfolge | Sequenziell pro Modell (Cache-Warmup intra-Modell möglich) |

## Ergebnisse — Cache-Hits

| Operation | Modell | n | Σ cached_read | Σ prompt_in | Cache-Anteil | Median-Cache-Hit |
|---|---|---:|---:|---:|---:|---:|
| Assessment | **opus** | 20 | 712 880 | 785 888 | **90.7 %** | 96.2 % |
| Assessment | **mimo** | 20 | **0** | 669 485 | **0.0 %** | 0.0 % |
| Summarize | opus | 5 | 0 | 72 495 | 0.0 % | — |
| Summarize | mimo | 5 | 0 | 63 171 | 0.0 % | — |
| Trends | opus | 3 | 0 | 52 663 | 0.0 % | — |
| Trends | mimo | 3 | 0 | 47 057 | 0.0 % | — |

> **Befund 1:** Opus-Cache via OpenRouter funktioniert hervorragend (ab Call 2 dauerhaft 91–97 %).
> **Befund 2:** MiMo-Cache **funktioniert nicht**, auch wenn `cache_control: ephemeral` mitgesendet wird. SARAH-Code-Pfad (siehe `sarah/src/lib/server/ai/client.ts:709` und `:881`) ist identisch — wir senden den Header genauso wie SARAH ihn sendet, lesen `prompt_tokens_details.cached_tokens` zurück: kommt nichts. Die OpenRouter-Pricing-Page für `xiaomi/mimo-v2.5-pro` ist hier irreführend bzw. die Provider-Implementierung steht aus.
> **Befund 3:** Summarize und Trends haben pro Call wechselnde Inhalte (Publikation/Cluster), also strukturell kein Prefix zum Cachen — auch Opus zeigt hier 0 %. Das ist erwartbar und nicht der Engpass.

## Ergebnisse — Kosten

| Operation | Modell | Σ cost | avg/call | Cold-avg (1–5) | Warm-avg (6+) |
|---|---|---:|---:|---:|---:|
| Assessment | opus | **$1.1279** | $0.0564 | $0.0906 | $0.0450 |
| Assessment | mimo | **$0.6991** | $0.0350 | $0.0348 | $0.0350 |
| Summarize  | opus | **$0.4871** | $0.0974 | — | — |
| Summarize  | mimo | **$0.0704** | $0.0141 | — | — |
| Trends     | opus | **$0.5308** | $0.1769 | — | — |
| Trends     | mimo | **$0.0929** | $0.0310 | — | — |

### Cost-Ratios (Faktor MiMo / Opus)

| Operation | Opus | MiMo | Faktor |
|---|---:|---:|:---:|
| Assessment | $1.1279 | $0.6991 | **1/1.6** |
| Summarize | $0.4871 | $0.0704 | **1/6.9** |
| Trends | $0.5308 | $0.0929 | **1/5.7** |

### Hochrechnung Wochenlast (25 Assess + 5 Summ + 3 Trends)

| Stack | Kosten pro Wochenlauf | Hochrechnung Jahr (50 Wochen) |
|---|---:|---:|
| Opus-pur | **$2.43** | ~$121 |
| MiMo-pur | **$1.04** | ~$52 |
| Hybrid Assess-Opus + Rest-MiMo | $1.59 | ~$80 |

> Faktor **1/2.3** auf Wochenlast — nicht 1/25.
> Hauptursache: Bei Assessment frisst der Opus-Cache (91 % Hit-Rate) den größten Teil seines Preisvorteils auf,
> während MiMo den eigenen Cache-Hebel nicht aktivieren konnte.

## Ergebnisse — Qualität (Konkordanz gegen Opus)

### Assessment (Verdict)

| Modell | ignorieren | scannen | lesenswert |
|---|---:|---:|---:|
| opus | 11 | 4 | 5 |
| mimo | 7 | 7 | 6 |

- **Verdict-Match MiMo vs Opus: 15/20 = 75 %**
- Mismatches (5 Fälle):
  - 4× MiMo eskaliert `ignorieren → scannen` (MiMo ist großzügiger)
  - 1× MiMo eskaliert `scannen → lesenswert`
- **Kernthese-Term-Overlap (Jaccard) avg: 0.24** — niedrig, MiMo formuliert die Kernthese substantiell anders.
- **Keine** „lesenswert"-Verfehlung von MiMo (also keine harten Misses bei den interessanten Artikeln);
  aber bemerkenswert: MiMo erzeugt im ersten Call nur 39 Output-Tokens mit leerer `kernthese` — MiMo-Quirk
  (siehe SARAH-Empty-Response-Failsafe), für Produktion müsste der Retry-Pfad eingebaut werden.

### Summarize (Konkordanz auf Publikations-Ebene)

| Metrik | avg Jaccard |
|---|---:|
| key_terms | **0.35** |
| thinkers | **0.17** |
| methods | **0.11** |
| summary text-overlap | 0.17 |

> Hier ist MiMo deutlich schwächer als Opus. Pro Publikation reproduziert MiMo zwar die Thematik,
> aber Denker-Listen und Methoden weichen stark ab. Für „eigene-Publikations-Summaries" als Suchindex
> ist das ein Risiko — MOJOs Stärke hängt an dieser Genauigkeit.

### Trends (Output-Vollständigkeit + Term-Overlap)

| Modell | finish_reason | Output chars (3 Cluster) |
|---|---|---|
| opus | stop, stop, stop | 9 653 / 9 681 / 10 831 |
| mimo | stop, stop, stop | 11 785 / 7 216 / 11 228 |

- **`max_tokens=32000` für MiMo hat geholfen** — alle drei Trends-Calls jetzt vollständig (Run 1 hatte `length`).
- **Term-Overlap mit Opus avg: 0.21** — unterschiedliche Diskurs-Pointierung, aber vergleichbare Länge.
- MiMo-Output für Trends wirkt qualitativ tragfähig (eigene Validierung empfohlen vor Produktion).

## Latency (Assessment)

| Modell | min | median | max |
|---|---:|---:|---:|
| opus | 11 s | 13 s | 29 s |
| mimo | 6 s | 22 s | 57 s |

> MiMo ist im Median ~1.7× langsamer als Opus (Reasoning-Tokens). Bei einem Batch-Lauf von 100 Artikeln
> sind das +15 Minuten — nicht kritisch, aber spürbar.

## Konsequenzen für MOJO

### 1. Assessment (`agent.run_agent`) — bleibt Opus

**Begründung:** Faktor nur 1/1.6 bei 25 % Verdict-Drift. Der Opus-Cache (91 %) macht Opus auf dieser Operation schon billig — MiMo bringt zu wenig Ersparnis für den Quality-Hit. Außerdem ist Assessment das pädagogische Kernurteil — hier nicht sparen.

### 2. Summarize (`summarize.run`) — Opus bleibt, aber A/B-Eval lohnt sich

**Begründung:** 7× billiger ist substantiell, aber thinkers-Jaccard 0.17 und methods 0.11 sind ein Risiko. Empfohlen: gezielte Eval auf 10 weiteren Publikationen mit Hand-Vergleich der `thinkers`-Listen. **NICHT** ohne diese Validierung auf MiMo umstellen.

### 3. Trends (`trends.run`) — Strong Candidate für MiMo

**Begründung:** 5.7× billiger, vollständige Outputs, finish=stop, vergleichbare Länge und Struktur. Trends ist außerdem eine analytische Generierung (kein Goldstand erforderlich), und der Term-Overlap 0.21 reflektiert unterschiedliche Pointierung, nicht Fehler. **Empfehlung: MiMo als Default für Trends, Opus als optionales Premium-Refresh quartalsweise.**

### 4. MiMo-Quirks im Produktivpfad

- `mimo.supports_anthropic_cache=True` bleibt drin — schadet nicht, ist auf der Wahrheits-Skala „aktuell wirkungslos, OpenRouter-Pricing legt aber nahe dass es noch kommt".
- **Empty-Response-Failsafe für MiMo einbauen** (analog zu `sarah/src/lib/server/ai/h2-einwand.ts:540` ff.): MiMo emittiert sporadisch `stop` mit leerem `tool_args` (im Test bei Assessment Call 1 gesehen). Vor Produktion: ein Retry-Layer beim ersten leeren Response.
- `max_tokens=32000` für Trends im Produktivpfad setzen (Reasoning-Burn frisst Output-Budget sonst auf).

## Nicht-Befunde / Offene Punkte

- **MiMo-Cache:** Warum funktioniert er nicht trotz korrektem Header? Wert eines Open-Issues bei OpenRouter / Recherche in der MiMo-Dokumentation. Falls aktivierbar, springt der Hybrid-Stack auf ~1/8 statt 1/2.3 auf Wochenlast.
- **Mistral:** Wegen 20 % Verdict-Match disqualifiziert, im aktuellen Test nicht erneut gemessen.
- **„1/25"-Behauptung:** Stammt aus SARAH-Kontext mit anderen Operationen (Argumentationsanalyse, längere Outputs, eventuell andere Cache-Treffer). Auf MOJO-Operationen empirisch nicht reproduzierbar.

## Anhang — Rohdaten

- `docs/cost_test_sarah_v2_mimo_cached.json` — vollständige Call-Records inkl. `cost_usd`, `tokens_in/out`, `cached_read`, `cache_pct`, `latency_s`, `finish_reason`, `tool_args_full`
- `scripts/cost_test_fixture.json` — Fixture für Reproduzierbarkeit
- `scripts/test_sarah_v2.py` — Test-Skript

> Reproduktion: `python3 scripts/test_sarah_v2.py --op all --out <neue-datei.json>`
