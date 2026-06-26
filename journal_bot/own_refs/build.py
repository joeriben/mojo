"""Build-Orchestrator: Sources → Identity → Extract → Resolve → Classify → Store.

Verarbeitet alle konfigurierten Sources in einem Lauf:

    for source in sources:
        for item in source.discover():
            canonical_id = identity.canonical_id_for(...)
            if inkrement_skip(item, store): continue
            extract = extract_refs(item.pdf_path)
            store.upsert_publication(...)
            store.upsert_source_ref(...)
            store.replace_pub_refs(...)

Nach Source-Iteration: `merge_duplicates` versucht Folder-Source-Items, die
ohne DOI eingelaufen sind, mit Zotero-Source-Items via Titel-Hash zu mergen
— wenn ein Title-Hash-Item heute schon mit einer DOI-canonical_id existiert,
werden die source_refs umgehängt und das Hash-Item gelöscht.

Plus zwei Public-Functions für die CLI:
- `build_report(store)` für `mojo refs report`
- `validate_pdf(path)` für `mojo refs validate <pdf>`

Keine LLM-Calls.
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

from journal_bot.own_refs.discourse import classify
from journal_bot.own_refs.extract import extract_refs, ExtractionResult
from journal_bot.own_refs.identity import (
    canonical_id_for,
    normalize_doi,
    normalize_text,
    first_author_lastname,
)
from journal_bot.own_refs.resolve import resolve_dois
from journal_bot.own_refs.text_resolve import resolve_text_refs
from journal_bot.own_refs.sources.base import DiscoveredItem, Source
from journal_bot.own_refs.store import (
    OwnRefsStore,
    Publication,
    PubRef,
    SourceRef,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "own_refs.db"


# ----- Result Dataclasses ----------------------------------------------------


@dataclass
class BuildStats:
    sources_processed: int = 0
    items_discovered: int = 0
    items_new: int = 0
    items_updated: int = 0
    items_skipped_unchanged: int = 0
    items_skipped_empty: int = 0
    items_without_pdf: int = 0
    pdfs_extracted: int = 0
    pdfs_failed: int = 0
    refs_total: int = 0
    dois_total: int = 0
    dois_resolved: int = 0
    text_refs_total: int = 0
    text_refs_resolved: int = 0
    dupes_merged: int = 0
    sources_with_errors: list[str] = field(default_factory=list)


# ----- Helpers ---------------------------------------------------------------


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _title_hash_id(title: str, year: int | None, authors: list[str]) -> str:
    """canonical_id, wenn man so tut, als hätte das Item keinen DOI."""
    return canonical_id_for(None, title, year, authors)


def _should_extract(item: DiscoveredItem, store: OwnRefsStore) -> bool:
    """True, wenn PDF (re-)extrahiert werden muss."""
    if not item.pdf_path:
        return False
    prev_mtime = store.pdf_mtime_for_source_item(
        item.source_type, item.source_key, item.source_item_id
    )
    if prev_mtime is None:
        return True                         # neu
    if item.pdf_mtime is None:
        return True                         # unklar → lieber re-extrahieren
    return item.pdf_mtime > prev_mtime      # geändert


# ----- Build Orchestrator ----------------------------------------------------


def build(
    sources: Sequence[Source],
    db_path: Path = DEFAULT_DB_PATH,
    force_refresh: bool = False,
    resolve_openalex: bool = True,
    resolve_text: bool = True,
    text_resolve_max_calls: int | None = None,
    verbose: bool = True,
) -> BuildStats:
    """Hauptbau: alle Sources durchlaufen, additiv in `own_refs.db` schreiben.

    `force_refresh=True` ignoriert pdf_mtime-Caches und re-extrahiert alles.
    `resolve_openalex=False` überspringt den OpenAlex-DOI-Resolver-Schritt
    (z. B. offline; DOIs landen dann als `doi_unresolved` im Store).
    `resolve_text=False` überspringt zusätzlich den Free-Text-Resolver
    (§2.4 — Author+Year+Title-Match gegen OpenAlex-Search). Cache ist
    persistent (`.own_refs_cache/text_oa/`), zweiter Lauf ist ein Cache-Walk.
    `text_resolve_max_calls=N` cappt die Anzahl der LIVE-Calls (Cache-Hits
    zählen nicht). Sinnvoll für Smoke-Tests.
    """
    if not sources:
        raise ValueError(
            "Keine Quellen konfiguriert. Beispiel:\n"
            "  mojo refs sources add zotero <COLLECTION_KEY>\n"
            "  mojo refs sources add folder /pfad/zu/PDFs"
        )

    stats = BuildStats()
    # Sammle (canonical_id, list[normalized_doi]) für späteren Resolve-Batch.
    pending_dois: dict[str, set[str]] = defaultdict(set)
    pending_text_refs: dict[str, list[str]] = defaultdict(list)

    with OwnRefsStore(db_path) as store:
        for source in sources:
            stats.sources_processed += 1
            if verbose:
                print(f"[build] Source: {source.source_type}:{source.source_key}")
            try:
                items = list(source.discover())
            except Exception as e:
                msg = f"{source.source_type}:{source.source_key} discover-failed: {e}"
                stats.sources_with_errors.append(msg)
                if verbose:
                    print(f"  [warn] {msg}")
                continue

            for item in items:
                stats.items_discovered += 1
                _ingest_item(item, store, stats, pending_dois, pending_text_refs,
                             force_refresh=force_refresh, verbose=verbose)

        # Nach Source-Iteration: Dupes über Titel-Hash mit jetzt-bekanntem-DOI mergen.
        merged = _merge_duplicates(store, verbose=verbose)
        stats.dupes_merged = merged

        # Phase 1: DOI-basiertes Resolve.
        if resolve_openalex and pending_dois:
            all_dois = sorted({d for ds in pending_dois.values() for d in ds})
            stats.dois_total = len(all_dois)
            if verbose:
                print(f"[build] Resolve {len(all_dois)} unique DOIs against OpenAlex …")
            resolved = resolve_dois(all_dois, verbose=verbose)
            stats.dois_resolved = sum(1 for r in resolved.values() if r.oa_id)
        else:
            resolved = {}
            if pending_dois:
                stats.dois_total = sum(len(ds) for ds in pending_dois.values())

        # Phase 2a: Free-Text-Resolve für FRISCH extrahierte Refs (aus
        # diesem Lauf). Wird in _persist_refs verwendet, damit text_resolved-
        # State direkt korrekt gesetzt wird statt erst text_unresolved → später.
        text_resolved: dict[str, object] = {}
        if resolve_text and pending_text_refs:
            import hashlib as _h
            text_pairs: list[tuple[str, str]] = []
            for canonical_id, cites in pending_text_refs.items():
                for cite in cites:
                    short_hash = _h.sha1(cite.encode("utf-8")).hexdigest()[:12]
                    ref_id = f"txt:{short_hash}"
                    text_pairs.append((ref_id, cite))
            if verbose:
                print(
                    f"[build] Text-Resolve {len(text_pairs)} freie Refs aus "
                    f"diesem Lauf gegen OpenAlex-Search …"
                )
            text_resolved = resolve_text_refs(
                text_pairs, verbose=verbose,
                max_calls=text_resolve_max_calls,
            )

        # Persistierung: in einem Rutsch DOI- und Text-Resolution einlesen.
        _persist_refs(
            store, pending_dois, pending_text_refs,
            resolved=resolved, text_resolved=text_resolved, stats=stats,
        )

        # Phase 2b: Catch-up — alle text_unresolved Refs, die nicht aus
        # diesem Lauf stammen (also Legacy aus früheren Builds), nachträglich
        # gegen die Search-API auflösen. Inkrementell: bei einem zweiten Lauf
        # ohne fresh PDFs würde Phase 2a leer bleiben, aber 2b zieht alte
        # Lücken hoch. Cache macht Re-Runs kostenfrei.
        if resolve_text:
            n_total, n_resolved = _catch_up_text_unresolved(
                store, max_calls=text_resolve_max_calls,
                already_processed_ref_ids=set(text_resolved.keys()),
                verbose=verbose,
            )
            stats.text_refs_total += n_total
            stats.text_refs_resolved += n_resolved

        # Phase 2a-Statistik in stats schreiben (für direkt aufgelöste Refs)
        stats.text_refs_total += len(text_resolved)
        stats.text_refs_resolved += sum(
            1 for r in text_resolved.values() if getattr(r, "oa_id", None)
        )

    return stats


def _catch_up_text_unresolved(
    store: OwnRefsStore,
    max_calls: int | None,
    already_processed_ref_ids: set[str],
    verbose: bool,
) -> tuple[int, int]:
    """Resolve existierende text_unresolved-Refs in der DB.

    Notwendig, weil `build()` nur frische Extraktionen ins `pending_text_refs`
    aufnimmt. Legacy-Refs aus früheren Läufen müssen separat angefasst werden,
    sonst bleiben sie ewig text_unresolved.

    Direkter UPDATE in pub_refs (statt replace_pub_refs), weil wir hier nur
    den Resolution-State einer einzelnen Reihe ändern — keinen Refresh der
    ganzen Pub.
    """
    con = store.con
    rows = con.execute(
        """
        SELECT canonical_id, ref_id, ref_text
          FROM pub_refs
         WHERE resolution_state = 'text_unresolved'
           AND ref_text IS NOT NULL
        """
    ).fetchall()
    if not rows:
        return (0, 0)

    pairs: list[tuple[str, str]] = []
    for r in rows:
        if r["ref_id"] in already_processed_ref_ids:
            continue
        pairs.append((r["ref_id"], r["ref_text"]))

    if verbose:
        print(
            f"[build] Catch-up: {len(pairs)} Legacy-text_unresolved-Refs "
            f"gegen OpenAlex-Search …"
        )
    if not pairs:
        return (0, 0)

    text_resolved = resolve_text_refs(
        pairs, verbose=verbose, max_calls=max_calls,
    )

    # UPDATE-Pass: nur die positiv aufgelösten Refs werden umgeschrieben.
    n_updated = 0
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    for ref_id, res in text_resolved.items():
        if not getattr(res, "oa_id", None):
            continue
        con.execute(
            """
            UPDATE pub_refs
               SET ref_oa_id = ?,
                   ref_doi   = COALESCE(?, ref_doi),
                   ref_year  = COALESCE(?, ref_year),
                   resolution_state = 'text_resolved',
                   resolved_at = ?
             WHERE ref_id = ?
            """,
            (res.oa_id, getattr(res, "matched_doi", None),
             getattr(res, "matched_year", None), now, ref_id),
        )
        n_updated += 1
    con.commit()
    return (len(pairs), n_updated)


def _ingest_item(
    item: DiscoveredItem,
    store: OwnRefsStore,
    stats: BuildStats,
    pending_dois: dict[str, set[str]],
    pending_text_refs: dict[str, list[str]],
    force_refresh: bool,
    verbose: bool,
) -> None:
    canonical = canonical_id_for(item.doi, item.title, item.year, item.authors)
    existing = store.get_publication(canonical)

    # Empty-stub guard: a source item with no title AND no PDF carries zero
    # grounding signal — it cannot be classified, embedded, or ref-extracted.
    # Such items appear when a bare DOI is dropped into the watched Zotero
    # collection without metadata retrieval (observed: 5 untitled AI&Society
    # DOI stubs in QM7TZT44). Faithfully ingesting them contaminates the
    # corpus and every coverage metric. Skip them, and self-heal any stub that
    # a prior build already wrote (the build is otherwise additive/idempotent).
    if not (item.title or "").strip() and not item.pdf_path:
        stats.items_skipped_empty += 1
        if existing is not None and store.delete_publication(canonical):
            if verbose:
                print(f"  [skip-empty] entfernt veralteten Leer-Stub: {canonical}")
        elif verbose:
            print(f"  [skip-empty] übersprungen (kein Titel, kein PDF): {canonical}")
        return

    extract_needed = force_refresh or _should_extract(item, store)

    pub_kwargs: dict = {}
    extraction: ExtractionResult | None = None
    notes = list(item.notes)
    if not item.pdf_path:
        stats.items_without_pdf += 1
        notes.append("no_pdf")
    elif extract_needed:
        extraction = extract_refs(Path(item.pdf_path))
        if extraction.status == "ok":
            stats.pdfs_extracted += 1
        else:
            stats.pdfs_failed += 1
            notes.append(f"extract:{extraction.status}")

    if extraction and extraction.status == "ok":
        pub_kwargs.update(
            fulltext_path=extraction.txt_path,
            fulltext_chars=extraction.fulltext_chars,
            fulltext_extracted_at=_now(),
            refs_extracted_at=_now(),
            refs_header_label=extraction.refs_header_label,
            refs_used_fallback=extraction.used_fallback_section,
        )

    discourse = classify(item.title, item.venue) or None
    pub = Publication(
        canonical_id=canonical,
        title=item.title,
        authors=item.authors,
        doi=normalize_doi(item.doi) or None,
        year=item.year,
        item_type=item.item_type,
        venue=item.venue,
        discourse=discourse,
        notes=notes,
        **pub_kwargs,
    )
    store.upsert_publication(pub)

    if existing is None:
        stats.items_new += 1
    elif extract_needed:
        stats.items_updated += 1
    else:
        stats.items_skipped_unchanged += 1

    store.upsert_source_ref(SourceRef(
        canonical_id=canonical,
        source_type=item.source_type,
        source_key=item.source_key,
        source_item_id=item.source_item_id,
        pdf_path=item.pdf_path,
        pdf_mtime=item.pdf_mtime,
        zotero_date_modified=item.zotero_date_modified,
        match_score=item.match_score,
    ))

    if extraction and extraction.status == "ok":
        for d in extraction.dois_in_refs:
            pending_dois[canonical].add(normalize_doi(d))
        # raw citations als unaufgelöste text refs ablegen
        for cite in extraction.raw_citations:
            # nur Citations, die keinen erkennbaren DOI haben (sonst Duplikat)
            from journal_bot.own_refs.extract import DOI_RE
            if DOI_RE.search(cite):
                continue
            pending_text_refs[canonical].append(cite)

    if verbose:
        marker = "new" if existing is None else ("upd" if extract_needed else "skip")
        print(
            f"  [{marker}] {item.source_type}:{item.source_item_id[:30]:<30} "
            f"{canonical[:24]:<24}  {item.title[:55]!r:<55}"
        )


def _persist_refs(
    store: OwnRefsStore,
    pending_dois: dict[str, set[str]],
    pending_text_refs: dict[str, list[str]],
    resolved,
    text_resolved,
    stats: BuildStats,
) -> None:
    """Schreibt pub_refs für jede Pub: aufgelöste DOIs → free-text refs.

    Vier mögliche Resolution-States pro Ref:
      - `doi_resolved`   — DOI vorhanden + OA-Treffer
      - `doi_unresolved` — DOI vorhanden, OA-Search ohne Treffer
      - `text_resolved`  — kein DOI, aber Author+Year+Title gegen OA gematcht
      - `text_unresolved` — kein DOI, Search erfolglos / Ref unparseable

    Robust gegen vereinzelte schlecht-strukturierte Pubs: schlägt
    `replace_pub_refs` für eine canonical_id fehl (z. B. weil die Pub durch
    `merge_duplicates` orphan wurde), wird sie geloggt und übersprungen — die
    übrigen Pubs werden weiter persistiert.
    """
    import hashlib
    import sqlite3

    all_canonical_ids = set(pending_dois.keys()) | set(pending_text_refs.keys())
    for canonical_id in sorted(all_canonical_ids):
        refs: list[PubRef] = []
        for d in sorted(pending_dois.get(canonical_id, set())):
            res = resolved.get(d) if resolved else None
            if res and res.oa_id:
                refs.append(PubRef(
                    canonical_id=canonical_id,
                    ref_id=f"doi:{d}",
                    ref_doi=d, ref_oa_id=res.oa_id, ref_year=res.year,
                    resolution_state="doi_resolved",
                ))
            else:
                refs.append(PubRef(
                    canonical_id=canonical_id, ref_id=f"doi:{d}",
                    ref_doi=d, resolution_state="doi_unresolved",
                ))
        for cite in pending_text_refs.get(canonical_id, []):
            short_hash = hashlib.sha1(cite.encode("utf-8")).hexdigest()[:12]
            ref_id = f"txt:{short_hash}"
            tres = text_resolved.get(ref_id) if text_resolved else None
            if tres is not None and getattr(tres, "oa_id", None):
                refs.append(PubRef(
                    canonical_id=canonical_id,
                    ref_id=ref_id,
                    ref_text=cite,
                    ref_doi=getattr(tres, "matched_doi", None),
                    ref_oa_id=tres.oa_id,
                    ref_year=getattr(tres, "matched_year", None),
                    resolution_state="text_resolved",
                ))
            else:
                refs.append(PubRef(
                    canonical_id=canonical_id,
                    ref_id=ref_id,
                    ref_text=cite,
                    resolution_state="text_unresolved",
                ))
        try:
            store.replace_pub_refs(canonical_id, refs)
            stats.refs_total += len(refs)
        except sqlite3.IntegrityError as e:
            stats.sources_with_errors.append(
                f"persist_refs canonical_id={canonical_id}: {e}"
            )


# ----- Duplicate-Merging -----------------------------------------------------


def _merge_duplicates(store: OwnRefsStore, verbose: bool = False) -> int:
    """Mergt Title-Hash-Items mit jetzt-bekannten-DOI-Items.

    Szenario: dasselbe Item lief erst aus dem FAUbox-Folder (ohne DOI →
    canonical_id = "hash:abc") und später aus Zotero (mit DOI →
    canonical_id = "doi:10.x/..."). Wir verschieben alle source_refs +
    pub_refs vom Hash-Item zum DOI-Item und löschen das Hash-Item.

    Match-Bedingung: gleicher normalized title + gleiches year +
    gleicher first_author_lastname.
    """
    con = store.con
    # Alle hash:-Items
    hash_rows = con.execute(
        "SELECT canonical_id, title, year, authors_json FROM publications "
        "WHERE canonical_id LIKE 'hash:%'"
    ).fetchall()
    merged = 0
    for row in hash_rows:
        hash_id = row["canonical_id"]
        title = row["title"]
        year = row["year"]
        authors = json.loads(row["authors_json"]) if row["authors_json"] else []
        # find DOI-item mit gleichem title-hash
        cands = con.execute(
            """
            SELECT canonical_id, title, year, authors_json FROM publications
            WHERE canonical_id LIKE 'doi:%'
            """
        ).fetchall()
        for cand in cands:
            cand_title = cand["title"]
            cand_year = cand["year"]
            cand_authors = (
                json.loads(cand["authors_json"]) if cand["authors_json"] else []
            )
            cand_first = normalize_text(first_author_lastname(cand_authors))
            hash_first = normalize_text(first_author_lastname(authors))
            # Leerer first-author auf EINER Seite ist erlaubt (FolderSource hat
            # keine Autoren), solange Title+Year identisch sind.
            authors_compatible = (
                cand_first == hash_first
                or not cand_first
                or not hash_first
            )
            if (
                normalize_text(cand_title) == normalize_text(title)
                and (cand_year == year or year is None or cand_year is None)
                and authors_compatible
            ):
                # Merge: source_refs umhängen + Hash-Item löschen.
                # pub_refs vom Hash-Item lassen wir fallen (das DOI-Item hat
                # bereits ein eigenes refs-Set, die Folder-Variante hatte
                # u. U. weniger DOIs).
                doi_id = cand["canonical_id"]
                con.execute(
                    "UPDATE source_refs SET canonical_id = ? WHERE canonical_id = ?",
                    (doi_id, hash_id),
                )
                con.execute("DELETE FROM pub_refs WHERE canonical_id = ?", (hash_id,))
                con.execute(
                    "DELETE FROM publications WHERE canonical_id = ?", (hash_id,)
                )
                merged += 1
                if verbose:
                    print(f"  [merge] {hash_id} → {doi_id} ({title[:50]!r})")
                break
    if merged:
        con.commit()
    return merged


# ----- Reporting & Validation ------------------------------------------------


def build_report(db_path: Path = DEFAULT_DB_PATH) -> dict:
    """Coverage pro Source × Jahr-Bucket (für `mojo refs report`)."""
    with OwnRefsStore(db_path) as store:
        con = store.con
        rows = con.execute(
            """
            SELECT sr.source_type, sr.source_key,
                   CASE
                       WHEN p.year IS NULL THEN 'unknown'
                       WHEN p.year < 2010 THEN '<2010'
                       WHEN p.year < 2015 THEN '2010-14'
                       WHEN p.year < 2020 THEN '2015-19'
                       ELSE '2020+'
                   END AS year_bucket,
                   COUNT(DISTINCT p.canonical_id) AS n_items,
                   SUM(CASE WHEN p.fulltext_chars > 0 THEN 1 ELSE 0 END) AS n_with_fulltext,
                   SUM(CASE WHEN p.doi IS NOT NULL THEN 1 ELSE 0 END) AS n_with_doi
            FROM publications p
            JOIN source_refs sr ON sr.canonical_id = p.canonical_id
            GROUP BY sr.source_type, sr.source_key, year_bucket
            ORDER BY sr.source_type, sr.source_key, year_bucket
            """
        ).fetchall()
    return {
        "buckets": [
            {
                "source_type": r["source_type"],
                "source_key": r["source_key"],
                "year_bucket": r["year_bucket"],
                "n_items": r["n_items"],
                "n_with_fulltext": r["n_with_fulltext"],
                "n_with_doi": r["n_with_doi"],
            }
            for r in rows
        ]
    }


def validate_pdf(pdf_path: Path) -> dict:
    """CLI-Smoke: gib zu einem konkreten PDF die Extraktions-Vorschau zurück.

    Wird von `mojo refs validate <pdf>` aufgerufen. Liefert eine kompakte
    Diagnose: Header gefunden? Wie viele DOIs? Welche Citations?
    """
    res = extract_refs(pdf_path)
    return {
        "pdf_path": str(pdf_path),
        "status": res.status,
        "fulltext_chars": res.fulltext_chars,
        "refs_header_label": res.refs_header_label,
        "refs_header_line": res.refs_header_line,
        "used_fallback_section": res.used_fallback_section,
        "n_dois": len(res.dois_in_refs),
        "n_raw_citations": len(res.raw_citations),
        "first_dois": res.dois_in_refs[:5],
        "first_citations": [c[:120] for c in res.raw_citations[:3]],
        "notes": res.notes,
    }


# ----- Sources from profile.json --------------------------------------------


def load_sources_from_profile(
    profile: dict, zotero_storage: Path
) -> list[Source]:
    """Resolve `refs_sources`-Block aus profile.json zu konkreten Source-Objekten.

    Liefert leere Liste, wenn der Block fehlt — der Build-Orchestrator wirft
    dann eine sprechende Exception (Akzeptanzkriterium: Default-Lauf
    abbrechen).
    """
    from journal_bot.own_refs.sources import FolderSource, ZoteroSource

    out: list[Source] = []
    for entry in profile.get("refs_sources", []) or []:
        t = entry.get("type")
        if t == "zotero":
            out.append(ZoteroSource(
                collection_key=entry["key"],
                zotero_storage=zotero_storage,
            ))
        elif t == "folder":
            out.append(FolderSource(folder_path=Path(entry["path"])))
        else:
            raise ValueError(f"Unbekannter source-type: {t!r} (entry: {entry})")
    return out
