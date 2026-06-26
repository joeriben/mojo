# AGENTS.md — Projektkontext für Coding-Assistenten

Dieses Dokument gilt für jeden Coding-Assistenten, der an MOJO arbeitet (Claude Code, GPT Codex, Cursor, Continue, etc.). `CLAUDE.md` enthält identischen Inhalt und bleibt für Kompatibilität erhalten.

**Neue Assistenten sollten zuerst `docs/mojo_2_grundorientierung.md` lesen** — das dauerhafte Orientierungsdokument für MOJO 2.0 (Plattform, Backtest-Stand, 2.0-Konturen, 1.x-Erhalt). Danach `HANDOVER.md` für den aktuellen Schritt.

**Arbeitskontext / Memory:** `docs/context/MEMORY.md` ist der Index über die aufgebauten Memory-Files (User-Profil, Feedback, Projekt-Entscheidungen). Bei Session-Start als Index lesen, relevante Files bei Bedarf nachladen.

## Was ist dieses Projekt?
Ein persönlicher Forschungsassistent für Benjamin Jörissen (FAU Erlangen-Nürnberg, Allgemeine Pädagogik / ästhetische & kulturelle Bildung). Der Bot sichtet wöchentlich wissenschaftliche Zeitschriften, bewertet jeden Beitrag gegen Benjamins publiziertes Werk, und produziert Digest-Einträge + Trend-Analysen.

## Architektur-Kern
- Opus-Summaries der eigenen Publikationen als Suchindex (`summaries.json`, ~28k Tokens)
- Opus-Agent mit Tool-Use (`read_publication`, `submit_digest_entry`) für Live-Interpretation
- Zwei-Phasen-Triage: DeepSeek-Screening (25er-Batches) → Opus-Assessment → optionale Opus-Verification
- OpenAlex ISSN-Fetcher + RSS/OJS/Custom-Fetcher, Crossref für Referenzlisten
- Citation-Tracker gegen authored_all (160 Publikationen, Vornamen-Disambiguation)
- Prompt-Caching via OpenRouter (`cache_control: ephemeral`, ~5 min TTL)
- Diskursraum-basierte Trend-Analyse (LLM + bibliometrisch)
- `projects.json` als neue Datenebene für aktive Forschungsprojekte

## Wichtige Pfade
- Zotero-Daten: `/Users/joerissen/FAUbox/Zotero` (NICHT `~/Zotero`)
- Zotero-Collection: "Benjamin's publications" (key `QM7TZT44`)
- Obsidian-Vault: `/Users/joerissen/Documents/Obsidian Vault/research/mojo/` (aber UX-problematisch, siehe `docs/context/feedback_obsidian_ux.md`)
- API-Key: `~/.config/mojo/openrouter_key` (chmod 600)
- S2-Key: `~/.config/mojo/s2_api_key`
- Store: `articles.db` im Projektordner
- Corpus: `corpus.json` + `summaries.json` im Projektordner
- Projekte: `projects.json` im Projektordner

## Konventionen
- Deutsch im User-facing Output (Digest, Trends, CLI-Meldungen, UI)
- Englisch im Code (Variablen, Docstrings, Kommentare)
- Konstanten in `settings.py`, Override per `profile.json` oder CLI-Flag
- Kein Over-Engineering: einfachste Lösung zuerst
- Kosten transparent: jeder LLM-Call wird mit Tokens + $ geloggt
- Volle Journal-Namen im User-Output, nicht Shortcodes (ZfPaed → "Zeitschrift für Pädagogik")

## Kostenkontrolle (KRITISCH)
- **NIEMALS Batch-API-Tests ohne vorherige Einzelkosten-Verifikation**
- Erst 2-3 Einzelcalls testen, Kosten pro Artikel messen, dem User zeigen
- Erst nach Bestätigung Batch starten
- Der Code in `cli.py cmd_digest()` enthält einen Safety-Check: bei >$0.15/Artikel nach den ersten 3 Artikeln wird abgebrochen
- `batch_screen()` in `agent.py` wirft `CacheNotHitError` bei <50% Cache-Hits ab Batch 2 nur für cache-kritische/teure Modelle; DeepSeek-Screening darf wegen fehlender Cache-Metrik nicht hart abbrechen
- Anthropic/OpenRouter-Cache-Mindestgrößen sind modellabhängig; Opus 4.6 braucht aktuell 4096 cachebare Tokens (`cache_control` ist darunter ein stiller No-Op)

