"""Research Agent — Missed-References-Detektor für Textentwürfe.

Der User lädt einen Text/Stub hoch. Der Agent durchsucht die MOJO-DB
(17k+ Artikel) und den Forscher-Corpus (160 Publikationen) nach:
- fehlenden Referenzen
- relevanten Artikeln
- Gegenargumenten
- methodischen Parallelen
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from journal_bot.llm_client import build_client
from journal_bot.settings import (
    CORPUS_JSON,
    MODEL_AGENT,
    RESEARCHER_AREAS,
    RESEARCHER_INSTITUTION,
    RESEARCHER_NAME,
    SUMMARIES_JSON,
)
from journal_bot.store import ARTICLES_DB, Store

CONTEXT_SUMMARY_MODEL = "deepseek/deepseek-v3.2"
SHORT_CONTEXT_CHARS = 4000
CONTEXT_SUMMARY_INPUT_CHARS = 60000
CONTEXT_SUMMARY_OUTPUT_CHARS = 6000


def _load_summaries() -> dict:
    if SUMMARIES_JSON.exists():
        data = json.loads(SUMMARIES_JSON.read_text(encoding="utf-8"))
        # summaries.json wraps actual summaries under "summaries" key
        if isinstance(data, dict) and "summaries" in data:
            return data["summaries"]
        return data
    return {}


def _load_corpus_index() -> list[dict]:
    """Lightweight index: pub_id, title, authors, year, venue."""
    if not CORPUS_JSON.exists():
        return []
    data = json.loads(CORPUS_JSON.read_text(encoding="utf-8"))
    # corpus.json has {"publications": [...], "authored_all": [...], ...}
    pubs = data.get("publications", [])
    if not isinstance(pubs, list):
        return []
    return [
        {
            "pub_id": p.get("pub_id", ""),
            "title": p.get("title", ""),
            "authors": p.get("authors", []),
            "year": p.get("year"),
            "venue": p.get("venue", ""),
        }
        for p in pubs
        if isinstance(p, dict)
    ]


def _search_articles_by_text(query: str, limit: int = 30) -> list[dict]:
    """Search articles.db by title/abstract keywords. Returns lightweight dicts."""
    store = Store()
    keywords = [w.strip() for w in query.split() if len(w.strip()) > 2]
    if not keywords:
        return []

    # Build LIKE conditions
    conditions = []
    params = []
    for kw in keywords[:5]:  # max 5 keywords
        conditions.append(
            "(title LIKE ? OR abstract LIKE ? OR openalex_abstract LIKE ?)"
        )
        pattern = f"%{kw}%"
        params.extend([pattern, pattern, pattern])

    where = " AND ".join(conditions)
    sql = (
        f"SELECT id, journal_short, journal_full, title, authors_json, abstract, "
        f"doi, year, agent_verdict, agent_entry_json, cost_usd "
        f"FROM articles WHERE {where} AND agent_verdict IS NOT NULL "
        f"ORDER BY year DESC LIMIT ?"
    )
    params.append(limit)

    with store._conn() as c:
        rows = c.execute(sql, params).fetchall()

    results = []
    for r in rows:
        entry = None
        if r["agent_entry_json"]:
            try:
                entry = json.loads(r["agent_entry_json"])
            except Exception:
                pass
        results.append({
            "id": r["id"],
            "journal": r["journal_full"] or r["journal_short"],
            "title": r["title"],
            "authors": json.loads(r["authors_json"]) if r["authors_json"] else [],
            "year": r["year"],
            "doi": r["doi"],
            "verdict": r["agent_verdict"],
            "kernthese": entry.get("kernthese", "") if entry else "",
        })
    return results


def _search_articles_by_verdict(
    verdicts: list[str], limit: int = 50
) -> list[dict]:
    """Get recent high-relevance articles."""
    store = Store()
    placeholders = ",".join("?" * len(verdicts))
    sql = (
        f"SELECT id, journal_short, journal_full, title, authors_json, "
        f"doi, year, agent_verdict, agent_entry_json "
        f"FROM articles WHERE agent_verdict IN ({placeholders}) "
        f"ORDER BY year DESC LIMIT ?"
    )
    params = list(verdicts) + [limit]

    with store._conn() as c:
        rows = c.execute(sql, params).fetchall()

    results = []
    for r in rows:
        entry = None
        if r["agent_entry_json"]:
            try:
                entry = json.loads(r["agent_entry_json"])
            except Exception:
                pass
        results.append({
            "id": r["id"],
            "journal": r["journal_full"] or r["journal_short"],
            "title": r["title"],
            "authors": json.loads(r["authors_json"]) if r["authors_json"] else [],
            "year": r["year"],
            "doi": r["doi"],
            "verdict": r["agent_verdict"],
            "kernthese": entry.get("kernthese", "") if entry else "",
            "bezuege": entry.get("bezuege", []) if entry else [],
        })
    return results


TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_mojo_db",
            "description": (
                "Search the MOJO article database (17,000+ screened journal articles) "
                "by keywords. Returns title, journal, year, verdict, and kernthese. "
                "Use this to find articles relevant to the user's text."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Space-separated keywords to search in title and abstract.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results (default 20).",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_high_relevance_articles",
            "description": (
                "Get recent articles rated 'lesenswert' or 'pflichtlektuere' by the MOJO agent. "
                "These are the most relevant articles to the researcher's work."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Max results (default 30).",
                    },
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_article_detail",
            "description": (
                "Read the full agent analysis of a specific article by its MOJO ID. "
                "Returns kernthese, bezuege, bemerkenswert, verdict reasoning."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "article_id": {
                        "type": "string",
                        "description": "The MOJO article ID (32-char hex).",
                    },
                },
                "required": ["article_id"],
            },
        },
    },
]


def _execute_tool(name: str, args: dict) -> str:
    """Execute a tool call and return result as string."""
    if name == "search_mojo_db":
        results = _search_articles_by_text(
            args.get("query", ""),
            limit=args.get("limit", 20),
        )
        if not results:
            return "Keine Treffer gefunden."
        lines = []
        for r in results:
            authors_str = ", ".join(r["authors"][:2])
            if len(r["authors"]) > 2:
                authors_str += " et al."
            lines.append(
                f"- [{r['verdict'].upper()}] {r['title']}\n"
                f"  {authors_str} ({r['year']}) — {r['journal']}\n"
                f"  ID: {r['id']}"
                + (f"\n  Kernthese: {r['kernthese'][:200]}" if r["kernthese"] else "")
            )
        return f"{len(results)} Treffer:\n\n" + "\n\n".join(lines)

    elif name == "get_high_relevance_articles":
        results = _search_articles_by_verdict(
            ["lesenswert", "pflichtlektuere"],
            limit=args.get("limit", 30),
        )
        if not results:
            return "Keine hochrelevanten Artikel gefunden."
        lines = []
        for r in results:
            authors_str = ", ".join(r["authors"][:2])
            if len(r["authors"]) > 2:
                authors_str += " et al."
            bezuege_str = ""
            if r.get("bezuege"):
                bezuege_str = "\n  Bezüge: " + "; ".join(
                    b.get("pub_kurz", "") + " (" + b.get("relation", "") + ")"
                    for b in r["bezuege"][:3]
                )
            lines.append(
                f"- [{r['verdict'].upper()}] {r['title']}\n"
                f"  {authors_str} ({r['year']}) — {r['journal']}\n"
                f"  ID: {r['id']}"
                + (f"\n  Kernthese: {r['kernthese'][:200]}" if r["kernthese"] else "")
                + bezuege_str
            )
        return f"{len(results)} hochrelevante Artikel:\n\n" + "\n\n".join(lines)

    elif name == "read_article_detail":
        article_id = args.get("article_id", "")
        store = Store()
        a = store.get(article_id)
        if not a:
            return f"Artikel {article_id} nicht gefunden."
        entry = a.agent_entry
        if isinstance(entry, str):
            entry = json.loads(entry)
        if not entry:
            return f"Keine Agent-Analyse für {a.title}."

        parts = [
            f"Titel: {a.title}",
            f"Journal: {a.journal_full or a.journal_short} ({a.year})",
            f"DOI: {a.doi}" if a.doi else "",
            f"Verdict: {a.agent_verdict}",
            f"Begründung: {entry.get('verdict_begruendung', '')}",
            f"\nKernthese: {entry.get('kernthese', '')}",
        ]
        if entry.get("bezuege"):
            parts.append("\nBezüge:")
            for b in entry["bezuege"]:
                parts.append(
                    f"  - {b.get('pub_kurz', '?')} ({b.get('relation', '?')}): "
                    f"{b.get('bezug', '')}"
                )
        if entry.get("bemerkenswert"):
            parts.append("\nBemerkenswert:")
            for b in entry["bemerkenswert"]:
                parts.append(f"  - {b}")
        if entry.get("theoretisch_methodisch"):
            parts.append(f"\nMethodisch: {entry['theoretisch_methodisch']}")

        return "\n".join(p for p in parts if p)

    return f"Unbekanntes Tool: {name}"


def _trim_text(text: str, max_chars: int, suffix: str = "\n\n[gekürzt]") -> str:
    """Trim text at a sensible boundary."""
    text = text.strip()
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    boundary = max(cut.rfind("\n\n"), cut.rfind("\n"), cut.rfind(". "))
    if boundary >= int(max_chars * 0.7):
        cut = cut[:boundary].rstrip()
    else:
        cut = cut.rstrip()
    return cut + suffix


def _fallback_context_digest(text: str) -> str:
    """Cheap local fallback when no LLM summary is available."""
    cleaned = re.sub(r"\n{3,}", "\n\n", text).strip()
    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    if not lines:
        return ""

    selected: list[str] = []
    total_chars = 0
    for line in lines:
        if line.startswith(("http://", "https://")):
            continue
        selected.append(line)
        total_chars += len(line) + 1
        if total_chars >= 2500 or len(selected) >= 18:
            break

    if not selected:
        selected = lines[:12]

    digest = "\n".join(selected)
    return _trim_text(
        "Automatisch komprimierter Arbeitskontext (Fallback ohne LLM):\n\n"
        + digest,
        3200,
    )


def _usage_cost(usage: Any, model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Prefer OpenRouter's reported cost, fall back only when necessary."""
    usage_dump = usage.model_dump() if hasattr(usage, "model_dump") else {}
    reported_cost = usage_dump.get("cost")
    if reported_cost is not None:
        return float(reported_cost)
    if "claude-opus" in model:
        return (prompt_tokens * 15.0 + completion_tokens * 75.0) / 1_000_000
    return 0.0


