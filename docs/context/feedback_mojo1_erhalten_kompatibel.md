# MOJO 1.x bleibt code-seitig erhalten und kombinierbar

**Datum**: 2026-05-24 (Festlegung von Benjamin nach Bestätigung der
MOJO-2.0-Grundorientierung)

## Festlegung

MOJO-1.x-Code bleibt **vollständig erhalten und API-kompatibel**, auch wenn
einzelne Funktionen in der 2.0-Cascade nicht mehr aktiv aufgerufen werden.
Insbesondere die werk-explizierenden LLM-Runs (Opus-Agent mit Tool-Use über
`corpus.json` + `summaries.json`, Diskursraum-Trends, Multi-Linsen-Scout)
bleiben funktional und aufruffähig.

Begründung (Zitat Benjamin, 2026-05-24):

> „MoJo 1.0 wird code-seitig erhalten, auch wenn Funktionen schlafen, bleiben
> sie vollständig kompatibel, insbesondere LLM-Runs die Kernthesen [und]
> Werkbezogen explizieren. Ich behalte mir vor erst einmal zu schauen wie
> algorithmische Läufe am Ende funktionieren, und ggf. wird es zu Kombinationen
> kommen."

## Wann das greift

Greift überall, wo 2.0-Module bestehende 1.x-Pfade *berühren* (Refs-Pipeline,
Cascade-Vetos, Set-Features, neue Eskalations-Slots). Nicht: Tippfehler-
Korrekturen oder Bugfixes in 1.x-Code, die Verhalten oder Signatur nicht
ändern.

## Wie das anzuwenden ist

- **Additiv, nicht ersetzend**: 2.0-Module hängen sich ein, ohne bestehende
  Aufrufpfade umzustellen. Neue CLI-Sub-Befehle (z. B. `mojo refs`) ergänzen,
  vorhandene (`mojo digest`, `mojo trends`, `mojo scout`, `mojo fetch`,
  `mojo ingest`, `mojo backup`) bleiben unverändert.
- **Datenebenen orthogonal**: `corpus.json` und `summaries.json` bleiben in
  ihrer heutigen Form bestehen. Neue Datenebenen (z. B. `own_refs.db`) leben
  daneben, nicht darüber. Keine Migration von 1.x-Daten auf 2.0-Strukturen.
- **Signaturen stabil**: Funktionen in `journal_bot/agent.py`,
  `journal_bot/digest.py`, `journal_bot/trends.py`, `journal_bot/scout.py`,
  `journal_bot/citation_tracker.py` werden weder umbenannt noch in ihren
  Parameterlisten verändert. Interne Refaktorierungen sind okay, solange
  äußere Aufrufer (CLI, Tests, Web-UI) keine Anpassung brauchen.
- **Kein „algorithmifizieren" via Wrapper**: ein bestehender LLM-Run darf
  nicht durch einen algorithmischen Stub mit identischer Signatur ersetzt
  werden — auch nicht „temporär".
- **Re-Aktivierung muss trivial sein**: ein schlafender LLM-Run muss durch
  Konfigurations-Flag (in `profile.json` oder per CLI-Argument)
  wieder eingeschaltet werden können, ohne Code-Anpassung im jeweiligen Modul.
- **Kombinations-Vorbehalt**: Benjamin hat sich explizit vorbehalten, später
  Kombinationen aus algorithmischer 2.0-Cascade und werk-explizierenden
  1.x-LLM-Runs zu evaluieren (z. B. LLM nur für die Cascade-Restmenge, oder
  algorithmische Veto-Up + LLM-Verification). Solche Kombinationen müssen
  ohne API-Bruch möglich bleiben.

## Vor jedem 2.0-Commit fragen

1. Berührt der Commit einen bestehenden 1.x-Aufrufpfad?
2. Falls ja: bleibt die Signatur stabil? Bleibt der Aufruf möglich? Lässt sich
   das Verhalten per Flag in den 1.x-Zustand zurückschalten?
3. Falls nein: gut, nichts weiter zu prüfen.

## Verwandte Memories

- [feedback_mojo2_reframe_algorithmic.md](feedback_mojo2_reframe_algorithmic.md) —
  was 2.0 ist (algorithmisch, drei Reframes); ergänzt sich mit dieser
  Festlegung zu: 2.0 ist algorithmisch UND 1.x bleibt zusätzlich erhalten.
- [project_opensource_agent_workflows.md](project_opensource_agent_workflows.md) —
  Open-Source-Pfad fordert ohnehin sauber dokumentierte Module statt
  Einmal-Snapshots; passt zur Additivität.
- [decision_llm_scan_tool_architecture.md](decision_llm_scan_tool_architecture.md) —
  „Tool-Calling ist möglicher Qualitätsfaktor und darf nicht blind entfernt
  werden" — analoge Festlegung im Scan-Agent-Kontext.

## Verankerung im Repo

- `docs/mojo_2_grundorientierung.md` §4 — zentrale Festlegung im
  Grundorientierungs-Dokument.
- `HANDOVER.md` §0 (Header-Verweis) — Pflichtlektüre vor §1.
