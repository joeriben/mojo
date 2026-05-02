"""Diskursraum-Management: CRUD + Profiling auf diskursraeume.json.

Diskursräume sind kuratierte thematische Cluster von Journals.
Dieses Modul verwaltet sie als editierbare JSON-Datendatei
(analog zu corpus.json / summaries.json).
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from journal_bot.settings import (
    JOURNALS,
    PROJECT_ROOT,
    RESEARCHER_AREAS,
    RESEARCHER_INSTITUTION,
    RESEARCHER_NAME,
    SUMMARIES_JSON,
)

DISKURSRAEUME_JSON = PROJECT_ROOT / "diskursraeume.json"


def load() -> dict:
    """Load diskursraeume.json. Returns empty structure if file missing."""
    if not DISKURSRAEUME_JSON.exists():
        return {"version": 1, "discourse_spaces": {}, "journal_clusters": {}}
    return json.loads(DISKURSRAEUME_JSON.read_text(encoding="utf-8"))


def save(data: dict) -> None:
    """Write diskursraeume.json with consistent formatting."""
    DISKURSRAEUME_JSON.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _today() -> str:
    return date.today().isoformat()


# ---------------------------------------------------------------- Spaces


def add_space(key: str, name: str, description: str) -> None:
    """Add a new discourse space."""
    data = load()
    spaces = data["discourse_spaces"]
    if key in spaces:
        raise ValueError(f"Diskursraum '{key}' existiert bereits.")
    spaces[key] = {
        "name": name,
        "description": description,
        "created": _today(),
        "modified": _today(),
    }
    save(data)


def rename_space(old_key: str, new_key: str) -> int:
    """Rename a discourse space key. Returns count of updated journal mappings."""
    data = load()
    spaces = data["discourse_spaces"]
    if old_key not in spaces:
        raise ValueError(f"Diskursraum '{old_key}' nicht gefunden.")
    if new_key in spaces:
        raise ValueError(f"Diskursraum '{new_key}' existiert bereits.")

    # Move space definition
    entry = spaces.pop(old_key)
    entry["modified"] = _today()
    spaces[new_key] = entry

    # Update all journal_clusters references
    updated = 0
    for short, clusters in data.get("journal_clusters", {}).items():
        if old_key in clusters:
            clusters[clusters.index(old_key)] = new_key
            updated += 1

    save(data)
    return updated


def remove_space(key: str) -> list[str]:
    """Remove a discourse space. Returns list of affected journal shorts."""
    data = load()
    spaces = data["discourse_spaces"]
    if key not in spaces:
        raise ValueError(f"Diskursraum '{key}' nicht gefunden.")

    del spaces[key]

    # Remove from all journal_clusters
    affected = []
    for short, clusters in data.get("journal_clusters", {}).items():
        if key in clusters:
            clusters.remove(key)
            affected.append(short)

    save(data)
    return affected


def update_space(key: str, name: str | None = None, description: str | None = None) -> None:
    """Update name and/or description of an existing space."""
    data = load()
    spaces = data["discourse_spaces"]
    if key not in spaces:
        raise ValueError(f"Diskursraum '{key}' nicht gefunden.")
    if name is not None:
        spaces[key]["name"] = name
    if description is not None:
        spaces[key]["description"] = description
    spaces[key]["modified"] = _today()
    save(data)


# ---------------------------------------------------------------- Journal Clusters


def assign_journal(short: str, clusters: list[str]) -> None:
    """Assign a journal to one or more discourse spaces (additive)."""
    data = load()
    spaces = data["discourse_spaces"]

    # Validate cluster keys
    for c in clusters:
        if c not in spaces:
            raise ValueError(f"Diskursraum '{c}' nicht gefunden.")

    # Validate journal short
    known_shorts = {j.short for j in JOURNALS}
    if short not in known_shorts:
        raise ValueError(
            f"Journal '{short}' nicht in settings.JOURNALS. "
            f"Bekannt: {', '.join(sorted(known_shorts))}"
        )

    jc = data.setdefault("journal_clusters", {})
    existing = jc.get(short, [])
    for c in clusters:
        if c not in existing:
            existing.append(c)
    jc[short] = existing
    save(data)


def unassign_journal(short: str, cluster: str) -> None:
    """Remove a journal from a discourse space."""
    data = load()
    jc = data.get("journal_clusters", {})
    if short not in jc:
        raise ValueError(f"Journal '{short}' hat keine Cluster-Zuordnungen.")
    if cluster not in jc[short]:
        raise ValueError(f"Journal '{short}' ist nicht in Diskursraum '{cluster}'.")
    jc[short].remove(cluster)
    save(data)


# ---------------------------------------------------------------- Migration


def migrate_from_settings() -> None:
    """One-time migration: write current hardcoded values to diskursraeume.json.

    Only writes if the file does not yet exist.
    """
    if DISKURSRAEUME_JSON.exists():
        print(f"[diskurs] {DISKURSRAEUME_JSON.name} existiert bereits, Migration übersprungen.")
        return

    from journal_bot.settings import DISCOURSE_SPACES

    today = _today()
    data = {
        "version": 1,
        "discourse_spaces": {},
        "journal_clusters": {},
    }

    for key, meta in DISCOURSE_SPACES.items():
        data["discourse_spaces"][key] = {
            "name": meta["name"],
            "description": meta["description"],
            "created": today,
            "modified": today,
        }

    for j in JOURNALS:
        if j.clusters:
            data["journal_clusters"][j.short] = list(j.clusters)

    save(data)
    print(f"[diskurs] Migration geschrieben: {DISKURSRAEUME_JSON}")


# ---------------------------------------------------------------- Profiling


@dataclass
class DiskursProfile:
    """Data-driven profile of a discourse space."""
    key: str
    name: str
    description: str
    journal_count: int
    article_count: int
    top_concepts: list[tuple[str, float]]       # (name, weighted_score)
    top_topics: list[tuple[str, float]]          # (name, weighted_score)
    verdict_counts: dict[str, int]               # verdict → count
    year_counts: dict[int, int]                  # year → article count
    cross_cluster: list[tuple[str, str, int]]    # (other_key, other_name, shared_journals)
    key_term_overlap: list[tuple[str, int]]      # (term, overlap_count)


def build_profile(
    cluster_key: str,
    window_years: int = 3,
) -> DiskursProfile:
    """Build a data-driven profile of a discourse space from articles.db."""
    from journal_bot.settings import DISCOURSE_SPACES, journals_in_cluster
    from journal_bot.store import Store

    if cluster_key not in DISCOURSE_SPACES:
        raise ValueError(f"Unbekannter Diskursraum: {cluster_key}")

    meta = DISCOURSE_SPACES[cluster_key]
    cluster_journals = journals_in_cluster(cluster_key)
    journal_shorts = [j.short for j in cluster_journals]

    store = Store()
    this_year = datetime.now().year
    start_year = this_year - window_years + 1
    articles = store.find_in_window(start_year=start_year, journals=journal_shorts)

    # 1. Aggregate OpenAlex concepts (weighted by score)
    concept_scores: dict[str, float] = defaultdict(float)
    concept_counts: dict[str, int] = defaultdict(int)
    for art in articles:
        concepts = art.openalex_concepts
        if isinstance(concepts, str):
            try:
                concepts = json.loads(concepts)
            except Exception:
                continue
        for c in (concepts or []):
            name = c.get("name", "")
            score = c.get("score", 0.5)
            if name:
                concept_scores[name] += score
                concept_counts[name] += 1

    top_concepts = sorted(
        [(name, concept_scores[name]) for name in concept_scores],
        key=lambda x: x[1],
        reverse=True,
    )[:20]

    # 2. Aggregate OpenAlex topics
    topic_scores: dict[str, float] = defaultdict(float)
    for art in articles:
        topics = art.openalex_topics
        if isinstance(topics, str):
            try:
                topics = json.loads(topics)
            except Exception:
                continue
        for t in (topics or []):
            name = t.get("name", "")
            score = t.get("score", 0.5)
            if name:
                topic_scores[name] += score

    top_topics = sorted(
        [(name, topic_scores[name]) for name in topic_scores],
        key=lambda x: x[1],
        reverse=True,
    )[:15]

    # 3. Verdict distribution
    verdict_counts: dict[str, int] = defaultdict(int)
    for art in articles:
        v = art.agent_verdict
        if v:
            verdict_counts[v] += 1
        else:
            verdict_counts["unverarbeitet"] += 1

    # 4. Year distribution
    year_counts: dict[int, int] = defaultdict(int)
    for art in articles:
        if art.year:
            year_counts[art.year] += 1

    # 5. Cross-cluster overlap
    cross_cluster: list[tuple[str, str, int]] = []
    cluster_journal_set = set(journal_shorts)
    for other_key, other_meta in DISCOURSE_SPACES.items():
        if other_key == cluster_key:
            continue
        other_journals = {j.short for j in journals_in_cluster(other_key)}
        shared = cluster_journal_set & other_journals
        if shared:
            cross_cluster.append((other_key, other_meta["name"], len(shared)))
    cross_cluster.sort(key=lambda x: x[2], reverse=True)

    # 6. Key term overlap with researcher's publications
    key_term_overlap: list[tuple[str, int]] = []
    if SUMMARIES_JSON.exists():
        sdata = json.loads(SUMMARIES_JSON.read_text(encoding="utf-8"))
        all_key_terms: set[str] = set()
        for s in sdata.get("summaries", {}).values():
            terms = s.get("key_terms", [])
            if isinstance(terms, str):
                try:
                    terms = json.loads(terms)
                except Exception:
                    terms = []
            for t in terms:
                all_key_terms.add(t.lower())

        # Count how many articles have concepts matching key terms
        term_hits: Counter[str] = Counter()
        for art in articles:
            concepts = art.openalex_concepts
            if isinstance(concepts, str):
                try:
                    concepts = json.loads(concepts)
                except Exception:
                    continue
            for c in (concepts or []):
                cname = c.get("name", "").lower()
                if cname in all_key_terms:
                    term_hits[cname] += 1

        key_term_overlap = term_hits.most_common(15)

    return DiskursProfile(
        key=cluster_key,
        name=meta["name"],
        description=meta["description"],
        journal_count=len(cluster_journals),
        article_count=len(articles),
        top_concepts=top_concepts,
        top_topics=top_topics,
        verdict_counts=dict(verdict_counts),
        year_counts=dict(sorted(year_counts.items())),
        cross_cluster=cross_cluster,
        key_term_overlap=key_term_overlap,
    )


def render_profile(profile: DiskursProfile) -> str:
    """Render a DiskursProfile as markdown."""
    lines: list[str] = []
    lines.append(f"# Diskursraum-Profil: {profile.name}")
    lines.append(f"_Key: `{profile.key}` · {profile.journal_count} Journals · "
                 f"{profile.article_count} Artikel_")
    lines.append(f"\n> {profile.description}")
    lines.append("")

    # Year distribution
    if profile.year_counts:
        lines.append("## Zeitliche Verteilung")
        for year in sorted(profile.year_counts):
            count = profile.year_counts[year]
            bar = "█" * min(count, 50)
            lines.append(f"  {year}  {bar} {count}")
        lines.append("")

    # Top concepts
    if profile.top_concepts:
        lines.append("## Top OpenAlex-Konzepte")
        lines.append("")
        for i, (name, score) in enumerate(profile.top_concepts, 1):
            lines.append(f"  {i:>2}. {name} ({score:.1f})")
        lines.append("")

    # Top topics
    if profile.top_topics:
        lines.append("## Top OpenAlex-Topics")
        lines.append("")
        for i, (name, score) in enumerate(profile.top_topics, 1):
            lines.append(f"  {i:>2}. {name} ({score:.1f})")
        lines.append("")

    # Key term overlap
    if profile.key_term_overlap:
        lines.append(f"## Überlappung mit {RESEARCHER_NAME}s Key Terms")
        lines.append("")
        for term, count in profile.key_term_overlap:
            lines.append(f"  {term}: {count} Artikel")
        lines.append("")

    # Cross-cluster overlap
    if profile.cross_cluster:
        lines.append("## Cross-Cluster-Overlap")
        lines.append("")
        for other_key, other_name, shared in profile.cross_cluster:
            lines.append(f"  {other_key} ({other_name}): {shared} geteilte Journals")
        lines.append("")

    # Verdicts
    if profile.verdict_counts:
        lines.append("## Agent-Verdicts")
        lines.append("")
        for verdict, count in sorted(profile.verdict_counts.items(),
                                      key=lambda x: x[1], reverse=True):
            lines.append(f"  {verdict}: {count}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------- Discovery


def _build_cluster_concept_profiles(
    window_years: int = 3,
) -> dict[str, dict[str, float]]:
    """Build concept→score dicts for each cluster (normalized)."""
    from journal_bot.settings import DISCOURSE_SPACES, journals_in_cluster
    from journal_bot.store import Store

    store = Store()
    this_year = datetime.now().year
    start_year = this_year - window_years + 1
    profiles: dict[str, dict[str, float]] = {}

    for key in DISCOURSE_SPACES:
        journal_shorts = [j.short for j in journals_in_cluster(key)]
        articles = store.find_in_window(start_year=start_year, journals=journal_shorts)
        scores: dict[str, float] = defaultdict(float)
        for art in articles:
            concepts = art.openalex_concepts
            if isinstance(concepts, str):
                try:
                    concepts = json.loads(concepts)
                except Exception:
                    continue
            for c in (concepts or []):
                name = c.get("name", "")
                score = c.get("score", 0.5)
                if name:
                    scores[name] += score
        profiles[key] = dict(scores)
    return profiles


def find_cross_cutting_concepts(
    window_years: int = 3,
    min_clusters: int = 3,
    min_total_score: float = 5.0,
) -> list[dict]:
    """Find concepts that appear strongly across multiple clusters.

    Returns list of {concept, clusters: [{key, score}], total_score}.
    """
    from journal_bot.settings import DISCOURSE_SPACES

    profiles = _build_cluster_concept_profiles(window_years)

    # Invert: concept → {cluster: score}
    concept_clusters: dict[str, dict[str, float]] = defaultdict(dict)
    for key, scores in profiles.items():
        for concept, score in scores.items():
            if score >= 1.0:  # only meaningful presence
                concept_clusters[concept][key] = score

    results = []
    for concept, clusters in concept_clusters.items():
        if len(clusters) >= min_clusters:
            total = sum(clusters.values())
            if total >= min_total_score:
                results.append({
                    "concept": concept,
                    "clusters": [
                        {"key": k, "score": round(v, 1)}
                        for k, v in sorted(clusters.items(), key=lambda x: x[1], reverse=True)
                    ],
                    "total_score": round(total, 1),
                    "cluster_count": len(clusters),
                })
    results.sort(key=lambda x: x["total_score"], reverse=True)
    return results


def suggest_new_spaces(
    window_years: int = 3,
    verbose: bool = True,
) -> str:
    """LLM-assisted discovery of potential new discourse spaces.

    Returns markdown output with suggestions.
    """
    from journal_bot.llm_client import build_client
    from journal_bot.settings import DISCOURSE_SPACES, MODEL_SUMMARIZE

    # Phase 1+2: data analysis (no LLM)
    cross_cutting = find_cross_cutting_concepts(window_years)

    # Build all cluster profiles for context
    all_profiles: list[str] = []
    for key in DISCOURSE_SPACES:
        p = build_profile(key, window_years)
        top_c = ", ".join(f"{n} ({s:.0f})" for n, s in p.top_concepts[:10])
        all_profiles.append(f"- {key} ({p.name}): {p.article_count} Artikel. "
                           f"Top-Konzepte: {top_c}")

    # Format cross-cutting concepts
    cross_lines: list[str] = []
    for cc in cross_cutting[:20]:
        cluster_list = ", ".join(
            f"{c['key']} ({c['score']})" for c in cc["clusters"]
        )
        cross_lines.append(
            f"- {cc['concept']} (Gesamt: {cc['total_score']}, "
            f"in {cc['cluster_count']} Räumen): {cluster_list}"
        )

    # Key terms from summaries
    key_terms_block = ""
    if SUMMARIES_JSON.exists():
        sdata = json.loads(SUMMARIES_JSON.read_text(encoding="utf-8"))
        all_terms: Counter[str] = Counter()
        for s in sdata.get("summaries", {}).values():
            terms = s.get("key_terms", [])
            if isinstance(terms, str):
                try:
                    terms = json.loads(terms)
                except Exception:
                    terms = []
            for t in terms:
                all_terms[t] += 1
        top_terms = all_terms.most_common(30)
        key_terms_block = "\n".join(f"  {t}: {c}×" for t, c in top_terms)

    # Phase 3: LLM synthesis
    system = f"""Du bist Forschungsberater für {RESEARCHER_NAME} ({RESEARCHER_INSTITUTION}).
{RESEARCHER_NAME} arbeitet an: {RESEARCHER_AREAS},
Bildungstheorie, qualitative Methoden (postqualitative Ansätze).

