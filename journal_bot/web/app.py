"""MOJO Web UI — Flask + HTMX prototype."""

from __future__ import annotations

import contextlib
import csv
import html as html_mod
import io
import json
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any
from flask import (
    Flask, render_template, render_template_string, request,
    abort, jsonify, send_file, session, Response,
)

from journal_bot.store import Store, ARTICLES_DB
from journal_bot.signals import suggest_emergent_motifs
from journal_bot.settings import (
    PROJECT_ROOT,
    CORPUS_JSON,
    DIGEST_DIR,
    DISCOURSE_SPACES,
    DISKURSRAEUME_JSON,
    JOURNALS,
    JOURNALS_JSON,
    KEY_FILE,
    MISTRAL_KEY_FILE,
    S2_KEY_FILE,
    MODEL_AGENT,
    MODEL_SUMMARIZE,
    RESEARCHER_AREAS,
    RESEARCHER_INSTITUTION,
    RESEARCHER_NAME,
    RESEARCHER_TRIAGE_TOPICS,
    SINCE_YEAR,
    SUMMARIES_JSON,
    ZOTERO_API_KEY_FILE,
    ZOTERO_COLLECTION,
    ZOTERO_STORAGE,
    ZOTERO_USER_ID_FILE,
    journals_in_cluster,
    save_profile,
)

app = Flask(
    __name__,
    template_folder="templates",
    static_folder="static",
)
app.secret_key = os.urandom(24)  # For session (lightweight state only)
# Hostname-scoped cookie name to avoid collisions with other localhost apps
# (browsers scope cookies & password managers by hostname, not port).
# Pair with `mojo.localhost:5555` access (see cmd_web in cli.py).
app.config["SESSION_COOKIE_NAME"] = "mojo_session"

# Server-side agent state (single-user tool, no cookie size limits)
# Context is persisted to disk so it survives server restarts.
_AGENT_CONTEXT_FILE = Path(__file__).parent.parent.parent / ".agent_context.json"
_LEGACY_AGENT_CONTEXT_FILE = Path(__file__).parent.parent.parent / ".agent_context.txt"


PROJECTS_JSON = PROJECT_ROOT / "projects.json"


def _load_projects() -> list[dict]:
    if PROJECTS_JSON.exists():
        try:
            data = json.loads(PROJECTS_JSON.read_text(encoding="utf-8"))
            return data.get("projects", [])
        except Exception:
            pass
    return []


def _save_projects(projects: list[dict]) -> None:
    payload = {"version": 1, "projects": projects}
    tmp = PROJECTS_JSON.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(PROJECTS_JSON)


def _empty_agent_context() -> dict[str, Any]:
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


def _normalize_agent_context(payload: Any, source_override: str | None = None) -> dict[str, Any]:
    from journal_bot.research_agent import prepare_context, _derive_argument_units_from_text

    if isinstance(payload, str):
        text = payload.strip()
        if not text:
            return _empty_agent_context()
        ctx = prepare_context(text, allow_llm=False)
        ctx["source"] = source_override or "legacy_fallback"
        return ctx

    if not isinstance(payload, dict):
        return _empty_agent_context()

    ctx = _empty_agent_context()
    ctx.update(payload)
    ctx["raw_text"] = str(ctx.get("raw_text", "") or "").strip()
    ctx["prompt_context"] = str(ctx.get("prompt_context", "") or "").strip()
    ctx["raw_chars"] = int(ctx.get("raw_chars") or len(ctx["raw_text"]))
    ctx["prompt_chars"] = int(ctx.get("prompt_chars") or len(ctx["prompt_context"]))
    ctx["argument_units"] = [
        str(item).strip()
        for item in (ctx.get("argument_units") or [])
        if str(item).strip()
    ]
    if ctx["prompt_context"] and not ctx["argument_units"]:
        ctx["argument_units"] = _derive_argument_units_from_text(ctx["prompt_context"])
    ctx["tokens_used"] = int(ctx.get("tokens_used") or 0)
    ctx["cost_usd"] = float(ctx.get("cost_usd") or 0.0)
    ctx["source"] = str(ctx.get("source", "") or source_override or "empty")
    ctx["model"] = str(ctx.get("model", "") or "")

    if ctx["raw_text"] and not ctx["prompt_context"]:
        rebuilt = prepare_context(ctx["raw_text"], allow_llm=False)
        rebuilt["source"] = source_override or rebuilt["source"]
        return rebuilt

    return ctx


def _load_agent_context() -> dict[str, Any]:
    if _AGENT_CONTEXT_FILE.exists():
        try:
            payload = json.loads(_AGENT_CONTEXT_FILE.read_text(encoding="utf-8"))
            return _normalize_agent_context(payload)
        except Exception:
            pass
    if _LEGACY_AGENT_CONTEXT_FILE.exists():
        try:
            payload = _LEGACY_AGENT_CONTEXT_FILE.read_text(encoding="utf-8")
            return _normalize_agent_context(payload, source_override="legacy_fallback")
        except Exception:
            pass
    return _empty_agent_context()


def _save_agent_context(ctx: dict[str, Any]) -> None:
    payload = _normalize_agent_context(ctx)
    tmp = _AGENT_CONTEXT_FILE.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    tmp.replace(_AGENT_CONTEXT_FILE)


_agent_state: dict = {
    "context": _load_agent_context(),
    "messages": [],
}


# --------------------------------------------------------- Jinja filters ---

@app.template_filter("format_number")
def format_number_filter(value):
    """Format number with locale-style thousands separator."""
    try:
        return f"{int(value):,}".replace(",", ".")
    except (ValueError, TypeError):
        return str(value)


@app.template_filter("cache_warning")
def cache_warning_filter(row):
    """Mirror llm_log.is_cache_warning so templates can render the ⚠ flag
    using the same threshold (<80 % hit, cache-critical endpoint, >= 2 calls)
    as the terminal report. Single source of truth lives in llm_log.py."""
    from journal_bot.llm_log import is_cache_warning
    try:
        return is_cache_warning(row)
    except Exception:
        return False

VERDICT_ORDER = ["pflichtlektuere", "lesenswert", "scannen", "ignorieren"]
VERDICT_RANK = {verdict: rank for rank, verdict in enumerate(VERDICT_ORDER)}
VERDICT_LABEL = {
    "pflichtlektuere": "Pflichtlektüre",
    "lesenswert": "Lesenswert",
    "scannen": "Scannen",
    "ignorieren": "Ignorieren",
}
RELATION_LABEL = {
    "erweitert": "erweitert",
    "widerspricht": "widerspricht",
    "parallelisiert": "parallel",
    "importiert": "Import",
    "tangential": "tangential",
}


def _store():
    return Store()


def _verdict_rank(verdict: str | None) -> int:
    return VERDICT_RANK.get(verdict or "", len(VERDICT_ORDER))


def _journal_full_name(short: str) -> str:
    for j in JOURNALS:
        if j.short == short:
            return j.name
    return short


def _active_projects() -> list[dict[str, Any]]:
    return [p for p in _load_projects() if p.get("status") == "active" and p.get("key")]


def _active_project_map() -> dict[str, dict[str, Any]]:
    return {p["key"]: p for p in _active_projects()}


def _article_project_keys(article: Any, project_map: dict[str, dict[str, Any]]) -> list[str]:
    if not project_map:
        return []

    keys: list[str] = []
    entry = article.agent_entry if isinstance(article.agent_entry, dict) else {}
    for key in entry.get("project_hits", []) or []:
        if key in project_map and key not in keys:
            keys.append(key)

    if article.signal_group in project_map and article.signal_group not in keys:
        keys.append(article.signal_group)

    return keys


def _normalize_agent_entry(entry: Any) -> dict[str, Any]:
    """Ensure a parsed agent_entry has all display-critical keys.

    The agent (esp. Gemini 3.5 Flash) sometimes omits fields like `kernthese`
    in its `submit_digest_entry` call. Templates access these directly
    (`a.agent_entry.kernthese[:300]`), so a missing key raised an
    UndefinedError that 500'd the entire digest view. Filling safe defaults
    here — the single chokepoint behind every parse site — keeps every
    template robust without per-template guards. Idempotent.
    """
    if not isinstance(entry, dict):
        entry = {}
    entry.setdefault("kernthese", "")
    entry.setdefault("verdict_begruendung", "")
    entry.setdefault("theoretisch_methodisch", "")
    entry.setdefault("bezuege", [])
    entry.setdefault("bemerkenswert", [])
    return entry


def _prepare_articles_for_view(
    articles: list[Any],
    project_map: dict[str, dict[str, Any]] | None = None,
) -> list[Any]:
    project_map = project_map or {}
    for a in articles:
        if a.agent_entry and isinstance(a.agent_entry, str):
            a.agent_entry = json.loads(a.agent_entry)
        # Store may already return agent_entry as a parsed dict, so normalize
        # unconditionally — not only in the str-parse branch — otherwise dicts
        # missing keys (e.g. Gemini omitting `kernthese`) reach the template raw.
        if a.agent_entry:
            a.agent_entry = _normalize_agent_entry(a.agent_entry)
        a.journal_full = a.journal_full or _journal_full_name(a.journal_short)
        a.project_keys = _article_project_keys(a, project_map)
        a.primary_project_key = a.project_keys[0] if a.project_keys else ""
        a.project_labels = [
            project_map[key]["name"]
            for key in a.project_keys
            if key in project_map
        ]
    return articles


