"""Multi-Source-Refs-Pipeline für MOJO 2.0 (§3.1 der Grundorientierung).

Liest eigene Publikationen aus mehreren Quellen (Zotero-Collections, freie
PDF-Ordner), extrahiert Literaturlisten, löst DOIs gegen OpenAlex auf,
klassifiziert in Diskursräume, persistiert idempotent nach `own_refs.db`.

Keine LLM-Calls. Additiv zu MOJO 1.x (`corpus.py`, `summaries.json` etc.):
diese Pipeline ersetzt nichts, sondern legt eine neue Datenebene daneben, an
die später Cascade-Veto-Regeln andocken.

Architektur-Referenzen:
- `docs/mojo_2_grundorientierung.md` §3.1
- `HANDOVER.md` §1 (Akzeptanzkriterien, Pipeline-Stufen)

Public API wird in den Submodulen aufgebaut. Ein- bzw. Re-Exports erfolgen
hier, sobald Build-Orchestrator und Store-Layer fertig sind.
"""