Du bekommst eine Analyse seiner Journal-Monitoring-Diskursräume und sollst vorschlagen,
ob neue Diskursräume sinnvoll wären oder bestehende umbenannt/zusammengelegt werden sollten.

Regeln:
- Maximal 3 Vorschläge für NEUE Diskursräume
- Maximal 3 Vorschläge für UMBENENNUNG/ZUSAMMENLEGUNG
- Jeder Vorschlag braucht: key, name, description, betroffene Journals/Konzepte, Begründung
- Keine generischen Cluster ("Interdisziplinäres") — nur wenn ein echter thematischer Kern erkennbar ist
- Auf Deutsch antworten"""

    user_msg = f"""Aktuelle Diskursräume und ihre Profile:

{chr(10).join(all_profiles)}

Querschnitt-Konzepte (erscheinen in ≥3 Diskursräumen):

{chr(10).join(cross_lines) if cross_lines else "(keine gefunden)"}

{RESEARCHER_NAME}s häufigste Key Terms (aus 53 Publikationen):

{key_terms_block or "(nicht verfügbar)"}

Aufgabe: Analysiere diese Daten und schlage vor:
1. Neue Diskursräume, die sich aus den Daten abzeichnen (0-3)
2. Umbenennungen oder Zusammenlegungen bestehender Räume (0-3)