def _group_articles_by_project(
    articles: list[Any],
    project_map: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    groups: list[dict[str, Any]] = []
    for project in _active_projects():
        key = project["key"]
        group_articles = [a for a in articles if getattr(a, "primary_project_key", "") == key]
        if not group_articles:
            continue
        groups.append({
            "key": key,
            "label": project.get("name", key),
            "articles": group_articles,
            "count": len(group_articles),
        })

    unassigned = [a for a in articles if not getattr(a, "primary_project_key", "")]
    if unassigned:
        groups.append({
            "key": "",
            "label": "Ohne Projektkontext",
            "articles": unassigned,
            "count": len(unassigned),
        })
    return groups


# ----------------------------------------------------------------- Routes ---

@app.route("/")
def digest():
    """Main digest view with filters."""
    from datetime import date
    store = _store()
    current_year = date.today().year
    project_map = _active_project_map()

    # Year range: default to current year
    has_any_filter = any(
        request.args.get(k)
        for k in ("year_from", "year_to", "cluster", "journal", "verdict", "project", "archived")
    )
    year_from = request.args.get("year_from", type=int)
    year_to = request.args.get("year_to", type=int)
    if year_from is None and year_to is None and not has_any_filter:
        year_from = current_year
        year_to = current_year

    cluster = request.args.get("cluster", "")
    journal = request.args.get("journal", "")
    verdict_filter = request.args.get("verdict", "")
    project_filter = request.args.get("project", "")
    sort_mode = request.args.get("sort", "verdict")

    # Build query
    journals_filter = None
    if cluster:
        journals_filter = [j.short for j in journals_in_cluster(cluster)]
    if journal:
        journals_filter = [journal]

    articles = store.find_in_window(
        start_year=year_from,
        end_year=year_to,
        journals=journals_filter,
        only_processed=True,
    )

    # Parse entry JSON
    articles = _prepare_articles_for_view(articles, project_map)

    # Hide archived unless explicitly requested
    show_archived = request.args.get("archived") == "1"
    if not show_archived:
        articles = [a for a in articles if not a.is_archived]

    # Additional verdict filter (uses effective verdict)
    if verdict_filter:
        articles = [a for a in articles if a.effective_verdict == verdict_filter]
    if project_filter:
        articles = [a for a in articles if project_filter in getattr(a, "project_keys", [])]

    ordered_articles = sorted(
        articles,
        key=lambda a: (
            _verdict_rank(a.effective_verdict),
            -(a.year or 0),
            (a.journal_full or "").lower(),
            (a.title or "").lower(),
        ),
    )

    # Citation hits across all verdicts
    cites_you = [a for a in ordered_articles if a.citation_hits]

    # Group by effective verdict
    by_verdict = {}
    for v in VERDICT_ORDER:
        by_verdict[v] = [a for a in ordered_articles if a.effective_verdict == v]

    project_sections = (
        _group_articles_by_project(ordered_articles, project_map)
        if sort_mode == "project" else []
    )

    # Available years for filter (always show all, not just filtered)
    with store._conn() as c:
        rows = c.execute(
            "SELECT DISTINCT year FROM articles WHERE agent_verdict IS NOT NULL "
            "ORDER BY year DESC"
        ).fetchall()
        all_years = [r[0] for r in rows if r[0]]

    clusters = [
        (k, meta["name"])
        for k, meta in DISCOURSE_SPACES.items()
    ]

    journal_list = sorted(
        [(j.short, j.name) for j in JOURNALS if j.enabled],
        key=lambda x: x[1],
    )

    return render_template(
        "digest.html",
        articles=ordered_articles,
        by_verdict=by_verdict,
        cites_you=cites_you,
        project_sections=project_sections,
        project_list=[(p["key"], p["name"]) for p in _active_projects()],
        verdict_label=VERDICT_LABEL,
        relation_label=RELATION_LABEL,
        all_years=all_years,
        clusters=clusters,
        journal_list=journal_list,
        filters={
            "year_from": year_from,
            "year_to": year_to,
            "cluster": cluster,
            "journal": journal,
            "verdict": verdict_filter,
            "project": project_filter,
            "sort": sort_mode,
        },
        total=len(ordered_articles),
    )


@app.route("/article/<article_id>")
def article_detail(article_id: str):
    """Single article detail view."""
    store = _store()
    a = store.get(article_id)
    if not a:
        abort(404)
    if a.agent_entry and isinstance(a.agent_entry, str):
        a.agent_entry = _normalize_agent_entry(json.loads(a.agent_entry))
    a.journal_full = a.journal_full or _journal_full_name(a.journal_short)

    return render_template(
        "article.html",
        a=a,
        verdict_label=VERDICT_LABEL,
        relation_label=RELATION_LABEL,
    )


@app.route("/diskurs")
@app.route("/diskurs/<cluster_key>")
def diskursraum(cluster_key: str | None = None):
    """Discourse space overview or detail."""
    store = _store()

    if not cluster_key:
        # Overview
        spaces = []
        for key, meta in DISCOURSE_SPACES.items():
            js = journals_in_cluster(key)
            shorts = [j.short for j in js]
            with store._conn() as c:
                if shorts:
                    placeholders = ",".join("?" * len(shorts))
                    total = c.execute(
                        f"SELECT COUNT(*) FROM articles WHERE journal_short IN ({placeholders})",
                        shorts,
                    ).fetchone()[0]
                    verdicts = dict(c.execute(
                        f"SELECT agent_verdict, COUNT(*) FROM articles "
                        f"WHERE journal_short IN ({placeholders}) AND agent_verdict IS NOT NULL "
                        f"GROUP BY agent_verdict",
                        shorts,
                    ).fetchall())
                    cites_count = c.execute(
                        f"SELECT COUNT(*) FROM articles "
                        f"WHERE journal_short IN ({placeholders}) "
                        f"AND citation_hits_json IS NOT NULL "
                        f"AND citation_hits_json != '[]' AND citation_hits_json != ''",
                        shorts,
                    ).fetchone()[0]
                else:
                    total = 0
                    verdicts = {}
                    cites_count = 0
            spaces.append({
                "key": key,
                "name": meta["name"],
                "description": meta["description"],
                "journals": js,
                "total": total,
                "verdicts": verdicts,
                "cites_count": cites_count,
            })
        return render_template("diskurs_list.html", spaces=spaces)

    # Detail for specific cluster
    meta = DISCOURSE_SPACES.get(cluster_key)
    if not meta:
        abort(404)

    js = journals_in_cluster(cluster_key)
    shorts = [j.short for j in js]

    articles = store.find_in_window(journals=shorts, only_processed=True)
    for a in articles:
        if a.agent_entry and isinstance(a.agent_entry, str):
            a.agent_entry = _normalize_agent_entry(json.loads(a.agent_entry))
        a.journal_full = a.journal_full or _journal_full_name(a.journal_short)

    by_verdict = {}
    for v in VERDICT_ORDER:
        by_verdict[v] = [a for a in articles if a.effective_verdict == v]

    cites_you = [a for a in articles if a.citation_hits]
    signal_groups: list[dict] = []
    grouped_signals: dict[str, list] = {}
    for a in articles:
        if a.signal_group and a.discourse_indicator != "kein_indikator":
            grouped_signals.setdefault(a.signal_group, []).append(a)
    for group_key, group_articles in grouped_signals.items():
        ordered = sorted(
            group_articles,
            key=lambda a: (
                _verdict_rank(a.effective_verdict),
                0 if a.discourse_indicator == "starker_indikator" else 1,
                -(a.year or 0),
            ),
        )
        subgroup_counts: dict[str, int] = {}
        for article in ordered:
            if article.suggested_subgroup:
                subgroup_counts[article.suggested_subgroup] = (
                    subgroup_counts.get(article.suggested_subgroup, 0) + 1
                )
        emergent_suggestions = []
        unassigned_articles = [
            a
            for a in ordered
            if not a.suggested_subgroup and a.discourse_indicator == "starker_indikator"
        ]
        if unassigned_articles:
            max_year = max((a.year or 0) for a in unassigned_articles)
            if max_year:
                unassigned_articles = [
                    a for a in unassigned_articles if (a.year or 0) >= max_year - 2
                ]
        for suggestion in suggest_emergent_motifs(
            unassigned_articles,
            background_articles=ordered,
        ):
            sample_articles = [
                article for article in ordered if article.id in set(suggestion.article_ids)
            ][:3]
            emergent_suggestions.append(
                {
                    "label": suggestion.label,
                    "article_count": suggestion.article_count,
                    "journal_count": suggestion.journal_count,
                    "strong_count": suggestion.strong_count,
                    "score": suggestion.score,
                    "articles": sample_articles,
                }
            )
        signal_groups.append(
            {
                "key": group_key,
                "label": group_key.replace("_", " "),
                "count": len(ordered),
                "strong_count": sum(
                    1 for a in ordered if a.discourse_indicator == "starker_indikator"
                ),
                "articles": ordered[:3],
                "subgroups": sorted(
                    subgroup_counts.items(),
                    key=lambda item: (-item[1], item[0]),
                )[:4],
                "emergent_suggestions": emergent_suggestions,
            }
        )
    signal_groups.sort(key=lambda item: (-item["strong_count"], -item["count"], item["key"]))

    # Per-journal stats
    journal_stats = []
    for j in js:
        count = sum(1 for a in articles if a.journal_short == j.short)
        journal_stats.append({"short": j.short, "name": j.name, "count": count})

    return render_template(
        "diskurs_detail.html",
        key=cluster_key,
        meta=meta,
        journals=js,
        journal_stats=journal_stats,
        articles=articles,
        by_verdict=by_verdict,
        cites_you=cites_you,
        signal_groups=signal_groups,
        verdict_label=VERDICT_LABEL,
        relation_label=RELATION_LABEL,
        total=len(articles),
    )


@app.route("/search")
def search():
    """Title search across all articles."""
    q = request.args.get("q", "").strip()
    articles = []
    if q:
        store = _store()
        pattern = f"%{q}%"
        with store._conn() as c:
            rows = c.execute(
                "SELECT * FROM articles WHERE title LIKE ? "
                "ORDER BY year DESC, fetched_at DESC LIMIT 100",
                (pattern,),
            ).fetchall()
        from journal_bot.store import _row_to_article
        articles = [_row_to_article(r) for r in rows]
        for a in articles:
            if a.agent_entry and isinstance(a.agent_entry, str):
                a.agent_entry = _normalize_agent_entry(json.loads(a.agent_entry))
            a.journal_full = a.journal_full or _journal_full_name(a.journal_short)

    return render_template(
        "search.html",
        articles=articles,
        q=q,
        verdict_label=VERDICT_LABEL,
        relation_label=RELATION_LABEL,
        total=len(articles),
    )


@app.route("/api/tooltip/<article_id>")
def api_tooltip(article_id: str):
    """HTMX endpoint: lazy-load tooltip content on hover.

    Strategy: show agent's verdict reasoning + kernthese if present, always
    append the original abstract as a fallback/context — so unprocessed
    articles (no agent_entry) and Gemini-triaged ones (no kernthese field)
    still surface a useful preview.
    """
    store = _store()
    a = store.get(article_id)
    if not a:
        return ""
    esc = html_mod.escape
    parts: list[str] = []

    # Agent entry available → show verdict + kernthese (defensive: support
    # Gemini-style schemas that use theoretisch_methodisch instead of kernthese)
    if a.agent_entry:
        if isinstance(a.agent_entry, str):
            a.agent_entry = _normalize_agent_entry(json.loads(a.agent_entry))
        e = a.agent_entry
        begr = e.get("verdict_begruendung") or ""
        kern = e.get("kernthese") or e.get("theoretisch_methodisch") or ""
        if begr:
            parts.append(f'<div class="tooltip-verdict">{esc(begr[:300])}</div>')
        if kern:
            parts.append(f'<div class="tooltip-kernthese">{esc(kern[:400])}</div>')

    # Always append abstract for context (especially helpful for unprocessed
    # entries in the review queue where the agent didn't produce a deepening)
    abstract = a.openalex_abstract or a.abstract
    if abstract:
        parts.append(f'<div class="tooltip-abstract">{esc(abstract[:500])}</div>')
    return "".join(parts)


@app.route("/api/verdict", methods=["POST"])
def api_set_verdict():
    """HTMX endpoint: set user verdict override."""
    store = _store()
    article_id = request.form.get("article_id", "")
    verdict = request.form.get("verdict", "")
    memo = request.form.get("memo", "")

    if not article_id:
        abort(400)

    a = store.get(article_id)
    if not a:
        abort(404)

    # Check if this is an upgrade to lesenswert that needs deepening
    old_effective = a.effective_verdict
    is_upgrade_to_lesenswert = (
        verdict in ("lesenswert", "pflichtlektuere")
        and old_effective not in ("lesenswert", "pflichtlektuere")
        and _needs_deepening(a)
    )

    store.set_user_verdict(article_id, verdict=verdict, memo=memo)

    # Auto-deepen on upgrade to lesenswert — im Hintergrund, sonst blockiert
    # der LLM-Call (10-30 s) die HTMX-Response und die User-Wahrnehmung ist
    # "Lesenswert wurde gar nicht registriert" (während Ignorieren sofort
    # antwortet, weil dort kein Deepen läuft). Eigene Store-Instanz pro Thread,
    # da sqlite3-Connections nicht zwischen Threads geteilt werden dürfen.
    if is_upgrade_to_lesenswert:
        threading.Thread(
            target=_run_deepen,
            args=(article_id, _store()),
            daemon=True,
        ).start()

    # Re-fetch to get updated state
    a = store.get(article_id)
    if a.agent_entry and isinstance(a.agent_entry, str):
        a.agent_entry = _normalize_agent_entry(json.loads(a.agent_entry))
    a.journal_full = a.journal_full or _journal_full_name(a.journal_short)

    return render_template(
        "_verdict_controls.html",
        a=a,
        verdict_label=VERDICT_LABEL,
    )


def _needs_deepening(a) -> bool:
    """Check if article has only a shallow analysis."""
    if not a.agent_entry:
        return True
    e = a.agent_entry if isinstance(a.agent_entry, dict) else json.loads(a.agent_entry)
    # Shallow indicators: no bezuege, placeholder kernthese, zero iterations
    kernthese = e.get("kernthese", "")
    if kernthese.startswith("(") and kernthese.endswith(")"):
        return True  # placeholder like "(Screening: ignorieren)"
    if not e.get("bezuege") and a.iterations == 0:
        return True
    return False


def _run_deepen(article_id: str, store: Store) -> None:
    """Run full assess_then_verify for an article, update DB.

    Stashes the previous agent_entry as _previous inside the new entry
    so the UI can show both for comparison.
    """
    from journal_bot.digest import process_article
    a = store.get(article_id)
    if not a:
        return

    # Save old entry for comparison
    old_entry = a.agent_entry
    if isinstance(old_entry, str):
        old_entry = json.loads(old_entry)

    try:
        process_article(a, store, verbose=False, mode="assess_verify")
    except Exception as e:
        print(f"[web] Vertiefen fehlgeschlagen für {article_id}: {e}")
        return

    # Stash old entry inside new one
    if old_entry:
        a = store.get(article_id)
        new_entry = a.agent_entry
        if isinstance(new_entry, str):
            new_entry = json.loads(new_entry)
        if new_entry and new_entry != old_entry:
            new_entry["_previous"] = old_entry
            with store._conn() as c:
                c.execute(
                    "UPDATE articles SET agent_entry_json = ? WHERE id = ?",
                    (json.dumps(new_entry, ensure_ascii=False), article_id),
                )


@app.route("/api/deepen/<article_id>", methods=["POST"])
def api_deepen(article_id: str):
    """HTMX endpoint: run full analysis on demand."""
    store = _store()
    a = store.get(article_id)
    if not a:
        abort(404)

    _run_deepen(article_id, store)

    # Re-fetch
    a = store.get(article_id)
    if a.agent_entry and isinstance(a.agent_entry, str):
        a.agent_entry = _normalize_agent_entry(json.loads(a.agent_entry))
    a.journal_full = a.journal_full or _journal_full_name(a.journal_short)

    return render_template(
        "_article_body.html",
        a=a,
        verdict_label=VERDICT_LABEL,
        relation_label=RELATION_LABEL,
    )


@app.route("/api/zotero/<article_id>", methods=["POST"])
def api_zotero(article_id: str):
    """HTMX endpoint: export article to Zotero."""
    from journal_bot.zotero_export import export_to_zotero
    store = _store()
    a = store.get(article_id)
    if not a:
        abort(404)
    try:
        zotero_key = export_to_zotero(article_id, store)
        return (
            f'<span style="color:var(--lesenswert); font-size:.85rem;">'
            f'In Zotero (<code>{zotero_key}</code>)</span>'
        )
    except Exception as e:
        # Keep the button so user can retry after fixing the issue
        return (
            f'<span id="zotero-{article_id}">'
            f'<span style="color:var(--pflichtlektuere); font-size:.85rem;">{e}</span> '
            f'<button class="btn" style="margin-left:.3rem;"'
            f' hx-post="/api/zotero/{article_id}"'
            f' hx-target="#zotero-{article_id}"'
            f' hx-swap="outerHTML">Nochmal</button>'
            f'</span>'
        )


@app.route("/api/obsidian/<article_id>", methods=["POST"])
def api_obsidian(article_id: str):
    """HTMX endpoint: export article as Obsidian Markdown."""
    from journal_bot.obsidian_export import export_to_obsidian
    store = _store()
    a = store.get(article_id)
    if not a:
        abort(404)
    try:
        path = export_to_obsidian(article_id, store)
        return (
            f'<span style="color:var(--lesenswert); font-size:.85rem;">'
            f'Obsidian ({path.name})</span>'
        )
    except Exception as e:
        return (
            f'<span style="color:var(--pflichtlektuere); font-size:.85rem;">'
            f'Fehler: {e}</span>'
        )


@app.route("/api/archive/<article_id>", methods=["POST"])
def api_archive(article_id: str):
    """HTMX endpoint: archive article (mark as done)."""
    store = _store()
    a = store.get(article_id)
    if not a:
        abort(404)
    store.set_archived(article_id, archived=not a.is_archived)
    a = store.get(article_id)
    return render_template("_archive_button.html", a=a)


@app.route("/review")
def review():
    """Review queue: articles not yet user-confirmed."""
    store = _store()
    year = request.args.get("year", type=int)
    verdict_filter = request.args.get("verdict", "")
    project_filter = request.args.get("project", "")
    sort_mode = request.args.get("sort", "verdict")
    project_map = _active_project_map()

    with store._conn() as c:
        sql = (
            "SELECT * FROM articles "
            "WHERE agent_verdict IS NOT NULL AND user_verdict IS NULL "
            "AND agent_verdict IN ('lesenswert', 'scannen', 'pflichtlektuere') "
        )
        params: list = []
        if year:
            sql += " AND year = ?"
            params.append(year)
        if verdict_filter:
            sql += " AND agent_verdict = ?"
            params.append(verdict_filter)
        sql += " ORDER BY CASE agent_verdict "
        sql += "   WHEN 'pflichtlektuere' THEN 0 "
        sql += "   WHEN 'lesenswert' THEN 1 "
        sql += "   WHEN 'scannen' THEN 2 "
        sql += " END, year DESC"
        rows = c.execute(sql, params).fetchall()

    from journal_bot.store import _row_to_article
    articles = [_row_to_article(r) for r in rows]
    articles = _prepare_articles_for_view(articles, project_map)
    if project_filter:
        articles = [a for a in articles if project_filter in getattr(a, "project_keys", [])]

    ordered_articles = sorted(
        articles,
        key=lambda a: (
            _verdict_rank(a.agent_verdict),
            -(a.year or 0),
            (a.journal_full or "").lower(),
            (a.title or "").lower(),
        ),
    )
    project_sections = (
        _group_articles_by_project(ordered_articles, project_map)
        if sort_mode == "project" else []
    )

    # Available years
    with store._conn() as c:
        year_rows = c.execute(
            "SELECT DISTINCT year FROM articles WHERE agent_verdict IS NOT NULL "
            "ORDER BY year DESC"
        ).fetchall()
        all_years = [r[0] for r in year_rows if r[0]]

    return render_template(
        "review.html",
        articles=ordered_articles,
        project_sections=project_sections,
        project_list=[(p["key"], p["name"]) for p in _active_projects()],
        verdict_label=VERDICT_LABEL,
        relation_label=RELATION_LABEL,
        all_years=all_years,
        filters={
            "year": year,
            "verdict": verdict_filter,
            "project": project_filter,
            "sort": sort_mode,
        },
        total=len(ordered_articles),
    )


@app.route("/overrides")
def overrides():
    """All user overrides for prompt optimization analysis."""
    store = _store()
    with store._conn() as c:
        rows = c.execute(
            "SELECT * FROM articles WHERE user_verdict IS NOT NULL "
            "ORDER BY user_verdict_at DESC"
        ).fetchall()

    from journal_bot.store import _row_to_article
    articles = [_row_to_article(r) for r in rows]
    for a in articles:
        if a.agent_entry and isinstance(a.agent_entry, str):
            a.agent_entry = _normalize_agent_entry(json.loads(a.agent_entry))
        a.journal_full = a.journal_full or _journal_full_name(a.journal_short)

    # Group by direction
    upgrades = [
        a for a in articles
        if _verdict_rank(a.user_verdict) < _verdict_rank(a.agent_verdict)
    ]
    downgrades = [
        a for a in articles
        if _verdict_rank(a.user_verdict) > _verdict_rank(a.agent_verdict)
    ]
    confirms = [a for a in articles if a.user_verdict == a.agent_verdict]

    return render_template(
        "overrides.html",
        articles=articles,
        upgrades=upgrades,
        downgrades=downgrades,
        confirms=confirms,
        verdict_label=VERDICT_LABEL,
        total=len(articles),
    )


def _md_to_html(text: str) -> str:
    """Convert markdown text to HTML, rendering tables properly."""
    esc = html_mod.escape
    lines = text.split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        # Detect markdown table: line with |, followed by separator |---|
        if ("|" in lines[i]
                and i + 1 < len(lines)
                and "|" in lines[i + 1]
                and set(lines[i + 1].replace("|", "").strip()) <= {"-", ":", " "}):
            # Parse header
            headers = [c.strip() for c in lines[i].split("|")]
            headers = [h for h in headers if h]  # remove empty from leading/trailing |
            out.append('<div style="overflow-x:auto;"><table class="md-table"><thead><tr>')
            for h in headers:
                out.append(f"<th>{esc(h)}</th>")
            out.append("</tr></thead><tbody>")
            i += 2  # skip header + separator
            while i < len(lines) and "|" in lines[i] and lines[i].strip():
                cells = [c.strip() for c in lines[i].split("|")]
                cells = [c for c in cells if c or cells.index(c) not in (0, len(cells) - 1)]
                # Handle leading/trailing empty from |...|
                raw = lines[i].strip()
                if raw.startswith("|"):
                    cells = [c.strip() for c in raw[1:].split("|")]
                    if cells and cells[-1] == "":
                        cells = cells[:-1]
                out.append("<tr>")
                for c in cells:
                    out.append(f"<td>{esc(c)}</td>")
                out.append("</tr>")
                i += 1
            out.append("</tbody></table></div>")
        elif lines[i].startswith("# "):
            out.append(f"<h3>{esc(lines[i][2:])}</h3>")
            i += 1
        elif lines[i].startswith("## "):
            out.append(f"<h4>{esc(lines[i][3:])}</h4>")
            i += 1
        elif lines[i].startswith("_") and lines[i].endswith("_"):
            out.append(f"<p style='color:var(--muted); font-size:.85rem;'><em>{esc(lines[i][1:-1])}</em></p>")
            i += 1
        elif lines[i].startswith("[biblio]") or lines[i].startswith("[trends]"):
            # Log lines → skip in rendered output
            i += 1
        elif lines[i].strip() == "":
            i += 1
        else:
            # Collect consecutive non-special lines as <pre>
            pre_lines = []
            while i < len(lines) and lines[i].strip() and "|" not in lines[i] and not lines[i].startswith("#") and not lines[i].startswith("[biblio]") and not lines[i].startswith("[trends]"):
                pre_lines.append(lines[i])
                i += 1
            if pre_lines:
                out.append(f'<pre style="white-space:pre-wrap; font-size:.85rem; line-height:1.5;">{esc(chr(10).join(pre_lines))}</pre>')
    return "\n".join(out)


def _render_agent_markdown(content: str) -> str:
    """Render agent output as HTML, with a no-dependency fallback."""
    try:
        import markdown
    except ModuleNotFoundError:
        return html_mod.escape(content).replace("\n", "<br>")

    try:
        return markdown.markdown(
            content,
            extensions=["tables", "fenced_code"],
        )
    except Exception:
        return html_mod.escape(content).replace("\n", "<br>")


@app.route("/api/diskurs/trends/<cluster_key>", methods=["POST"])
def api_diskurs_trends(cluster_key: str):
    """HTMX endpoint: run LLM trend analysis for a discourse space."""
    if cluster_key not in DISCOURSE_SPACES:
        abort(404)

    from journal_bot import trends

    esc = html_mod.escape
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            result = trends.run(cluster=cluster_key, verbose=True)
    except Exception as e:
        return (
            f'<div class="card" style="border-color:var(--pflichtlektuere);">'
            f'<strong>Fehler:</strong> {esc(str(e))}</div>'
        )

    output = buf.getvalue()
    status = result.get("status", "")
    cost = result.get("cost_usd", 0)
    path = result.get("path", "")

    cluster_name = esc(DISCOURSE_SPACES[cluster_key]["name"])
    parts = [f'<div class="card">']
    parts.append(f'<h3 style="margin-bottom:.5rem;">Trend-Analyse — {cluster_name}</h3>')
    if status == "ok":
        parts.append(
            f'<p style="font-size:.85rem; color:var(--muted);">'
            f'{result.get("count", 0)} Artikel analysiert · ${cost:.3f}'
            f'{" · " + esc(path) if path else ""}</p>'
        )
    # If the trend analysis wrote a markdown file, render it
    if path:
        try:
            from pathlib import Path
            md_content = Path(path).read_text(encoding="utf-8")
            parts.append(
                f'<details style="margin-top:.75rem;" open>'
                f'<summary><strong>Vollständiges Dossier</strong></summary>'
                f'<div style="margin-top:.5rem;">{_md_to_html(md_content)}</div>'
                f'</details>'
            )
        except Exception:
            pass
    parts.append('</div>')
    return "\n".join(parts)


@app.route("/api/diskurs/biblio/<cluster_key>", methods=["POST"])
def api_diskurs_biblio(cluster_key: str):
    """HTMX endpoint: run bibliometric analysis for a discourse space."""
    if cluster_key not in DISCOURSE_SPACES:
        abort(404)

    from journal_bot import biblio

    esc = html_mod.escape
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            result = biblio.run(cluster=cluster_key, verbose=True)
    except Exception as e:
        return (
            f'<div class="card" style="border-color:var(--pflichtlektuere);">'
            f'<strong>Fehler:</strong> {esc(str(e))}</div>'
        )
    output = buf.getvalue()
    path = result.get("path", "")

    cluster_name = esc(DISCOURSE_SPACES[cluster_key]["name"])
    parts = [f'<div class="card">']
    parts.append(f'<h3 style="margin-bottom:.5rem;">Bibliometrie — {cluster_name}</h3>')
    parts.append(
        f'<p style="font-size:.85rem; color:var(--muted);">'
        f'{result.get("count", 0)} meistzitierte Werke'
        f'{" · Höchste Zitation: " + str(result.get("top_cited", 0)) if result.get("top_cited") else ""}'
        f'</p>'
    )
    # Render the markdown report with proper tables
    if path:
        try:
            from pathlib import Path
            md_content = Path(path).read_text(encoding="utf-8")
            parts.append(f'<div style="margin-top:.5rem;">{_md_to_html(md_content)}</div>')
        except Exception:
            pass
    parts.append('</div>')
    return "\n".join(parts)


@app.route("/api/diskurs/profile/<cluster_key>", methods=["POST"])
def api_diskurs_profile(cluster_key: str):
    """HTMX endpoint: build and render discourse space profile."""
    if cluster_key not in DISCOURSE_SPACES:
        abort(404)

    from journal_bot.diskurs import build_profile, render_profile

    try:
        profile = build_profile(cluster_key)
        md = render_profile(profile)
    except Exception as e:
        return (
            f'<div class="card" style="border-color:var(--pflichtlektuere);">'
            f'<strong>Fehler:</strong> {html_mod.escape(str(e))}</div>'
        )

    return f'<div class="card">{_md_to_html(md)}</div>'


# ================================================================ Setup ===


def _get_profile() -> dict:
    """Read current researcher profile from settings (reflects profile.json)."""
    import journal_bot.settings as s
    return {
        "name": s.RESEARCHER_NAME,
        "institution": s.RESEARCHER_INSTITUTION,
        "areas": s.RESEARCHER_AREAS,
        "triage_topics": list(s.RESEARCHER_TRIAGE_TOPICS),
        "zotero_collection": s.ZOTERO_COLLECTION,
        "zotero_storage": str(s.ZOTERO_STORAGE),
        "since_year": s.SINCE_YEAR,
        "digest_dir": str(s.DIGEST_DIR),
        "model_agent": s.MODEL_AGENT,
        "model_summarize": s.MODEL_SUMMARIZE,
    }


def _file_status(path: Path, count_key: str | None = None) -> dict:
    """Get status of a JSON data file."""
    if not path.exists():
        return {"exists": False, "count": 0, "size_kb": 0, "modified": ""}
    stat = path.stat()
    count = 0
    if count_key:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if count_key == "publications":
                # corpus.json: {"publications": [...]}
                count = len(data.get("publications", []))
            elif count_key == "summaries":
                # summaries.json: {"summaries": {...}, "model": ...}
                count = len(data.get("summaries", {}))
            elif isinstance(data, dict):
                count = len(data)
            elif isinstance(data, list):
                count = len(data)
        except Exception:
            pass
    return {
        "exists": True,
        "count": count,
        "size_kb": round(stat.st_size / 1024),
        "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M"),
    }


