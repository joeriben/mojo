"""CRUD operations for journals.json — the journal registry."""

from __future__ import annotations

import json
from pathlib import Path

from journal_bot.settings import PROJECT_ROOT, JOURNALS_JSON

_PATH = JOURNALS_JSON


def load() -> dict:
    """Load the journals.json file."""
    return json.loads(_PATH.read_text(encoding="utf-8"))


def save(data: dict) -> None:
    """Write journals.json with consistent formatting."""
    _PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def add_journal(
    name: str,
    short: str,
    issn: str,
    clusters: list[str] | None = None,
    journal_type: str = "openalex",
) -> str:
    """Add a journal to journals.json and assign clusters in diskursraeume.json.

    Returns a status message.
    """
    data = load()
    journals = data.get("journals", [])

    # Check for duplicates
    existing_shorts = {j["short"].lower() for j in journals}
    if short.lower() in existing_shorts:
        return f"Journal '{short}' existiert bereits."

    existing_issns = set()
    for j in journals:
        url = j.get("url", "")
        if url.startswith("issn:"):
            existing_issns.add(url[5:])
    if issn in existing_issns:
        return f"ISSN {issn} ist bereits registriert."

    # Add journal entry
    entry = {
        "name": name,
        "short": short,
        "type": journal_type,
        "url": f"issn:{issn}",
        "enabled": True,
    }
    journals.append(entry)
    data["journals"] = journals
    save(data)

    # Assign clusters in diskursraeume.json
    if clusters:
        from journal_bot.diskurs import load as load_diskurs, save as save_diskurs
        dr = load_diskurs()
        dr_clusters = dr.get("journal_clusters", {})
        dr_clusters[short] = clusters
        dr["journal_clusters"] = dr_clusters
        save_diskurs(dr)

    cluster_str = ", ".join(clusters) if clusters else "(keine)"
    return f"✓ {name} ({short}, {issn}) hinzugefügt → Diskursräume: {cluster_str}"


def remove_journal(short: str) -> str:
    """Remove a journal from journals.json and diskursraeume.json.

    Returns a status message.
    """
    data = load()
    journals = data.get("journals", [])
    before = len(journals)
    journals = [j for j in journals if j["short"] != short]

    if len(journals) == before:
        return f"Journal '{short}' nicht gefunden."

    data["journals"] = journals
    save(data)

    # Remove from diskursraeume.json
    from journal_bot.diskurs import load as load_diskurs, save as save_diskurs
    dr = load_diskurs()
    dr_clusters = dr.get("journal_clusters", {})
    removed_clusters = dr_clusters.pop(short, [])
    dr["journal_clusters"] = dr_clusters
    save_diskurs(dr)

    return f"✓ {short} entfernt (war in: {', '.join(removed_clusters) or 'keinem Cluster'})"


def list_journals() -> list[dict]:
    """Return all journals with their cluster assignments."""
    data = load()

    # Load clusters from diskursraeume.json
    from journal_bot.diskurs import load as load_diskurs
    dr = load_diskurs()
    dr_clusters = dr.get("journal_clusters", {})

    result = []
    for j in data.get("journals", []):
        result.append({
            **j,
            "clusters": dr_clusters.get(j["short"], []),
        })
    return result
