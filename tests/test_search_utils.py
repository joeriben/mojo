"""Tests for word-boundary / regex search (journal_bot.search_utils).

The central regression these guard: a substring search for "mental" used to
match "environmental". Word-boundary matching must not.
"""

import sqlite3

import pytest

from journal_bot.search_utils import (
    SearchError,
    build_query_patterns,
    register_regexp,
    search_rows,
)


def _db(titles_abstracts):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE articles (title TEXT, abstract TEXT)")
    conn.executemany("INSERT INTO articles VALUES (?, ?)", titles_abstracts)
    return conn


def _search(conn, query, **kw):
    kw.setdefault("select", "title")
    kw.setdefault("fields", ("title", "abstract"))
    kw.setdefault("order_by", "title")
    return [r["title"] for r in search_rows(conn, query, **kw)]


# --- pattern construction --------------------------------------------------

def test_word_query_splits_into_whole_word_patterns():
    assert build_query_patterns("mental health") == [
        r"(?<!\w)mental(?!\w)",
        r"(?<!\w)health(?!\w)",
    ]


def test_quoted_phrase_is_one_pattern_with_flexible_whitespace():
    assert build_query_patterns('"mental health"') == [r"(?<!\w)mental\s+health(?!\w)"]


def test_empty_query_yields_no_patterns():
    assert build_query_patterns("") == []
    assert build_query_patterns("   ") == []


def test_special_chars_are_escaped():
    # "C++" must be matched literally, not as a regex.
    assert build_query_patterns("C++") == [r"(?<!\w)C\+\+(?!\w)"]


def test_regex_mode_passes_query_through():
    assert build_query_patterns("bildung.*medien", regex_mode=True) == ["bildung.*medien"]


def test_regex_mode_rejects_invalid_regex():
    with pytest.raises(SearchError):
        build_query_patterns("foo(", regex_mode=True)


# --- behaviour against a tiny corpus --------------------------------------

CORPUS = [
    ("Mental health in schools", ""),
    ("Environmental policy and crisis", ""),      # substring "mental", not the word
    ("Fundamental questions of pedagogy", ""),    # substring "mental", not the word
    ("Health and the mental world", ""),          # both words, not adjacent
    ("Notes on C++ in education", ""),
]


def test_mental_does_not_match_environmental_or_fundamental():
    conn = _db(CORPUS)
    hits = _search(conn, "mental")
    assert "Mental health in schools" in hits
    assert "Health and the mental world" in hits
    assert "Environmental policy and crisis" not in hits
    assert "Fundamental questions of pedagogy" not in hits


def test_multi_word_is_and_of_whole_words():
    conn = _db(CORPUS)
    hits = _search(conn, "mental health")
    # both whole words present (any order) -> matches
    assert set(hits) == {"Mental health in schools", "Health and the mental world"}


def test_quoted_phrase_requires_adjacency():
    conn = _db(CORPUS)
    hits = _search(conn, '"mental health"')
    assert hits == ["Mental health in schools"]  # not the "mental world ... health" row


def test_and_across_fields():
    conn = _db([("Mental resilience", "a study of health systems")])
    # one word in title, the other in abstract -> still matches (combined blob)
    assert _search(conn, "mental health") == ["Mental resilience"]


def test_special_char_token_matches_literally():
    conn = _db(CORPUS)
    assert _search(conn, "C++") == ["Notes on C++ in education"]


def test_regex_mode_against_corpus():
    conn = _db(CORPUS)
    hits = _search(conn, r"ment(a|e)l", regex_mode=True)
    assert "Mental health in schools" in hits
    # regex is free-form: "environmental"/"fundamental" DO contain "mental" here
    assert "Environmental policy and crisis" in hits


def test_empty_query_returns_no_rows():
    conn = _db(CORPUS)
    assert _search(conn, "") == []


def test_register_regexp_is_idempotent():
    conn = _db(CORPUS)
    register_regexp(conn)
    register_regexp(conn)  # must not raise
    assert conn.execute("SELECT 1 WHERE 'abc' REGEXP ?", ("b",)).fetchone() is not None
