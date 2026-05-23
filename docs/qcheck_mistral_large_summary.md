# Q-Check: Mistral Large vs Production-Stack

**Datum:** 2026-05-23
**Frage:** Ist Mistral Large (nativ via api.mistral.ai) ein viabler Ersatz für (a) Opus in der Triage und (b) MiMo in der Trend-Analyse?

**Stichprobe:**
- Assessment: 50 Artikel aus `scripts/qcheck_assessment_ids.json` (stratifiziert, identisch zum MiMo-vs-Opus-Q-Check vom 2026-05-16)
- Trends: 3 Cluster × 40 Artikel (`digitale_kultur`, `medienpaed`, `erziehungswiss`), MiMo-Baseline aus `qcheck_trends.json` recycled

**Kosten dieses Q-Checks:** $0.80 Assessment + $0.04 Trends = **$0.84 total**

---

## TL;DR

| Aufgabe | Empfehlung | Grund |
|---|---|---|
| **Triage (Assessment)** | **Nein** | Mistral kann nicht "ignorieren" sagen — 0 % Ignorieren-Precision, 43 % Workload-Erhöhung |
| **Trends (regelmäßig)** | **Bedingt ja**, als "Barometer-Modus" | 29 % billiger als MiMo, vergleichbare Qualität (Jaccard 0.19 vs MiMo-vs-Opus 0.20–0.26), aber 2–3× langsamer |
| **DSGVO als Argument** | irrelevant | (User-Klarstellung) |
| **Implicit Cache** | unzuverlässig | 28 % Hit-Rate, stochastisch — kein deterministischer Workload-Spar wie bei Anthropic-Cache |

---

## 1. Triage — Konfusionsmatrix (50 Artikel)

| Opus → / Mistral ↓ | ignorieren | lesenswert | scannen | Σ |
|---|---:|---:|---:|---:|
| **ignorieren** (15) | 0 | 4 | 11 | 15 |
| **lesenswert** (20) | 0 | 18 | 2 | 20 |
| **scannen** (15) | 0 | 14 | 1 | 15 |
| **Σ (Mistral)** | **0** | **36** | **14** | 50 |

### Kernzahlen

| Metrik | Mistral | MiMo (2026-05-16) | Opus (Gold) |
|---|---:|---:|---:|
| Verdict-Match | **38 %** | 70 % | 100 % |
| Lesenswert-Recall | **90 %** | 78 % | 100 % |
| False-Skip auf lesenswert | **10 %** | 22 % | 0 % |
| Ignorieren-Precision | **0 %** | (mittel) | 100 % |
| False-Escalate (Opus=ignor → Mistral nicht) | **100 %** | — | 0 % |
| Avg Kosten/Call | $0.016 (uncached) | $0.012 | $0.019 (cached) |
| Avg Latenz | ~17 s | ~6 s | ~5 s |
| Cache-Hit-Rate (>50 %) | 28 % stochastisch | 0 % (Bug) | >80 % deterministisch |

### Interpretation

