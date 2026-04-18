#!/usr/bin/env python3
"""Summarize user overrides in articles.db for prompt calibration."""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path


VERDICT_ORDER = {
    "pflichtlektuere": 0,
    "lesenswert": 1,
    "scannen": 2,
    "ignorieren": 3,
}

STOPWORDS = {
    "aber", "als", "auch", "auf", "aus", "bei", "bzw", "das", "dass", "dem",
    "den", "der", "des", "die", "dies", "diese", "dieser", "doch", "dort",
    "ein", "eine", "einer", "eines", "einem", "einen", "etwas", "fuer",
    "für",
    "hat", "hier", "ihre", "ihren", "ihres", "ihrem", "ihnen", "immer",
    "ist", "kein", "keine", "leider", "mehr", "mich", "mit", "nach", "nicht",
    "noch", "nur", "oder", "sehr", "seine", "sich", "sind", "soll", "ueber",
    "über",
    "und", "unter", "vom", "von", "vor", "war", "weil", "wenn", "wird",
    "wirkt", "wohl", "zum", "zur", "zwar",
}


@dataclass
class OverrideRow:
    article_id: str
    year: int | None
    journal: str
    title: str
    agent_verdict: str
    user_verdict: str
    user_memo: str
    direction: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Auswertung der User-Overrides in articles.db",
    )
    parser.add_argument(
        "--db",
        default="articles.db",
        help="Pfad zur SQLite-DB (Default: articles.db)",
    )
    parser.add_argument(
        "--sample-limit",
        type=int,
        default=8,
        help="Wie viele Beispieltitel pro Richtung gezeigt werden (Default: 8)",
    )
    parser.add_argument(
        "--journal-limit",
        type=int,
        default=8,
        help="Wie viele Journale pro Richtung gezeigt werden (Default: 8)",
    )
    parser.add_argument(
        "--keyword-limit",
        type=int,
        default=10,
        help="Wie viele Memo-Keywords pro Richtung gezeigt werden (Default: 10)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="JSON statt Text ausgeben",
    )
    return parser.parse_args()


def _verdict_rank(verdict: str) -> int | None:
    return VERDICT_ORDER.get(verdict)


def _classify_direction(agent_verdict: str, user_verdict: str) -> str:
    agent_rank = _verdict_rank(agent_verdict)
    user_rank = _verdict_rank(user_verdict)
    if agent_rank is None or user_rank is None:
        return "other"
    if user_rank < agent_rank:
        return "upgrade"
    if user_rank > agent_rank:
        return "downgrade"
    return "confirm"


def load_rows(db_path: Path) -> list[OverrideRow]:
    query = """
        SELECT
            id,
            year,
            COALESCE(NULLIF(journal_full, ''), journal_short) AS journal,
            title,
            agent_verdict,
            user_verdict,
            COALESCE(user_memo, '') AS user_memo
        FROM articles
        WHERE user_verdict IS NOT NULL
          AND agent_verdict IS NOT NULL
        ORDER BY user_verdict_at DESC, year DESC, title ASC
    """
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(query).fetchall()

    return [
        OverrideRow(
            article_id=row["id"],
            year=row["year"],
            journal=row["journal"] or "",
            title=row["title"] or "",
            agent_verdict=row["agent_verdict"] or "",
            user_verdict=row["user_verdict"] or "",
            user_memo=row["user_memo"].strip(),
            direction=_classify_direction(row["agent_verdict"], row["user_verdict"]),
        )
        for row in rows
    ]


def _collect_keywords(rows: list[OverrideRow], limit: int) -> list[tuple[str, int]]:
    counts: Counter[str] = Counter()
    for row in rows:
        for token in re.findall(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ-]{2,}", row.user_memo.lower()):
            if token in STOPWORDS:
                continue
            counts[token] += 1
    return counts.most_common(limit)


def _top_journals(rows: list[OverrideRow], limit: int) -> list[tuple[str, int]]:
    counts = Counter(row.journal for row in rows if row.journal)
    return counts.most_common(limit)


def _transition_counts(rows: list[OverrideRow]) -> list[tuple[str, int]]:
    counts = Counter(f"{row.agent_verdict} -> {row.user_verdict}" for row in rows)
    return counts.most_common()


