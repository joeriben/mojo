"""Zero-cost journal profiling and candidate discovery via OpenAlex topics."""

from __future__ import annotations

import hashlib
import json
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import httpx

import journal_bot.settings as settings


OPENALEX_SOURCES = "https://api.openalex.org/sources"
OPENALEX_TOPICS = "https://api.openalex.org/topics"
POLITE_MAILTO = "mojo@localhost"
USER_AGENT = f"mojo/0.1 (mailto:{POLITE_MAILTO})"
HEADERS = {"User-Agent": USER_AGENT, "Accept": "application/json"}
CACHE_DIR = settings.PROJECT_ROOT / ".openalex_cache"
CACHE_DIR.mkdir(exist_ok=True)

_GENERIC_TOKENS = {
    "education", "educational", "research", "studies", "study", "learning",
    "social", "theory", "theoretical", "analysis", "culture", "cultural",
}


def _cache_path(kind: str, key: str) -> Path:
    safe = hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]
    return CACHE_DIR / f"{kind}_{safe}.json"


def _cached_get(kind: str, url: str, params: dict[str, Any], timeout: float = 20) -> dict | None:
    cache_key = json.dumps({"url": url, "params": params}, ensure_ascii=False, sort_keys=True)
    cp = _cache_path(kind, cache_key)
    if cp.exists():
        try:
            return json.loads(cp.read_text(encoding="utf-8"))
        except Exception:
            cp.unlink(missing_ok=True)
    try:
        resp = httpx.get(
            url,
            params=params,
            headers=HEADERS,
            timeout=timeout,
            follow_redirects=True,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        cp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return data
    except Exception:
        return None


def _normalize_topic_item(item: Any) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None
    name = (
        item.get("display_name")
        or (item.get("topic") or {}).get("display_name")
        or (item.get("concept") or {}).get("display_name")
        or ""
    )
    if not name:
        return None
    score = item.get("score")
    try:
        score = round(float(score), 1)
    except (TypeError, ValueError):
        score = None
    return {
        "id": item.get("id") or (item.get("topic") or {}).get("id") or (item.get("concept") or {}).get("id") or "",
        "name": name,
        "score": score,
    }


def normalize_source_topics(src: dict[str, Any], limit: int = 5) -> tuple[list[dict[str, Any]], str | None]:
    for key in ("topics", "x_concepts"):
        items = []
        for raw in src.get(key) or []:
            topic = _normalize_topic_item(raw)
            if topic:
                items.append(topic)
        if items:
            return items[:limit], key
    return [], None


def _profile_terms(limit: int = 12) -> list[str]:
    raw_terms: list[str] = []
    raw_terms.extend(settings.RESEARCHER_TRIAGE_TOPICS or [])
    raw_terms.extend(re.split(r"[,\n;]+", settings.RESEARCHER_AREAS or ""))

    seen: set[str] = set()
    out: list[str] = []
    for term in raw_terms:
        cleaned = " ".join(str(term or "").strip().split())
        if len(cleaned) < 4:
            continue
        folded = cleaned.lower()
        if folded in seen:
            continue
        seen.add(folded)
        out.append(cleaned)
        if len(out) >= limit:
            break
    return out


def profile_terms(limit: int = 12) -> list[str]:
    return _profile_terms(limit=limit)


def _tokenize(text: str) -> list[str]:
    return [
        tok for tok in re.findall(r"[a-zA-ZÀ-ÿ0-9]{3,}", (text or "").lower())
        if tok not in _GENERIC_TOKENS
    ]


def _similarity(a: str, b: str) -> float:
    a_norm = " ".join((a or "").lower().split())
    b_norm = " ".join((b or "").lower().split())
    if not a_norm or not b_norm:
        return 0.0

    a_tokens = set(_tokenize(a_norm))
    b_tokens = set(_tokenize(b_norm))
    overlap = 0.0
    if a_tokens and b_tokens:
        overlap = len(a_tokens & b_tokens) / max(len(a_tokens | b_tokens), 1)

    contains = 0.9 if a_norm in b_norm or b_norm in a_norm else 0.0
    seq = SequenceMatcher(None, a_norm, b_norm).ratio() * 0.55
    return max(overlap, contains, seq)


def compute_source_profile_fit(
    source_or_topics: dict[str, Any] | list[dict[str, Any]],
    *,
    topic_limit: int = 15,
) -> dict[str, Any]:
    if isinstance(source_or_topics, dict):
        topics, _ = normalize_source_topics(source_or_topics, limit=topic_limit)
    else:
        topics = list(source_or_topics or [])[:topic_limit]

    terms = _profile_terms(limit=12)
    if not topics or not terms:
        return {
            "score": 0.0,
            "fit_label": "unbestimmt",
            "tier_hint": "C",
            "matched_profile_terms": [],
            "matched_topics": [],
        }

    matches: list[dict[str, Any]] = []
    weighted_total = 0.0
    weighted_hits = 0.0

    for topic in topics:
        weight = float(topic.get("score") or 50.0)
        weighted_total += weight

        best_term = ""
        best_sim = 0.0
        for term in terms:
            sim = _similarity(topic.get("name", ""), term)
            if sim > best_sim:
                best_sim = sim
                best_term = term

        if best_sim < 0.24:
            continue

        weighted_hits += weight * best_sim
        matches.append({
            "topic": topic.get("name", ""),
            "profile_term": best_term,
            "score": round(best_sim * 100, 1),
        })

    score = round((weighted_hits / weighted_total) * 100, 1) if weighted_total else 0.0
    if score >= 45:
        fit_label = "hoch"
        tier_hint = "A"
    elif score >= 20:
        fit_label = "mittel"
        tier_hint = "B"
    else:
        fit_label = "niedrig"
        tier_hint = "C"

    matches.sort(key=lambda item: item["score"], reverse=True)
    return {
        "score": score,
        "fit_label": fit_label,
        "tier_hint": tier_hint,
        "matched_profile_terms": list(dict.fromkeys(m["profile_term"] for m in matches[:5])),
        "matched_topics": matches[:5],
    }


def search_topics(query: str, per_page: int = 3) -> list[dict[str, Any]]:
    q = " ".join((query or "").split())
    if not q:
        return []
    data = _cached_get(
        "topic_search",
        OPENALEX_TOPICS,
        {
            "search": q,
            "mailto": POLITE_MAILTO,
            "per-page": per_page,
        },
    )
    if not data:
        return []

    hits: list[dict[str, Any]] = []
    for raw in data.get("results") or []:
        name = raw.get("display_name") or ""
        hits.append({
            "id": raw.get("id", ""),
            "name": name,
            "works_count": raw.get("works_count", 0),
            "similarity": round(_similarity(q, name) * 100, 1),
            "field": (raw.get("field") or {}).get("display_name", ""),
            "subfield": (raw.get("subfield") or {}).get("display_name", ""),
            "domain": (raw.get("domain") or {}).get("display_name", ""),
        })
    hits.sort(key=lambda item: (item["similarity"], item["works_count"]), reverse=True)
    return hits


def _tracked_journal_meta(source: dict[str, Any]) -> dict[str, Any]:
    source_names = {
        " ".join((source.get("display_name") or source.get("name") or "").lower().split()),
    }
    source_issns = {str(val).strip() for val in (source.get("issn") or []) if str(val).strip()}
    if source.get("issn_l"):
        source_issns.add(str(source.get("issn_l")).strip())

    for journal in settings.JOURNALS:
        journal_issns = set()
        if journal.issn:
            journal_issns.add(journal.issn.strip())
        if journal.url.startswith("issn:"):
            journal_issns.add(journal.url.removeprefix("issn:").strip())

        if source_issns & journal_issns:
            return {
                "tracked": True,
                "tracked_short": journal.short,
                "tracked_name": journal.name,
                "tracked_tier": journal.tier,
            }

        journal_name = " ".join(journal.name.lower().split())
        if journal_name and journal_name in source_names:
            return {
                "tracked": True,
                "tracked_short": journal.short,
                "tracked_name": journal.name,
                "tracked_tier": journal.tier,
            }

    return {
        "tracked": False,
        "tracked_short": "",
        "tracked_name": "",
        "tracked_tier": "",
    }


def list_sources_for_topic(topic_id: str, per_page: int = 6) -> list[dict[str, Any]]:
    topic_key = (topic_id or "").rsplit("/", 1)[-1]
    if not topic_key:
        return []
    data = _cached_get(
        "sources_by_topic",
        OPENALEX_SOURCES,
        {
            "filter": f"type:journal,topics.id:{topic_key}",
            "sort": "works_count:desc",
            "per-page": per_page,
            "mailto": POLITE_MAILTO,
        },
    )
    if not data:
        return []
    return data.get("results") or []


def discover_candidate_journals(
    *,
    max_topics: int = 8,
    per_topic: int = 6,
    max_results: int = 20,
) -> dict[str, Any]:
    terms = _profile_terms(limit=min(max_topics * 4, 24))
    resolved_topics: list[dict[str, Any]] = []
    seen_topic_ids: set[str] = set()
    by_source: dict[str, dict[str, Any]] = {}

    for term in terms:
        if len(resolved_topics) >= max_topics:
            break
        topic_hits = search_topics(term, per_page=3)
        if not topic_hits:
            continue
        topic = topic_hits[0]
        if topic["id"] in seen_topic_ids:
            continue
        seen_topic_ids.add(topic["id"])
        resolved_topics.append({
            "query": term,
            "topic_id": topic["id"],
            "topic_name": topic["name"],
            "similarity": topic["similarity"],
            "field": topic["field"],
            "subfield": topic["subfield"],
        })

        for source in list_sources_for_topic(topic["id"], per_page=per_topic):
            source_id = source.get("id", "")
            if not source_id:
                continue
            fit = compute_source_profile_fit(source)
            top_topics, _ = normalize_source_topics(source, limit=4)
            stats = source.get("summary_stats") or {}

            entry = by_source.setdefault(source_id, {
                "id": source_id,
                "name": source.get("display_name", ""),
                "issn_l": source.get("issn_l", ""),
                "issn": list(source.get("issn") or []),
                "works_count": source.get("works_count", 0),
                "publisher": source.get("host_organization_name", ""),
                "homepage_url": source.get("homepage_url", ""),
                "is_oa": bool(source.get("is_oa")),
                "h_index": stats.get("h_index"),
                "mean_citedness": stats.get("2yr_mean_citedness"),
                "fit": fit,
                "top_topics": top_topics,
                "matched_profile_terms": [],
                "matched_topics": [],
                "match_count": 0,
                "support_score": 0.0,
            })

            entry["matched_profile_terms"].append(term)
            entry["matched_topics"].append(topic["name"])
            entry["match_count"] += 1
            entry["support_score"] += 1.0 + (topic["similarity"] / 100.0)

            if fit["score"] > entry["fit"]["score"]:
                entry["fit"] = fit
            if top_topics and len(top_topics) > len(entry["top_topics"]):
                entry["top_topics"] = top_topics

    candidates = []
    for entry in by_source.values():
        entry["matched_profile_terms"] = list(dict.fromkeys(entry["matched_profile_terms"]))
        entry["matched_topics"] = list(dict.fromkeys(entry["matched_topics"]))
        entry.update(_tracked_journal_meta(entry))
        candidates.append(entry)

    candidates.sort(
        key=lambda item: (
            item["tracked"],
            -(item["fit"]["score"]),
            -item["match_count"],
            -item["support_score"],
            -int(item.get("works_count") or 0),
        )
    )

    return {
        "profile_terms": _profile_terms(limit=max_topics),
        "resolved_topics": resolved_topics,
        "candidates": candidates[:max_results],
    }
