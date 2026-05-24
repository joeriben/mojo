"""Iter 10 / Phase 1a: Pull OpenAlex bibliographies for Level-1 Trigger-Authors.

Pro Trigger-Autor (Macgilchrist, Jarke, Chun) wird die OpenAlex-Author-ID
disambiguiert und alle publizierten Works inkl. referenced_works gezogen.
Output: backtest_data/trigger_bibliographies/{slug}.json

Methodik:
- Author-Search via /authors?search=...
- Disambiguation per Affiliation-Hints (für Jarke und Macgilchrist gibt es Namens-Dupes)
- Works-Pull via /works?filter=author.id:...&per-page=200&cursor=*
- Pro Work: id, doi, title, year, primary_location.source.display_name (journal),
  primary_topic, concepts, authorships, referenced_works
- Caching via httpx + JSON-Disk

KEINE LLM-Calls. Reine OpenAlex-API.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import httpx


POLITE_MAILTO = "mojo@localhost"
USER_AGENT = f"mojo/0.1 iter10 (mailto:{POLITE_MAILTO})"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = PROJECT_ROOT / "backtest_data" / "trigger_bibliographies"
CACHE_DIR = PROJECT_ROOT / ".enrichment_cache" / "iter10_authors"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


# Trigger-Autoren mit Disambiguations-Hinweisen.
# Patterns aus signals.py: ("macgilchrist", "jarke", "wendy chun", "wendy hui kyong")
TRIGGER_AUTHORS = [
    {
        "slug": "macgilchrist",
        "search_name": "Felicitas Macgilchrist",
        "affiliation_keywords": [
            "oldenburg", "bremen", "leibniz", "georg-eckert", "ifab",
            "göttingen", "education", "media", "pedagog",
        ],
    },
    {
        "slug": "jarke",
        "search_name": "Juliane Jarke",
        "affiliation_keywords": [
            "bremen", "graz", "salzburg", "ifib", "algorithmic", "datafication",
        ],
    },
    {
        "slug": "wendy_chun",
        "search_name": "Wendy Hui Kyong Chun",
        "affiliation_keywords": [
            "simon fraser", "brown", "toronto", "media", "communication",
        ],
    },
]


def http_get_json(url: str, cache_key: str | None = None, timeout: float = 30) -> dict | None:
    """GET JSON mit File-Cache. cache_key bestimmt die Datei (None = kein Cache)."""
    cache_file = None
    if cache_key:
        import hashlib
        safe = hashlib.sha256(cache_key.encode()).hexdigest()[:24]
        cache_file = CACHE_DIR / f"{safe}.json"
        if cache_file.exists():
            try:
                return json.loads(cache_file.read_text(encoding="utf-8"))
            except Exception:
                cache_file.unlink(missing_ok=True)
    try:
        resp = httpx.get(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            timeout=timeout,
            follow_redirects=True,
        )
        if resp.status_code != 200:
            print(f"  ! HTTP {resp.status_code} for {url[:100]}")
            return None
        data = resp.json()
        if cache_file:
            cache_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return data
    except Exception as e:
        print(f"  ! Exception {type(e).__name__} for {url[:100]}: {e}")
        return None


def search_author(search_name: str, affiliation_keywords: list[str]) -> dict | None:
    """Suche Autor in OpenAlex, wähle besten Treffer per Affiliation-Match.

    Rückgabe: dict mit id (OpenAlex-ID), display_name, works_count, last_known_institution
              oder None bei keinem Treffer.
    """
    url = (
        f"https://api.openalex.org/authors?search={search_name.replace(' ', '+')}"
        f"&per-page=25&mailto={POLITE_MAILTO}"
    )
    data = http_get_json(url, cache_key=f"author_search:{search_name}")
    if not data or "results" not in data:
        return None
    results = data["results"]
    if not results:
        return None

    def aff_score(author: dict) -> int:
        """Anzahl Affiliations, die einen Keyword-Match haben + works_count-Bonus."""
        # last_known_institution + affiliations (alle bisherigen)
        affs_text_parts = []
        lki = author.get("last_known_institution") or {}
        if lki.get("display_name"):
            affs_text_parts.append(lki["display_name"])
        if lki.get("country_code"):
            affs_text_parts.append(lki["country_code"])
        for aff in author.get("affiliations", []) or []:
            inst = aff.get("institution") or {}
            if inst.get("display_name"):
                affs_text_parts.append(inst["display_name"])
        # Topics als Affiliation-Proxy
        for topic in (author.get("topics") or [])[:5]:
            if topic.get("display_name"):
                affs_text_parts.append(topic["display_name"])
        affs_blob = " ".join(affs_text_parts).lower()
        n_matches = sum(1 for kw in affiliation_keywords if kw.lower() in affs_blob)
        # Tie-breaker: works_count (mehr Works ≈ etabliertere Person)
        wc = author.get("works_count", 0)
        return n_matches * 1000 + min(wc, 999)

    ranked = sorted(results, key=aff_score, reverse=True)
    best = ranked[0]
    print(f"  Author-Suche '{search_name}': {len(results)} Treffer, "
          f"bester: {best.get('display_name')} "
          f"(ID={best.get('id','?').split('/')[-1]}, "
          f"works_count={best.get('works_count',0)}, "
          f"institution={(best.get('last_known_institution') or {}).get('display_name','?')})")
    # Liste die Top-3 für manuelle Kontrolle
    for i, a in enumerate(ranked[:3]):
        print(f"    #{i+1}: {a.get('display_name')} "
              f"(works={a.get('works_count',0)}, "
              f"inst={(a.get('last_known_institution') or {}).get('display_name','?')}, "
              f"score={aff_score(a)})")
    return best


def pull_all_works(author_id: str, max_pages: int = 20) -> list[dict]:
    """Cursor-paginated pull aller Works eines Autors via /works?filter=author.id:..."""
    aid = author_id.rsplit("/", 1)[-1]  # nur "Annnnn"
    cursor = "*"
    all_works: list[dict] = []
    page = 0
    while page < max_pages:
        page += 1
        url = (
            f"https://api.openalex.org/works?filter=author.id:{aid}"
            f"&per-page=200&cursor={cursor}"
            f"&select=id,doi,title,publication_year,primary_location,primary_topic,"
            f"concepts,authorships,referenced_works,type"
            f"&mailto={POLITE_MAILTO}"
        )
        data = http_get_json(url, cache_key=f"works:{aid}:{cursor}")
        if not data:
            print(f"    ! Page {page}: kein Response, Abbruch.")
            break
        results = data.get("results", []) or []
        all_works.extend(results)
        meta = data.get("meta", {})
        next_cursor = meta.get("next_cursor")
        print(f"    Page {page}: {len(results)} Works, total={meta.get('count','?')}, "
              f"next_cursor={'yes' if next_cursor else 'no'}")
        if not next_cursor or not results:
            break
        cursor = next_cursor
        time.sleep(0.1)  # höflich
    return all_works


def slim_work(w: dict) -> dict:
    """Reduziere auf die Felder, die wir für die 2nd-Network-Analyse brauchen."""
    primary_loc = w.get("primary_location") or {}
    source = primary_loc.get("source") or {}
    primary_topic = w.get("primary_topic") or {}
    return {
        "id": w.get("id", "").rsplit("/", 1)[-1],
        "doi": w.get("doi", "") or "",
        "title": w.get("title", "") or "",
        "year": w.get("publication_year"),
        "type": w.get("type", ""),
        "journal": source.get("display_name", "") or "",
        "journal_id": (source.get("id", "") or "").rsplit("/", 1)[-1],
        "primary_topic": primary_topic.get("display_name", "") or "",
        "primary_topic_id": (primary_topic.get("id", "") or "").rsplit("/", 1)[-1],
        "concepts": [
            {"id": (c.get("id", "") or "").rsplit("/", 1)[-1],
             "name": c.get("display_name", "") or "",
             "level": c.get("level"),
             "score": c.get("score")}
            for c in (w.get("concepts") or [])[:10]
        ],
        "authors": [
            {"id": (au.get("author", {}).get("id", "") or "").rsplit("/", 1)[-1],
             "name": au.get("author", {}).get("display_name", "") or "",
             "position": au.get("author_position", "")}
            for au in (w.get("authorships") or [])
        ],
        "referenced_works": [
            (rid or "").rsplit("/", 1)[-1]
            for rid in (w.get("referenced_works") or [])
        ],
    }


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Output dir: {OUT_DIR}")
    print(f"Cache dir:  {CACHE_DIR}\n")

    summary = {}
    for trig in TRIGGER_AUTHORS:
        slug = trig["slug"]
        print(f"\n=== {slug} ({trig['search_name']}) ===")
        author = search_author(trig["search_name"], trig["affiliation_keywords"])
        if not author:
            print(f"  ! Keine Autor-Treffer gefunden, skip.")
            continue
        aid = author["id"].rsplit("/", 1)[-1]
        works = pull_all_works(author["id"])
        if not works:
            print(f"  ! Keine Works gezogen, skip.")
            continue
        slim_works = [slim_work(w) for w in works]
        # Diagnose
        n_refs_total = sum(len(w["referenced_works"]) for w in slim_works)
        journals = {w["journal"] for w in slim_works if w["journal"]}
        out_obj = {
            "trigger_author": {
                "slug": slug,
                "search_name": trig["search_name"],
                "openalex_id": aid,
                "display_name": author.get("display_name", ""),
                "last_known_institution": (author.get("last_known_institution") or {}).get("display_name", ""),
                "works_count_openalex": author.get("works_count", 0),
            },
            "works": slim_works,
        }
        out_file = OUT_DIR / f"{slug}.json"
        out_file.write_text(json.dumps(out_obj, ensure_ascii=False, indent=2), encoding="utf-8")
        summary[slug] = {
            "openalex_id": aid,
            "display_name": author.get("display_name", ""),
            "works_pulled": len(slim_works),
            "total_referenced_works": n_refs_total,
            "distinct_publication_journals": len(journals),
        }
        print(f"  → {len(slim_works)} Works mit {n_refs_total} Refs (zusammen) gespeichert in {out_file.name}")

    print("\n=== Summary ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    (OUT_DIR / "_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    sys.exit(main() or 0)
