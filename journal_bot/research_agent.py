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
SEARCH_STOPWORDS = {
    "aber", "about", "against", "all", "als", "and", "an", "are", "auf", "aus",
    "bei", "beim", "beyond", "bitte", "can", "contra", "das", "dass", "dem",
    "den", "der", "des", "die", "dies", "diese", "diesem", "diesen", "dieser",
    "doch", "durch", "ein", "eine", "einer", "eines", "er", "es", "etc", "for",
    "from", "für", "gegen", "gibt", "hat", "have", "how", "ich", "im", "in",
    "into", "ist", "kann", "können", "mit", "nach", "nicht", "oder", "of", "on",
    "relevant", "sind", "so", "such", "text", "texte", "this", "to", "und", "was",
    "welche", "welcher", "welches", "welchen", "which", "wie", "wo", "zu",
    "zum", "zur",
}
QUESTION_NOISE = {
    "agent", "artikel", "artikeln", "bezug", "bezüge", "db", "entwurf",
    "entwurfs", "fehlen", "fehlende", "frage", "literatur", "missed", "mojo",
    "ref", "referenz", "referenzen", "recherche", "research", "soll", "suchen",
    "suche", "thema", "themen", "user",
}
ARGUMENT_TERM_NOISE = {
    "als", "auch", "braucht", "damit", "deuten", "dies", "diese", "dieser",
    "diesem", "diesen", "ein", "eine", "einer", "eines", "fragen", "greifen",
    "hat", "hier", "ihr", "ihre", "ihren", "ihres", "ihm", "ihn", "kurz", "mehr",
    "nicht", "noch", "nur", "problem", "probleme", "relevant", "sein", "sind",
    "sie", "soll", "sollte", "sondern", "stärker", "ueber", "und", "unter",
    "verstehen", "viel", "von", "vor", "warum", "weil", "werden", "wider",
    "widerspruch", "widersprüche", "wird", "wie", "wir", "zwischen",
}
GENERIC_SEARCH_TERMS = {
    "art", "arts", "bildung", "creative", "creativity", "culture", "cultural",
    "digital", "education", "educational", "kunst", "learning", "media", "school",
}
VERDICT_SCORE = {
    "pflichtlektuere": 6,
    "lesenswert": 4,
    "scannen": 1,
    "ignorieren": -4,
}
FIELD_WEIGHTS = {
    "title": 5,
    "authors": 4,
    "topics": 4,
    "concepts": 3,
    "signal_group": 3,
    "subgroup": 3,
    "kernthese": 2,
    "abstract": 2,
    "entry": 1,
}


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


def _normalize_search_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").lower()).strip()


def _extract_search_terms(text: str, *, min_len: int = 3) -> list[str]:
    tokens = re.findall(r"[A-Za-zÀ-ÿ0-9][A-Za-zÀ-ÿ0-9_\-/\.]*", text.lower())
    terms: list[str] = []
    for token in tokens:
        token = token.strip("._-/")
        if len(token) < min_len:
            continue
        if token in SEARCH_STOPWORDS or token in QUESTION_NOISE:
            continue
        if token.isdigit():
            continue
        terms.append(token)
    deduped: list[str] = []
    for term in terms:
        if term not in deduped:
            deduped.append(term)
    return deduped


def _clean_argument_terms(terms: list[str]) -> list[str]:
    cleaned: list[str] = []
    for term in terms:
        if term in ARGUMENT_TERM_NOISE:
            continue
        if term not in cleaned:
            cleaned.append(term)
    return cleaned