def _scan_cost_source_label(source: str) -> str:
    return {
        "scope_recent": "gleicher Scope, letzte verarbeitete Artikel",
        "global_recent": "globale letzte verarbeitete Artikel",
        "fallback": "Fallback-Wert",
    }.get(source, source)


def _resolve_historical_scan_scope(data: dict[str, Any], store: Store) -> dict[str, Any]:
    from journal_bot.scan_jobs import discover_history_years, get_journal_config

    mode = str(data.get("mode", "") or "").strip()
    if mode == "year":
        year = int(data.get("year") or 0)
        if year < 1900 or year > 2100:
            raise ValueError("Bitte ein gültiges Jahr angeben.")
        return {
            "mode": mode,
            "label": f"Jahrgang {year} über alle aktiven Journals",
            "journals": [],
            "journal_name": "",
            "selected_years": [year],
            "available_years": [year],
            "start_year": year,
            "end_year": year,
        }

    if mode == "journal_history":
        journal_short = str(data.get("journal") or "").strip()
        max_years = int(data.get("max_years") or 10)
        if not journal_short:
            raise ValueError("Bitte ein Journal auswählen.")
        if max_years < 1:
            raise ValueError("Max. Jahrgänge muss mindestens 1 sein.")

        journal = get_journal_config(journal_short)
        if not journal:
            raise ValueError(f"Journal {journal_short!r} nicht gefunden.")

        available_years = discover_history_years(journal_short, store)
        if not available_years:
            raise ValueError(
                "Für dieses Journal konnten keine verfügbaren Jahrgänge ermittelt werden. "
                "Automatische Historien-Scans brauchen DB-Treffer oder ISSN/OpenAlex-Abdeckung."
            )

        selected_years = available_years[:max_years]
        return {
            "mode": mode,
            "label": f"{journal.name} — neueste {len(selected_years)} verfügbare Jahrgänge",
            "journals": [journal_short],
            "journal_name": journal.name,
            "selected_years": selected_years,
            "available_years": available_years,
            "start_year": min(selected_years),
            "end_year": max(selected_years),
        }

    raise ValueError("Unbekanntes Scan-Szenario.")