Mistrals **Lesenswert-Detektion ist tatsächlich besser als die von MiMo** (90 % Recall, 10 % False-Skip — beides klar besser als MiMo's 78 % / 22 %). Wäre die Aufgabe binär ("ist das was?"), wäre Mistral der bessere Kandidat als MiMo.

**Aber die Triage ist nicht binär**, sondern dreistufig. Mistral kollabiert die "ignorieren"-Stufe komplett:
- Opus markiert 15/50 = 30 % als "ignorieren"
- Mistral sagt **kein einziges Mal** "ignorieren"
- Diese 15 Artikel landen bei Mistral entweder als "scannen" (11×) oder "lesenswert" (4×)

Konkrete Folge für Wochenlauf:
- Opus: 35 Artikel zum Sichten, 15 weg (workable)
- Mistral: 50 Artikel zum Sichten, 0 weg → **+43 % Workload**

### Diagnose (vom User bestätigt)

> "Mistral kann ambivalente Aspekte nicht offenhalten."

Das passt zum Bias-Muster: alles, was nicht clear-cut ablehnbar ist, wird als interessant eingestuft. Mistrals Vorteil bei der Lesenswert-Erkennung ist die andere Seite derselben Münze — die Schwelle ist niedrig.

**Konsequenz: Triage-Stack bleibt unverändert (DeepSeek → Opus assess → Opus verify).** Eventuell weiterer Sub-Befund (nicht im Critical Path): Mistral als zweite Meinung auf Opus' "scannen"-Verdikte könnte als Verify-Layer interessant sein, weil sein Up-Bias Opus' Konservativität kompensiert. Nicht Q-Check-Thema heute.

---

## 2. Trends — Cluster-Vergleich (3 × 40 Artikel)

| Cluster | Mistral $ | MiMo $ | Mistral chars | MiMo chars | term-Jaccard | Mistral Latenz |
|---|---:|---:|---:|---:|---:|---:|
| digitale_kultur | $0.0131 | $0.0159 | 13,094 | 9,518 | 0.17 | 72.7 s |
| medienpaed | $0.0140 | $0.0210 | 12,955 | 11,406 | 0.19 | 77.2 s |
| erziehungswiss | $0.0136 | $0.0199 | 14,697 | 10,948 | 0.19 | 86.3 s |
| **Σ** | **$0.0406** | **$0.0568** | 40,746 | 31,872 | **0.19 avg** | — |

**Faktor: Mistral ist 29 % billiger als MiMo. Output 27 % länger. Avg term-Jaccard 0.19 — vergleichbar zum MiMo-vs-Opus-Q-Check (0.20–0.26).**

### Output-Qualität (Beispiel-Lead-Sätze)

Alle drei Cluster-Outputs zeigen sich strukturiert mit dem Standard-Trends-Markdown-Layout (Überblick / Konsolidierende Diskurse / Differenzierungen / Methoden / Ausreißer / Absenzen). Beispiel-Eröffnungen:

**digitale_kultur:**
> Das Fenster umfasst 40 Beiträge aus sechs Journalen, wobei *AI & Society* (12) und *STHV* (14) dominieren [...]. Auffällig ist die starke Präsenz **kritischer Reflexionen zu KI und algorithmischer Steuerung** – nicht als technologische Innovation, sondern als **soziotechnische Infrastruktur** [...].

**medienpaed:**
> Das Zeitfenster 2024–2026 zeigt eine klare Fokussierung der deutschsprachigen Medienpädagogik auf **Extended Reality (XR) und Künstliche Intelligenz (KI)** als zentrale Gegenstände. Auffällig ist die Dominanz von **praxisnahen Erprobungen** (z. B. VR im Sportunterricht, XR im Musikunterricht) gegenüber theoretischen Grundlagenreflexionen [...].

**erziehungswiss:**
> Das Fenster umfasst 40 Beiträge aus vier deutschsprachigen und internationalen Journals (*EthicsEd*, *Discourse*, *PCS*, *ZfE*) zwischen 2024 und 2026. Auffällig ist die starke Präsenz **ethisch-philosophischer Reflexionen** (v. a. in *EthicsEd*) [...].

→ konkret, mit Quantifizierung, ohne Buzzword-Inflation. Inhaltlich vergleichbar zum MiMo-Output.

### Cache-Verhalten in Trends

**0 % bei allen 3 Calls.** Mistrals implicit cache hat im Trends-Lauf gar nicht zugegriffen — drei aufeinanderfolgende Calls mit identischem ~700-Token-System-Prompt, alle uncached. Das bestätigt die stochastische Natur des Mistral-Caches.

### Hochrechnung "Wochen-Barometer"

Bei einem hypothetischen Wochenlauf über alle 7 Diskursräume:

- Mistral: 7 × ~$0.014 = **~$0.10/Woche, ~$5/Jahr**
- MiMo: 7 × ~$0.019 = **~$0.13/Woche, ~$7/Jahr**

Differenz: ~$2/Jahr. Operativ irrelevant — die Cost-Frage ist hier nicht entscheidend. **Entscheidend ist Qualität, Latenz und Bedienbarkeit.**

---

## 3. Mistral Implicit Cache: warum nicht verlässlich?

In der Assessment-Stichprobe (50 Calls, identischer 29k-Token System-Prompt):
- 14/50 Calls (28 %) hatten Cache-Hit >50 %
- Verteilung: stochastisch über den Lauf, kein Warmup-Effekt
- Hit-Calls: 96–99 % cached (wenn Hit, dann fast voll)
- Miss-Calls: 0 % cached

Beobachtetes Muster: **Mistral cached pro Backend-Instanz, und Routing ist nicht sticky.** Der gleiche Prefix wird auf verschiedenen Instanzen gecacht; wenn die Anfrage auf eine "kalte" Instanz routet, ist der Cache nicht da.

Im Gegensatz dazu: Anthropic mit `cache_control: ephemeral` liefert deterministisch >80 % Cache-Hits (nach Warmup), weil der Cache global verwaltet wird.

**Konsequenz für die Cost-Schätzung:**
- Meine $0.016/call (Assessment) und $0.014/call (Trends) sind die **uncached Worst-Case-Schätzung** — Mistral liefert kein `cost`-Feld in der `usage`, also rechnet `extract_stats()` über die Preistabelle ohne Cache-Discount
- Tatsächliche Kosten liegen ~10–20 % darunter, abhängig vom Glück mit dem Routing
- Mistral-Cache-Discount ist nicht öffentlich klar dokumentiert; bei OpenAI-kompatiblen API üblicherweise ~50 % off für cached input

**Bug zu beheben (low priority):** `multi_provider.extract_stats()` rechnet für Mistral den Cache nicht ein. Solange Cache-Verhalten stochastisch ist und Mistral nicht produktiv läuft, nicht dringend.

---

## 4. Empfehlung

### Triage
**Keine Änderung.** Stack bleibt: DeepSeek-Screen → Opus-Assess → Opus-Verify. Mistral disqualifiziert wegen Workload-Erhöhung +43 % bei 0 % Ignorieren-Precision.

### Trends — Status quo
**MiMo bleibt Default für reguläre Trend-Dossiers.** Die 29 %-Ersparnis bei Mistral ist absolut zu klein ($2/Jahr), die Latenz 2-3× schlechter, und die Token-Verbosität (+27 %) bedeutet längere Lese-Texte ohne signifikant mehr Information.

### Trends — "Barometer"-Modus (neue Idee)
**Wenn ein leichtgewichtiges Trends-Format gewünscht ist** ("monatlicher Sci-Wetterbericht": kurze 200-Wort-Beobachtung pro Cluster statt 800-1500-Wort-Dossier), ist Mistral ein interessanter Kandidat **mit modifiziertem Prompt**:

- Output auf 200–400 Wörter cappen
- Latenz wird kürzer durch kürzeren Output (typisch 30–45 s)
- Kosten pro Barometer-Lauf: ~$0.005/Cluster
- Wöchentlich über alle 7 Cluster: $0.04/Woche, $2/Jahr
- Quality: Mistrals Output-Strukturierung war im Q-Check stark — eignet sich für Standformat

**Falls du das willst, ist der nächste Schritt ein eigener `trends.barometer()` Modus, der separat von `trends.run()` einen kürzeren Prompt + Mistral verwendet. Das ist keine Q-Check-Entscheidung mehr, sondern Feature-Arbeit.**

### Mistral-Wiring
**Lass es im Code, nicht aktivieren.** `ROUTES["mistral"]` bleibt für künftige Experimente (Verify-Layer? Barometer?). `extract_stats()`-Cache-Bug bleibt offen, ist nicht produktiv-blockierend.

---

## 5. Tabelle aller getesteten Modelle (Stand 2026-05-23)

| Modell | Preis in/out | Cache-Modell | Triage-Eignung | Trends-Eignung | Produktiv |
|---|---|---|---|---|---|
| **Opus 4.7** | $5 / $25 /Mtok | Anthropic explicit (cache-read $0.50, deterministisch) | **Gold** | (teuer aber gut) | ✓ assess/verify |
| **Sonnet 4.6** | $3 / $15 /Mtok | Anthropic explicit | (nicht getestet) | (nicht getestet) | — |
| **Haiku 4.5** | $1 / $5 /Mtok | Anthropic explicit | (nicht getestet) | (nicht getestet) | — |
| **MiMo 2.5 Pro** | $1 / $3 /Mtok | OpenRouter cache_control ($0.20 cache-read) | False-Skip 22 % | **Gold-aktiv** | ✓ trends |
| **Mistral Large** | $0.50 / $1.50 /Mtok | implicit stochastic | **disqualifiziert** | viable für Barometer | — |
| **DeepSeek v3.2** | $0.26 / $1.10 /Mtok | implicit | (nicht direkt vergleichbar — anderes Format) | (nicht getestet) | ✓ screen |

---

## Anhang: Rohdaten

- `docs/qcheck_mistral_assessment.json` — 50 Calls, Full-Verdict-Vergleich
- `docs/qcheck_mistral_assessment.md` — gerendert
- `docs/qcheck_mistral_trends.json` — 3 Cluster, Mistral + MiMo-Baseline
- `docs/qcheck_mistral_trends.md` — gerendert mit Full-Outputs
- Goldstandard-Stichprobe: `scripts/qcheck_assessment_ids.json` (unverändert, identisch zum MiMo-Q-Check)