def prepare_context(
    text: str,
    model: str = CONTEXT_SUMMARY_MODEL,
    allow_llm: bool = True,
) -> dict[str, Any]:
    """Prepare a compact context dossier for the research agent."""
    raw_text = text.strip()
    if not raw_text:
        return {
            "raw_text": "",
            "raw_chars": 0,
            "prompt_context": "",
            "prompt_chars": 0,
            "source": "empty",
            "model": "",
            "tokens_used": 0,
            "cost_usd": 0.0,
        }

    if len(raw_text) <= SHORT_CONTEXT_CHARS:
        prompt_context = _trim_text(raw_text, SHORT_CONTEXT_CHARS, suffix="")
        return {
            "raw_text": raw_text,
            "raw_chars": len(raw_text),
            "prompt_context": prompt_context,
            "prompt_chars": len(prompt_context),
            "source": "raw_short",
            "model": "",
            "tokens_used": 0,
            "cost_usd": 0.0,
        }

    if allow_llm:
        try:
            client = build_client()
            source_text = _trim_text(raw_text, CONTEXT_SUMMARY_INPUT_CHARS)
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Du verdichtest wissenschaftliche Textentwürfe für einen "
                            "Rechercheagenten. Extrahiere nur die such- und argumentationsrelevanten "
                            "Informationen. Antworte auf Deutsch, stark komprimiert, in Markdown."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            "Erstelle ein kurzes Arbeitsdossier für einen Literatur-Rechercheagenten.\n"
                            "Ziel: Der Agent soll fehlende Referenzen, relevante Artikel, "
                            "Gegenargumente und methodische Parallelen finden können, ohne den "
                            "Volltext erneut zu sehen.\n\n"
                            "Format:\n"
                            "## Fokus\n"
                            "- Texttyp/Ziel\n"
                            "- Zentrale Frage oder These\n"
                            "- 3-6 Kernargumente\n"
                            "## Schlüsselbegriffe\n"
                            "- 8-15 Suchbegriffe oder Query-Phrasen\n"
                            "## Vorhandene Referenzen und Debatten\n"
                            "- genannte Autor:innen, Werke, Schulen, Begriffe\n"
                            "## Empirischer/methodischer Kontext\n"
                            "- Material, Feld, Methoden, Fallbeispiele\n"
                            "## Offene Anschlussstellen\n"
                            "- Wo weitere Literatur besonders nützlich wäre\n\n"
                            "Maximal ca. 700 Wörter, keine Ausschmückung, keine Wiederholung.\n\n"
                            "TEXT:\n"
                            f"{source_text}"
                        ),
                    },
                ],
                max_tokens=1200,
                extra_body={"transforms": ["middle-out"]},
            )
            content = (response.choices[0].message.content or "").strip()
            if content:
                usage = getattr(response, "usage", None)
                prompt_tokens = usage.prompt_tokens if usage else 0
                completion_tokens = usage.completion_tokens if usage else 0
                prompt_context = _trim_text(content, CONTEXT_SUMMARY_OUTPUT_CHARS)
                return {
                    "raw_text": raw_text,
                    "raw_chars": len(raw_text),
                    "prompt_context": prompt_context,
                    "prompt_chars": len(prompt_context),
                    "source": "llm_summary",
                    "model": model,
                    "tokens_used": prompt_tokens + completion_tokens,
                    "cost_usd": _usage_cost(
                        usage,
                        model,
                        prompt_tokens,
                        completion_tokens,
                    ) if usage else 0.0,
                }
        except Exception:
            pass

    prompt_context = _fallback_context_digest(raw_text)
    return {
        "raw_text": raw_text,
        "raw_chars": len(raw_text),
        "prompt_context": prompt_context,
        "prompt_chars": len(prompt_context),
        "source": "fallback_excerpt" if allow_llm else "legacy_fallback",
        "model": "",
        "tokens_used": 0,
        "cost_usd": 0.0,
    }


