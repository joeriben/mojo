"""MOJO Web UI — Flask + HTMX prototype."""

from __future__ import annotations

import contextlib
import csv
import html as html_mod
import io
import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from flask import (
    Flask, render_template, render_template_string, request,
    abort, jsonify, send_file, session, Response,
)

from journal_bot.store import Store, ARTICLES_DB
from journal_bot.settings import (
    CORPUS_JSON,
    DIGEST_DIR,
    DISCOURSE_SPACES,
    DISKURSRAEUME_JSON,
    JOURNALS,
    JOURNALS_JSON,
    KEY_FILE,
    MODEL_AGENT,
    MODEL_SUMMARIZE,
    RESEARCHER_AREAS,
    RESEARCHER_INSTITUTION,
    RESEARCHER_NAME,
    RESEARCHER_TRIAGE_TOPICS,
    SINCE_YEAR,
    SUMMARIES_JSON,
    ZOTERO_COLLECTION,
    ZOTERO_STORAGE,
    journals_in_cluster,
    save_profile,
)

app = Flask(
    __name__,
    template_folder="templates",
    static_folder="static",
)
app.secret_key = os.urandom(24)  # For session (lightweight state only)

# Server-side agent state (single-user tool, no cookie size limits)
# Context is persisted to disk so it survives server restarts.
_AGENT_CONTEXT_FILE = Path(__file__).parent.parent.parent / ".agent_context.txt"


def _load_agent_context() -> str:
    if _AGENT_CONTEXT_FILE.exists():
        try:
            return _AGENT_CONTEXT_FILE.read_text(encoding="utf-8")
        except Exception:
            pass
    return ""


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
                a.agent_entry = json.loads(a.agent_entry)
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
    api_key_status = {"exists": False, "masked": ""}
    if KEY_FILE.exists():
        key = KEY_FILE.read_text().strip()
        if key:
            api_key_status = {
                "exists": True,
                "masked": key[:7] + "…" + key[-4:] if len(key) > 12 else "***",
            }

    # Discourse spaces as ordered list of (key, meta) tuples
    spaces = list(DISCOURSE_SPACES.items())

    # Count journals per discourse space
    space_journal_counts = {
        key: len(journals_in_cluster(key)) for key in DISCOURSE_SPACES
    }

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
        db_stats=db_stats,
        db_size_mb=db_size_mb,
        api_key_status=api_key_status,
        verdict_label=VERDICT_LABEL,
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

    # Handle API key separately (written to KEY_FILE, not profile.json)
    api_key = request.form.get("api_key", "").strip()
    if api_key:
        KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
        KEY_FILE.write_text(api_key + "\n")
        KEY_FILE.chmod(0o600)
        key_msg = " · API-Key aktualisiert"
    else:
        key_msg = ""

    return f'<span style="color:var(--lesenswert);">✓ Profil gespeichert{key_msg}</span>'


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


# ============================================================= Backup ===


@app.route("/api/backup/db")
def api_backup_db():
    """Download articles.db as backup."""
    if not ARTICLES_DB.exists():
        abort(404)
    # Copy to temp to avoid locking issues
    import tempfile
    tmp = Path(tempfile.mktemp(suffix=".db"))
    shutil.copy2(ARTICLES_DB, tmp)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    return send_file(
        tmp,
        as_attachment=True,
        download_name=f"mojo_backup_{ts}.db",
        mimetype="application/x-sqlite3",
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

    ctx = _agent_state["context"]
    return render_template(
        "agent.html",
        db_article_count=stats["total"],
        corpus_count=corpus_count,
        context_set=bool(ctx),
        context_preview=(ctx[:200] + "…") if ctx else "",
        context_chars=len(ctx),
        messages=_agent_state["messages"],
    )


@app.route("/api/agent/context", methods=["POST", "DELETE"])
def api_agent_context():
    """Set or clear the agent's text context (persisted to disk)."""
    if request.method == "DELETE":
        _agent_state["context"] = ""
        _AGENT_CONTEXT_FILE.unlink(missing_ok=True)
        return jsonify({"ok": True})

    data = request.get_json(force=True)
    text = data.get("text", "").strip()
    _agent_state["context"] = text
    _AGENT_CONTEXT_FILE.write_text(text, encoding="utf-8")
    return jsonify({"ok": True, "chars": len(text)})


@app.route("/api/agent/chat", methods=["POST"])
def api_agent_chat():
    """Process a chat message with the research agent."""
    import markdown
    from journal_bot.research_agent import chat as agent_chat

    data = request.get_json(force=True)
    message = data.get("message", "").strip()
    history = data.get("history", [])

    if not message:
        return jsonify({"error": "Keine Nachricht."}), 400

    user_context = _agent_state["context"] or None

    try:
        result = agent_chat(
            message=message,
            history=history,
            user_context=user_context,
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    # Convert markdown to HTML
    try:
        html_content = markdown.markdown(
            result["content"],
            extensions=["tables", "fenced_code"],
        )
    except Exception:
        html_content = html_mod.escape(result["content"]).replace("\n", "<br>")

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
    _agent_state["context"] = ""
    return jsonify({"ok": True})


# ============================================================== Main ===


def main():
    app.run(debug=True, port=5555)


if __name__ == "__main__":
    main()
