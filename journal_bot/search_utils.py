"""Word-boundary / regex search over articles.db — shared by web UI and agent.

Problem this solves: the old search used SQL ``LIKE '%mental%'``, a pure
substring match. So a query for *mental health* also returned *environmental*
(which contains the substring "mental"), and even the phrase *mental health*
matched *environmental health*. Substring matching has no notion of a word.

Approach: register a Python ``REGEXP`` function on the SQLite connection and
match against a regex built from the query. Two modes:

- **word mode** (default): every whitespace token must appear as a *whole word*
  (not flanked by word characters), in any order — an AND of word-boundary
  lookaheads. Quoted ``"..."`` segments are matched as a contiguous phrase.
  ``mental health`` → requires the word "mental" AND the word "health", so it
  no longer matches "environmental".
- **regex mode**: the query is used verbatim as a Python regular expression.
  This is what the LLM agent uses when it wants precise control (it is good at
  writing regexes from a natural-language intent).

Matching is case-insensitive and DOTALL (``.`` spans newlines) in both modes,
so multi-line abstracts behave like one blob.

Performance: REGEXP cannot use an index, so this scans every row and runs the
compiled pattern once per row over the concatenated search fields. For the
~18k-row articles.db that is a few tens of milliseconds — fine for an
interactive search and for a single agent tool call. If the corpus grows by an
order of magnitude, add an FTS5 prefilter in front of the REGEXP refinement.
"""

from __future__ import annotations

import re
import sqlite3
from functools import lru_cache
from typing import Any, Sequence


class SearchError(ValueError):
    """Raised when a user-supplied regex (regex mode) does not compile."""


# Text columns scanned by default. They are concatenated into one blob so an
# AND-of-words query matches even when the words are spread across fields
# (e.g. one word in the title, another in the abstract). These are JSON columns
# for some entries (authors_json, agent_entry_json, topics, concepts); we match
# their raw text, which holds the human-readable values we want to find. JSON
# is stored with ensure_ascii=False, so umlauts survive as real characters.
SEARCH_FIELDS: tuple[str, ...] = (
    "title",
    "abstract",
    "openalex_abstract",
    "agent_entry_json",
    "authors_json",
    "openalex_topics",
    "openalex_concepts",
    "signal_group",
    "suggested_subgroup_reason",
)

# Split a query into quoted phrases and bare tokens:
#   foo "bar baz" qux  ->  ('', 'foo'), ('bar baz', ''), ('', 'qux')
_TOKEN_RE = re.compile(r'"([^"]*)"|(\S+)')

_FLAGS = re.IGNORECASE | re.DOTALL


@lru_cache(maxsize=256)
def _compile(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, _FLAGS)


def _sqlite_regexp(pattern: str, value: Any) -> int:
    """SQLite REGEXP callback: ``value REGEXP pattern`` -> regexp(pattern, value)."""
    if value is None:
        return 0
    if not isinstance(value, str):
        value = str(value)
    try:
        return 1 if _compile(pattern).search(value) else 0
    except re.error:
        return 0


def register_regexp(conn: sqlite3.Connection) -> None:
    """Make the ``REGEXP`` operator available on this connection.

    Cheap and idempotent — safe to call on every freshly opened connection.
    """
    try:
        conn.create_function("regexp", 2, _sqlite_regexp, deterministic=True)
    except (TypeError, sqlite3.NotSupportedError):
        # deterministic= needs Python >= 3.8 and SQLite >= 3.8.3.
        conn.create_function("regexp", 2, _sqlite_regexp)


def build_query_patterns(query: str, *, regex_mode: bool = False) -> list[str]:
    """Turn a user query into a list of regex patterns that must ALL match.

    Returns ``[]`` when the query has no usable content. Raises
    :class:`SearchError` when ``regex_mode`` is set and the query is not a valid
    regular expression.

    In word mode each whitespace token (or quoted phrase) becomes its own
    pattern, and the patterns are ANDed by the caller. This is deliberately
    *not* a single ``(?=.*word1)(?=.*word2)`` lookahead pattern: the greedy
    ``.*`` inside such a lookahead backtracks catastrophically over the multi-KB
    text blobs in this corpus. A list of plain ``(?<!\w)word(?!\w)`` patterns,
    each run with a forward ``re.search``, stays fast.
    """
    query = (query or "").strip()
    if not query:
        return []

    if regex_mode:
        try:
            re.compile(query, _FLAGS)
        except re.error as exc:
            raise SearchError(f"Ungültiger regulärer Ausdruck: {exc}") from exc
        return [query]

    # Word mode: one whole-word pattern per token. (?<!\w)...(?!\w) is used
    # instead of \b so tokens that begin/end with non-word characters (e.g.
    # "C++") still match correctly.
    patterns: list[str] = []
    for phrase, word in _TOKEN_RE.findall(query):
        token = (phrase or word).strip().strip('"')
        if not token:
            continue
        words = [re.escape(w) for w in token.split() if w]
        if not words:
            continue
        body = r"\s+".join(words)  # phrase: flexible whitespace between words
        patterns.append(rf"(?<!\w){body}(?!\w)")

    return patterns


def regexp_blob(fields: Sequence[str] = SEARCH_FIELDS) -> str:
    """SQL expression concatenating the search fields into one matchable blob."""
    return " || ' ' || ".join(f"COALESCE({f}, '')" for f in fields)


def search_rows(
    conn: sqlite3.Connection,
    query: str,
    *,
    select: str = "*",
    fields: Sequence[str] = SEARCH_FIELDS,
    regex_mode: bool = False,
    where_extra: str = "",
    order_by: str = "year DESC, fetched_at DESC",
    limit: int = 100,
) -> list[sqlite3.Row]:
    """Run a word-boundary / regex search over ``articles`` and return rows.

    Only ``query`` is user input and it is bound as a parameter; ``select``,
    ``fields``, ``where_extra`` and ``order_by`` are code-controlled and
    interpolated. Returns ``[]`` for an empty query (never raises for that);
    raises :class:`SearchError` only for an invalid regex in ``regex_mode``.
    """
    patterns = build_query_patterns(query, regex_mode=regex_mode)
    if not patterns:
        return []

    register_regexp(conn)
    blob = regexp_blob(fields)
    where = " AND ".join(f"({blob}) REGEXP ?" for _ in patterns)
    params: list[Any] = list(patterns)
    if where_extra:
        where += f" AND ({where_extra})"
    sql = (
        f"SELECT {select} FROM articles WHERE {where} "
        f"ORDER BY {order_by} LIMIT ?"
    )
    params.append(int(limit))

    return conn.execute(sql, params).fetchall()