Für jeden Vorschlag: key, name, description, Begründung mit konkretem Datenbezug."""

    if verbose:
        print("[diskurs] Sende Analyse an LLM...")

    client = build_client()
    resp = client.chat.completions.create(
        model=MODEL_SUMMARIZE,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.3,
        max_tokens=2000,
    )

    usage = resp.usage
    cost = 0.0
    usage_dump: dict = {}
    if usage:
        usage_dump = (
            usage.model_dump() if hasattr(usage, "model_dump") else {}
        )
        cost = float(usage_dump.get("cost") or 0.0)
        if cost == 0.0:
            cost = (
                (usage.prompt_tokens / 1_000_000) * 0.80
                + (usage.completion_tokens / 1_000_000) * 4.00
            )
        if verbose:
            print(f"[diskurs] Tokens: {usage.prompt_tokens} in, "
                  f"{usage.completion_tokens} out — ${cost:.3f}")

    from journal_bot.llm_log import record_llm_call
    record_llm_call(
        endpoint="diskurs_discover", model=MODEL_SUMMARIZE,
        usage=usage_dump, cost_usd=cost, status="ok",
        window_years=window_years,
    )

    llm_output = resp.choices[0].message.content or ""

    # Build final markdown
    lines = [
        f"# Diskursraum-Analyse: Vorschläge",
        f"_Datum: {date.today().isoformat()} · Fenster: {window_years} Jahre · "
        f"Kosten: ${cost:.3f}_",
        "",
        "## Datengrundlage",
        "",
    ]
    lines.extend(all_profiles)
    lines.append("")

    if cross_lines:
        lines.append("## Querschnitt-Konzepte")
        lines.append("")
        lines.extend(cross_lines)
        lines.append("")

    lines.append("## LLM-Vorschläge")
    lines.append("")
    lines.append(llm_output)

    return "\n".join(lines)
