"""§2.5 Volltext-LLM-Eskalations-Slot (NICHT Default!).

Für Items, die nach allen Cascade-Regeln (Vorfilter + own_coupling + adversarial
veto) noch in der Unklar-Zone sind — typischerweise selection_mode in
(complementarity, similarity, mixed) mit verdict=scannen/ignorieren und
einer Restspannung im Signal-Profil. Höchstens ~5–10 % der Items, manuell
oder wöchentlicher Batch.

Module:
- `select`: SQL-Selektoren auf articles.db (welche Items eskalieren?)
- `fulltext`: OpenAlex-best-OA-Location + Unpaywall-Fallback (PDF + Text)

LLM-Aufruf bleibt separat — siehe HANDOVER §2.5: KEINE Batch-LLM-Calls ohne
vorherige Einzelkosten-Verifikation.
"""

from journal_bot.escalation.fulltext import (
    FetchResult,
    cache_paths,
    extract_fulltext,
    fetch_fulltext_for_article,
)
from journal_bot.escalation.select import (
    EscalationCandidate,
    select_candidates,
)

__all__ = [
    "EscalationCandidate",
    "FetchResult",
    "cache_paths",
    "extract_fulltext",
    "fetch_fulltext_for_article",
    "select_candidates",
]
