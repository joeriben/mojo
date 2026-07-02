"""OpenAlex-Work-ID → Titel/Jahr Resolver mit File-Cache (Polite-Pool).

Pendant zu `resolve.py` (das DOIs auflöst), aber für nackte OpenAlex-Work-IDs
(`W…`). Wird gebraucht, um geteilte Referenzen in den grounded Werk-Bezügen
lesbar zu machen (`OA:W2549826052` → »Researching a Posthuman World«).

Kein LLM. Reiner Metadaten-Lookup, idempotent über den Cache.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE_DIR = PROJECT_ROOT / ".enrichment_cache" / "oa_titles"

POLITE_MAILTO = "mojo@localhost"
USER_AGENT = f"mojo/1.0 own_refs (mailto:{POLITE_MAILTO})"
BATCH_SIZE = 25
THROTTLE_SECONDS = 0.12


def _bare_id(oa_id: str) -> str:
    """`https://openalex.org/W123` | `W123` → `W123`."""
    return (oa_id or "").rstrip("/").rsplit("/", 1)[-1].strip()


def _cache_path(wid: str, cache_dir: Path) -> Path:
    return cache_dir / f"{wid}.json"


def resolve_oa_titles(
    oa_ids: set[str] | list[str],
    cache_dir: Path = DEFAULT_CACHE_DIR,
    *,
    verbose: bool = False,
) -> dict[str, dict]:
    """Resolve OpenAlex-Work-IDs → {bare_wid: {"title": str|None, "year": int|None}}.

    Cached pro ID; leeres `{}` markiert „nicht in OpenAlex / nicht auflösbar".
    """
    wanted = {_bare_id(x) for x in oa_ids if x}
    wanted.discard("")
    out: dict[str, dict] = {}
    todo: list[str] = []

    cache_dir.mkdir(parents=True, exist_ok=True)
    for wid in wanted:
        p = _cache_path(wid, cache_dir)
        if p.exists():
            try:
                d = json.loads(p.read_text(encoding="utf-8"))
                out[wid] = d
                continue
            except (json.JSONDecodeError, OSError):
                pass
        todo.append(wid)

    if verbose:
        print(f"[oa_titles] cache_hit={len(out)}, todo={len(todo)}")

    if todo:
        with httpx.Client(headers={"User-Agent": USER_AGENT}) as client:
            for i in range(0, len(todo), BATCH_SIZE):
                batch = todo[i:i + BATCH_SIZE]
                found: dict[str, dict] = {}
                try:
                    r = client.get(
                        "https://api.openalex.org/works",
                        params={
                            "filter": "openalex_id:" + "|".join(batch),
                            "select": "id,title,publication_year",
                            "per-page": BATCH_SIZE,
                        },
                        timeout=30.0,
                    )
                    r.raise_for_status()
                    for w in r.json().get("results", []):
                        wid = _bare_id(w.get("id", ""))
                        found[wid] = {"title": w.get("title"),
                                      "year": w.get("publication_year")}
                except httpx.HTTPError as e:
                    if verbose:
                        print(f"[oa_titles] batch error: {e}")
                for wid in batch:
                    info = found.get(wid, {})
                    _cache_path(wid, cache_dir).write_text(
                        json.dumps(info, ensure_ascii=False), encoding="utf-8"
                    )
                    out[wid] = info
                time.sleep(THROTTLE_SECONDS)

    return out