def _row_to_search_result(
    row,
    *,
    score: float = 0.0,
    match_reasons: list[str] | None = None,
) -> dict:
    entry = None
    if row["agent_entry_json"]:
        try:
            entry = json.loads(row["agent_entry_json"])
        except Exception:
            pass

    topics = []
    concepts = []
    citation_hits = []
    if row["openalex_topics"]:
        try:
            topics = json.loads(row["openalex_topics"])
        except Exception:
            topics = []
    if row["openalex_concepts"]:
        try:
            concepts = json.loads(row["openalex_concepts"])
        except Exception:
            concepts = []
    if row["citation_hits_json"]:
        try:
            citation_hits = json.loads(row["citation_hits_json"])
        except Exception:
            citation_hits = []

    return {
        "id": row["id"],
        "journal": row["journal_full"] or row["journal_short"],
        "title": row["title"],
        "authors": json.loads(row["authors_json"]) if row["authors_json"] else [],
        "year": row["year"],
        "doi": row["doi"],
        "verdict": row["agent_verdict"],
        "verdict_reason": entry.get("verdict_begruendung", "") if entry else "",
        "kernthese": entry.get("kernthese", "") if entry else "",
        "bezuege": entry.get("bezuege", []) if entry else [],
        "topics": [t.get("name", "") for t in topics if isinstance(t, dict) and t.get("name")],
        "concepts": [c.get("name", "") for c in concepts if isinstance(c, dict) and c.get("name")],
        "signal_group": row["signal_group"] or "",
        "suggested_subgroup": row["suggested_subgroup"] or "",
        "discourse_indicator": row["discourse_indicator"] or "",
        "citation_hits_count": len(citation_hits),
        "score": score,
        "match_reasons": match_reasons or [],
    }


def _candidate_search_rows(terms: list[str], limit: int = 220):
    if not terms:
        return []

    store = Store()
    fields = [
        "title",
        "authors_json",
        "abstract",
        "openalex_abstract",
        "agent_entry_json",
        "openalex_topics",
        "openalex_concepts",
        "signal_group",
        "suggested_subgroup",
        "suggested_subgroup_reason",
        "citation_hits_json",
    ]
    conditions = []
    params: list[Any] = []
    for term in terms[:12]:
        pattern = f"%{term.lower()}%"
        field_cond = " OR ".join(f"LOWER(COALESCE({field}, '')) LIKE ?" for field in fields)
        conditions.append(f"({field_cond})")
        params.extend([pattern] * len(fields))

    sql = (
        "SELECT id, journal_short, journal_full, title, authors_json, abstract, openalex_abstract, doi, year, "
        "agent_verdict, agent_entry_json, cost_usd, openalex_topics, openalex_concepts, "
        "signal_group, suggested_subgroup, discourse_indicator, citation_hits_json "
        "FROM articles WHERE agent_verdict IS NOT NULL "
        f"AND ({' OR '.join(conditions)}) "
        "ORDER BY year DESC LIMIT ?"
    )
    params.append(limit)

    with store._conn() as c:
        return c.execute(sql, params).fetchall()


