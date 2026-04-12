"""MOJO Web UI — Flask + HTMX prototype."""

from __future__ import annotations

import json
from flask import Flask, render_template, request, abort, jsonify

from journal_bot.store import Store
from journal_bot.settings import DISCOURSE_SPACES, JOURNALS, journals_in_cluster

app = Flask(
    __name__,
    template_folder="templates",
    static_folder="static",
)

VERDICT_ORDER = ["pflichtlektuere", "lesenswert", "scannen", "ignorieren"]
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


def _journal_full_name(short: str) -> str:
    for j in JOURNALS:
        if j.short == short:
            return j.name
    return short


# ----------------------------------------------------------------- Routes ---

@app.route("/")
def digest():
    """Main digest view with filters."""
    from datetime import date
    store = _store()
    # Default to current year if no filters set at all
    has_any_filter = any(request.args.get(k) for k in ("year", "cluster", "journal", "verdict", "archived"))
    year = request.args.get("year", type=int)
    if year is None and not has_any_filter:
        year = date.today().year
    cluster = request.args.get("cluster", "")
    journal = request.args.get("journal", "")
    verdict_filter = request.args.get("verdict", "")

    # Build query
    journals_filter = None
    if cluster:
        journals_filter = [j.short for j in journals_in_cluster(cluster)]
    if journal:
        journals_filter = [journal]

    articles = store.find_in_window(
        start_year=year,
        end_year=year if year else None,
        journals=journals_filter,
        only_processed=True,
    )

    # Parse entry JSON
    for a in articles:
        if a.agent_entry and isinstance(a.agent_entry, str):
            a.agent_entry = json.loads(a.agent_entry)
        a.journal_full = a.journal_full or _journal_full_name(a.journal_short)

    # Hide archived unless explicitly requested
    show_archived = request.args.get("archived") == "1"
    if not show_archived:
        articles = [a for a in articles if not a.is_archived]

    # Additional verdict filter (uses effective verdict)
    if verdict_filter:
        articles = [a for a in articles if a.effective_verdict == verdict_filter]

    # Citation hits across all verdicts
    cites_you = [a for a in articles if a.citation_hits]

    # Group by effective verdict
    by_verdict = {}
    for v in VERDICT_ORDER:
        by_verdict[v] = [a for a in articles if a.effective_verdict == v]

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
        articles=articles,
        by_verdict=by_verdict,
        cites_you=cites_you,
        verdict_label=VERDICT_LABEL,
        relation_label=RELATION_LABEL,
        all_years=all_years,
        clusters=clusters,
        journal_list=journal_list,
        filters={
            "year": year,
            "cluster": cluster,
            "journal": journal,
            "verdict": verdict_filter,
        },
        total=len(articles),
    )


@app.route("/article/<article_id>")
def article_detail(article_id: str):
    """Single article detail view."""
    store = _store()
    a = store.get(article_id)
    if not a:
        abort(404)
    if a.agent_entry and isinstance(a.agent_entry, str):
        a.agent_entry = json.loads(a.agent_entry)
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
                else:
                    total = 0
                    verdicts = {}
            spaces.append({
                "key": key,
                "name": meta["name"],
                "description": meta["description"],
                "journals": js,
                "total": total,
                "verdicts": verdicts,
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
            a.agent_entry = json.loads(a.agent_entry)
        a.journal_full = a.journal_full or _journal_full_name(a.journal_short)

    by_verdict = {}
    for v in VERDICT_ORDER:
        by_verdict[v] = [a for a in articles if a.effective_verdict == v]

    cites_you = [a for a in articles if a.citation_hits]

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
        verdict_label=VERDICT_LABEL,
        relation_label=RELATION_LABEL,
        total=len(articles),
    )


@app.route("/api/tooltip/<article_id>")
def api_tooltip(article_id: str):
    """HTMX endpoint: lazy-load tooltip content on hover."""
    store = _store()
    a = store.get(article_id)
    if not a or not a.agent_entry:
        return ""
    if isinstance(a.agent_entry, str):
        a.agent_entry = json.loads(a.agent_entry)
    e = a.agent_entry
    parts = []
    if e.get("verdict_begruendung"):
        parts.append(f'<div class="tooltip-verdict">{e["verdict_begruendung"][:300]}</div>')
    if e.get("kernthese"):
        parts.append(f'<div class="tooltip-kernthese">{e["kernthese"][:400]}</div>')
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

    # Auto-deepen on upgrade to lesenswert
    if is_upgrade_to_lesenswert:
        _run_deepen(article_id, store)

    # Re-fetch to get updated state
    a = store.get(article_id)
    if a.agent_entry and isinstance(a.agent_entry, str):
        a.agent_entry = json.loads(a.agent_entry)
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
        a.agent_entry = json.loads(a.agent_entry)
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
    for a in articles:
        if a.agent_entry and isinstance(a.agent_entry, str):
            a.agent_entry = json.loads(a.agent_entry)
        a.journal_full = a.journal_full or _journal_full_name(a.journal_short)

    # Available years
    with store._conn() as c:
        year_rows = c.execute(
            "SELECT DISTINCT year FROM articles WHERE agent_verdict IS NOT NULL "
            "ORDER BY year DESC"
        ).fetchall()
        all_years = [r[0] for r in year_rows if r[0]]

    return render_template(
        "review.html",
        articles=articles,
        verdict_label=VERDICT_LABEL,
        relation_label=RELATION_LABEL,
        all_years=all_years,
        filters={"year": year, "verdict": verdict_filter},
        total=len(articles),
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
            a.agent_entry = json.loads(a.agent_entry)
        a.journal_full = a.journal_full or _journal_full_name(a.journal_short)

    # Group by direction
    upgrades = [a for a in articles
                if VERDICT_ORDER.index(a.user_verdict) < VERDICT_ORDER.index(a.agent_verdict)
                if a.user_verdict in VERDICT_ORDER and a.agent_verdict in VERDICT_ORDER]
    downgrades = [a for a in articles
                  if VERDICT_ORDER.index(a.user_verdict) > VERDICT_ORDER.index(a.agent_verdict)
                  if a.user_verdict in VERDICT_ORDER and a.agent_verdict in VERDICT_ORDER]
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


def main():
    app.run(debug=True, port=5555)


if __name__ == "__main__":
    main()