def _render_monitoring_panel(
    *,
    message: str = "",
    message_ok: bool = True,
    run_result: dict[str, Any] | None = None,
) -> str:
    from journal_bot.monitoring import WEEKDAY_LABELS, monitoring_status

    return render_template(
        "_monitoring_panel.html",
        monitoring=monitoring_status(),
        weekdays=sorted(WEEKDAY_LABELS.items()),
        message=message,
        message_ok=message_ok,
        run_result=run_result,
    )


@app.route("/setup")
def setup():
    """Setup page with profile, Zotero, journals, system tabs."""
    store = _store()
    db_stats = store.stats()

    # DB file size
    db_size_mb = "?"
    if ARTICLES_DB.exists():
        db_size_mb = round(ARTICLES_DB.stat().st_size / (1024 * 1024))

    # Journal article counts
    journal_counts = db_stats.get("by_journal", {})

    # API key status
    def _key_status(path: Path) -> dict:
        if path.exists():
            k = path.read_text().strip()
            if k:
                return {"exists": True, "masked": k[:7] + "…" + k[-4:] if len(k) > 12 else "***"}
        return {"exists": False, "masked": ""}

    api_key_status = _key_status(KEY_FILE)
    s2_key_status = _key_status(S2_KEY_FILE)
    zotero_user_id_status = _key_status(ZOTERO_USER_ID_FILE)
    zotero_api_key_status = _key_status(ZOTERO_API_KEY_FILE)
    mistral_key_status = _key_status(MISTRAL_KEY_FILE)

    # Discourse spaces as ordered list of (key, meta) tuples
    spaces = list(DISCOURSE_SPACES.items())

    # Count journals per discourse space
    space_journal_counts = {
        key: len(journals_in_cluster(key)) for key in DISCOURSE_SPACES
    }
    from journal_bot.journal_topics import journal_profile_status

    return render_template(
        "setup.html",
        profile=_get_profile(),
        home=str(Path.home()),
        corpus_status=_file_status(CORPUS_JSON, count_key="publications"),
        summaries_status=_file_status(SUMMARIES_JSON, count_key="summaries"),
        journals=JOURNALS,
        journal_counts=journal_counts,
        spaces=spaces,
        space_journal_counts=space_journal_counts,
        projects=_load_projects(),
        db_stats=db_stats,
        db_size_mb=db_size_mb,
        current_year=datetime.now().year,
        api_key_status=api_key_status,
        s2_key_status=s2_key_status,
        zotero_user_id_status=zotero_user_id_status,
        zotero_api_key_status=zotero_api_key_status,
        mistral_key_status=mistral_key_status,
        verdict_label=VERDICT_LABEL,
        journal_profiles=journal_profile_status(),
    )