def _score_search_row(row, terms: list[str], phrases: list[str], intent: str) -> tuple[float, list[str]]:
    entry = {}
    if row["agent_entry_json"]:
        try:
            entry = json.loads(row["agent_entry_json"])
        except Exception:
            entry = {}

    topics = []
    concepts = []
    citation_hits = []
    if row["openalex_topics"]:
        try:
            topics = json.loads(row["openalex_topics"])
        except Exception:
            topics = []
    if row["openalex_concepts"]:
        try:
            concepts = json.loads(row["openalex_concepts"])
        except Exception:
            concepts = []
    if row["citation_hits_json"]:
        try:
            citation_hits = json.loads(row["citation_hits_json"])
        except Exception:
            citation_hits = []

    def _blob(value) -> str:
        if isinstance(value, str):
            return _normalize_search_text(value)
        if isinstance(value, list):
            values = []
            for item in value:
                if isinstance(item, dict):
                    values.extend(str(v) for v in item.values() if isinstance(v, str))
                else:
                    values.append(str(item))
            return _normalize_search_text(" ".join(values))
        if isinstance(value, dict):
            return _normalize_search_text(
                " ".join(str(v) for v in value.values() if isinstance(v, str))
            )
        return ""

    field_blobs = {
        "title": _blob(row["title"]),
        "authors": _blob(row["authors_json"]),
        "abstract": _blob((row["abstract"] or "") + " " + (row["openalex_abstract"] or "")),
        "topics": _blob(topics),
        "concepts": _blob(concepts),
        "signal_group": _blob((row["signal_group"] or "") + " " + (row["discourse_indicator"] or "")),
        "subgroup": _blob(row["suggested_subgroup"] or ""),
        "kernthese": _blob(entry.get("kernthese", "")),
        "entry": _blob(entry),
    }

    score = float(VERDICT_SCORE.get(row["agent_verdict"], 0))
    term_weights = {
        term: max(0.45, 2.2 - idx * 0.12) * (0.55 if term in GENERIC_SEARCH_TERMS else 1.0)
        for idx, term in enumerate(terms)
    }
    phrase_weights = {
        phrase: max(1.6, 3.0 - idx * 0.2)
        for idx, phrase in enumerate(phrases)
    }
    matched_terms: dict[str, list[str]] = {}
    specific_hits = 0
    for label, blob in field_blobs.items():
        hits = [term for term in terms if term in blob]
        phrase_hits = [phrase for phrase in phrases if phrase and phrase in blob]
        all_hits = list(dict.fromkeys(hits + phrase_hits))
        if all_hits:
            hit_weight = sum(term_weights.get(term, 1.0) for term in hits)
            hit_weight += sum(phrase_weights.get(phrase, 2.0) for phrase in phrase_hits)
            score += FIELD_WEIGHTS.get(label, 1) * hit_weight
            matched_terms[label] = all_hits[:4]
            specific_hits += sum(1 for term in hits if term not in GENERIC_SEARCH_TERMS)
            specific_hits += len(phrase_hits)

    if row["year"]:
        score += max(min((int(row["year"]) - 2018) * 0.15, 1.5), 0)
    if citation_hits:
        score += 1.5
    if entry.get("bezuege"):
        score += min(len(entry["bezuege"]), 3) * 0.75
    if row["discourse_indicator"] == "starker_indikator":
        score += 1.25
    if intent == "methods":
        method_terms = {"method", "methods", "methodik", "methode", "ethnograph", "interview", "analyse", "praxe"}
        if any(term in field_blobs["abstract"] or term in field_blobs["entry"] for term in method_terms):
            score += 2.0
    elif intent == "counter":
        if "widerspricht" in field_blobs["entry"] or "krit" in field_blobs["entry"]:
            score += 2.0
    if matched_terms and specific_hits == 0:
        score -= 3.0

    reasons: list[str] = []
    label_map = {
        "title": "Titel",
        "authors": "Autor:innen",
        "topics": "Topics",
        "concepts": "Konzepte",
        "signal_group": "Signalgruppe",
        "subgroup": "Sub-Motiv",
        "kernthese": "Kernthese",
        "abstract": "Abstract",
        "entry": "Agent-Analyse",
    }
    for key in ["title", "topics", "concepts", "signal_group", "subgroup", "kernthese", "abstract", "authors"]:
        if key in matched_terms:
            reasons.append(f"{label_map[key]}: {', '.join(matched_terms[key][:3])}")
    if citation_hits:
        reasons.append("zitiert Benjamin")
    if entry.get("bezuege"):
        first = entry["bezuege"][0]
        pub = first.get("pub_kurz", "")
        relation = first.get("relation", "")
        if pub:
            reasons.append(f"Agent-Bezug: {pub} ({relation})")

    return score, reasons[:4]


def _parse_context_sections(user_context: str | None) -> dict[str, list[str]]:
    if not user_context:
        return {}

    aliases = {
        "argumentationseinheiten": "argument_units",
        "argumentative einheiten": "argument_units",
        "argumenteinheiten": "argument_units",
        "argumentationskomplexe": "argument_units",
        "fokus": "focus",
        "schlüsselbegriffe": "keywords",
        "schlusselbegriffe": "keywords",
        "vorhandene referenzen und debatten": "references",
        "empirischer/methodischer kontext": "methods",
        "offene anschlussstellen": "gaps",
    }
    sections: dict[str, list[str]] = {}
    current = ""
    for raw_line in user_context.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("## "):
            current = aliases.get(_normalize_search_text(line[3:]), "")
            if current and current not in sections:
                sections[current] = []
            continue
        if not current:
            continue
        if line.startswith("- "):
            line = line[2:].strip()
        sections.setdefault(current, []).append(line)
    return sections


