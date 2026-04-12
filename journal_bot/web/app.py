"""MOJO Web UI — Flask + HTMX prototype."""

from __future__ import annotations

import json
from flask import Flask, render_template, request, abort

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
    has_any_filter = any(request.args.get(k) for k in ("year", "cluster", "journal", "verdict"))
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

    # Additional verdict filter
    if verdict_filter:
        articles = [a for a in articles if a.agent_verdict == verdict_filter]

    # Citation hits across all verdicts
    cites_you = [a for a in articles if a.citation_hits]

    # Group by verdict
    by_verdict = {}
    for v in VERDICT_ORDER:
        by_verdict[v] = [a for a in articles if a.agent_verdict == v]

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
        by_verdict[v] = [a for a in articles if a.agent_verdict == v]

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


def main():
    app.run(debug=True, port=5555)


if __name__ == "__main__":
    main()