@app.route("/api/setup/profile", methods=["POST"])
def api_setup_profile():
    """HTMX: Save researcher profile to profile.json."""
    esc = html_mod.escape

    # Build profile dict from form
    triage_raw = request.form.get("triage_topics", "")
    triage_topics = [t.strip() for t in triage_raw.split("\n") if t.strip()]

    profile_data = {
        "name": request.form.get("name", "").strip(),
        "institution": request.form.get("institution", "").strip(),
        "areas": request.form.get("areas", "").strip(),
        "triage_topics": triage_topics,
        "zotero_collection": request.form.get("zotero_collection", "").strip(),
        "zotero_storage": request.form.get("zotero_storage", "").strip(),
        "since_year": int(request.form.get("since_year", 2018)),
        "digest_dir": request.form.get("digest_dir", "").strip(),
        "model_agent": request.form.get("model_agent", "").strip(),
        "model_summarize": request.form.get("model_summarize", "").strip(),
    }

    # Remove empty strings (fall back to defaults)
    profile_data = {k: v for k, v in profile_data.items() if v}

    if not profile_data.get("name"):
        return '<span style="color:var(--pflichtlektuere);">Name ist Pflichtfeld.</span>'

    try:
        save_profile(profile_data)
    except Exception as e:
        return f'<span style="color:var(--pflichtlektuere);">Fehler: {esc(str(e))}</span>'

    return '<span style="color:var(--lesenswert);">✓ Profil gespeichert</span>'


API_KEY_FIELDS = [
    ("api_key", KEY_FILE, "OpenRouter"),
    ("s2_api_key", S2_KEY_FILE, "Semantic Scholar"),
    ("zotero_user_id", ZOTERO_USER_ID_FILE, "Zotero User-ID"),
    ("zotero_api_key", ZOTERO_API_KEY_FILE, "Zotero API-Key"),
    ("mistral_api_key", MISTRAL_KEY_FILE, "Mistral"),
]


@app.route("/api/setup/api-keys", methods=["POST"])
def api_setup_api_keys():
    """HTMX: Write any non-empty API key fields to ~/.config/mojo/."""
    esc = html_mod.escape
    updated = []
    errors = []

    for form_field, key_file, label in API_KEY_FIELDS:
        val = request.form.get(form_field, "").strip()
        if not val:
            continue
        try:
            key_file.parent.mkdir(parents=True, exist_ok=True)
            key_file.write_text(val + "\n")
            key_file.chmod(0o600)
            updated.append(label)
        except OSError as e:
            errors.append(f"{label}: {e}")

    if errors and not updated:
        return f'<span style="color:var(--pflichtlektuere);">Fehler: {esc("; ".join(errors))}</span>'

    msg = "Keine Änderungen." if not updated else f"✓ Aktualisiert: {', '.join(updated)}"
    if errors:
        msg += f" · Fehler: {esc('; '.join(errors))}"
    color = "lesenswert" if updated and not errors else "scannen" if updated else "muted"
    return f'<span style="color:var(--{color});">{msg}</span>'


@app.route("/api/setup/ingest", methods=["POST"])
def api_setup_ingest():
    """HTMX: Run Zotero ingest (corpus.json update)."""
    from journal_bot import corpus
    esc = html_mod.escape
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            corpus.ingest(
                collection_name=ZOTERO_COLLECTION,
                output=CORPUS_JSON,
            )
        output = buf.getvalue()
        return (
            f'<div style="color:var(--lesenswert); font-size:.85rem;">'
            f'✓ Corpus aktualisiert</div>'
            f'<pre style="font-size:.8rem; margin-top:.5rem; white-space:pre-wrap;">'
            f'{esc(output[-1000:])}</pre>'
        )
    except Exception as e:
        return (
            f'<div style="color:var(--pflichtlektuere); font-size:.85rem;">'
            f'Fehler: {esc(str(e))}</div>'
            f'<pre style="font-size:.8rem; margin-top:.5rem; white-space:pre-wrap;">'
            f'{esc(buf.getvalue()[-500:])}</pre>'
        )


@app.route("/api/setup/summarize", methods=["POST"])
def api_setup_summarize():
    """HTMX: Run summarize (summaries.json update)."""
    from journal_bot import summarize
    esc = html_mod.escape
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            summarize.run(corpus_path=CORPUS_JSON, output_path=SUMMARIES_JSON)
        output = buf.getvalue()
        return (
            f'<div style="color:var(--lesenswert); font-size:.85rem;">'
            f'✓ Summaries aktualisiert</div>'
            f'<pre style="font-size:.8rem; margin-top:.5rem; white-space:pre-wrap;">'
            f'{esc(output[-1000:])}</pre>'
        )
    except Exception as e:
        return (
            f'<div style="color:var(--pflichtlektuere); font-size:.85rem;">'
            f'Fehler: {esc(str(e))}</div>'
        )


# ========================================================= Matrix API ===