def _derive_argument_units_from_text(prompt_context: str) -> list[str]:
    sections = _parse_context_sections(prompt_context)
    units: list[str] = []

    def _add(items: list[str], prefix: str = "") -> None:
        for item in items:
            clean = item.strip(" -")
            if not clean:
                continue
            text = f"{prefix}{clean}" if prefix else clean
            if len(text) < 20:
                continue
            if text not in units:
                units.append(text)

    if sections.get("argument_units"):
        _add(sections["argument_units"])
    if not units:
        _add(sections.get("focus", []))
    if len(units) < 5:
        _add(sections.get("gaps", []), prefix="Offene Anschlussstelle: ")
    if len(units) < 6:
        _add(sections.get("methods", []), prefix="Methodischer Komplex: ")
    if len(units) < 6:
        _add(sections.get("references", []), prefix="Debattenkontext: ")

    if not units:
        paragraphs = [
            line.strip() for line in prompt_context.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        _add(paragraphs[:6])

    return units[:6]


def _ensure_argument_units(prompt_context: str) -> tuple[str, list[str]]:
    units = _derive_argument_units_from_text(prompt_context)
    if not units:
        return prompt_context, []

    sections = _parse_context_sections(prompt_context)
    if sections.get("argument_units"):
        return prompt_context, units

    extra = "\n".join(["## Argumenteinheiten"] + [f"- {unit}" for unit in units])
    merged = prompt_context.rstrip()
    if merged:
        merged += "\n\n" + extra
    else:
        merged = extra
    return merged, units


def _detect_search_intent(message: str) -> str:
    msg = _normalize_search_text(message)
    if any(token in msg for token in ["methode", "methodisch", "zugang", "methodological", "method"]):
        return "methods"
    if any(token in msg for token in ["gegenargument", "widerspruch", "kritik", "counter", "opposition"]):
        return "counter"
    if any(token in msg for token in ["fehl", "referenz", "bezug", "missed"]):
        return "missing_refs"
    if any(token in msg for token in ["relevant", "anschluss", "welche artikel", "relevante artikel"]):
        return "relevant"
    return "general"


def _build_search_plan(message: str, user_context: str | None = None) -> dict[str, Any]:
    intent = _detect_search_intent(message)
    sections = _parse_context_sections(user_context)
    message_terms = _extract_search_terms(message)
    phrases: list[str] = []
    terms: list[str] = []

    def _add_items(items: list[str], *, phrase_limit: int, term_limit: int) -> None:
        for item in items[:phrase_limit]:
            clean = item.strip()
            if clean and len(clean) >= 4 and clean not in phrases:
                phrases.append(clean)
        for item in items[:term_limit]:
            for term in _extract_search_terms(item):
                if term not in terms:
                    terms.append(term)

    if intent == "methods":
        _add_items(sections.get("methods", []), phrase_limit=5, term_limit=5)
        _add_items(sections.get("keywords", []), phrase_limit=4, term_limit=6)
    elif intent == "counter":
        _add_items(sections.get("focus", []), phrase_limit=4, term_limit=5)
        _add_items(sections.get("gaps", []), phrase_limit=4, term_limit=5)
        _add_items(sections.get("keywords", []), phrase_limit=4, term_limit=5)
    elif intent == "missing_refs":
        _add_items(sections.get("gaps", []), phrase_limit=5, term_limit=5)
        _add_items(sections.get("references", []), phrase_limit=4, term_limit=4)
        _add_items(sections.get("keywords", []), phrase_limit=5, term_limit=6)
        _add_items(sections.get("focus", []), phrase_limit=3, term_limit=4)
    else:
        _add_items(sections.get("keywords", []), phrase_limit=6, term_limit=8)
        _add_items(sections.get("focus", []), phrase_limit=4, term_limit=5)

    for term in message_terms:
        if term not in terms:
            terms.append(term)

    specific_terms = [term for term in terms if term not in GENERIC_SEARCH_TERMS]
    generic_terms = [term for term in terms if term in GENERIC_SEARCH_TERMS]
    if len(specific_terms) >= 4:
        terms = specific_terms[:10] + generic_terms[:2]

    return {
        "intent": intent,
        "phrases": phrases[:8],
        "terms": terms[:14],
    }


def _build_argument_plan(
    unit: str,
    intent: str,
    user_context: str | None = None,
) -> dict[str, Any]:
    """Build a tighter search plan for one argumentative unit."""
    terms = _clean_argument_terms(_extract_search_terms(unit))
    phrases = [unit.strip()] if unit.strip() else []

    # Only supplement lightly from the global keyword pool if the unit is too thin.
    if len(terms) < 5 and user_context:
        sections = _parse_context_sections(user_context)
        for bucket in ("keywords", "references", "methods", "gaps"):
            for item in sections.get(bucket, [])[:4]:
                for term in _extract_search_terms(item):
                    if term not in terms:
                        terms.append(term)
                    if len(terms) >= 8:
                        break
                if len(terms) >= 8:
                    break
            if len(terms) >= 8:
                break
    terms = _clean_argument_terms(terms)

    specific_terms = [term for term in terms if term not in GENERIC_SEARCH_TERMS]
    generic_terms = [term for term in terms if term in GENERIC_SEARCH_TERMS]
    if len(specific_terms) >= 3:
        terms = specific_terms[:8] + generic_terms[:2]

    return {
        "intent": intent,
        "phrases": phrases[:3],
        "terms": terms[:10],
        "argument_unit": unit,
    }


def _search_articles_by_plan(plan: dict[str, Any], limit: int = 12) -> list[dict]:
    terms = plan.get("terms") or []
    phrases = [_normalize_search_text(p) for p in (plan.get("phrases") or []) if p.strip()]
    rows = _candidate_search_rows(list(dict.fromkeys(terms + phrases)), limit=220)

    scored: list[dict] = []
    for row in rows:
        score, reasons = _score_search_row(row, terms, phrases, plan.get("intent", "general"))
        if score <= 0:
            continue
        scored.append(_row_to_search_result(row, score=score, match_reasons=reasons))

    non_ignored = [item for item in scored if item["verdict"] != "ignorieren"]
    if non_ignored:
        scored = non_ignored

    scored.sort(
        key=lambda item: (
            -item["score"],
            -VERDICT_SCORE.get(item["verdict"], 0),
            -(item["year"] or 0),
        )
    )
    return scored[:limit]


def _format_search_results(results: list[dict], *, include_reasons: bool = False) -> str:
    lines = []
    for r in results:
        authors_str = ", ".join(r["authors"][:2])
        if len(r["authors"]) > 2:
            authors_str += " et al."
        parts = [
            f"- [{r['verdict'].upper()}] {r['title']}",
            f"  {authors_str} ({r['year']}) — {r['journal']}",
            f"  ID: {r['id']}",
        ]
        if include_reasons and r.get("match_reasons"):
            parts.append("  Warum passend: " + " | ".join(r["match_reasons"][:3]))
        if r["kernthese"]:
            parts.append(f"  Kernthese: {r['kernthese'][:220]}")
        lines.append("\n".join(parts))
    return "\n\n".join(lines)


def _argument_reason_prefix(intent: str) -> str:
    if intent == "counter":
        return "Bezug zum Argument: mögliche Gegenposition oder produktive Spannung"
    if intent == "methods":
        return "Bezug zum Argument: methodisch anschlussfähig"
    if intent == "missing_refs":
        return "Bezug zum Argument: kann diesen Punkt stützen, erweitern oder irritieren"
    return "Bezug zum Argument: anschlussfähig"


def _argument_focus_summary(argument_unit: str, result: dict[str, Any]) -> str:
    unit_terms = _clean_argument_terms(_extract_search_terms(argument_unit))
    specific_terms = [term for term in unit_terms if term not in GENERIC_SEARCH_TERMS]
    focus_terms = specific_terms[:4] or unit_terms[:4]
    if not focus_terms:
        return ""

    result_blob = _normalize_search_text(
        " ".join(
            [
                result.get("title", ""),
                result.get("kernthese", ""),
                " ".join(result.get("topics", [])),
                " ".join(result.get("concepts", [])),
                result.get("signal_group", ""),
                result.get("suggested_subgroup", ""),
                result.get("discourse_indicator", ""),
            ]
        )
    )
    overlaps = [term for term in focus_terms if term in result_blob][:3]
    if overlaps:
        return "greift hier besonders " + ", ".join(overlaps) + " auf"
    return "relevant für " + ", ".join(focus_terms[:3])


def _format_argument_results(
    argument_unit: str,
    results: list[dict],
    *,
    intent: str,
    heading: str,
) -> str:
    lines = [heading, f"- {argument_unit}"]
    for r in results:
        authors_str = ", ".join(r["authors"][:2])
        if len(r["authors"]) > 2:
            authors_str += " et al."
        lines.append(
            f"- [{r['verdict'].upper()}] {r['title']}\n"
            f"  {authors_str} ({r['year']}) — {r['journal']}\n"
            f"  ID: {r['id']}"
        )
        reason_parts = []
        focus_summary = _argument_focus_summary(argument_unit, r)
        if focus_summary:
            reason_parts.append(focus_summary)
        if r.get("match_reasons"):
            reason_parts.append(" | ".join(r["match_reasons"][:2]))
        if r.get("bezuege"):
            first = r["bezuege"][0]
            pub = first.get("pub_kurz", "")
            relation = first.get("relation", "")
            if pub:
                reason_parts.append(f"Agent-Bezug: {pub} ({relation})")
        if reason_parts:
            lines.append(
                f"  {_argument_reason_prefix(intent)}: " + " | ".join(reason_parts)
            )
        if r["kernthese"]:
            lines.append(f"  Kernthese: {r['kernthese'][:220]}")
    return "\n".join(lines)


def _search_by_argument_units(
    message: str,
    user_context: str | None = None,
    *,
    per_argument_limit: int = 2,
    max_arguments: int = 4,
    include_empty: bool = False,
) -> list[dict[str, Any]]:
    sections = _parse_context_sections(user_context)
    units = sections.get("argument_units") or _derive_argument_units_from_text(user_context or "")
    intent = _detect_search_intent(message)

    groups: list[dict[str, Any]] = []
    for idx, unit in enumerate(units[:max_arguments], start=1):
        plan = _build_argument_plan(unit, intent, user_context)
        results = _search_articles_by_plan(plan, limit=max(per_argument_limit, 1))
        if not results and not include_empty:
            continue
        groups.append(
            {
                "index": idx,
                "unit": unit,
                "intent": intent,
                "results": results[:per_argument_limit] if results else [],
            }
        )
    return groups


def build_retrieval_prefetch(message: str, user_context: str | None = None) -> str:
    plan = _build_search_plan(message, user_context)

    parts = [
        "=== AUTOMATISCHE VORRECHERCHE AUS DER MOJO-DB ===",
        f"Intent: {plan['intent']}",
    ]
    if plan["phrases"]:
        parts.append("Leitphrasen: " + "; ".join(plan["phrases"][:5]))
    if plan["terms"]:
        parts.append("Suchterme: " + ", ".join(plan["terms"][:10]))

    groups = _search_by_argument_units(
        message,
        user_context,
        per_argument_limit=2,
        max_arguments=4,
    )
    if groups:
        parts.append(f"Argumenteinheiten: {len(groups)}")
        for group in groups:
            parts.append("")
            parts.append(
                _format_argument_results(
                    group["unit"],
                    group["results"],
                    intent=group["intent"],
                    heading=f"### Argument {group['index']}",
                )
            )
    else:
        results = _search_articles_by_plan(plan, limit=6)
        if not results:
            return ""
        parts.append("")
        parts.append(_format_search_results(results[:6], include_reasons=True))

    parts.append("")
    parts.append(
        "Nutze diese Treffer als Startpunkt. Argumentiere nach Möglichkeit einheitsbezogen, "
        "nicht nur auf Volltext-Ebene."
    )
    return "\n".join(parts)


def _format_authors_short(authors: list[str]) -> str:
    authors_str = ", ".join(authors[:2])
    if len(authors) > 2:
        authors_str += " et al."
    return authors_str


def _short_excerpt(text: str, max_chars: int = 220) -> str:
    return _trim_text(text or "", max_chars, suffix="…")


def _should_force_argument_report(message: str, user_context: str | None = None) -> bool:
    sections = _parse_context_sections(user_context)
    units = sections.get("argument_units") or _derive_argument_units_from_text(user_context or "")
    if not units:
        return False

    intent = _detect_search_intent(message)
    if intent != "general":
        return True

    msg = _normalize_search_text(message)
    mentions_argument = "argument" in msg or "komplex" in msg
    mentions_text = any(token in msg for token in ["aufsatz", "entwurf", "text", "paper"])
    asks_relation = any(token in msg for token in ["bezug", "damit", "tun", "warum", "wieso", "welcher", "welche"])
    return mentions_argument and (mentions_text or asks_relation)


def _argument_report_intent(message: str) -> str:
    intent = _detect_search_intent(message)
    return intent if intent != "general" else "relevant"


def _argument_report_title(intent: str) -> str:
    if intent == "counter":
        return "Argumentationsbezogene Prüfung auf Gegenargumente und Widersprüche"
    if intent == "methods":
        return "Argumentationsbezogene Prüfung auf methodische Parallelen"
    if intent == "missing_refs":
        return "Argumentationsbezogene Prüfung auf fehlende Referenzen"
    return "Argumentationsbezogene Relevanzprüfung"


def _format_argument_findings(group: dict[str, Any]) -> list[str]:
    lines = [
        f"## Argumentationskomplex {group['index']}",
        f"Darstellung des Komplexes: {group['unit']}",
        "",
        "Findings des Agents:",
    ]

    results = group.get("results") or []
    if not results:
        lines.append("- Kein klarer Treffer in der MOJO-DB für diesen Komplex.")
        return lines

    for result in results:
        title_link = f"[{result['title']}](/article/{result['id']})"
        lines.append(
            f"- [{result['verdict'].upper()}] {title_link}\n"
            f"  {_format_authors_short(result['authors'])} ({result['year']}) — {result['journal']}"
        )

        focus_summary = _argument_focus_summary(group["unit"], result)
        if focus_summary:
            lines.append(f"  Argumentbezug: {focus_summary[:1].upper() + focus_summary[1:]}.")

        bezuege = result.get("bezuege") or []
        if bezuege:
            first = bezuege[0]
            pub = first.get("pub_kurz", "")
            relation = first.get("relation", "")
            bezug_text = _short_excerpt(first.get("bezug", ""), 220)
            relation_label = f"{pub} ({relation})".strip() if pub else relation
            if relation_label and bezug_text:
                lines.append(
                    f"  Eigener Publikationsbezug: {relation_label} — {bezug_text}"
                )
            elif relation_label:
                lines.append(f"  Eigener Publikationsbezug: {relation_label}")

        if result.get("verdict_reason"):
            lines.append(
                f"  Agent-Einschätzung: {_short_excerpt(result['verdict_reason'], 220)}"
            )

        if result.get("kernthese"):
            lines.append(f"  Kernthese: {_short_excerpt(result['kernthese'], 260)}")
    return lines


def build_argument_report(message: str, user_context: str | None = None) -> str:
    intent = _argument_report_intent(message)
    groups = _search_by_argument_units(
        message,
        user_context,
        per_argument_limit=2,
        max_arguments=6,
        include_empty=True,
    )
    if not groups:
        return ""

    lines = [_argument_report_title(intent), ""]
    for idx, group in enumerate(groups):
        if idx:
            lines.extend(["", "---", ""])
        lines.extend(_format_argument_findings(group))
    lines.extend([
        "",
        "Hinweis: Die Gliederung ist erzwungen argumentbezogen. Leere oder schwache Abschnitte zeigen,",
        "dass für den jeweiligen Komplex in der aktuellen MOJO-DB noch kein überzeugender Treffer vorliegt.",
    ])
    return "\n".join(lines)


def _search_articles_by_text(
    query: str,
    user_context: str | None = None,
    limit: int = 30,
) -> list[dict]:
    """Search articles.db robustly from natural-language or keyword queries."""
    plan = _build_search_plan(query, user_context)
    return _search_articles_by_plan(plan, limit=limit)


def _search_articles_by_verdict(
    verdicts: list[str], limit: int = 50
) -> list[dict]:
    """Get recent high-relevance articles."""
    store = Store()
    placeholders = ",".join("?" * len(verdicts))
    sql = (
        "SELECT id, journal_short, journal_full, title, authors_json, doi, year, "
        "agent_verdict, agent_entry_json, openalex_topics, openalex_concepts, "
        "signal_group, suggested_subgroup, discourse_indicator, citation_hits_json "
        f"FROM articles WHERE agent_verdict IN ({placeholders}) "
        "ORDER BY year DESC LIMIT ?"
    )
    params = list(verdicts) + [limit]

    with store._conn() as c:
        rows = c.execute(sql, params).fetchall()

    return [_row_to_search_result(r) for r in rows]


TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_mojo_db",
            "description": (
                "Search the MOJO article database (17,000+ screened journal articles) "
                "from natural-language or keyword queries. It matches not only title and "
                "abstract, but also agent analyses, OpenAlex topics/concepts, signal groups, "
                "and other stored metadata. Use this to find articles relevant to the user's text."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural-language search request or compact keyword bundle.",
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


def _execute_tool(name: str, args: dict, user_context: str | None = None) -> str:
    """Execute a tool call and return result as string."""
    if name == "search_mojo_db":
        query = args.get("query", "")
        groups = _search_by_argument_units(
            query,
            user_context,
            per_argument_limit=2,
            max_arguments=4,
        )
        if groups:
            lines = []
            total_hits = sum(len(group["results"]) for group in groups)
            lines.append(
                f"{total_hits} Treffer über {len(groups)} Argumente:"
            )
            for group in groups:
                lines.append("")
                lines.append(
                    _format_argument_results(
                        group["unit"],
                        group["results"],
                        intent=group["intent"],
                        heading=f"### Argument {group['index']}",
                    )
                )
            return "\n".join(lines)

        results = _search_articles_by_text(
            query,
            user_context=user_context,
            limit=args.get("limit", 20),
        )
        if not results:
            return "Keine Treffer gefunden."
        return f"{len(results)} Treffer:\n\n" + _format_search_results(
            results,
            include_reasons=True,
        )

    elif name == "get_high_relevance_articles":
        results = _search_articles_by_verdict(
            ["lesenswert", "pflichtlektuere"],
            limit=args.get("limit", 30),
        )
        if not results:
            return "Keine hochrelevanten Artikel gefunden."
        return f"{len(results)} hochrelevante Artikel:\n\n" + _format_search_results(
            results,
            include_reasons=True,
        )

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
            "argument_units": [],
            "source": "empty",
            "model": "",
            "tokens_used": 0,
            "cost_usd": 0.0,
        }

    if len(raw_text) <= SHORT_CONTEXT_CHARS:
        prompt_context = _trim_text(raw_text, SHORT_CONTEXT_CHARS, suffix="")
        prompt_context, argument_units = _ensure_argument_units(prompt_context)
        return {
            "raw_text": raw_text,
            "raw_chars": len(raw_text),
            "prompt_context": prompt_context,
            "prompt_chars": len(prompt_context),
            "argument_units": argument_units,
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
                            "- Wo weitere Literatur besonders nützlich wäre\n"
                            "## Argumenteinheiten\n"
                            "- 4-8 eigenständige argumentative Komplexe des Texts, jeweils als knapper Bullet\n\n"
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
                prompt_context, argument_units = _ensure_argument_units(prompt_context)
                return {
                    "raw_text": raw_text,
                    "raw_chars": len(raw_text),
                    "prompt_context": prompt_context,
                    "prompt_chars": len(prompt_context),
                    "argument_units": argument_units,
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
    prompt_context, argument_units = _ensure_argument_units(prompt_context)
    return {
        "raw_text": raw_text,
        "raw_chars": len(raw_text),
        "prompt_context": prompt_context,
        "prompt_chars": len(prompt_context),
        "argument_units": argument_units,
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
        "- Wenn Argumenteinheiten vorliegen, arbeite argumentationsbezogen: prüfe Belege, Lücken",
        "  und Gegenpositionen pro Einheit statt nur für den Volltext als Ganzes.",
        "- Es kann eine automatische Vorrecherche mit Kandidaten geben. Nutze sie als Startpunkt,",
        "  aber prüfe sie kritisch und lies bei Bedarf Details per Tool nach.",
        "- Wenn der Text klar genug ist, mach proaktiv mehrere Suchen mit unterschiedlichen",
        "  Query-Bündeln statt nur einer generischen Suchanfrage.",
        "- Sei ehrlich über die Grenzen der Suche und benenne Unsicherheiten offen.",
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
    if _should_force_argument_report(message, user_context):
        content = build_argument_report(message, user_context)
        if content:
            return {
                "content": content,
                "tokens_used": 0,
                "tokens_in": 0,
                "tokens_out": 0,
                "cost_usd": 0.0,
            }

    client = build_client()
    model = model or MODEL_AGENT
    system_prompt = build_system_prompt(user_context)

    # Build messages
    prefetch = build_retrieval_prefetch(message, user_context)
    user_message = message
    if prefetch:
        user_message += "\n\n" + prefetch

    messages = []
    for h in history[-20:]:  # Keep last 20 turns
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": user_message})

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
            result = _execute_tool(
                tc.function.name,
                args,
                user_context=user_context,
            )
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
