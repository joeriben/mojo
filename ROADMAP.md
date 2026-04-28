# ROADMAP

## ✓ Erledigt
- [x] OpenAlex-Pagination (cursor-based paging)
- [x] Journal-Coverage-Analyse (welche Journals werden zitiert aber nicht getrackt?)
- [x] Scout (Watchlist-Evaluation via Haiku)
- [x] Rename journal-bot → mojo
- [x] Diskursraum-Management (CRUD, Profiling, Discovery, diskursraeume.json)
- [x] Multi-Linsen-Scout (3× Haiku + Opus-Synthese, Positionalitäts-Report)
- [x] Namensfindung → MOJO (Monitoring Journals)
- [x] Phase 5b: Scout-Volllauf (49 Journals), 8 aufgenommen (ZfPaed, EthicsEd, REPCS, SAE, BJET, JAC, BDS, STHV)
- [x] Phase 5c: Historical Backfill (`mojo fetch --since 2016`, 17.465 Artikel, 10 Jahre, alle 28 Journals)
- [x] Journal-Aufnahme-Workflow: journals.json + `mojo journal add/list/remove`
- [x] Testfall "Kulturelle Bildung" (aesthetische_kulturelle_bildung: 3→6 Journals)
- [x] Workflow-Scripts für autonomen Agenten (docs/workflows/)

## Nächste Schritte

### Erster Digest-Lauf
- [ ] `mojo digest --next 20` auf den neuen Journals testen
- [ ] Haiku-Triage verifizieren (filtert irrelevante Artikel vor Opus)
- [ ] Kosten und Qualität der Verdicts prüfen

### Trend-Analyse
- [ ] `mojo trends --cluster aesthetische_kulturelle_bildung` (jetzt 6 Journals, genug Substanz)
- [ ] `mojo biblio --cluster aesthetische_kulturelle_bildung` (10 Jahre Daten)
- [ ] Alle 7 Räume durchlaufen

### Open-Source-Vorbereitung
- [ ] Pfade abstrahieren (Zotero-Pfad, Obsidian-Vault → Konfigurierbar)
- [ ] API-Key-Management generalisieren
- [ ] README für externe Nutzer
- [ ] Watchlist-✓ automatisieren bei `mojo journal add`

### Obsidian / Ausgabe
- [ ] Obsidian-Output überdenken (Benjamin findet Obsidian "nerdig")
- [ ] Alternative: einfache HTML-Reports? Zotero-Writeback? E-Mail-Digest?

## Qualitätsverbesserungen
- [ ] Biblio: Autor-Fallback für Sammelbände
- [ ] Biblio: DOI-Validierung, Dedup-Verbesserung
- [ ] Summarize: Qualitätsprüfung der 53 Summaries (stichprobenartig)
- [ ] Agent: Feedback-Loop (Digest-Einträge als nützlich/daneben markieren → DB)

## Diskursraum-Weiterentwicklung
- [ ] Positionalitäts-Report auf bereits getrackte Journals anwenden (nicht nur Kandidaten)
- [ ] `mojo diskurs profile --deep` (Haiku-Interpretation des Datenprofils)

## Infrastruktur
- [ ] launchd-Setup für wöchentliche Ausführung
- [ ] Token-Logging in DB (pro Call: model, tokens_in, tokens_out, cost, timestamp)
- [ ] Kosten-Budget-Check (optional)
- [ ] Sonderfälle: zkmb.de, e-flux (Scraper nötig, nicht via OpenAlex)

## Architektur (bei Bedarf)
- [ ] Delegation-first: Haiku als Vorsortierung, Opus nur für Kandidaten — relevant bei >50 Artikeln/Woche
- [ ] Anthropic Batch API (50% Rabatt) für wöchentliche Batch-Digest-Läufe

## Bugs / Risiken

### [HIGH] Anthropic-Cache-Mindestschwelle wird nicht überall geprüft

**Beobachtung (extern, SACAnEv-Run, 2026-04-27):** OpenRouter akzeptiert `cache_control: {"type": "ephemeral"}` auch für System-Prompts unter Anthropics Mindestgröße — und cached dann *still* gar nicht. Ergebnis: Vollkosten auf jeden Call statt 10–25 % der Cache-Read-Rate. Konkreter Test mit `claude-sonnet-4.5` und 445-Token-Systemprompt: 0 % cached_tokens auf Call 2 und 3, kein Fehler/Warning.

**Anthropic-Mindestgrößen (Stand 2026-04):**
- Sonnet / Opus: **1024 Tokens** im cache_control'd Block
- Haiku: **2048 Tokens** im cache_control'd Block

Unterhalb dieser Schwellen ist `cache_control` ein No-Op.

**MoJo-Risikoflächen** (alle Stellen mit `cache_control`):
- `agent.py` — Opus-Agent mit ~23k-Token-Systemprompt → unkritisch (weit über Schwelle), zusätzlich existiert `CacheNotHitError`-Check ab Batch 2
- `scout.py:_run_lens` — Lens-Prompts (LENS_A/B/C) mit Opus-Modell → muss verifiziert werden, ob jeder Lens-Prompt ≥1024 Tokens hat
- `trends.py`, `research_agent.py` — analog, ungeprüft
- `batch_digest.py` — geht über `agent.py`, vermutlich ok

**Maßnahmen:**
1. Audit aller Stellen mit `cache_control` — Token-Größe des cached Blocks dokumentieren, mit Anthropics Schwelle abgleichen
2. **`CacheNotHitError`-Mechanik aus `agent.py:599–613` universell anwenden**, nicht nur in `batch_screen` — als Helper-Funktion `_verify_cache(usage, batch_num, min_ratio=0.5)` oder als Decorator
3. **Pre-Flight Cache-Verifikationsskript** (`scripts/cache_verify.py` o.ä.) das vor jedem produktiven Lauf 3 Test-Calls macht und die Cache-Hit-Rate verifiziert. Vorbild: `/Users/joerissen/ai/sacanev/scripts/cache_verify.py`
4. Dokumentation in `AGENTS.md` ergänzen: „Bei Anthropic ist `cache_control` ein silent No-Op unter 1024 (Sonnet/Opus) bzw. 2048 (Haiku) Tokens"

**Reproduktion (~1¢ Kosten):**
```bash
python3 -c "
from openai import OpenAI
client = OpenAI(base_url='https://openrouter.ai/api/v1', api_key=open('$HOME/.config/mojo/openrouter_key').read().strip())
short_sys = 'Du bist ein Reader-Agent. Antworte mit JSON.'  # ~10 tokens, weit unter Schwelle
msgs = [
    {'role': 'system', 'content': [{'type': 'text', 'text': short_sys, 'cache_control': {'type': 'ephemeral'}}]},
    {'role': 'user', 'content': 'Test'},
]
for i in range(3):
    r = client.chat.completions.create(model='anthropic/claude-sonnet-4.5', messages=msgs, max_tokens=20)
    pd = r.usage.model_dump().get('prompt_tokens_details') or {}
    print(f'call {i+1}: prompt={r.usage.prompt_tokens} cached={pd.get(\"cached_tokens\", 0)}')
"
# Erwartet: alle 3 Calls cached=0 obwohl System-Prompt unverändert
```

**Externer Auslöser:** ~$40-Lauf wurde durch genau diese Konstellation verursacht (kurzer cached System-Prompt → kein Cache-Hit → Vollkosten × N Calls).
