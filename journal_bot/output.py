"""Markdown-Digest, abgelegt im Obsidian-Vault."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from journal_bot.config import Config
from journal_bot.fetchers.base import Article
from journal_bot.scorer import ScoreResult


@dataclass
class ScoredArticle:
    article: Article
    score: ScoreResult


def _stars(n: int) -> str:
    return "★" * n + "☆" * (5 - n)


def render_digest(cfg: Config, scored: list[ScoredArticle]) -> str:
    today = date.today().isoformat()
    full = sorted(
        [s for s in scored if s.score.score >= cfg.scoring.min_score_full],
        key=lambda s: s.score.score,
        reverse=True,
    )
    listing = sorted(
        [
            s
            for s in scored
            if cfg.scoring.min_score_listing <= s.score.score < cfg.scoring.min_score_full
        ],
        key=lambda s: s.score.score,
        reverse=True,
    )

    lines: list[str] = []
    lines.append(f"# Journal-Digest — {today}")
    lines.append("")
    lines.append(
        f"_{len(scored)} neue Einträge gesichtet, "
        f"{len(full)} lohnen eine ausführliche Betrachtung, "
        f"{len(listing)} im Kurzüberblick._"
    )
    lines.append("")

    if full:
        lines.append("## Empfohlen")
        lines.append("")
        for s in full:
            lines.extend(_render_full(s))
            lines.append("")

    if listing:
        lines.append("## Kurzüberblick")
        lines.append("")
        for s in listing:
            a, r = s.article, s.score
            link = f"[{a.title}]({a.url})" if a.url else a.title
            lines.append(
                f"- {_stars(r.score)} **{a.journal}** — {link} "
                f"_{', '.join(a.authors)[:80]}_ — {r.begruendung}"
            )
        lines.append("")

    ignored = [s for s in scored if s.score.score < cfg.scoring.min_score_listing]
    if ignored:
        lines.append(f"<details><summary>Ignoriert ({len(ignored)})</summary>")
        lines.append("")
        for s in ignored:
            a = s.article
            lines.append(f"- {a.journal}: {a.title}")
        lines.append("")
        lines.append("</details>")
        lines.append("")

    return "\n".join(lines)


def _render_full(s: ScoredArticle) -> list[str]:
    a, r = s.article, s.score
    out = []
    title = f"[{a.title}]({a.url})" if a.url else a.title
    out.append(f"### {_stars(r.score)} {title}")
    meta_bits = [a.journal_full]
    if a.authors:
        meta_bits.append(", ".join(a.authors))
    if a.published:
        meta_bits.append(a.published[:10])
    if a.doi:
        meta_bits.append(f"DOI: {a.doi}")
    out.append(f"_{' · '.join(meta_bits)}_")
    out.append("")
    if r.annotation:
        out.append(r.annotation)
        out.append("")
    out.append(f"**Relevanz:** {r.begruendung}")
    if r.schlagworte:
        tags = " ".join(f"#{w.replace(' ', '_')}" for w in r.schlagworte)
        out.append(f"**Tags:** {tags}")
    return out


def write_digest(cfg: Config, text: str) -> Path:
    cfg.paths.digest_dir.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    dated = cfg.paths.digest_dir / f"digest-{today}.md"
    dated.write_text(text, encoding="utf-8")
    # latest-Pointer
    latest = cfg.paths.digest_dir / "digest.md"
    latest.write_text(
        f"> _Neuester Lauf: [[digest-{today}]]_\n\n" + text,
        encoding="utf-8",
    )
    return dated