def _save_journals_json() -> None:
    """Write current JOURNALS state back to journals.json."""
    data = json.loads(JOURNALS_JSON.read_text(encoding="utf-8"))
    journal_by_short = {j["short"]: j for j in data.get("journals", [])}
    for j in JOURNALS:
        if j.short in journal_by_short:
            journal_by_short[j.short]["tier"] = j.tier
    data["journals"] = list(journal_by_short.values())
    JOURNALS_JSON.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _save_diskursraeume_json() -> None:
    """Write current DISCOURSE_SPACES + cluster assignments to diskursraeume.json."""
    today = datetime.now().strftime("%Y-%m-%d")
    dr_data = {
        "version": 1,
        "discourse_spaces": {},
        "journal_clusters": {},
    }
    for key, meta in DISCOURSE_SPACES.items():
        dr_data["discourse_spaces"][key] = {
            "name": meta["name"],
            "description": meta["description"],
            "created": meta.get("created", today),
            "modified": today,
        }
    for j in JOURNALS:
        if j.clusters:
            dr_data["journal_clusters"][j.short] = list(j.clusters)
    DISKURSRAEUME_JSON.write_text(
        json.dumps(dr_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


@app.route("/api/setup/matrix", methods=["POST"])
def api_setup_matrix():
    """Save journal tier + cluster assignments from the matrix form."""
    data = request.get_json(force=True)
    journal_map = data.get("journals", {})

    changes = 0
    short_to_journal = {j.short: j for j in JOURNALS}
    for short, vals in journal_map.items():
        j = short_to_journal.get(short)
        if not j:
            continue
        new_tier = vals.get("tier", j.tier)
        new_clusters = vals.get("clusters", list(j.clusters))
        if new_tier != j.tier:
            j.tier = new_tier
            changes += 1
        if sorted(new_clusters) != sorted(j.clusters):
            j.clusters = new_clusters
            changes += 1

    if changes:
        _save_journals_json()
        _save_diskursraeume_json()

    return jsonify({"ok": True, "message": f"✓ {changes} Änderungen gespeichert"})


@app.route("/api/setup/diskursraum/_new", methods=["POST"])
def api_setup_diskursraum_new():
    """Create a new discourse space. Returns JSON."""
    import re as re_mod
    data = request.form
    key = data.get("key", "").strip().lower()
    name = data.get("name", "").strip()
    description = data.get("description", "").strip()

    if not key or not name:
        return jsonify({"ok": False, "error": "Schlüssel und Name sind Pflicht."})
    if not re_mod.match(r'^[a-z_]+$', key):
        return jsonify({"ok": False, "error": "Schlüssel: nur Kleinbuchstaben und _"})
    if key in DISCOURSE_SPACES:
        return jsonify({"ok": False, "error": f"«{key}» existiert bereits."})

    today = datetime.now().strftime("%Y-%m-%d")
    DISCOURSE_SPACES[key] = {
        "name": name,
        "description": description,
        "created": today,
        "modified": today,
    }
    _save_diskursraeume_json()
    return jsonify({"ok": True, "key": key, "name": name})


@app.route("/api/setup/diskursraum/<key>", methods=["POST"])
def api_setup_diskursraum_update(key: str):
    """Update discourse space name/description. Returns JSON."""
    if key not in DISCOURSE_SPACES:
        return jsonify({"ok": False, "error": "Nicht gefunden."}), 404

    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()

    if name:
        DISCOURSE_SPACES[key]["name"] = name
    if description is not None:
        DISCOURSE_SPACES[key]["description"] = description
    DISCOURSE_SPACES[key]["modified"] = datetime.now().strftime("%Y-%m-%d")
    _save_diskursraeume_json()

    return jsonify({"ok": True, "key": key, "name": DISCOURSE_SPACES[key]["name"]})


@app.route("/api/setup/diskursraum/<key>", methods=["DELETE"])
def api_setup_diskursraum_delete(key: str):
    """Delete a discourse space. Returns JSON."""
    if key not in DISCOURSE_SPACES:
        return jsonify({"ok": False, "error": "Nicht gefunden."}), 404

    name = DISCOURSE_SPACES[key]["name"]
    del DISCOURSE_SPACES[key]

    for j in JOURNALS:
        if key in j.clusters:
            j.clusters.remove(key)

    _save_diskursraeume_json()
    return jsonify({"ok": True, "name": name})


# ── Projects CRUD ──

@app.route("/api/setup/project/_new", methods=["POST"])
def api_setup_project_new():
    """Create a new project. Expects JSON."""
    data = request.get_json(force=True)
    key = (data.get("key") or "").strip().lower()
    name = (data.get("name") or "").strip()
    if not key or not name:
        return jsonify({"ok": False, "error": "Schlüssel und Name sind Pflicht."})

    projects = _load_projects()
    if any(p["key"] == key for p in projects):
        return jsonify({"ok": False, "error": f"Schlüssel «{key}» existiert bereits."})

    projects.append({
        "key": key,
        "name": name,
        "type": "funded_project",
        "status": "active",
        "funder": data.get("funder", ""),
        "period": data.get("period", ""),
        "description": data.get("description", ""),
        "relevance_shifts": [],
        "connected_publications": [],
    })
    _save_projects(projects)
    return jsonify({"ok": True})


@app.route("/api/setup/project/<key>", methods=["POST"])
def api_setup_project_update(key: str):
    """Update an existing project. Expects JSON."""
    data = request.get_json(force=True)
    projects = _load_projects()
    proj = next((p for p in projects if p["key"] == key), None)
    if not proj:
        return jsonify({"ok": False, "error": "Projekt nicht gefunden."}), 404

    proj["name"] = (data.get("name") or proj["name"]).strip()
    proj["status"] = data.get("status", proj.get("status", "active"))
    proj["funder"] = (data.get("funder") or "").strip()
    proj["period"] = (data.get("period") or "").strip()
    proj["description"] = (data.get("description") or "").strip()

    rs_raw = data.get("relevance_shifts", "")
    if isinstance(rs_raw, str):
        proj["relevance_shifts"] = [l.strip() for l in rs_raw.split("\n") if l.strip()]
    elif isinstance(rs_raw, list):
        proj["relevance_shifts"] = rs_raw

    cp_raw = data.get("connected_publications", "")
    if isinstance(cp_raw, str):
        proj["connected_publications"] = [p.strip() for p in cp_raw.split(",") if p.strip()]
    elif isinstance(cp_raw, list):
        proj["connected_publications"] = cp_raw

    _save_projects(projects)
    return jsonify({"ok": True})


@app.route("/api/setup/project/<key>", methods=["DELETE"])
def api_setup_project_delete(key: str):
    """Delete a project."""
    projects = _load_projects()
    before = len(projects)
    projects = [p for p in projects if p["key"] != key]
    if len(projects) == before:
        return jsonify({"ok": False, "error": "Nicht gefunden."}), 404
    _save_projects(projects)
    return jsonify({"ok": True})


def _matrix_context() -> dict:
    """Shared context for rendering the matrix fragment."""
    store = _store()
    db_stats = store.stats()
    return {
        "journals": JOURNALS,
        "journal_counts": db_stats.get("by_journal", {}),
        "spaces": list(DISCOURSE_SPACES.items()),
    }


@app.route("/api/setup/matrix-fragment")
def api_setup_matrix_fragment():
    """HTMX: Return just the matrix table HTML (for reload after diskurs changes)."""
    return render_template("_matrix_table.html", **_matrix_context())


# ======================================================= Journal CRUD ===


@app.route("/api/setup/journal", methods=["POST"])
def api_setup_journal_add():
    """Add a new journal.  Expects JSON body."""
    from journal_bot.journals import add_journal
    data = request.get_json(force=True)
    esc = html_mod.escape

    name = (data.get("name") or "").strip()
    short = (data.get("short") or "").strip()
    journal_type = (data.get("type") or "openalex").strip()
    url = (data.get("url") or "").strip()
    issn = (data.get("issn") or "").strip()
    tier = (data.get("tier") or "B").strip()
    clusters = data.get("clusters") or []

    if not name or not short:
        return jsonify({"ok": False, "error": "Name und Kurzname sind Pflicht."})

    msg = add_journal(
        name=name,
        short=short,
        journal_type=journal_type,
        url=url,
        issn=issn,
        tier=tier,
        clusters=clusters,
    )

    if not msg.startswith("✓"):
        return jsonify({"ok": False, "error": msg})

    # Reload in-memory JOURNALS list
    _reload_journals()

    return jsonify({"ok": True, "message": msg})


@app.route("/api/setup/journal/<short>", methods=["DELETE"])
def api_setup_journal_delete(short: str):
    """Remove a journal.  Articles stay in the DB."""
    from journal_bot.journals import remove_journal

    msg = remove_journal(short)
    if not msg.startswith("✓"):
        return jsonify({"ok": False, "error": msg}), 404

    _reload_journals()
    return jsonify({"ok": True, "message": msg})


@app.route("/api/setup/journal/test", methods=["POST"])
def api_setup_journal_test():
    """Test-fetch a journal config.  Returns article count + sample titles."""
    from journal_bot.settings import JournalConfig
    from journal_bot.fetchers import build_fetcher

    data = request.get_json(force=True)
    jc = JournalConfig(
        name=data.get("name", "Test"),
        short=data.get("short", "_test"),
        type=data.get("type", "openalex"),
        url=data.get("url", ""),
        issn=data.get("issn", ""),
        tier="C",
    )

    try:
        fetcher = build_fetcher(jc)
        articles = fetcher.fetch()
    except Exception as e:
        return jsonify({"ok": False, "error": str(e), "count": 0, "sample": []})

    sample = [
        {"title": a.title, "authors": a.authors, "date": a.published}
        for a in articles[:5]
    ]
    return jsonify({
        "ok": True,
        "count": len(articles),
        "sample": sample,
        "message": f"{len(articles)} Artikel gefunden",
    })


@app.route("/api/openalex/lookup")
def api_openalex_lookup():
    """Check if an ISSN is indexed in OpenAlex.  Returns source metadata."""
    import httpx as _httpx
    from journal_bot.journal_topics import compute_source_profile_fit, normalize_source_topics

    issn = request.args.get("issn", "").strip()
    if not issn:
        return jsonify({"ok": False, "error": "ISSN fehlt."})

    try:
        resp = _httpx.get(
            f"https://api.openalex.org/sources/issn:{issn}",
            params={"mailto": "mojo@localhost"},
            timeout=15,
        )
        if resp.status_code == 404:
            return jsonify({"ok": True, "found": False, "message": f"ISSN {issn} nicht in OpenAlex."})
        resp.raise_for_status()
        src = resp.json()
        top_topics, topics_source = normalize_source_topics(src, limit=5)
        profile_fit = compute_source_profile_fit(src)
        return jsonify({
            "ok": True,
            "found": True,
            "name": src.get("display_name", ""),
            "works_count": src.get("works_count", 0),
            "openalex_id": src.get("id", ""),
            "top_topics": top_topics,
            "topics_source": topics_source,
            "profile_fit": profile_fit,
            "message": f"{src.get('display_name', '?')} — {src.get('works_count', '?')} Werke",
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})


@app.route("/api/openalex/journal-candidates")
def api_openalex_journal_candidates():
    from journal_bot.journal_topics import discover_candidate_journals

    try:
        max_topics = int(request.args.get("max_topics") or 8)
        per_topic = int(request.args.get("per_topic") or 6)
        max_results = int(request.args.get("max_results") or 20)
        result = discover_candidate_journals(
            max_topics=max(1, min(max_topics, 12)),
            per_topic=max(1, min(per_topic, 12)),
            max_results=max(1, min(max_results, 50)),
        )
    except Exception as exc:
        return (
            f'<div style="padding:.9rem; border:1px solid var(--pflichtlektuere); border-radius:8px;">'
            f'<strong>Fehler:</strong> {html_mod.escape(str(exc))}</div>'
        )

    return render_template("_journal_candidates.html", result=result)


@app.route("/api/openalex/journal-profiles")
def api_openalex_journal_profiles():
    from journal_bot.journal_topics import journal_profile_status

    return render_template(
        "_journal_profiles.html",
        journal_profiles=journal_profile_status(),
    )


@app.route("/api/openalex/journal-profiles/refresh", methods=["POST"])
def api_openalex_journal_profiles_refresh():
    from journal_bot.journal_topics import journal_profile_status, refresh_journal_profiles

    try:
        topic_limit = int(request.form.get("topic_limit") or 80)
        topic_limit = max(10, min(topic_limit, 200))
        refresh_journal_profiles(topic_limit=topic_limit)
        status = journal_profile_status()
        status["message"] = (
            f"Profile aktualisiert: {status['found_count']} gefunden, "
            f"{status['missing_count']} ohne OpenAlex-Profil."
        )
        return render_template("_journal_profiles.html", journal_profiles=status)
    except Exception as exc:
        return (
            f'<div class="card" style="border-color:var(--pflichtlektuere);">'
            f'<strong>Fehler:</strong> {html_mod.escape(str(exc))}</div>'
        )


@app.route("/api/setup/journal/custom-config", methods=["POST"])
def api_setup_journal_custom_config():
    """Save a custom fetcher config.  Validates against the fixed schema."""
    from journal_bot.fetchers.configurable_fetcher import save_config, validate_config

    data = request.get_json(force=True)
    short = (data.get("short") or "").strip()
    config = data.get("config")

    if not short:
        return jsonify({"ok": False, "error": "Kurzname fehlt."})
    if not isinstance(config, dict):
        return jsonify({"ok": False, "error": "config muss ein JSON-Objekt sein."})

    errors = validate_config(config)
    if errors:
        return jsonify({"ok": False, "error": "; ".join(errors)})

    try:
        path = save_config(short, config)
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)})

    return jsonify({"ok": True, "message": f"✓ Config gespeichert: {path.name}"})


