"""Feature-Extraction für algorithmischen Triage-Backtest.

Baut features.parquet pro Artikel mit allen algorithmischen Features, die
für die 8 Backtest-Verfahren (siehe docs/context/project_backtest_algorithmic_heuristics.md)
benötigt werden — bewusst LLM-frei.

Gold-Set: alle 461 Artikel mit user_verdict (für Train/Test).
Vollset:  alle Artikel mit agent_verdict (für spätere Validierung/Ausblick).

Usage:
    .venv/bin/python scripts/backtest_extract_features.py
    → schreibt:  backtest_data/features_gold.parquet  (n=461)
                 backtest_data/features_all.parquet   (n≈16k, optional via --all)
                 backtest_data/trigger_neighborhood.json
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "articles.db"
CORPUS = ROOT / "corpus.json"
OUT_DIR = ROOT / "backtest_data"

# Aus CLAUDE.md / project_trigger_autoren.md
TRIGGER_AUTHOR_PATTERNS = [
    "macgilchrist", "jarke",
    "wendy hui kyong chun", "wendy chun",
]


def load_authored_dois() -> set[str]:
    """DOIs aus corpus.json/authored_all — Benjamins 160 Publikationen."""
    c = json.loads(CORPUS.read_text())
    dois = set()
    for pub in c.get("authored_all", []):
        doi = (pub.get("doi") or "").strip().lower()
        if doi:
            dois.add(doi)
    return dois


def load_authored_coauthors() -> set[str]:
    """Alle Co-Autor-Namen aus den 160 authored_all-Publikationen (lowercase),
    inklusive Benjamin selbst und allen Kollaborateuren über die Jahre.
    Signal: wenn ein Paper jemanden aus Benjamins Co-Autor-Netzwerk hat,
    ist die Wahrscheinlichkeit erhöht, dass es ihm thematisch nahe steht."""
    c = json.loads(CORPUS.read_text())
    names: set[str] = set()
    for pub in c.get("authored_all", []):
        authors = pub.get("authors") or []
        if isinstance(authors, str):
            authors = [authors]
        for a in authors:
            a_str = str(a).strip().lower()
            if not a_str:
                continue
            # Normalize "Last, First" → "first last" und auch nur Last
            if "," in a_str:
                last, first = a_str.split(",", 1)
                names.add(f"{first.strip()} {last.strip()}".strip())
                names.add(last.strip())
            else:
                names.add(a_str)
                # Letztes Wort als Nachname-Approximation
                parts = a_str.split()
                if parts:
                    names.add(parts[-1])
    # Filter zu kurze/zu generische Tokens (Initials etc.)
    return {n for n in names if len(n) > 2 and not n.replace(".", "").isdigit()}


def extract_ref_dois(refs_json_str: str | None) -> set[str]:
    """crossref_refs ist JSON-Array von Ref-Dicts; extrahiere alle DOIs."""
    if not refs_json_str:
        return set()
    try:
        refs = json.loads(refs_json_str)
    except json.JSONDecodeError:
        return set()
    if not isinstance(refs, list):
        return set()
    out = set()
    for r in refs:
        if isinstance(r, dict):
            doi = (r.get("DOI") or r.get("doi") or "").strip().lower()
            if doi:
                out.add(doi)
        elif isinstance(r, str):
            doi = r.strip().lower()
            if doi:
                out.add(doi)
    return out


def extract_openalex_ref_ids(refs_json_str: str | None) -> set[str]:
    if not refs_json_str:
        return set()
    try:
        refs = json.loads(refs_json_str)
    except json.JSONDecodeError:
        return set()
    if not isinstance(refs, list):
        return set()
    return {str(r).strip() for r in refs if r}


def extract_topic_names(topics_json_str: str | None, min_score: float = 0.0) -> set[str]:
    """OpenAlex-Topics/Concepts kommen als [{'name': ..., 'score': ...}, ...].
    Wir verwenden 'name' als Identifier (Topic-Namen sind stabil)."""
    if not topics_json_str:
        return set()
    try:
        topics = json.loads(topics_json_str)
    except json.JSONDecodeError:
        return set()
    if not isinstance(topics, list):
        return set()
    out = set()
    for t in topics:
        if isinstance(t, dict):
            name = t.get("name") or t.get("display_name")
            score = float(t.get("score", 1.0) or 1.0)
            if name and score >= min_score:
                out.add(str(name).lower())
        elif isinstance(t, str):
            out.add(t.lower())
    return out


def extract_topic_score_dict(topics_json_str: str | None) -> dict[str, float]:
    """Wie extract_topic_names, aber als dict {name: score} für Vektor-Konstruktion."""
    if not topics_json_str:
        return {}
    try:
        topics = json.loads(topics_json_str)
    except json.JSONDecodeError:
        return {}
    if not isinstance(topics, list):
        return {}
    out: dict[str, float] = {}
    for t in topics:
        if isinstance(t, dict):
            name = t.get("name") or t.get("display_name")
            score = float(t.get("score", 1.0) or 1.0)
            if name:
                key = str(name).lower()
                out[key] = max(out.get(key, 0.0), score)
        elif isinstance(t, str):
            out[t.lower()] = max(out.get(t.lower(), 0.0), 1.0)
    return out


def author_string_lower(authors_json_str: str | None) -> str:
    if not authors_json_str:
        return ""
    try:
        authors = json.loads(authors_json_str)
    except json.JSONDecodeError:
        return ""
    if not isinstance(authors, list):
        return ""
    return " | ".join(str(a) for a in authors).lower()


def trigger_match(authors_lower: str) -> int:
    return int(any(pat in authors_lower for pat in TRIGGER_AUTHOR_PATTERNS))


def citation_hit_count(citation_hits_json_str: str | None) -> int:
    if not citation_hits_json_str or citation_hits_json_str == "[]":
        return 0
    try:
        hits = json.loads(citation_hits_json_str)
    except json.JSONDecodeError:
        return 0
    return len(hits) if isinstance(hits, list) else 0


def build_trigger_neighborhood(conn: sqlite3.Connection, authored_dois: set[str]) -> dict:
    """Aggregiert crossref_refs aller Trigger-Autor-Artikel + authored_all-DOIs
    zu einem Multi-Set von DOIs (Counter)."""
    pat = "|".join(TRIGGER_AUTHOR_PATTERNS)
    rows = conn.execute(
        """
        SELECT id, authors_json, crossref_refs
        FROM articles
        WHERE LOWER(authors_json) REGEXP ?
          AND crossref_refs IS NOT NULL AND crossref_refs != '[]'
        """,
        (pat,),
    ).fetchall()

    doi_counts: dict[str, int] = {}
    for _id, _authors, refs_str in rows:
        for doi in extract_ref_dois(refs_str):
            doi_counts[doi] = doi_counts.get(doi, 0) + 1

    # Zusätzlich: authored_all-DOIs als hochgewichtete "Nachbarschaft" mergen.
    # Jeder authored_all-DOI bekommt Count = 1 (oder höher, wenn schon präsent).
    for doi in authored_dois:
        doi_counts[doi] = max(doi_counts.get(doi, 0), 1)

    return doi_counts


def fetch_articles(conn: sqlite3.Connection, only_gold: bool) -> list[sqlite3.Row]:
    base = """
        SELECT id, journal_short, journal_full, year, title, abstract, openalex_abstract,
               authors_json, doi, crossref_refs, openalex_refs,
               openalex_topics, openalex_concepts,
               citation_hits_json, agent_verdict, user_verdict
        FROM articles
        WHERE agent_verdict IS NOT NULL
    """
    if only_gold:
        base += " AND user_verdict IS NOT NULL AND user_verdict != ''"
    return conn.execute(base).fetchall()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true",
                        help="Auch features_all.parquet erzeugen (≈16k Zeilen)")
    args = parser.parse_args()

    OUT_DIR.mkdir(exist_ok=True)

    authored_dois = load_authored_dois()
    print(f"authored_all DOIs: {len(authored_dois)}")
    coauthors = load_authored_coauthors()
    print(f"authored_all coauthors: {len(coauthors)}")

    # SQLite hat kein REGEXP — UDF registrieren
    import re

    def _regexp(pattern: str, value: str | None) -> int:
        if value is None:
            return 0
        return 1 if re.search(pattern, value, re.IGNORECASE) else 0

    conn = sqlite3.connect(str(DB))
    conn.create_function("REGEXP", 2, _regexp)
    conn.row_factory = sqlite3.Row

    trigger_nbhd = build_trigger_neighborhood(conn, authored_dois)
    print(f"Trigger-Nachbarschaft: {len(trigger_nbhd)} unique DOIs")
    (OUT_DIR / "trigger_neighborhood.json").write_text(
        json.dumps({"n_dois": len(trigger_nbhd),
                    "authored_n": len(authored_dois),
                    "doi_counts": trigger_nbhd}, indent=2)
    )

    concept_score_lookup: dict[str, dict[str, float]] = {}

    def build_df(only_gold: bool) -> pd.DataFrame:
        rows = fetch_articles(conn, only_gold)
        print(f"Fetched {len(rows)} articles (only_gold={only_gold})")
        records = []
        for r in rows:
            authors_lower = author_string_lower(r["authors_json"])
            ref_dois = extract_ref_dois(r["crossref_refs"])
            openalex_ref_ids = extract_openalex_ref_ids(r["openalex_refs"])
            topic_names = extract_topic_names(r["openalex_topics"])
            concept_names = extract_topic_names(r["openalex_concepts"])
            # Konzept-Score-Vector mergen aus topics + concepts
            cs_topics = extract_topic_score_dict(r["openalex_topics"])
            cs_concepts = extract_topic_score_dict(r["openalex_concepts"])
            cs_merged = {**cs_topics, **cs_concepts}
            concept_score_lookup[str(r["id"])] = cs_merged
            abstract = (r["abstract"] or r["openalex_abstract"] or "").strip()
            # Author-Overlap zu Benjamins Co-Autor-Netzwerk
            # Suche jedes Co-Autor-Token im authors_lower-String
            coauthor_hits = sum(1 for name in coauthors if name in authors_lower)

            records.append({
                "id": r["id"],
                "journal_short": r["journal_short"],
                "journal_full": r["journal_full"],
                "year": r["year"],
                "title": r["title"] or "",
                "abstract": abstract,
                "abstract_len": len(abstract),
                "has_abstract": int(bool(abstract)),
                "doi": (r["doi"] or "").lower(),
                "authors_lower": authors_lower,
                "agent_verdict": r["agent_verdict"] or "",
                "user_verdict": r["user_verdict"] or "",
                # ↓ Features
                "f_citation_hit_count":     citation_hit_count(r["citation_hits_json"]),
                "f_trigger_author_match":   trigger_match(authors_lower),
                "f_ref_overlap_authored":   len(ref_dois & authored_dois),
                "f_ref_overlap_trigger":    sum(trigger_nbhd.get(d, 0) for d in ref_dois),
                "f_ref_count_total":        len(ref_dois),
                "f_openalex_ref_count":     len(openalex_ref_ids),
                "f_topic_count":            len(topic_names),
                "f_concept_count":          len(concept_names),
                "f_coauthor_hits":          coauthor_hits,
                "f_title_len":              len(r["title"] or ""),
                "f_year_normalized":        max(0, (int(r["year"]) - 2000)) if r["year"] else 0,
                "topics":                   "|".join(sorted(topic_names)),
                "concepts":                 "|".join(sorted(concept_names)),
            })
        return pd.DataFrame(records)

    gold = build_df(only_gold=True)
    gold_path = OUT_DIR / "features_gold.parquet"
    gold.to_parquet(gold_path, index=False)
    print(f"\nWrote {gold_path}: {len(gold)} rows, {len(gold.columns)} cols")

    # Konzept-Vector als separate JSON-Datei (sparse)
    concept_vector_path = OUT_DIR / "concept_scores_gold.json"
    cs_out = {aid: {k: round(v, 4) for k, v in d.items() if v > 0}
              for aid, d in concept_score_lookup.items()}
    concept_vector_path.write_text(json.dumps(cs_out))
    print(f"Wrote {concept_vector_path}: {len(cs_out)} articles")

    # Quick sanity-check
    print("\n=== Gold-Set Verteilung (user_verdict) ===")
    print(gold["user_verdict"].value_counts().to_string())
    print("\n=== Feature-Zusammenfassung ===")
    feat_cols = [c for c in gold.columns if c.startswith("f_")]
    print(gold[feat_cols].describe().T[["mean", "min", "max", "std"]].round(3).to_string())

    if args.all:
        all_df = build_df(only_gold=False)
        all_path = OUT_DIR / "features_all.parquet"
        all_df.to_parquet(all_path, index=False)
        print(f"\nWrote {all_path}: {len(all_df)} rows")


if __name__ == "__main__":
    main()
