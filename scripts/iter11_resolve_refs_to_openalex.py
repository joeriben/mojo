"""Iter 11 / Phase 3: Resolve extracted DOI-refs to OpenAlex Work-IDs.

Input: backtest_data/own_bibliography/refs/{key}.json (mit dois_in_refs).
Output:
- backtest_data/own_bibliography/refs_resolved.json
  {
    "all_own_ref_dois": [...],          # Union of all DOIs in Benjamin's refs
    "all_own_ref_oa_ids": [...],        # Union of OpenAlex Work-IDs (https://openalex.org/Wxxx)
    "per_item": {
      "{zotero_key}": {
        "dois": [...], "oa_ids": [...]
      }
    },
    "resolution_summary": {
      "n_dois_input": ...,
      "n_dois_resolved_in_oa": ...
    }
  }

KEINE LLM-Calls. OpenAlex-API mit Polite-Pool (mailto), gecacht in
.enrichment_cache/iter11_oa_doi/{doi_hash}.json.

Wir batchen 25 DOIs pro OpenAlex-Call via filter=doi:... .
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

import httpx

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "backtest_data" / "own_bibliography"
REFS_DIR = DATA_DIR / "refs"
OUT_PATH = DATA_DIR / "refs_resolved.json"

CACHE_DIR = PROJECT_ROOT / ".enrichment_cache" / "iter11_oa_doi"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

POLITE_MAILTO = "mojo@localhost"
USER_AGENT = f"mojo/0.1 iter11 (mailto:{POLITE_MAILTO})"

BATCH = 25  # OpenAlex erlaubt | im filter — 25 DOIs ergeben URLs unter 2 KB


def doi_cache_path(doi: str) -> Path:
    h = hashlib.sha1(doi.encode()).hexdigest()
    return CACHE_DIR / f"{h}.json"


def load_cached(doi: str) -> dict | None:
    p = doi_cache_path(doi)
    if p.exists():
        return json.loads(p.read_text())
    return None


def save_cache(doi: str, payload: dict) -> None:
    doi_cache_path(doi).write_text(json.dumps(payload, ensure_ascii=False))


def normalize_doi(doi: str) -> str:
    d = doi.strip().lower()
    d = d.rstrip(".,;:)]")
    # Sometimes prefixed with full URL
    for pfx in ("https://doi.org/", "http://doi.org/", "doi:", "https://dx.doi.org/"):
        if d.startswith(pfx):
            d = d[len(pfx):]
    return d


def collect_all_dois() -> dict[str, list[str]]:
    """Liefert dict zotero_key → list[normalized DOIs from refs]."""
    per_item: dict[str, list[str]] = {}
    for path in sorted(REFS_DIR.glob("*.json")):
        data = json.loads(path.read_text())
        dois = [normalize_doi(d) for d in (data.get("dois_in_refs") or [])]
        dois = [d for d in dois if d and len(d) > 7]
        if dois:
            per_item[data["zotero_key"]] = dois
    return per_item


def resolve_batch(client: httpx.Client, dois: list[str]) -> dict[str, dict]:
    """OpenAlex batch query. Return dict doi → work-info or {} if not found."""
    filter_val = "|".join(dois)
    url = "https://api.openalex.org/works"
    params = {
        "filter": f"doi:{filter_val}",
        "per-page": str(min(200, len(dois) * 2)),
        "select": "id,doi,title,publication_year,primary_location",
        "mailto": POLITE_MAILTO,
    }
    try:
        r = client.get(url, params=params, timeout=30.0)
        if r.status_code != 200:
            print(f"  [warn] OpenAlex {r.status_code}: {r.text[:200]}")
            return {}
        results = r.json().get("results", [])
    except httpx.HTTPError as e:
        print(f"  [warn] OpenAlex error: {e}")
        return {}
    out = {}
    for w in results:
        wd = (w.get("doi") or "").lower().replace("https://doi.org/", "")
        if wd:
            out[wd] = {
                "oa_id": w.get("id"),
                "doi": wd,
                "title": w.get("title"),
                "year": w.get("publication_year"),
            }
    return out


def main() -> None:
    per_item = collect_all_dois()
    all_dois = sorted({d for ds in per_item.values() for d in ds})
    print(f"[resolve] {len(per_item)} Items mit Refs-DOIs, {len(all_dois)} eindeutige DOIs total.")

    # Cache prüfen.
    resolved: dict[str, dict] = {}
    todo: list[str] = []
    for d in all_dois:
        c = load_cached(d)
        if c is not None:
            resolved[d] = c
        else:
            todo.append(d)
    print(f"[resolve] Cache-Hit: {len(resolved)}, neu zu lösen: {len(todo)}")

    if todo:
        client = httpx.Client(headers={"User-Agent": USER_AGENT})
        for i in range(0, len(todo), BATCH):
            batch = todo[i : i + BATCH]
            batch_resolved = resolve_batch(client, batch)
            for d in batch:
                info = batch_resolved.get(d, {})  # leer = nicht in OA
                save_cache(d, info)
                resolved[d] = info
            print(
                f"  Batch {i // BATCH + 1}/{(len(todo) + BATCH - 1) // BATCH}: "
                f"{len(batch_resolved)}/{len(batch)} hits"
            )
            time.sleep(0.12)  # konservatives Throttling unter Polite-Pool-Limit (10/s)
        client.close()

    # Aggregate.
    all_oa_ids = sorted({v["oa_id"] for v in resolved.values() if v.get("oa_id")})
    n_resolved = sum(1 for v in resolved.values() if v.get("oa_id"))

    per_item_out = {}
    for zkey, dois in per_item.items():
        oa_ids = sorted({resolved[d]["oa_id"] for d in dois if resolved.get(d, {}).get("oa_id")})
        per_item_out[zkey] = {
            "n_dois": len(dois),
            "n_oa_ids": len(oa_ids),
            "dois": dois,
            "oa_ids": oa_ids,
        }

    out = {
        "all_own_ref_dois": all_dois,
        "all_own_ref_oa_ids": all_oa_ids,
        "per_item": per_item_out,
        "resolution_summary": {
            "n_items_with_doi_refs": len(per_item),
            "n_dois_input": len(all_dois),
            "n_dois_resolved_in_oa": n_resolved,
            "n_unique_oa_ids": len(all_oa_ids),
            "oa_resolution_rate": round(n_resolved / max(1, len(all_dois)), 3),
        },
    }
    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(
        f"[resolve] Geschrieben: {OUT_PATH}\n"
        f"          {n_resolved}/{len(all_dois)} DOIs in OpenAlex aufgelöst → "
        f"{len(all_oa_ids)} unique Work-IDs."
    )


if __name__ == "__main__":
    main()
