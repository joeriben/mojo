"""Export articles as Obsidian-compatible Markdown."""

from __future__ import annotations

import json
import re
from pathlib import Path

from journal_bot.settings import DIGEST_DIR
from journal_bot.store import Store, StoredArticle


VERDICT_LABEL = {
    "pflichtlektuere": "PFLICHTLEKTÜRE",
    "lesenswert": "LESENSWERT",
    "scannen": "SCANNEN",
    "ignorieren": "IGNORIEREN",
}

RELATION_LABEL = {
    "erweitert": "erweitert",
    "widerspricht": "widerspricht",
    "parallelisiert": "parallel",
    "importiert": "Import",
    "tangential": "tangential",
}


def _slug(s: str, n: int = 60) -> str:
    s = re.sub(r"[^\w\s-]", "", s or "", flags=re.UNICODE)
    s = re.sub(r"\s+", "-", s.strip())
    return (s[:n].strip("-").lower()) or "eintrag"


def render_article_md(a: StoredArticle) -> str:
    """Render a StoredArticle as Obsidian Markdown."""
    e = a.agent_entry
    if isinstance(e, str):
        e = json.loads(e)

    verdict = a.user_verdict or a.agent_verdict
    lines: list[str] = []

    # YAML frontmatter
    lines.append("---")
    lines.append(f"title: \"{a.title}\"")
    lines.append(f"journal: \"{a.journal_full or a.journal_short}\"")
    if a.authors:
        lines.append(f"authors: [{', '.join(repr(x) for x in a.authors[:5])}]")
    if a.year:
        lines.append(f"year: {a.year}")
    if a.doi:
        lines.append(f"doi: \"{a.doi}\"")
    lines.append(f"verdict: \"{verdict}\"")
    if a.user_memo:
        lines.append(f"memo: \"{a.user_memo}\"")
    lines.append(f"mojo_id: \"{a.id}\"")
    lines.append("---")
    lines.append("")

    # Title
    lines.append(f"## {a.title}")
    meta = []
    if a.authors:
        meta.append(", ".join(a.authors[:5]))
    meta.append(a.journal_full or a.journal_short)
    if a.doi:
        meta.append(f"[doi:{a.doi}](https://doi.org/{a.doi})")
    lines.append("_" + " · ".join(meta) + "_")
    lines.append("")

    if not e:
        lines.append("_(Keine Agent-Analyse vorhanden.)_")
        return "\n".join(lines)

    # Verdict
    label = VERDICT_LABEL.get(verdict, verdict)
    lines.append(f"**Verdict:** {label} — {e.get('verdict_begruendung', '')}")
    lines.append("")

    # Citation hits
    citation_hits = a.citation_hits or []
    if citation_hits:
        lines.append("### Zitiert Dich")
        for h in citation_hits:
            if not isinstance(h, dict):
                continue
            authors = ", ".join(h.get("pub_authors", [])[:2]) or "?"
            conf = h.get("confidence", "")
            prefix = "_(wahrscheinlich)_ " if conf == "medium" else ""
            lines.append(
                f"- {prefix}**{authors}** ({h.get('pub_year')}): "
                f"{h.get('pub_title', '')[:100]} · `{h.get('pub_id')}`"
            )
        lines.append("")

    # Kernthese
    lines.append("### Kernthese")
    lines.append(e.get("kernthese", ""))
    lines.append("")

    # Bezüge
    bezuege = e.get("bezuege") or []
    lines.append("### Bezüge zu Deinem Werk")
    if not bezuege:
        lines.append("_Keine substantiellen Bezüge gefunden._")
    else:
        for b in bezuege:
            rel = RELATION_LABEL.get(b.get("relation", ""), b.get("relation", ""))
            lines.append(f"\n**{b.get('pub_kurz', '?')}** (`{b.get('pub_id', '?')}`, {rel})")
            lines.append(b.get("bezug", ""))
    lines.append("")

    # Bemerkenswert
    bemerkenswert = e.get("bemerkenswert") or []
    if bemerkenswert:
        lines.append("### Bemerkenswert")
        for note in bemerkenswert:
            lines.append(f"- {note}")
        lines.append("")

    # Methodisch
    if e.get("theoretisch_methodisch"):
        lines.append("### Methodisch / Theoretisch")
        lines.append(e["theoretisch_methodisch"])
        lines.append("")

    # User memo
    if a.user_memo:
        lines.append("### Memo")
        lines.append(f"_{a.user_memo}_")
        lines.append("")

    # Footer
    lines.append("---")
    lines.append(
        f"_{a.iterations} Iterationen · "
        f"{a.tokens_in:,} in / {a.tokens_out:,} out · "
        f"${a.cost_usd:.3f}_"
    )

    return "\n".join(lines)


def export_to_obsidian(
    article_id: str,
    store: Store,
    base_dir: Path = DIGEST_DIR,
) -> Path:
    """Export one article as Markdown. Returns the file path."""
    a = store.get(article_id)
    if not a:
        raise ValueError(f"Article {article_id} not found")

    verdict = a.user_verdict or a.agent_verdict
    subdir = base_dir / verdict
    subdir.mkdir(parents=True, exist_ok=True)

    filename = f"{_slug(a.title)}.md"
    path = subdir / filename
    path.write_text(render_article_md(a), encoding="utf-8")
    return path