def _sample_rows(rows: list[OverrideRow], limit: int) -> list[dict[str, object]]:
    sample = []
    for row in rows[:limit]:
        sample.append(
            {
                "year": row.year,
                "journal": row.journal,
                "title": row.title,
                "agent_verdict": row.agent_verdict,
                "user_verdict": row.user_verdict,
                "user_memo": row.user_memo,
            }
        )
    return sample


def build_summary(
    rows: list[OverrideRow],
    sample_limit: int,
    journal_limit: int,
    keyword_limit: int,
) -> dict[str, object]:
    grouped = {
        "upgrade": [row for row in rows if row.direction == "upgrade"],
        "downgrade": [row for row in rows if row.direction == "downgrade"],
        "confirm": [row for row in rows if row.direction == "confirm"],
        "other": [row for row in rows if row.direction == "other"],
    }

    return {
        "total_rows": len(rows),
        "upgrades": len(grouped["upgrade"]),
        "downgrades": len(grouped["downgrade"]),
        "confirms": len(grouped["confirm"]),
        "other": len(grouped["other"]),
        "transitions": _transition_counts(
            [row for row in rows if row.direction in {"upgrade", "downgrade"}]
        ),
        "upgrade_journals": _top_journals(grouped["upgrade"], journal_limit),
        "downgrade_journals": _top_journals(grouped["downgrade"], journal_limit),
        "upgrade_keywords": _collect_keywords(grouped["upgrade"], keyword_limit),
        "downgrade_keywords": _collect_keywords(grouped["downgrade"], keyword_limit),
        "upgrade_samples": _sample_rows(grouped["upgrade"], sample_limit),
        "downgrade_samples": _sample_rows(grouped["downgrade"], sample_limit),
    }


def print_text(summary: dict[str, object]) -> None:
    print("Override-Auswertung")
    print(f"Gesamt mit User-Verdict: {summary['total_rows']}")
    print(
        "Upgrades: {upgrades} | Downgrades: {downgrades} | Confirms: {confirms} | Other: {other}".format(
            **summary,
        )
    )

    print("\nTransitions")
    for label, count in summary["transitions"]:
        print(f"- {label}: {count}")

    print("\nTop-Journale (Upgrades)")
    for journal, count in summary["upgrade_journals"]:
        print(f"- {journal}: {count}")

    print("\nTop-Journale (Downgrades)")
    for journal, count in summary["downgrade_journals"]:
        print(f"- {journal}: {count}")

    print("\nMemo-Keywords (Upgrades)")
    for keyword, count in summary["upgrade_keywords"]:
        print(f"- {keyword}: {count}")

    print("\nMemo-Keywords (Downgrades)")
    for keyword, count in summary["downgrade_keywords"]:
        print(f"- {keyword}: {count}")

    print("\nBeispiele (Upgrades)")
    for row in summary["upgrade_samples"]:
        memo = row["user_memo"] or "-"
        print(
            f"- {row['year'] or '?'} | {row['journal']} | "
            f"{row['agent_verdict']} -> {row['user_verdict']} | {row['title']}"
        )
        print(f"  Memo: {memo}")

    print("\nBeispiele (Downgrades)")
    for row in summary["downgrade_samples"]:
        memo = row["user_memo"] or "-"
        print(
            f"- {row['year'] or '?'} | {row['journal']} | "
            f"{row['agent_verdict']} -> {row['user_verdict']} | {row['title']}"
        )
        print(f"  Memo: {memo}")


def main() -> int:
    args = parse_args()
    db_path = Path(args.db)
    if not db_path.exists():
        raise SystemExit(f"DB nicht gefunden: {db_path}")

    rows = load_rows(db_path)
    summary = build_summary(
        rows,
        sample_limit=args.sample_limit,
        journal_limit=args.journal_limit,
        keyword_limit=args.keyword_limit,
    )

    if args.json:
        payload = {
            key: [asdict(row) for row in value] if isinstance(value, list) and value and isinstance(value[0], OverrideRow) else value
            for key, value in summary.items()
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    print_text(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
