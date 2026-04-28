"""Zero-cost journal profiling and candidate discovery via OpenAlex topics."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
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
JOURNAL_PROFILES_JSON = settings.PROJECT_ROOT / "journal_profiles.json"

_GENERIC_TOKENS = {
    "education", "educational", "research", "studies", "study", "learning",
    "social", "theory", "theoretical", "analysis", "culture", "cultural",
}

_PARADIGMATIC_SIGNAL_RULES = {
    "posthuman/material": [
        "posthuman", "more-than-human", "nonhuman", "material", "sociomaterial",
        "anthropocene", "ecology", "ecological", "multispecies",
    ],
    "digital/ai/data": [
        "artificial intelligence", "algorithm", "datafication", "digital",
        "platform", "automation", "machine learning", "technology",
    ],
    "aesthetic/cultural": [
        "arts", "artistic", "aesthetic", "cultural education", "creativity",
        "museum", "performance", "music", "visual",
    ],
    "resilience/transformation": [
        "resilience", "sustainability", "climate", "environmental",
        "transformation", "future", "futurity", "planetary",
    ],
    "bildungstheorie/philosophy": [
        "philosophy", "subject", "subjectivation", "bildung", "pedagogy",
        "ethics", "educational theory", "democracy",
    ],
}

_METHODOLOGICAL_SIGNAL_RULES = {
    "qualitative": [
        "ethnography", "interview", "case study", "qualitative", "narrative",
        "participatory", "action research", "discourse analysis",
    ],
    "quantitative": [
        "quantitative", "survey", "statistical", "measurement", "assessment",
        "regression", "randomized", "experiment",
    ],
    "review/synthesis": [
        "review", "meta-analysis", "systematic", "bibliometric", "scoping",
        "literature",
    ],
    "theoretical": [
        "philosophy", "theory", "conceptual", "critical theory",
        "epistemology", "ontology",
    ],
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

    def _nested_name(key: str) -> str:
        nested = item.get(key)
        if isinstance(nested, dict):
            return nested.get("display_name") or ""
        return ""

    return {
        "id": item.get("id") or (item.get("topic") or {}).get("id") or (item.get("concept") or {}).get("id") or "",
        "name": name,
        "score": score,
        "domain": _nested_name("domain"),
        "field": _nested_name("field"),
        "subfield": _nested_name("subfield"),
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


def _now_stamp() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _topic_weight(topic: dict[str, Any]) -> float:
    try:
        return max(float(topic.get("score") or 0.0), 1.0)
    except (TypeError, ValueError):
        return 1.0


def _journal_issn(journal: Any) -> str:
    if getattr(journal, "issn", ""):
        return str(journal.issn).strip()
    url = str(getattr(journal, "url", "") or "")
    if url.startswith("issn:"):
        return url.removeprefix("issn:").strip()
    return ""


def _journal_openalex_source_key(journal: Any) -> str:
    url = str(getattr(journal, "url", "") or "")
    if "openalex.org/" in url:
        return url.rstrip("/").rsplit("/", 1)[-1]
    if url.startswith("S") and url[1:].isdigit():
        return url
    return ""


def fetch_source_for_journal(journal: Any) -> tuple[dict[str, Any] | None, str]:
    """Fetch a journal/source object from OpenAlex using source id or ISSN."""
    source_key = _journal_openalex_source_key(journal)
    if source_key:
        data = _cached_get(
            "source_by_id",
            f"{OPENALEX_SOURCES}/{source_key}",
            {"mailto": POLITE_MAILTO},
        )
        if data:
            return data, ""
        return None, f"OpenAlex-Source nicht gefunden: {source_key}"

    issn = _journal_issn(journal)
    if not issn:
        return None, "Keine ISSN/OpenAlex-Source am Journal hinterlegt."

    data = _cached_get(
        "source_by_issn",
        f"{OPENALEX_SOURCES}/issn:{issn}",
        {"mailto": POLITE_MAILTO},
    )
    if data:
        return data, ""
    return None, f"ISSN nicht in OpenAlex gefunden: {issn}"


def _cluster_topics(topics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[tuple[str, str, str], dict[str, Any]] = {}
    for topic in topics:
        domain = topic.get("domain") or ""
        field = topic.get("field") or ""
        subfield = topic.get("subfield") or ""
        key = (domain, field, subfield)
        label_parts = [part for part in key if part]
        label = " / ".join(label_parts) if label_parts else "OpenAlex topics"
        bucket = buckets.setdefault(key, {
            "label": label,
            "domain": domain,
            "field": field,
            "subfield": subfield,
            "weight": 0.0,
            "topic_count": 0,
            "top_topics": [],
        })
        bucket["weight"] += _topic_weight(topic)
        bucket["topic_count"] += 1
        if len(bucket["top_topics"]) < 8:
            bucket["top_topics"].append(topic.get("name", ""))

    clusters = list(buckets.values())
    clusters.sort(key=lambda item: (item["weight"], item["topic_count"]), reverse=True)
    for cluster in clusters:
        cluster["weight"] = round(cluster["weight"], 1)
    return clusters


def _infer_signals(
    topics: list[dict[str, Any]],
    rules: dict[str, list[str]],
) -> list[dict[str, Any]]:
    signal_hits: list[dict[str, Any]] = []
    topic_names = [str(topic.get("name", "") or "") for topic in topics]
    for label, needles in rules.items():
        matched: list[str] = []
        score = 0.0
        for topic_name in topic_names:
            folded = topic_name.lower()
            for needle in needles:
                if needle in folded:
                    matched.append(topic_name)
                    score += 1.0
                    break
        if matched:
            signal_hits.append({
                "label": label,
                "score": round(score, 1),
                "matched_topics": list(dict.fromkeys(matched))[:5],
            })
    signal_hits.sort(key=lambda item: item["score"], reverse=True)
    return signal_hits


def _dominant_disciplines(topic_clusters: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for cluster in topic_clusters[:6]:
        label = cluster.get("label") or ""
        if not label or label == "OpenAlex topics":
            continue
        out.append({
            "label": label,
            "weight": cluster.get("weight", 0.0),
            "top_topics": cluster.get("top_topics", [])[:4],
        })
    return out


def build_profile_from_source(
    journal_meta: dict[str, Any],
    source: dict[str, Any],
    *,
    topic_limit: int = 80,
) -> dict[str, Any]:
    topics, topics_source = normalize_source_topics(source, limit=topic_limit)
    topic_clusters = _cluster_topics(topics)
    fit = compute_source_profile_fit(topics, topic_limit=topic_limit)
    stats = source.get("summary_stats") or {}

    profile = {
        "journal_short": journal_meta.get("journal_short", ""),
        "journal_name": journal_meta.get("journal_name") or source.get("display_name", ""),
        "journal_tier": journal_meta.get("journal_tier", ""),
        "journal_clusters": journal_meta.get("journal_clusters", []),
        "source_kind": journal_meta.get("source_kind", "tracked"),
        "openalex_source_id": source.get("id", ""),
        "openalex_display_name": source.get("display_name", ""),
        "issn": journal_meta.get("issn") or source.get("issn_l") or "",
        "issn_l": source.get("issn_l", ""),
        "all_issns": list(source.get("issn") or []),
        "publisher": source.get("host_organization_name", ""),
        "homepage_url": source.get("homepage_url", ""),
        "works_count": source.get("works_count", 0),
        "h_index": stats.get("h_index"),
        "mean_citedness": stats.get("2yr_mean_citedness"),
        "topics_source": topics_source,
        "topics_raw": topics,
        "topic_clusters": topic_clusters,
        "paradigmatic_signals": _infer_signals(topics, _PARADIGMATIC_SIGNAL_RULES),
        "disciplinary_home": _dominant_disciplines(topic_clusters),
        "methodological_signals": _infer_signals(topics, _METHODOLOGICAL_SIGNAL_RULES),
        "fit_to_research_profile": fit,
        "source_status": "found",
        "source_error": "",
        "updated_at": _now_stamp(),
    }
    return profile


def build_journal_profile(journal: Any, *, topic_limit: int = 80) -> dict[str, Any]:
    meta = {
        "journal_short": getattr(journal, "short", ""),
        "journal_name": getattr(journal, "name", ""),
        "journal_tier": getattr(journal, "tier", ""),
        "journal_clusters": list(getattr(journal, "clusters", []) or []),
        "source_kind": "tracked",
        "issn": _journal_issn(journal),
    }

    source, error = fetch_source_for_journal(journal)
    if not source:
        return {
            **meta,
            "openalex_source_id": "",
            "openalex_display_name": "",
            "topics_source": "",
            "topics_raw": [],
            "topic_clusters": [],
            "paradigmatic_signals": [],
            "disciplinary_home": [],
            "methodological_signals": [],
            "fit_to_research_profile": compute_source_profile_fit([]),
            "source_status": "missing",
            "source_error": error,
            "updated_at": _now_stamp(),
        }

    return build_profile_from_source(meta, source, topic_limit=topic_limit)


def load_journal_profile_store(path: Path | None = None) -> dict[str, Any]:
    profile_path = path or JOURNAL_PROFILES_JSON
    if not profile_path.exists():
        return {
            "version": 1,
            "updated_at": "",
            "profiles": [],
        }
    try:
        data = json.loads(profile_path.read_text(encoding="utf-8"))
    except Exception:
        return {
            "version": 1,
            "updated_at": "",
            "profiles": [],
        }
    if not isinstance(data, dict):
        return {
            "version": 1,
            "updated_at": "",
            "profiles": [],
        }
    data.setdefault("version", 1)
    data.setdefault("updated_at", "")
    data.setdefault("profiles", [])
    return data


def save_journal_profile_store(
    profiles: list[dict[str, Any]],
    path: Path | None = None,
) -> dict[str, Any]:
    profile_path = path or JOURNAL_PROFILES_JSON
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": 1,
        "updated_at": _now_stamp(),
        "profiles": profiles,
    }
    tmp = profile_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(profile_path)
    return payload


def refresh_journal_profiles(
    *,
    journals: list[Any] | None = None,
    include_disabled: bool = False,
    topic_limit: int = 80,
    path: Path | None = None,
) -> dict[str, Any]:
    selected = journals if journals is not None else settings.JOURNALS
    existing_profiles = list(load_journal_profile_store(path).get("profiles") or [])
    existing_by_short = {
        str(profile.get("journal_short", "")): profile
        for profile in existing_profiles
        if profile.get("journal_short")
    }
    profiles: list[dict[str, Any]] = []
    for journal in selected:
        if not include_disabled and not getattr(journal, "enabled", True):
            continue
        profile = build_journal_profile(journal, topic_limit=topic_limit)
        old_profile = existing_by_short.get(str(profile.get("journal_short", "")))
        if profile.get("source_status") != "found" and old_profile and old_profile.get("source_status") == "found":
            preserved = dict(old_profile)
            preserved["journal_tier"] = getattr(journal, "tier", preserved.get("journal_tier", ""))
            preserved["journal_clusters"] = list(getattr(journal, "clusters", []) or [])
            preserved["refresh_attempted_at"] = _now_stamp()
            preserved["refresh_error"] = profile.get("source_error", "")
            profiles.append(preserved)
            continue
        profiles.append(profile)

    profiles.sort(
        key=lambda item: (
            item.get("source_status") != "found",
            -(item.get("fit_to_research_profile", {}).get("score") or 0),
            str(item.get("journal_name", "")).lower(),
        )
    )
    return save_journal_profile_store(profiles, path=path)


def journal_profile_status(path: Path | None = None) -> dict[str, Any]:
    profile_path = path or JOURNAL_PROFILES_JSON
    store = load_journal_profile_store(profile_path)
    profiles = list(store.get("profiles") or [])
    found = [p for p in profiles if p.get("source_status") == "found"]
    missing = [p for p in profiles if p.get("source_status") != "found"]
    return {
        "path": str(profile_path),
        "exists": profile_path.exists(),
        "updated_at": store.get("updated_at", ""),
        "count": len(profiles),
        "found_count": len(found),
        "missing_count": len(missing),
        "size_kb": round(profile_path.stat().st_size / 1024, 1) if profile_path.exists() else 0,
        "profiles": profiles,
    }


def route_query_to_journal_profiles(
    query: str,
    *,
    profiles: list[dict[str, Any]] | None = None,
    limit: int = 12,
) -> list[dict[str, Any]]:
    q = " ".join((query or "").split())
    if not q:
        return []

    if profiles is None:
        profiles = list(load_journal_profile_store().get("profiles") or [])

    routed: list[dict[str, Any]] = []
    for profile in profiles:
        topics = list(profile.get("topics_raw") or [])[:80]
        if not topics:
            continue

        weighted_total = 0.0
        weighted_hits = 0.0
        matched_topics: list[dict[str, Any]] = []
        for topic in topics:
            weight = _topic_weight(topic)
            weighted_total += weight
            sim = _similarity(q, topic.get("name", ""))
            if sim < 0.16:
                continue
            weighted_hits += weight * sim
            matched_topics.append({
                "topic": topic.get("name", ""),
                "score": round(sim * 100, 1),
            })

        topic_score = (weighted_hits / weighted_total) * 100 if weighted_total else 0.0
        cluster_score = 0.0
        for cluster in profile.get("topic_clusters") or []:
            cluster_score = max(cluster_score, _similarity(q, cluster.get("label", "")) * 100)
        profile_prior = float(profile.get("fit_to_research_profile", {}).get("score") or 0.0)
        score = round(min((topic_score * 0.7) + (cluster_score * 0.2) + (profile_prior * 0.1), 100.0), 1)

        if score >= 24:
            routing = "deep"
        elif score >= 12:
            routing = "medium"
        else:
            routing = "shallow"

        matched_topics.sort(key=lambda item: item["score"], reverse=True)
        routed.append({
            "journal_short": profile.get("journal_short", ""),
            "journal_name": profile.get("journal_name", ""),
            "journal_tier": profile.get("journal_tier", ""),
            "routing": routing,
            "score": score,
            "matched_topics": matched_topics[:5],
            "profile_fit": profile.get("fit_to_research_profile", {}),
            "dominant_disciplines": profile.get("disciplinary_home", [])[:3],
        })

    routed.sort(key=lambda item: item["score"], reverse=True)
    return routed[:limit]
