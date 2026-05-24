#!/usr/bin/env python3
"""Backfill selection/discourse metadata for already processed articles."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from journal_bot.signals import derive_attention_profile, load_signal_resources
from journal_bot.store import Store


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backfill attention metadata in articles.db",
    )
    parser.add_argument(
        "--db",
        default="articles.db",
        help="Pfad zur SQLite-DB (Default: articles.db)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Optional: nur die ersten N verarbeiteten Artikel aktualisieren",
    )
    parser.add_argument(
        "--since-year",
        type=int,
        default=None,
        help="Optional: nur Artikel ab diesem Jahr",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    store = Store(Path(args.db))
    signal_resources = load_signal_resources()
    articles = store.find_in_window(start_year=args.since_year, only_processed=True)
    if args.limit is not None:
        articles = articles[:args.limit]

    updated = 0
    with_entry = 0
    for article in articles:
        source_entry = dict(article.agent_entry or {})
        source_entry.pop("selection_mode", None)
        source_entry.pop("discourse_indicator", None)
        source_entry.pop("signal_group", None)
        source_entry.pop("project_hits", None)
        source_entry.pop("suggested_subgroup", None)
        source_entry.pop("suggested_subgroup_reason", None)
        source_entry.pop("suggested_subgroup_confidence", None)
        profile = derive_attention_profile(
            article_id=article.id,
            title=article.title,
            authors=article.authors,
            abstract=article.abstract,
            openalex_abstract=article.openalex_abstract,
            crossref_refs=article.crossref_refs,
            openalex_refs=article.openalex_refs,
            entry=source_entry,
            signal_resources=signal_resources,
        )

        entry = None
        if article.agent_entry:
            entry = dict(source_entry)
            entry["selection_mode"] = profile.selection_mode
            entry["discourse_indicator"] = profile.discourse_indicator
            entry["signal_group"] = profile.signal_group
            entry["suggested_subgroup"] = profile.suggested_subgroup
            entry["suggested_subgroup_reason"] = profile.suggested_subgroup_reason
            entry["suggested_subgroup_confidence"] = profile.suggested_subgroup_confidence
            if profile.project_hits:
                entry["project_hits"] = profile.project_hits
            elif "project_hits" in entry:
                entry.pop("project_hits", None)
            with_entry += 1

        store.set_attention_profile(
            article.id,
            selection_mode=profile.selection_mode,
            discourse_indicator=profile.discourse_indicator,
            signal_group=profile.signal_group,
            suggested_subgroup=profile.suggested_subgroup,
            suggested_subgroup_reason=profile.suggested_subgroup_reason,
            suggested_subgroup_confidence=profile.suggested_subgroup_confidence,
            entry=entry,
        )
        updated += 1

    print(
        f"Attention-Metadaten aktualisiert: {updated} Artikel "
        f"({with_entry} mit agent_entry_json angereichert)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
