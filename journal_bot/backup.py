"""Create portable ZIP backups of local MOJO user data."""

from __future__ import annotations

import json
import sqlite3
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from journal_bot.settings import (
    CORPUS_JSON,
    DIGEST_DIR,
    DISKURSRAEUME_JSON,
    JOURNALS_JSON,
    PROFILE_JSON,
    PROJECT_ROOT,
    SUMMARIES_JSON,
)
from journal_bot.store import ARTICLES_DB
from journal_bot.fetchers.configurable_fetcher import CUSTOM_CONFIG_DIR


PROJECTS_JSON = PROJECT_ROOT / "projects.json"
BACKUP_DIR = PROJECT_ROOT / "backups"
BACKUP_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class BackupEntry:
    source: Path
    archive_path: str
    logical_name: str


@dataclass(frozen=True)
class BackupResult:
    archive_path: Path
    included: list[dict]
    skipped: list[str]


def default_backup_path(now: datetime | None = None) -> Path:
    now = now or datetime.now()
    ts = now.strftime("%Y%m%d_%H%M%S")
    return BACKUP_DIR / f"mojo_user_backup_{ts}.zip"


def create_backup_archive(
    output_path: Path | None = None,
    *,
    include_digests: bool = True,
) -> BackupResult:
    """Create a ZIP archive with local MOJO user data.

    Included by default:
    - profile.json
    - projects.json
    - journals.json
    - diskursraeume.json
    - corpus.json
    - summaries.json
    - articles.db (consistent SQLite snapshot)
    - custom fetcher JSON configs (except bundled examples)
    - digest_dir contents, if configured and usable

    Excluded on purpose:
    - API keys
    - Zotero storage
    - caches
    """
    output_path = Path(output_path) if output_path else default_backup_path()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    entries, skipped = _collect_entries(include_digests=include_digests, archive_path=output_path)
    included: list[dict] = []

    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for entry in entries:
            source = entry.source
            temp_snapshot: Path | None = None
            try:
                if source == ARTICLES_DB:
                    temp_snapshot = _snapshot_sqlite(source)
                    source_to_write = temp_snapshot
                else:
                    source_to_write = source

                zf.write(source_to_write, arcname=entry.archive_path)
                included.append({
                    "logical_name": entry.logical_name,
                    "archive_path": entry.archive_path,
                    "size_bytes": source_to_write.stat().st_size,
                })
            finally:
                if temp_snapshot and temp_snapshot.exists():
                    temp_snapshot.unlink()

        manifest = {
            "schema_version": BACKUP_SCHEMA_VERSION,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "included": included,
            "skipped": skipped,
            "notes": [
                "API-Keys und externe Zotero-Daten sind absichtlich nicht enthalten.",
                "Das Archiv ist als portables Nutzer-Backup gedacht.",
            ],
        }
        zf.writestr(
            "manifest.json",
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        )

    return BackupResult(archive_path=output_path, included=included, skipped=skipped)


def _collect_entries(
    *,
    include_digests: bool,
    archive_path: Path,
) -> tuple[list[BackupEntry], list[str]]:
    entries: list[BackupEntry] = []
    skipped: list[str] = []

    core_files = [
        ("profile", PROFILE_JSON),
        ("projects", PROJECTS_JSON),
        ("journals", JOURNALS_JSON),
        ("diskursraeume", DISKURSRAEUME_JSON),
        ("corpus", CORPUS_JSON),
        ("summaries", SUMMARIES_JSON),
        ("articles_db", ARTICLES_DB),
    ]

    for logical_name, path in core_files:
        if path.exists() and path.is_file():
            entries.append(
                BackupEntry(
                    source=path,
                    archive_path=f"project_root/{path.name}",
                    logical_name=logical_name,
                )
            )
        else:
            skipped.append(f"{path.name} fehlt")

    custom_configs = sorted(
        p for p in CUSTOM_CONFIG_DIR.glob("*.json")
        if p.is_file() and not p.name.startswith("_example_")
    )
    if custom_configs:
        for path in custom_configs:
            entries.append(
                BackupEntry(
                    source=path,
                    archive_path=f"custom_fetchers/{path.name}",
                    logical_name=f"custom_fetcher:{path.stem}",
                )
            )
    else:
        skipped.append("keine benutzerdefinierten Fetcher-Configs")

    if include_digests:
        entries.extend(_collect_digest_entries(archive_path=archive_path, skipped=skipped))
    else:
        skipped.append("digest_dir ausgelassen (--no-digests)")

    return entries, skipped


def _collect_digest_entries(
    *,
    archive_path: Path,
    skipped: list[str],
) -> list[BackupEntry]:
    digest_entries: list[BackupEntry] = []

    if not DIGEST_DIR.exists():
        skipped.append("digest_dir fehlt")
        return digest_entries
    if not DIGEST_DIR.is_dir():
        skipped.append("digest_dir ist kein Verzeichnis")
        return digest_entries
    if DIGEST_DIR.resolve() == PROJECT_ROOT.resolve():
        skipped.append("digest_dir = Projektwurzel, daher nicht rekursiv gesichert")
        return digest_entries
    if not DIGEST_DIR.resolve().is_relative_to(PROJECT_ROOT.resolve()):
        skipped.append("digest_dir liegt ausserhalb des Projektordners und wurde nicht automatisch gesichert")
        return digest_entries

    for path in sorted(DIGEST_DIR.rglob("*")):
        if not path.is_file():
            continue
        if path.resolve() == archive_path.resolve():
            continue
        rel = path.relative_to(DIGEST_DIR)
        digest_entries.append(
            BackupEntry(
                source=path,
                archive_path=f"digest_dir/{rel.as_posix()}",
                logical_name=f"digest:{rel.as_posix()}",
            )
        )

    if not digest_entries:
        skipped.append("digest_dir ist leer")

    return digest_entries


def _snapshot_sqlite(source: Path) -> Path:
    """Create a consistent SQLite copy for backup archives."""
    tmp = tempfile.NamedTemporaryFile(prefix="mojo_backup_", suffix=".db", delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()

    src = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    dst = sqlite3.connect(tmp_path)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()

    return tmp_path