@app.route("/api/setup/scan/preview", methods=["POST"])
def api_setup_scan_preview():
    from journal_bot.scan_jobs import prepare_scan_scope

    data = request.get_json(force=True)
    store = _store()
    try:
        scope = _resolve_historical_scan_scope(data, store)
        preview = prepare_scan_scope(
            store,
            start_year=scope["start_year"],
            end_year=scope["end_year"],
            journals=scope["journals"] or None,
            verbose=False,
            fetch_metadata=True,
        )
    except Exception as exc:
        return (
            f'<div class="card" style="border-color:var(--pflichtlektuere);">'
            f'<strong>Fehler:</strong> {html_mod.escape(str(exc))}</div>'
        )

    return render_template(
        "_scan_preview.html",
        scope=scope,
        preview=preview,
        cost_source_label=_scan_cost_source_label(preview["avg_cost_source"]),
    )


@app.route("/api/setup/scan/run", methods=["POST"])
def api_setup_scan_run():
    from journal_bot import agent as agent_mod
    from journal_bot.batch_digest import run_batch_digest
    from journal_bot.scan_jobs import prepare_scan_scope
    from journal_bot.settings import MODEL_AGENT

    data = request.get_json(force=True)
    store = _store()

    try:
        scope = _resolve_historical_scan_scope(data, store)
        cost_limit_usd = float(data.get("cost_limit_usd") or 0)
        if cost_limit_usd <= 0:
            raise ValueError("Bitte ein positives Kostenlimit angeben.")
        model = str(data.get("model") or MODEL_AGENT).strip() or MODEL_AGENT
    except Exception as exc:
        return (
            f'<div class="card" style="border-color:var(--pflichtlektuere);">'
            f'<strong>Fehler:</strong> {html_mod.escape(str(exc))}</div>'
        )

    try:
        preview_before = prepare_scan_scope(
            store,
            start_year=scope["start_year"],
            end_year=scope["end_year"],
            journals=scope["journals"] or None,
            verbose=False,
            fetch_metadata=True,
        )
    except Exception as exc:
        return (
            f'<div class="card" style="border-color:var(--pflichtlektuere);">'
            f'<strong>Fehler beim Vorziehen der Metadaten:</strong> {html_mod.escape(str(exc))}</div>'
        )

    pending = store.find_unprocessed(
        journals=scope["journals"] or None,
        since_year=scope["start_year"],
        end_year=scope["end_year"],
    )

    logs: list[str] = []

    def _capture_log(message: str) -> None:
        logs.append(message)

    batch = run_batch_digest(
        pending,
        store,
        model=model,
        no_screen=False,
        verbose=True,
        logger=_capture_log,
        cost_limit_usd=cost_limit_usd,
    )

    summary_after = prepare_scan_scope(
        store,
        start_year=scope["start_year"],
        end_year=scope["end_year"],
        journals=scope["journals"] or None,
        verbose=False,
        fetch_metadata=False,
    )

    return render_template(
        "_scan_run_result.html",
        scope=scope,
        preview_before=preview_before,
        summary_after=summary_after,
        batch=batch,
        logs=logs,
        cost_limit_usd=cost_limit_usd,
        model=model,
        screen_model=agent_mod.MODEL_SCREEN,
        cost_source_label=_scan_cost_source_label(summary_after["avg_cost_source"]),
    )


@app.route("/api/setup/monitoring-fragment")
def api_setup_monitoring_fragment():
    return _render_monitoring_panel()


@app.route("/api/setup/monitoring/install", methods=["POST"])
def api_setup_monitoring_install():
    from journal_bot.monitoring import install_monitoring_schedule

    data = request.get_json(force=True)
    try:
        install_monitoring_schedule(
            weekday=int(data.get("weekday") or 1),
            hour=int(data.get("hour") or 7),
            minute=int(data.get("minute") or 0),
            digest_next=int(data.get("digest_next") or 50),
            since_year=int(data.get("since_year") or datetime.now().year - 1),
        )
        return _render_monitoring_panel(
            message="Monitoring-Zeitplan gespeichert und LaunchAgent geladen.",
            message_ok=True,
        )
    except Exception as exc:
        return _render_monitoring_panel(message=str(exc), message_ok=False)


@app.route("/api/setup/monitoring/disable", methods=["POST"])
def api_setup_monitoring_disable():
    from journal_bot.monitoring import disable_monitoring_schedule

    try:
        disable_monitoring_schedule()
        return _render_monitoring_panel(
            message="Monitoring deaktiviert und LaunchAgent entfernt.",
            message_ok=True,
        )
    except Exception as exc:
        return _render_monitoring_panel(message=str(exc), message_ok=False)


@app.route("/api/setup/monitoring/run", methods=["POST"])
def api_setup_monitoring_run():
    from journal_bot.monitoring import run_monitoring_now

    data = request.get_json(force=True)
    try:
        run_result = run_monitoring_now(
            digest_next=int(data.get("digest_next") or 50),
            since_year=int(data.get("since_year") or datetime.now().year - 1),
        )
        message = "Monitoring-Lauf beendet." if run_result["ok"] else "Monitoring-Lauf mit Fehler beendet."
        return _render_monitoring_panel(
            message=message,
            message_ok=run_result["ok"],
            run_result=run_result,
        )
    except Exception as exc:
        return _render_monitoring_panel(message=str(exc), message_ok=False)


def _reload_journals() -> None:
    """Reload the in-memory JOURNALS list after add/delete."""
    import journal_bot.settings as _settings
    _settings.JOURNALS[:] = _settings._load_journals()


# ============================================================= Backup ===


@app.route("/api/backup/full")
def api_backup_full():
    """Download a full ZIP backup of local user data."""
    from journal_bot.backup import create_backup_archive
    import tempfile

    tmp = Path(tempfile.mktemp(suffix=".zip"))
    create_backup_archive(output_path=tmp)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    return send_file(
        tmp,
        as_attachment=True,
        download_name=f"mojo_user_backup_{ts}.zip",
        mimetype="application/zip",
    )


@app.route("/api/export/json")
def api_export_json():
    """Export all articles as JSON (metadata + verdicts, no full agent_entry)."""
    store = _store()
    with store._conn() as c:
        rows = c.execute(
            "SELECT id, journal_short, journal_full, title, authors_json, "
            "doi, url, year, agent_verdict, user_verdict, user_memo, cost_usd, "
            "fetched_at, agent_processed_at "
            "FROM articles ORDER BY year DESC, fetched_at DESC"
        ).fetchall()

    articles = []
    for r in rows:
        articles.append({
            "id": r["id"],
            "journal": r["journal_full"] or r["journal_short"],
            "title": r["title"],
            "authors": json.loads(r["authors_json"]) if r["authors_json"] else [],
            "doi": r["doi"],
            "url": r["url"],
            "year": r["year"],
            "agent_verdict": r["agent_verdict"],
            "user_verdict": r["user_verdict"],
            "user_memo": r["user_memo"],
            "cost_usd": r["cost_usd"],
            "fetched_at": r["fetched_at"],
            "processed_at": r["agent_processed_at"],
        })

    ts = datetime.now().strftime("%Y%m%d_%H%M")
    output = json.dumps(articles, ensure_ascii=False, indent=2)
    return Response(
        output,
        mimetype="application/json",
        headers={"Content-Disposition": f"attachment; filename=mojo_export_{ts}.json"},
    )


@app.route("/api/export/raw-package")
def api_export_raw_package():
    """Export article raw data without personal analysis fields."""
    from journal_bot.article_exchange import default_raw_export_path, export_raw_articles
    import tempfile

    tmp_dir = Path(tempfile.mkdtemp(prefix="mojo_raw_export_"))
    tmp = default_raw_export_path(tmp_dir)
    result = export_raw_articles(_store(), output_path=tmp)
    return send_file(
        result.archive_path,
        as_attachment=True,
        download_name=result.archive_path.name,
        mimetype="application/zip",
    )


@app.route("/api/export/csv")
def api_export_csv():
    """Export all articles as CSV."""
    store = _store()
    with store._conn() as c:
        rows = c.execute(
            "SELECT id, journal_short, journal_full, title, authors_json, "
            "doi, url, year, agent_verdict, user_verdict, user_memo, cost_usd, "
            "fetched_at, agent_processed_at "
            "FROM articles ORDER BY year DESC, fetched_at DESC"
        ).fetchall()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "id", "journal", "title", "authors", "doi", "url", "year",
        "agent_verdict", "user_verdict", "user_memo", "cost_usd",
        "fetched_at", "processed_at",
    ])
    for r in rows:
        authors = ", ".join(json.loads(r["authors_json"])) if r["authors_json"] else ""
        writer.writerow([
            r["id"],
            r["journal_full"] or r["journal_short"],
            r["title"],
            authors,
            r["doi"],
            r["url"],
            r["year"],
            r["agent_verdict"],
            r["user_verdict"],
            r["user_memo"],
            r["cost_usd"],
            r["fetched_at"],
            r["agent_processed_at"],
        ])

    ts = datetime.now().strftime("%Y%m%d_%H%M")
    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=mojo_export_{ts}.csv"},
    )


