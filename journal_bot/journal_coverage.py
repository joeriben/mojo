"""Journal-Coverage-Analyse: welche Journals werden am häufigsten zitiert,
und tracken wir sie?

Methode:
  1. Alle Crossref-Referenzlisten eines Diskursraums/Zeitfensters sammeln
  2. journal-title-Feld extrahieren und normalisieren
  3. Häufigkeitsranking (wie oft wird dieses Journal zitiert?)
  4. Abgleich gegen settings.JOURNALS → tracked / untracked
  5. Ausgabe: Tabelle mit Empfehlungen

Kein LLM. Rein Python. Null Kosten.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path

from journal_bot.settings import DISCOURSE_SPACES, JOURNALS, journals_in_cluster
from journal_bot.store import Store, StoredArticle


# ---------------------------------------------------------------- Normalisierung


def _normalize_journal(raw: str) -> str:
    """Normalize journal name for aggregation.

    Lowercases, strips whitespace/punctuation variants, collapses unicode dashes,
    removes 'the' prefix.
    """
    s = raw.strip()
    if not s:
        return ""
    # Unicode normalize (e.g. non-breaking spaces, special dashes)
    s = unicodedata.normalize("NFKC", s)
    s = s.lower()
    # Collapse various dashes/hyphens
    s = re.sub(r"[\u2010-\u2015\u2212\u00ad]", "-", s)
    # Remove trailing periods and commas
    s = s.strip(".,;: ")
    # Remove leading "the "
    s = re.sub(r"^the\s+", "", s)
    # Collapse whitespace
    s = re.sub(r"\s+", " ", s)
    return s


def _abbreviation_key(name: str) -> str:
    """Build a condensed key from significant words for fuzzy matching.

    Strips stopwords, punctuation, and short words to match abbreviated forms
    like 'AI Soc' against 'AI & Society'.
    """
    stop = {"the", "a", "an", "of", "in", "on", "for", "and", "to", "from",
            "with", "by", "at", "as", "&", "-", "–"}
    words = _normalize_journal(name).split()
    sig = [w.rstrip(".,") for w in words if w not in stop and len(w) > 1]
    return " ".join(sig)


def _build_tracked_index() -> dict[str, str]:
    """Build a lookup: normalized journal name → short name for tracked journals.

    Builds multiple keys per journal (full name, short name, abbreviation key)
    to catch Crossref abbreviation variants.
    """
    idx: dict[str, str] = {}
    for j in JOURNALS:
        idx[_normalize_journal(j.name)] = j.short
        idx[j.short.lower()] = j.short
        abbr = _abbreviation_key(j.name)
        if abbr and len(abbr) > 2:
            idx[abbr] = j.short
    return idx


# Precomputed list of (abbreviation_key words, short) for prefix matching
_TRACKED_ABBR_WORDS: list[tuple[list[str], str]] = []


def _init_abbr_words() -> None:
    if _TRACKED_ABBR_WORDS:
        return
    for j in JOURNALS:
        words = _abbreviation_key(j.name).split()
        if len(words) >= 2:
            _TRACKED_ABBR_WORDS.append((words, j.short))


def _fuzzy_match_tracked(name: str) -> str:
    """Try to match a possibly abbreviated journal name against tracked journals.

    Uses prefix matching: each word in the query must be a prefix of a
    corresponding word in the tracked journal's abbreviation key.
    Requires all query words to match and at least 2 words.
    """
    _init_abbr_words()
    query_words = _abbreviation_key(name).split()
    if len(query_words) < 2:
        return ""
    for tracked_words, short in _TRACKED_ABBR_WORDS:
        if len(query_words) != len(tracked_words):
            continue
        if all(tw.startswith(qw) or qw.startswith(tw)
               for qw, tw in zip(query_words, tracked_words)):
            return short
    return ""


# ---------------------------------------------------------------- Analyse


def analyze(
    cluster: str,
    window_years: int = 3,
    min_citations: int = 3,
) -> list[dict]:
    """Aggregate cited journals in a discourse space.

    Returns list of dicts sorted by citation count:
      {name, normalized, count, unique_citing_articles, tracked, tracked_as}
    """
    store = Store()

    if cluster not in DISCOURSE_SPACES:
        raise ValueError(f"Unbekannter Cluster: {cluster}")

    journals = [j.short for j in journals_in_cluster(cluster)]
    this_year = datetime.now().year
    start_year = this_year - window_years + 1

    articles = store.find_in_window(start_year=start_year, journals=journals)

    tracked_idx = _build_tracked_index()

    # Aggregation
    journal_counts: Counter[str] = Counter()       # normalized name → total refs
    journal_articles: dict[str, set[str]] = defaultdict(set)  # → set of citing article IDs
    journal_display: dict[str, Counter[str]] = defaultdict(Counter)  # → raw name variants

    for art in articles:
        refs = art.crossref_refs
        if isinstance(refs, str):
            try:
                refs = json.loads(refs)
            except Exception:
                continue
        if not isinstance(refs, list):
            continue

        for ref in refs:
            raw_journal = (ref.get("journal") or "").strip()
            if not raw_journal:
                continue
            norm = _normalize_journal(raw_journal)
            if not norm or len(norm) < 3:
                continue

            journal_counts[norm] += 1
            journal_articles[norm].add(art.id)
            journal_display[norm][raw_journal] += 1

    # Build results
    results: list[dict] = []
    for norm, count in journal_counts.most_common():
        if count < min_citations:
            break
        # Pick the most common display variant
        display_name = journal_display[norm].most_common(1)[0][0]
        tracked_as = tracked_idx.get(norm, "")
        if not tracked_as:
            tracked_as = tracked_idx.get(_abbreviation_key(display_name), "")
        if not tracked_as:
            tracked_as = _fuzzy_match_tracked(display_name)
        results.append({
            "name": display_name,
            "normalized": norm,
            "count": count,
            "unique_citing_articles": len(journal_articles[norm]),
            "tracked": bool(tracked_as),
            "tracked_as": tracked_as,
        })

    return results


# ---------------------------------------------------------------- Rendering


def render_markdown(
    cluster: str,
    results: list[dict],
    window_years: int = 3,
) -> str:
    meta = DISCOURSE_SPACES.get(cluster, {})
    this_year = datetime.now().year
    start_year = this_year - window_years + 1
    window_label = f"{start_year}-{this_year}"

    tracked = [r for r in results if r["tracked"]]
    untracked = [r for r in results if not r["tracked"]]

    lines: list[str] = []
    lines.append(f"# Journal-Coverage: {meta.get('name', cluster)}")
    lines.append(f"_Fenster: {window_label} · {len(results)} Journals mit "
                 f"≥{results[-1]['count'] if results else '?'} Zitationen_")
    lines.append("")

    # Summary
    lines.append(f"**{len(tracked)}** getrackte Journals in den Referenzlisten, "
                 f"**{len(untracked)}** nicht getrackt.")
    lines.append("")

    # Untracked — the interesting part
    if untracked:
        lines.append("## Nicht getrackte Journals (nach Zitationshäufigkeit)")
        lines.append("")
        lines.append("| # | Journal | Zit. | Art. | |")
        lines.append("|---|---------|------|------|-|")
        for i, r in enumerate(untracked, 1):
            lines.append(
                f"| {i} | {r['name']} | {r['count']} | "
                f"{r['unique_citing_articles']} | |"
            )
        lines.append("")
        lines.append("_Zit. = Gesamtzitationen; Art. = verschiedene zitierende Artikel_")
        lines.append("")

    # Tracked — for completeness
    if tracked:
        lines.append("## Bereits getrackte Journals")
        lines.append("")
        lines.append("| # | Journal | Kürzel | Zit. | Art. |")
        lines.append("|---|---------|--------|------|------|")
        for i, r in enumerate(tracked, 1):
            lines.append(
                f"| {i} | {r['name']} | {r['tracked_as']} | {r['count']} | "
                f"{r['unique_citing_articles']} |"
            )
        lines.append("")

    lines.append("---")
    lines.append(
        f"_Cluster: {meta.get('name', cluster)} · "
        f"Fenster: {window_label} · Keine LLM-Kosten_"
    )
    return "\n".join(lines)


# ---------------------------------------------------------------- CLI-Entry


def run(
    cluster: str,
    window_years: int = 3,
    min_citations: int = 3,
    verbose: bool = True,
    out_dir: Path | None = None,
) -> dict:
    from journal_bot.settings import DIGEST_DIR
    out_dir = out_dir or DIGEST_DIR

    if verbose:
        print(f"[coverage] Cluster: {cluster}")

    results = analyze(cluster, window_years, min_citations)

    tracked = sum(1 for r in results if r["tracked"])
    untracked = sum(1 for r in results if not r["tracked"])

    if verbose:
        print(f"[coverage] {len(results)} Journals gefunden "
              f"({tracked} getrackt, {untracked} nicht getrackt)")
        if results:
            print(f"[coverage] Top-zitiertes Journal: "
                  f"{results[0]['name']} ({results[0]['count']}×)")
        # Show top untracked
        top_untracked = [r for r in results if not r["tracked"]][:5]
        if top_untracked:
            print(f"[coverage] Top nicht-getrackt:")
            for r in top_untracked:
                print(f"           {r['count']:>4}× | {r['name']}")

    md = render_markdown(cluster, results, window_years)

    trends_dir = out_dir / "trends"
    trends_dir.mkdir(parents=True, exist_ok=True)
    filename = (f"coverage_{date.today().isoformat()}_{cluster}_"
                f"{datetime.now().year - window_years + 1}-{datetime.now().year}.md")
    out_path = trends_dir / filename
    out_path.write_text(md, encoding="utf-8")

    if verbose:
        print(f"[coverage] Geschrieben: {out_path}")

    return {
        "status": "ok",
        "path": str(out_path),
        "total_journals": len(results),
        "tracked": tracked,
        "untracked": untracked,
    }
