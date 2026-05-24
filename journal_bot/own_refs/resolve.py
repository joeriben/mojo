"""DOI → OpenAlex-Work-ID via Polite-Pool, mit File-Cache.

Portiert aus `scripts/iter11_resolve_refs_to_openalex.py`. Die wesentliche
Akzeptanzkriterium-2-Implikation steht im Cache-Pfad-Default:

    .enrichment_cache/iter11_oa_doi/<sha1(doi)>.json

Das ist derselbe Pfad, den der Iter-11-Snapshot bereits gefüllt hat
(~318 Files). Beim ersten produktiven `mojo refs build` werden diese Cache-
Files ohne API-Call wiederverwendet — zweiter Lauf ist 0 OpenAlex-Calls.

OpenAlex erlaubt im `filter=doi:...` bis zu ~25 DOIs pro Anfrage (URL-Limit).
Polite-Pool: `mailto`-Parameter + `User-Agent`-Header, ~10 req/s erlaubt;
wir throttlen konservativ auf 0.12 s zwischen Batches.

KEINE LLM-Calls. Pure HTTP.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import httpx

from journal_bot.own_refs.identity import normalize_doi

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE_DIR = PROJECT_ROOT / ".enrichment_cache" / "iter11_oa_doi"

POLITE_MAILTO = "mojo@localhost"
USER_AGENT = f"mojo/1.0 own_refs (mailto:{POLITE_MAILTO})"
BATCH_SIZE = 25
THROTTLE_SECONDS = 0.12


@dataclass
class ResolvedRef:
    doi: str                    # normalized
    oa_id: str | None = None    # "https://openalex.org/W..." oder None falls nicht in OA
    title: str | None = None
    year: int | None = None


# -- Cache --------------------------------------------------------------------


def _cache_path(doi: str, cache_dir: Path) -> Path:
    h = hashlib.sha1(doi.encode("utf-8")).hexdigest()
    return cache_dir / f"{h}.json"


def _load_cached(doi: str, cache_dir: Path) -> ResolvedRef | None:
    p = _cache_path(doi, cache_dir)
    if not p.exists():
        return None
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    # leeres dict = damals als "nicht in OpenAlex" markiert
    if not d:
        return ResolvedRef(doi=doi)
    return ResolvedRef(
        doi=d.get("doi") or doi,
        oa_id=d.get("oa_id"),
        title=d.get("title"),
        year=d.get("year"),
    )


def _save_cache(doi: str, info: dict, cache_dir: Path) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    _cache_path(doi, cache_dir).write_text(
        json.dumps(info, ensure_ascii=False), encoding="utf-8"
    )


# -- API-Calls ----------------------------------------------------------------


def _resolve_batch(client: httpx.Client, dois: list[str]) -> dict[str, dict]:
    filter_val = "|".join(dois)
    params = {
        "filter": f"doi:{filter_val}",
        "per-page": str(min(200, max(25, len(dois) * 2))),
        "select": "id,doi,title,publication_year",
        "mailto": POLITE_MAILTO,
    }
    try:
        r = client.get("https://api.openalex.org/works", params=params, timeout=30.0)
    except httpx.HTTPError as e:
        print(f"  [warn] OpenAlex network error: {e}")
        return {}
    if r.status_code != 200:
        print(f"  [warn] OpenAlex {r.status_code}: {r.text[:200]}")
        return {}
    out: dict[str, dict] = {}
    for w in r.json().get("results", []):
        wd = (w.get("doi") or "").lower().replace("https://doi.org/", "")
        if wd:
            out[wd] = {
                "oa_id": w.get("id"),
                "doi": wd,
                "title": w.get("title"),
                "year": w.get("publication_year"),
            }
    return out


# -- Public API ---------------------------------------------------------------


def resolve_dois(
    dois: Iterable[str],
    cache_dir: Path = DEFAULT_CACHE_DIR,
    verbose: bool = False,
) -> dict[str, ResolvedRef]:
    """Auflösen einer Iterable von DOIs.

    Returns: dict normalized_doi → ResolvedRef. Auch DOIs, die nicht in
    OpenAlex sind, landen im dict (mit `oa_id=None`), damit Folge-Aufrufe
    sie nicht erneut anfragen.
    """
    normalized = sorted({normalize_doi(d) for d in dois if d})
    normalized = [d for d in normalized if len(d) > 7]
    cache_dir.mkdir(parents=True, exist_ok=True)

    resolved: dict[str, ResolvedRef] = {}
    todo: list[str] = []
    for d in normalized:
        cached = _load_cached(d, cache_dir)
        if cached is not None:
            resolved[d] = cached
        else:
            todo.append(d)

    if verbose:
        print(
            f"[resolve] {len(normalized)} DOIs total, "
            f"cache_hit={len(resolved)}, todo={len(todo)}"
        )
    if not todo:
        return resolved

    client = httpx.Client(headers={"User-Agent": USER_AGENT})
    try:
        for i in range(0, len(todo), BATCH_SIZE):
            batch = todo[i:i + BATCH_SIZE]
            results = _resolve_batch(client, batch)
            for d in batch:
                info = results.get(d, {})
                _save_cache(d, info, cache_dir)
                if info:
                    resolved[d] = ResolvedRef(
                        doi=info["doi"],
                        oa_id=info.get("oa_id"),
                        title=info.get("title"),
                        year=info.get("year"),
                    )
                else:
                    resolved[d] = ResolvedRef(doi=d)
            if verbose:
                n_hits = sum(1 for d in batch if resolved[d].oa_id)
                print(
                    f"  Batch {i // BATCH_SIZE + 1}/"
                    f"{(len(todo) + BATCH_SIZE - 1) // BATCH_SIZE}: "
                    f"{n_hits}/{len(batch)} resolved"
                )
            time.sleep(THROTTLE_SECONDS)
    finally:
        client.close()

    return resolved