def build_system_prompt(user_context: str | None = None) -> str:
    """Build system prompt for the research agent."""
    summaries = _load_summaries()
    corpus_index = _load_corpus_index()

    # DB stats
    store = Store()
    stats = store.stats()

    prompt_parts = [
        f"Du bist der MOJO Research Agent für {RESEARCHER_NAME} "
        f"({RESEARCHER_INSTITUTION}).",
        f"Forschungsgebiete: {RESEARCHER_AREAS}.",
        "",
        "Deine Aufgabe: Du hilfst beim Schreiben wissenschaftlicher Texte, indem du:",
        "1. Fehlende Referenzen identifizierst (Missed References)",
        "2. Relevante Artikel aus der MOJO-Datenbank findest",
        "3. Gegenargumente und Widersprüche in der Literatur aufzeigst",
        "4. Methodische Parallelen und Zugänge empfiehlst",
        "",
        f"Du hast Zugriff auf {stats['total']} gescreente Artikel "
        f"({stats['processed']} mit Agent-Analyse) und "
        f"{len(corpus_index)} eigene Publikationen.",
        "",
        "=== EIGENE PUBLIKATIONEN ===",
    ]

    # Add publication index
    for pub in corpus_index:
        authors = ", ".join(pub["authors"][:2])
        prompt_parts.append(
            f"- {pub['pub_id']}: {pub['title']} ({authors}, {pub['year']}) — {pub['venue']}"
        )

    # Add summaries if available
    if summaries:
        prompt_parts.append("")
        prompt_parts.append("=== KURZPROFILE DER EIGENEN PUBLIKATIONEN ===")
        for pub_id, s in sorted(
            summaries.items(), key=lambda kv: kv[1].get("year", 0), reverse=True
        ):
            prompt_parts.append(f"\n[{pub_id}] {s.get('title', '?')} ({s.get('year', '?')})")
            prompt_parts.append(s.get("summary", ""))

    prompt_parts.extend([
        "",
        "=== REGELN ===",
        "- Antworte auf Deutsch, sachlich und präzise. Kein Pampering, keine Emojis,",
        "  keine emotionale Kommunikation. Die User sind Akademiker*innen.",
        "- Nutze die Tools, um die MOJO-DB zu durchsuchen. Halluziniere keine Artikel.",
        "- Wenn du Artikel empfiehlst, gib immer Titel, Autoren, Jahr und Journal an.",
        "- Verlinke Artikel als /article/<id> für die MOJO-Detailseite.",
        "- Unterscheide zwischen: echten Bezügen (substantive connections) und "
        "  thematischen Überlappungen (shared reference frames).",
        "- Sei ehrlich über die Grenzen deiner Suche. LIKE-Suche findet nicht alles.",
        "- Wenn der Text klar genug ist, mach proaktiv mehrere Suchen mit "
        "  verschiedenen Keywords.",
    ])

    if user_context:
        prompt_parts.extend([
            "",
            "=== AKTUELLER ARBEITSKONTEXT DES USERS ===",
            "Das Folgende ist ein kondensiertes Dossier des hochgeladenen Texts.",
            "Nutze es als Such- und Argumentkontext; nenne Unsicherheiten offen, wenn Details fehlen.",
            "",
            user_context,
        ])

    return "\n".join(prompt_parts)


