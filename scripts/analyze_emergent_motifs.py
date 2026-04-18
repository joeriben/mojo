#!/usr/bin/env python3
"""Inspect corpus-level emergent motif suggestions for unassigned signal-group articles."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from journal_bot.signals import suggest_emergent_motifs
from journal_bot.store import Store


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Show emergent motif suggestions from unassigned articles."
    )
    parser.add_argument(
        "--group",
        help="Only inspect one signal_group (e.g. ai4artsed).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="Maximum motifs per signal group (default: 5).",
    )
    parser.add_argument(
        "--examples",
        type=int,
        default=3,
        help="Example article titles per motif (default: 3).",
    )
    parser.add_argument(
        "--recent-years",
        type=int,
        default=3,
        help="Rolling time window from latest article year (default: 3 years incl. latest).",
    )
    parser.add_argument(
        "--strong-only",
        action="store_true",
        help="Only inspect articles with starker_indikator.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    store = Store()
    articles = [
        article
        for article in store.find_in_window(only_processed=True)
        if article.signal_group and not article.suggested_subgroup
    ]
    if args.group:
        articles = [article for article in articles if article.signal_group == args.group]

    by_group: dict[str, list] = {}
    for article in articles:
        by_group.setdefault(article.signal_group, []).append(article)

    for group in sorted(by_group):
        print(f"\n[{group}]")
        group_articles = by_group[group]
        if args.strong_only:
            group_articles = [
                article
                for article in group_articles
                if article.discourse_indicator == "starker_indikator"
            ]
        if args.recent_years > 0 and group_articles:
            max_year = max(article.year or 0 for article in group_articles)
            if max_year:
                min_year = max_year - args.recent_years + 1
                group_articles = [
                    article for article in group_articles if (article.year or 0) >= min_year
                ]
        suggestions = suggest_emergent_motifs(
            group_articles,
            background_articles=by_group[group],
            limit=args.limit,
        )
        if not suggestions:
            print("  (keine stabilen emergenten Motive)")
            continue
        article_lookup = {article.id: article for article in group_articles}
        for suggestion in suggestions:
            print(
                f"  - {suggestion.label} | {suggestion.article_count} Artikel "
                f"| {suggestion.journal_count} Journals | {suggestion.strong_count} stark"
            )
            for article_id in suggestion.article_ids[: args.examples]:
                article = article_lookup.get(article_id)
                if not article:
                    continue
                print(f"      * {article.title} ({article.year or 'o.J.'})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