# ============================================================== Agent ===


@app.route("/agent")
def agent_page():
    """Research agent chat page."""
    store = _store()
    stats = store.stats()

    # Count corpus publications
    corpus_count = 0
    if CORPUS_JSON.exists():
        try:
            data = json.loads(CORPUS_JSON.read_text(encoding="utf-8"))
            corpus_count = len(data.get("publications", []))
        except Exception:
            pass

    ctx = _normalize_agent_context(_agent_state["context"])
    return render_template(
        "agent.html",
        db_article_count=stats["total"],
        corpus_count=corpus_count,
        context_set=bool(ctx.get("prompt_context")),
        context_preview=(
            ctx["prompt_context"][:300] + "…"
            if ctx.get("prompt_context") and len(ctx["prompt_context"]) > 300
            else ctx.get("prompt_context", "")
        ),
        context_chars=ctx.get("prompt_chars", 0),
        raw_chars=ctx.get("raw_chars", 0),
        context_source=ctx.get("source", ""),
        context_model=ctx.get("model", ""),
        context_tokens=ctx.get("tokens_used", 0),
        context_cost_display=f"${ctx['cost_usd']:.4f}" if ctx.get("cost_usd") else "",
        context_units_count=len(ctx.get("argument_units", [])),
        messages=_agent_state["messages"],
    )


@app.route("/api/agent/context", methods=["POST", "DELETE"])
def api_agent_context():
    """Set or clear the agent's text context (persisted to disk)."""
    if request.method == "DELETE":
        _agent_state["context"] = _empty_agent_context()
        _AGENT_CONTEXT_FILE.unlink(missing_ok=True)
        _LEGACY_AGENT_CONTEXT_FILE.unlink(missing_ok=True)
        return jsonify({"ok": True})

    from journal_bot.research_agent import prepare_context

    data = request.get_json(force=True)
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "Kein Text übergeben."}), 400

    ctx = prepare_context(text)
    _agent_state["context"] = ctx
    _save_agent_context(ctx)
    return jsonify({
        "ok": True,
        "raw_chars": ctx["raw_chars"],
        "context_chars": ctx["prompt_chars"],
        "source": ctx["source"],
        "model": ctx["model"],
        "tokens_used": ctx["tokens_used"],
        "cost_usd": ctx["cost_usd"],
        "argument_units_count": len(ctx.get("argument_units", [])),
        "preview": (
            ctx["prompt_context"][:300] + "…"
            if len(ctx["prompt_context"]) > 300
            else ctx["prompt_context"]
        ),
    })


@app.route("/api/agent/chat", methods=["POST"])
def api_agent_chat():
    """Process a chat message with the research agent."""
    from journal_bot.research_agent import chat as agent_chat

    data = request.get_json(force=True)
    message = data.get("message", "").strip()
    history = data.get("history", [])

    if not message:
        return jsonify({"error": "Keine Nachricht."}), 400

    user_context = _normalize_agent_context(_agent_state["context"]).get("prompt_context") or None

    try:
        result = agent_chat(
            message=message,
            history=history,
            user_context=user_context,
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    html_content = _render_agent_markdown(result["content"])

    # Store server-side for page reload
    msgs = _agent_state["messages"]
    msgs.append({"role": "user", "content": message})
    msgs.append({
        "role": "assistant",
        "content": result["content"],
        "content_html": html_content,
    })
    # Keep last 40 messages
    _agent_state["messages"] = msgs[-40:]

    return jsonify({
        "content": result["content"],
        "html": html_content,
        "tokens_used": result["tokens_used"],
        "cost_usd": result["cost_usd"],
    })


@app.route("/api/agent/clear", methods=["POST"])
def api_agent_clear():
    """Clear agent chat history."""
    _agent_state["messages"] = []
    return jsonify({"ok": True})


# ============================================================== Costs ===


@app.route("/api/costs/summary")
def api_costs_summary():
    """JSON aggregation of LLM costs from llm_calls.

    Query params:
      since=YYYY-MM-DD (default: 30 days ago)
      by=endpoint|model|day (default: endpoint)
    """
    from datetime import timedelta
    from journal_bot.llm_log import summarize_costs, total_cost_since

    since_param = (request.args.get("since") or "").strip()
    by = (request.args.get("by") or "endpoint").strip()
    if by not in ("endpoint", "model", "day"):
        return jsonify({"error": "by must be endpoint|model|day"}), 400

    if not since_param:
        since_param = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

    try:
        rows = summarize_costs(since=since_param, by=by)
        total = total_cost_since(since_param)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
    return jsonify({"since": since_param, "by": by, "total": total, "rows": rows})


@app.route("/api/costs/recent")
def api_costs_recent():
    """JSON list of the most recent LLM calls."""
    from journal_bot.llm_log import recent_calls

    limit = max(1, min(int(request.args.get("limit") or 50), 500))
    return jsonify({"calls": recent_calls(limit=limit)})


@app.route("/api/costs/fragment")
def api_costs_fragment():
    """HTMX fragment: cost panel for the setup page."""
    from datetime import timedelta
    from journal_bot.llm_log import summarize_costs, total_cost_since, recent_calls

    since_7d = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
    since_30d = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    since_today = datetime.now().strftime("%Y-%m-%d")

    by_endpoint = summarize_costs(since=since_30d, by="endpoint")
    by_day = summarize_costs(since=since_30d, by="day")
    by_model = summarize_costs(since=since_30d, by="model")
    last_calls = recent_calls(limit=20)
    total_today = total_cost_since(since_today)
    total_7d = total_cost_since(since_7d)
    total_30d = total_cost_since(since_30d)

    esc = html_mod.escape
    parts: list[str] = []
    parts.append(
        f'<div class="card" style="margin-top:.75rem;">'
        f'<h3 style="margin-bottom:.5rem;">LLM-Kosten</h3>'
    )
    parts.append(
        f'<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:.5rem;margin-bottom:.75rem;">'
        f'<div><div style="font-size:.75rem;color:var(--muted);">Heute</div>'
        f'<div style="font-size:1.2rem;font-weight:600;">${total_today:.3f}</div></div>'
        f'<div><div style="font-size:.75rem;color:var(--muted);">Letzte 7 Tage</div>'
        f'<div style="font-size:1.2rem;font-weight:600;">${total_7d:.2f}</div></div>'
        f'<div><div style="font-size:.75rem;color:var(--muted);">Letzte 30 Tage</div>'
        f'<div style="font-size:1.2rem;font-weight:600;">${total_30d:.2f}</div></div>'
        f'</div>'
    )

    if by_endpoint:
        parts.append('<details open style="margin-top:.5rem;"><summary><strong>Nach Endpoint (30 Tage)</strong></summary>')
        parts.append('<table style="width:100%;font-size:.85rem;margin-top:.4rem;border-collapse:collapse;">')
        parts.append('<thead><tr><th style="text-align:left;">Endpoint</th><th style="text-align:right;">Calls</th><th style="text-align:right;">Total</th></tr></thead><tbody>')
        for r in by_endpoint:
            parts.append(
                f'<tr><td>{esc(r["bucket"] or "?")}</td>'
                f'<td style="text-align:right;">{r["calls"]}</td>'
                f'<td style="text-align:right;">${r["total_cost"]:.3f}</td></tr>'
            )
        parts.append('</tbody></table></details>')

    if by_model:
        parts.append('<details style="margin-top:.5rem;"><summary><strong>Nach Modell (30 Tage)</strong></summary>')
        parts.append('<table style="width:100%;font-size:.85rem;margin-top:.4rem;border-collapse:collapse;">')
        parts.append('<thead><tr><th style="text-align:left;">Modell</th><th style="text-align:right;">Calls</th><th style="text-align:right;">Total</th></tr></thead><tbody>')
        for r in by_model:
            parts.append(
                f'<tr><td>{esc(r["bucket"] or "?")}</td>'
                f'<td style="text-align:right;">{r["calls"]}</td>'
                f'<td style="text-align:right;">${r["total_cost"]:.3f}</td></tr>'
            )
        parts.append('</tbody></table></details>')

    if by_day:
        parts.append('<details style="margin-top:.5rem;"><summary><strong>Nach Tag (30 Tage)</strong></summary>')
        parts.append('<table style="width:100%;font-size:.85rem;margin-top:.4rem;border-collapse:collapse;">')
        parts.append('<thead><tr><th style="text-align:left;">Tag</th><th style="text-align:right;">Calls</th><th style="text-align:right;">Total</th></tr></thead><tbody>')
        for r in sorted(by_day, key=lambda x: x["bucket"], reverse=True):
            parts.append(
                f'<tr><td>{esc(r["bucket"] or "?")}</td>'
                f'<td style="text-align:right;">{r["calls"]}</td>'
                f'<td style="text-align:right;">${r["total_cost"]:.3f}</td></tr>'
            )
        parts.append('</tbody></table></details>')

    if last_calls:
        parts.append('<details style="margin-top:.5rem;"><summary><strong>Letzte 20 Calls</strong></summary>')
        parts.append('<table style="width:100%;font-size:.75rem;margin-top:.4rem;border-collapse:collapse;">')
        parts.append('<thead><tr><th style="text-align:left;">Zeit</th><th>Endpoint</th><th>Modell</th><th style="text-align:right;">Cost</th><th>Status</th></tr></thead><tbody>')
        for c in last_calls:
            ts = (c["timestamp"] or "")[:19].replace("T", " ")
            cost_str = f'${c["cost_usd"]:.4f}'
            status = c["status"] or "?"
            color = "var(--lesenswert)" if status == "ok" else "var(--pflichtlektuere)"
            parts.append(
                f'<tr><td>{esc(ts)}</td>'
                f'<td>{esc(c["endpoint"])}</td>'
                f'<td>{esc((c["model"] or "")[:25])}</td>'
                f'<td style="text-align:right;">{cost_str}</td>'
                f'<td style="color:{color};">{esc(status)}</td></tr>'
            )
        parts.append('</tbody></table></details>')

    parts.append('</div>')
    return "\n".join(parts)


# ============================================================== Main ===


def main():
    print("[web] MOJO UI auf http://mojo.localhost:5555")
    app.run(debug=True, host="127.0.0.1", port=5555)


if __name__ == "__main__":
    main()