def chat(
    message: str,
    history: list[dict[str, str]],
    user_context: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """Run a single chat turn with tool use.

    Returns dict with: content, html, tokens_used, cost_usd
    """
    client = build_client()
    model = model or MODEL_AGENT
    system_prompt = build_system_prompt(user_context)

    # Build messages
    messages = []
    for h in history[-20:]:  # Keep last 20 turns
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": message})

    total_input = 0
    total_output = 0
    total_cost = 0.0
    max_iterations = 5
    system_message = {
        "role": "system",
        "content": [
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ],
    }

    for _ in range(max_iterations):
        response = client.chat.completions.create(
            model=model,
            messages=[system_message] + messages,
            tools=TOOL_DEFINITIONS,
            max_tokens=4096,
            extra_body={"transforms": ["middle-out"]},
        )

        choice = response.choices[0]
        usage = getattr(response, "usage", None)
        if usage:
            prompt_tokens = usage.prompt_tokens or 0
            completion_tokens = usage.completion_tokens or 0
            total_input += prompt_tokens
            total_output += completion_tokens
            total_cost += _usage_cost(
                usage,
                model,
                prompt_tokens,
                completion_tokens,
            )

        # If no tool calls, we're done
        tool_calls = getattr(choice.message, "tool_calls", None) or []
        if not tool_calls:
            content = choice.message.content or ""
            break

        # Process tool calls
        messages.append({
            "role": "assistant",
            "content": choice.message.content or "",
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in tool_calls
            ],
        })
        for tc in tool_calls:
            try:
                args = json.loads(tc.function.arguments)
            except Exception:
                args = {}
            result = _execute_tool(tc.function.name, args)
            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result,
            })
    else:
        content = messages[-1].get("content", "") if messages else "Max iterations erreicht."
        if hasattr(messages[-1], "content"):
            content = messages[-1].content or content

    return {
        "content": content,
        "tokens_used": total_input + total_output,
        "tokens_in": total_input,
        "tokens_out": total_output,
        "cost_usd": total_cost,
    }
