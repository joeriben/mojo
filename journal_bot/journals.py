"""CRUD operations for journals.json — the journal registry."""

from __future__ import annotations

import json
import re
from pathlib import Path

from journal_bot.settings import PROJECT_ROOT, JOURNALS_JSON

_PATH = JOURNALS_JSON

# Retrieval types that can be configured via the UI.
VALID_TYPES = {"openalex", "rss", "ojs", "html", "dce", "custom"}


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
    journal_type: str = "openalex",
    url: str = "",
    issn: str = "",
    tier: str = "B",
    clusters: list[str] | None = None,
) -> str:
    """Add a journal to journals.json and assign clusters in diskursraeume.json.

    The url field depends on the type:
      - openalex: "issn:XXXX-XXXX" (built from issn param if url is empty)
      - rss/ojs:  feed URL
      - html:     page URL
      - custom:   ignored (config lives in fetchers/custom/{short}.json)
      - dce:      hardcoded in fetcher

    Returns a status message (starts with ✓ on success).
    """
    if journal_type not in VALID_TYPES:
        return f"Unbekannter Typ: {journal_type}. Erlaubt: {', '.join(sorted(VALID_TYPES))}"

    # Sanitize short code
    short_clean = re.sub(r"[^a-zA-Z0-9_-]", "", short)
    if not short_clean or len(short_clean) < 2:
        return "Kurzname muss mindestens 2 alphanumerische Zeichen haben."

    data = load()
    journals = data.get("journals", [])

    # Check for duplicates
    existing_shorts = {j["short"].lower() for j in journals}
    if short_clean.lower() in existing_shorts:
        return f"Journal '{short_clean}' existiert bereits."

    # Build URL from ISSN for openalex if not explicitly given
    if journal_type == "openalex":
        if not url and issn:
            url = f"issn:{issn}"
        if not url:
            return "OpenAlex-Journals brauchen eine ISSN."

    # For rss/ojs: URL is required
    if journal_type in ("rss", "ojs") and not url:
        return f"{journal_type.upper()}-Journals brauchen eine Feed-URL."

    # For custom: verify config file exists
    if journal_type == "custom":
        from journal_bot.fetchers.configurable_fetcher import CUSTOM_CONFIG_DIR
        config_path = CUSTOM_CONFIG_DIR / f"{short_clean}.json"
        if not config_path.exists():
            return (
                f"Custom-Config nicht gefunden: {config_path.name}. "
                f"Bitte zuerst die Config-Datei anlegen."
            )

    # Check ISSN uniqueness (if provided)
    if issn:
        for j in journals:
            j_url = j.get("url", "")
            j_issn = j.get("issn", "")
            if issn in (j_url.removeprefix("issn:"), j_issn):
                return f"ISSN {issn} ist bereits registriert ({j['short']})."

    # Build entry
    entry: dict = {
        "name": name,
        "short": short_clean,
        "type": journal_type,
        "url": url,
        "tier": tier,
        "enabled": True,
    }
    if issn:
        entry["issn"] = issn

    journals.append(entry)
    data["journals"] = journals
    save(data)

    # Assign clusters in diskursraeume.json
    if clusters:
        from journal_bot.diskurs import load as load_diskurs, save as save_diskurs
        dr = load_diskurs()
        dr_clusters = dr.get("journal_clusters", {})
        dr_clusters[short_clean] = clusters
        dr["journal_clusters"] = dr_clusters
        save_diskurs(dr)

    cluster_str = ", ".join(clusters) if clusters else "(keine)"
    type_label = f"[{journal_type}]"
    return f"✓ {name} ({short_clean}) hinzugefügt {type_label} → Diskursräume: {cluster_str}"


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
