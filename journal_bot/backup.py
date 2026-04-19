"""Create portable ZIP backups of local MOJO user data."""

from __future__ import annotations

import json
import sqlite3
import shutil
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
AGENT_CONTEXT_JSON = PROJECT_ROOT / ".agent_context.json"
LEGACY_AGENT_CONTEXT_TXT = PROJECT_ROOT / ".agent_context.txt"
BACKUP_DIR = PROJECT_ROOT / "backups"
BACKUP_SCHEMA_VERSION = 1
CORE_ARCHIVE_MEMBERS = [
    "project_root/profile.json",
    "project_root/projects.json",
    "project_root/journals.json",
    "project_root/diskursraeume.json",
    "project_root/corpus.json",
    "project_root/summaries.json",
    "project_root/articles.db",
]


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


@dataclass(frozen=True)
class RestoreResult:
    archive_path: Path
    restored: list[str]
    skipped: list[str]
    warnings: list[str]
    profile_updates: dict[str, str]


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
            "project_root": str(PROJECT_ROOT),
            "digest_dir": str(DIGEST_DIR),
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


def restore_backup_archive(
    archive_path: Path,
    *,
    restore_digests: bool = True,
    digest_dir_override: Path | None = None,
    zotero_storage_override: Path | None = None,
    dry_run: bool = False,
) -> RestoreResult:
    """Restore a user backup archive into the current project checkout."""
    archive_path = Path(archive_path)
    restored: list[str] = []
    skipped: list[str] = []
    warnings: list[str] = []
    profile_updates: dict[str, str] = {}

    with zipfile.ZipFile(archive_path, "r") as zf:
        manifest = _read_manifest(zf)
        archived_names = set(zf.namelist())
        missing_core = [name for name in CORE_ARCHIVE_MEMBERS if name not in archived_names]
        for name in missing_core:
            warnings.append(f"Kernbestandteil fehlt im Archiv: {name}")

        profile_payload = _load_archived_json(zf, "project_root/profile.json")
        target_digest_dir = DIGEST_DIR
        patched_profile: dict | None = None
        if profile_payload is not None:
            patched_profile, target_digest_dir, profile_updates = _prepare_profile_for_restore(
                profile_payload,
                manifest=manifest,
                has_digest_entries=any(name.startswith("digest_dir/") for name in archived_names),
                digest_dir_override=digest_dir_override,
                zotero_storage_override=zotero_storage_override,
                warnings=warnings,
            )
        elif digest_dir_override is not None:
            target_digest_dir = Path(digest_dir_override).expanduser()

        for name in sorted(archived_names):
            if name.endswith("/") or name == "manifest.json":
                continue
            if name == "project_root/profile.json":
                continue

            destination = _restore_destination(
                archive_member=name,
                target_digest_dir=target_digest_dir,
                restore_digests=restore_digests,
                skipped=skipped,
            )
            if destination is None:
                continue

            restored.append(str(destination))
            if dry_run:
                continue

            destination.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(name, "r") as src, destination.open("wb") as dst:
                shutil.copyfileobj(src, dst)

        if patched_profile is not None:
            restored.append(str(PROFILE_JSON))
            if not dry_run:
                PROFILE_JSON.write_text(
                    json.dumps(patched_profile, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )

    return RestoreResult(
        archive_path=archive_path,
        restored=restored,
        skipped=skipped,
        warnings=warnings,
        profile_updates=profile_updates,
    )


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

    if AGENT_CONTEXT_JSON.exists() and AGENT_CONTEXT_JSON.is_file():
        entries.append(
            BackupEntry(
                source=AGENT_CONTEXT_JSON,
                archive_path=f"project_root/{AGENT_CONTEXT_JSON.name}",
                logical_name="agent_context",
            )
        )
    elif LEGACY_AGENT_CONTEXT_TXT.exists() and LEGACY_AGENT_CONTEXT_TXT.is_file():
        entries.append(
            BackupEntry(
                source=LEGACY_AGENT_CONTEXT_TXT,
                archive_path=f"project_root/{LEGACY_AGENT_CONTEXT_TXT.name}",
                logical_name="agent_context_legacy",
            )
        )
    else:
        skipped.append("kein persistierter Agent-Kontext")

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


def _read_manifest(zf: zipfile.ZipFile) -> dict:
    try:
        with zf.open("manifest.json", "r") as fh:
            return json.loads(fh.read().decode("utf-8"))
    except KeyError:
        return {}


def _load_archived_json(zf: zipfile.ZipFile, name: str) -> dict | None:
    try:
        with zf.open(name, "r") as fh:
            return json.loads(fh.read().decode("utf-8"))
    except KeyError:
        return None


def _prepare_profile_for_restore(
    profile_payload: dict,
    *,
    manifest: dict,
    has_digest_entries: bool,
    digest_dir_override: Path | None,
    zotero_storage_override: Path | None,
    warnings: list[str],
) -> tuple[dict, Path, dict[str, str]]:
    profile = dict(profile_payload)
    updates: dict[str, str] = {}

    original_project_root_raw = manifest.get("project_root") or ""
    original_project_root = Path(original_project_root_raw).expanduser() if original_project_root_raw else None

    restored_digest_dir = _rewrite_digest_dir(
        profile,
        original_project_root=original_project_root,
        has_digest_entries=has_digest_entries,
        digest_dir_override=digest_dir_override,
        warnings=warnings,
    )
    if restored_digest_dir is not None:
        updates["digest_dir"] = str(restored_digest_dir)

    if zotero_storage_override is not None:
        z_path = Path(zotero_storage_override).expanduser()
        profile["zotero_storage"] = str(z_path)
        updates["zotero_storage"] = str(z_path)
    else:
        raw_zotero = str(profile.get("zotero_storage", "") or "").strip()
        if raw_zotero and not Path(raw_zotero).expanduser().exists():
            warnings.append(
                f"zotero_storage aus dem Backup existiert hier nicht: {raw_zotero}"
            )

    target_digest_dir = Path(profile.get("digest_dir") or DIGEST_DIR).expanduser()
    return profile, target_digest_dir, updates


def _rewrite_digest_dir(
    profile: dict,
    *,
    original_project_root: Path | None,
    has_digest_entries: bool,
    digest_dir_override: Path | None,
    warnings: list[str],
) -> Path | None:
    if digest_dir_override is not None:
        new_digest_dir = Path(digest_dir_override).expanduser()
        profile["digest_dir"] = str(new_digest_dir)
        return new_digest_dir

    raw_digest_dir = str(profile.get("digest_dir", "") or "").strip()
    if not raw_digest_dir:
        new_digest_dir = PROJECT_ROOT / "output"
        profile["digest_dir"] = str(new_digest_dir)
        return new_digest_dir

    digest_path = Path(raw_digest_dir).expanduser()

    if not digest_path.is_absolute():
        new_digest_dir = (PROJECT_ROOT / digest_path).resolve()
        profile["digest_dir"] = str(new_digest_dir)
        return new_digest_dir

    if original_project_root and digest_path.is_relative_to(original_project_root):
        rel = digest_path.relative_to(original_project_root)
        new_digest_dir = PROJECT_ROOT / rel
        profile["digest_dir"] = str(new_digest_dir)
        return new_digest_dir

    if has_digest_entries:
        fallback_dir = PROJECT_ROOT / digest_path.name
        profile["digest_dir"] = str(fallback_dir)
        warnings.append(
            f"digest_dir konnte nicht exakt umgeschrieben werden; nutze Fallback im Projekt: {fallback_dir}"
        )
        return fallback_dir

    warnings.append(
        f"digest_dir aus dem Backup bleibt unveraendert und sollte lokal geprueft werden: {raw_digest_dir}"
    )
    return digest_path


def _restore_destination(
    *,
    archive_member: str,
    target_digest_dir: Path,
    restore_digests: bool,
    skipped: list[str],
) -> Path | None:
    if archive_member.startswith("project_root/"):
        rel = archive_member[len("project_root/"):]
        if not rel:
            return None
        return PROJECT_ROOT / rel

    if archive_member.startswith("custom_fetchers/"):
        rel = archive_member[len("custom_fetchers/"):]
        if not rel:
            return None
        return CUSTOM_CONFIG_DIR / rel

    if archive_member.startswith("digest_dir/"):
        if not restore_digests:
            skipped.append(f"{archive_member} ausgelassen (--no-digests)")
            return None
        rel = archive_member[len("digest_dir/"):]
        if not rel:
            return None
        return target_digest_dir / rel

    skipped.append(f"unbekannter Archivpfad: {archive_member}")
    return None