## Lokales Recherche-LLM (Ollama, kostenfrei)
- Der Recherche-Agent (`research_agent.chat` / `focused_db_chat`, web `/agent`) kann pro Anfrage auf ein lokales Ollama-Modell umgeschaltet werden → Tool-Loops kostenfrei. Toggle „lokal" im Agent-Panel; persistiert pro Session.
- Abstraktion: `llm_client.build_research_backend(local=...)` liefert ein `LLMBackend` (Client/Modell/Cache/extra_body). Lokal = Plain-String-System (kein `cache_control`), kein OpenRouter-`transforms`, Kosten 0.
- Modellwahl: Dropdown im Agent-Panel, befüllt aus `llm_client.list_local_models()` (= `ollama list`); pro Session persistiert. Fallback-Default `model_agent_local` (profile.json/`MOJO_MODEL_AGENT_LOCAL`, aktuell `qwen3:8b`). Weitere Settings: `ollama_base_url` (`MOJO_OLLAMA_URL`), `research_use_local` (Default false, `MOJO_RESEARCH_LOCAL`).
- `llm_client.check_local_backend()` macht Preflight (Server erreichbar / Modell gepullt / Runner lauffähig) UND probt, ob das Modell **strukturierte `tool_calls`** liefert (der Loop liest `choice.message.tool_calls`; sonst sucht er nie) — Ergebnis pro Modell gecacht, Probe dient zugleich als Warm-up. Bei Fehler handlungsanweisende Meldung statt 500; KEIN stiller Fallback auf die kostenpflichtige Cloud.
- Tool-Calling-Verlässlichkeit ist modell × Ollama-Version-abhängig UND teils INTERMITTIEREND. Beobachtet (2026-06-16, App 0.12.11): `qwen3:8b` end-to-end validiert (langsam, „denkt"); `llama3.3` ✓ (42 GB, ~36s); `mistral-nemo` einmal `[TOOL_CALLS]`-Leak, danach mehrfach sauber → NICHT als „kaputt" verallgemeinern (Ein-Sample-Fehlschluss); `gemma3` kein Tool-Support. Die Probe fängt nur Stand-zur-Probe-Zeit; intermittierende Leaks können durchrutschen — Modellwahl bleibt User-Sache (Dropdown).

## Was NICHT tun
- Keine `.env`-Dateien vorschreiben (User kennt das Konzept nicht / will es nicht)
- Keine Zotero-Collections manuell anlegen lassen
- Keine Multi-Step-Setup-Anleitungen (Bot fragt interaktiv, wenn was fehlt)
- Keine Trend-Analyse über ALLE Journals gleichzeitig (→ Diskursräume!)
- Keine Trend-Labels bei <3 Zitationsjahren oder <5 Gesamtzitationen
- Keine "theoretische Verortung" in Summaries (das ist Interpretation, nicht Zusammenfassung)
- Keine Rückfragen wenn der nächste Schritt offensichtlich ist — einfach machen
- Keine optimistischen Projektionen auf Basis von Einzeltests
- Petar Jandrić NICHT als Trigger-Autor (zu viel Output, zu wenig Trennschärfe)

## Diskursräume (in `diskursraeume.json` definiert)
deutsche, erziehungswiss, digitale_kultur, medienpaed, bildungstheorie, aesthetische_kulturelle_bildung, resilienz

## Trigger-Autoren (Escalation unabhängig vom Tier)
MacGilchrist, Jarke, Chun (Wendy Hui Kyong Chun)

## Benjamins 5 disziplinäre Beheimatungen
1. Allgemeine Pädagogik / Bildungstheorie (institutionelle Heimat)
2. Posthumanismus / STS / Resilienz
3. Medienbildung / Medienpädagogik
4. Pädagogische Medienforschung / Medienwissenschaft
5. Kulturwissenschaft / Ästhetik

## Aktive Forschungsprojekte (siehe `projects.json`)
- Cultural Resilience (Research Programme 2020–2029)
- MetaKuBi (BMBF, 2024–2028)
- AI4ArtsEd (BMBF, 2024–2026)
- ComeArts (2023–2026)
- DiäS-KuBi (2023–2025)

## Offene Sonderfälle
- zkmb.de (nicht in OpenAlex, Scraper nötig)
- e-flux Journal (nicht in OpenAlex, Scraper nötig, stabile `/journal/<nr>/` Struktur)
- Vollständige Journal-Watchlist: `docs/journal_watchlist_full.md`

## Weiterführende Dokumentation
- `docs/mojo_2_grundorientierung.md` — **Pflicht-Vorlektüre** für MOJO 2.0: Plattform-Beschreibung, Backtest-Stand, 2.0-Konturen, 1.x-Erhalt-Festlegung, Anti-Drift
- `HANDOVER.md` — Aktueller Arbeitsstand, offene Themen, $43-Vorfall-Kontext
- `README.md` — Installations- und Nutzungsanleitung
- `ARCHITECTURE.md` — Detaillierte Architektur
- `ROADMAP.md` — Feature-Roadmap
- `DEVLOG.md` — Entwicklungshistorie
- `docs/context/` — Aufgebauter Arbeitskontext (Memory-Files)
- `docs/ui_entwurf.md` — UI-Konzept
