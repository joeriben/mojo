"""mojo CLI.

Subcommands:
  ingest     — Zotero-Collection (ZOTERO_COLLECTION) nach corpus.json
               (einmalig oder bei Änderung, keine LLM-Kosten)
  summarize  — Corpus mit dem konfigurierten Modell zu Kurzprofilen (summaries.json)
               (einmalig, ~3€)
  backup     — ZIP-Backup des lokalen Nutzerzustands
               (DB + Profil + Projekte + Corpus + Summaries + Konfiguration)
  restore    — Restore eines Nutzer-Backups in ein frisches Checkout
  export-raw — Rohdatenpaket fuer andere Installationen (ohne Bewertungen)
  import-raw — Rohdatenpaket importieren, ohne erneut zu fetchen
  fetch      — Feeds → OpenAlex/Crossref-Enrichment → articles.db
               (wöchentlich, keine LLM-Kosten)
  backfill   — Fehlende Abstracts aus Crossref-Cache/Playwright/Zotero nachziehen
               (einmalig oder nach fetch, keine LLM-Kosten)
  digest     — Agent-Lauf über Store-Einträge oder ad-hoc via --doi
               (Kosten ~$0.50–$1 pro Artikel dank Caching)
  trends     — Aggregat-Trendanalyse aus articles.db nach Obsidian
               (gelegentlich, ~$1–3 pro Run je nach Fenster)
  journal-topics
             — OpenAlex-Journalprofile refreshen/ranken (keine LLM-Kosten)
  stats      — Kurze Statistik über articles.db
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from journal_bot import abstract_backfill, corpus, digest, fetch, summarize
from journal_bot.batch_digest import run_batch_digest
from journal_bot.settings import (
    CORPUS_JSON,
    PROJECT_ROOT,
    SINCE_YEAR,
    SUMMARIES_JSON,
    ZOTERO_COLLECTION,
    ZOTERO_STORAGE,
    _load_profile,
    save_profile,
)
from journal_bot.store import Store


# --------------------------------------------------------------- Commands ---


def cmd_ingest(args: argparse.Namespace) -> int:
    corpus.ingest(
        collection_name=args.collection,
        since_year=args.since,
        output=Path(args.output),
    )
    return 0


def cmd_summarize(args: argparse.Namespace) -> int:
    summarize.run(
        corpus_path=Path(args.corpus),
        output_path=Path(args.output),
        limit=args.limit,
    )
    return 0


def cmd_fetch(args: argparse.Namespace) -> int:
    fetch.run(verbose=not args.quiet, since_year=args.since)
    return 0


def cmd_backup(args: argparse.Namespace) -> int:
    from journal_bot.backup import create_backup_archive

    output = Path(args.output) if args.output else None
    result = create_backup_archive(
        output_path=output,
        include_digests=not args.no_digests,
    )

    print(f"[backup] Geschrieben: {result.archive_path}")
    print(f"[backup] Enthalten: {len(result.included)} Dateien")
    if result.skipped:
        print("[backup] Hinweise:")
        for item in result.skipped:
            print(f"  - {item}")
    print("[backup] API-Keys und Zotero-Storage sind absichtlich nicht enthalten.")
    return 0


def cmd_restore(args: argparse.Namespace) -> int:
    from journal_bot.backup import restore_backup_archive

    result = restore_backup_archive(
        Path(args.archive),
        restore_digests=not args.no_digests,
        digest_dir_override=Path(args.digest_dir) if args.digest_dir else None,
        zotero_storage_override=Path(args.zotero_storage) if args.zotero_storage else None,
        dry_run=args.dry_run,
    )

    prefix = "[restore:dry-run]" if args.dry_run else "[restore]"
    print(f"{prefix} Archiv: {result.archive_path}")
    print(f"{prefix} Ziele: {len(result.restored)}")
    if result.profile_updates:
        print(f"{prefix} Profil-Anpassungen:")
        for key, value in result.profile_updates.items():
            print(f"  - {key}: {value}")
    if result.warnings:
        print(f"{prefix} Hinweise:")
        for item in result.warnings:
            print(f"  - {item}")
    if result.skipped:
        print(f"{prefix} Ausgelassen:")
        for item in result.skipped:
            print(f"  - {item}")
    if args.dry_run:
        print(f"{prefix} Es wurden keine Dateien geschrieben.")
    else:
        print(f"{prefix} Restore abgeschlossen.")
    return 0


def cmd_export_raw(args: argparse.Namespace) -> int:
    from journal_bot.article_exchange import default_raw_export_path, export_raw_articles

    store = Store()
    journals = args.journals.split(",") if args.journals else None
    output = Path(args.output) if args.output else default_raw_export_path(PROJECT_ROOT / "exports")
    result = export_raw_articles(
        store,
        output_path=output,
        journals=journals,
        since_year=args.since,
    )
    print(f"[export-raw] Geschrieben: {result.archive_path}")
    print(f"[export-raw] Artikel: {result.article_count}")
    print("[export-raw] Enthalten: Artikel, Abstracts, DOI/URLs und Enrichment; keine Bewertungen oder Memos.")
    return 0


def cmd_import_raw(args: argparse.Namespace) -> int:
    from journal_bot.article_exchange import import_raw_articles

    store = Store()
    result = import_raw_articles(store, Path(args.archive))
    print(f"[import-raw] Archiv: {result.archive_path}")
    print(f"[import-raw] Importiert: {result.imported}")
    print(f"[import-raw] Neu: {result.created}")
    print(f"[import-raw] Aktualisiert: {result.updated}")
    if result.skipped:
        print(f"[import-raw] Uebersprungen: {result.skipped}")
    if result.warnings:
        print("[import-raw] Hinweise:")
        for item in result.warnings:
            print(f"  - {item}")
    print("[import-raw] Agent- und User-Auswertungen bleiben unberuehrt.")
    return 0


def cmd_digest(args: argparse.Namespace) -> int:
    from journal_bot.settings import MODEL_AGENT
    store = Store()
    model = getattr(args, "model", None) or MODEL_AGENT
    cost_limit = getattr(args, "cost_limit", None)

    if args.doi:
        result = digest.process_by_doi(
            args.doi,
            store,
            journal=args.journal,
            verbose=not args.quiet,
        )
        print(f"\n[digest] Geschrieben: {result['markdown_path']}")
        return 0

    # Batch-Modus: N ungeprozessierte Artikel aus dem Store
    journals_filter = args.journals.split(",") if args.journals else None
    since_year = args.since if hasattr(args, "since") else None
    pending = store.find_unprocessed(
        limit=args.next, journals=journals_filter, since_year=since_year,
    )
    if not pending:
        print("[digest] Keine ungeprozessierten Artikel im Store. "
              "Tipp: mojo fetch laufen lassen.")
        return 0

    batch_result = run_batch_digest(
        pending,
        store,
        model=model,
        no_screen=args.no_screen,
        verbose=not args.quiet,
        cost_limit_usd=cost_limit,
    )

    # 7-Tage-Cross-Wave-Cache-Report nach jedem Lauf — Welle-Tabelle zeigt
    # nur diese Welle, hier ist der Trend über alle Wellen der letzten Woche.
    # Erlaubt zu sehen, ob ein einzelner Cache-Einbruch isoliert war oder
    # ob sich was systematisch verschlechtert. Reine SQL-Aggregation, kostet
    # nichts. Aus mit --no-weekly-summary. Schwelle min_calls=5 schützt vor
    # Cold-Start-False-Positives über mehrere Wellen.
    if not args.quiet and not getattr(args, "no_weekly_summary", False):
        from datetime import datetime, timedelta, timezone
        from journal_bot.llm_log import cache_hit_stats, format_cache_report
        since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        weekly = cache_hit_stats(since=since)
        if weekly:
            print("\n" + format_cache_report(
                weekly,
                title="7-Tage · Cache-Hit-Rate (alle Wellen)",
                min_calls_for_flag=5,
            ))

    return 1 if batch_result.aborted else 0


def cmd_trends(args: argparse.Namespace) -> int:
    from journal_bot import trends
    from journal_bot.settings import available_clusters, journals_in_cluster

    if args.list_clusters:
        print("Verfügbare Diskursräume:\n")
        for key, meta, count in available_clusters():
            print(f"  {key:20s}  {count:>2} Journals   {meta['name']}")
            print(f"  {'':20s}  {meta['description']}")
            js = ", ".join(j.short for j in journals_in_cluster(key))
            print(f"  {'':20s}  → {js}")
            print()
        return 0

    if not args.cluster and not args.journals:
        print("Fehler: --cluster NAME oder --journals J1,J2 angeben.")
        print("        --list-clusters zeigt verfügbare Diskursräume.")
        return 2

    trends.run(
        cluster=args.cluster or "",
        window_years=args.window_years,
        journals=args.journals.split(",") if args.journals else None,
        verbose=not args.quiet,
    )
    return 0


def _parse_year_window(spec: str) -> tuple[int, int]:
    """'2016-2019' → (2016, 2019)."""
    try:
        a, b = spec.split("-", 1)
        return int(a), int(b)
    except (ValueError, AttributeError):
        raise SystemExit(f"Ungültiges Jahr-Fenster '{spec}', erwartet JJJJ-JJJJ.")


def cmd_explore(args: argparse.Namespace) -> int:
    from journal_bot import corpus_explore

    if args.action == "trends":
        corpus_explore.run(
            early=_parse_year_window(args.early),
            late=_parse_year_window(args.late),
            score_min=args.score_min,
            min_journal=args.min_journal,
            top_n=args.top_n,
            out=Path(args.out) if args.out else None,
            verbose=not args.quiet,
        )
        return 0
    if args.action == "coupling":
        corpus_explore.coupling.run(
            start_year=args.start_year,
            end_year=args.end_year,
            max_df=args.max_df,
            min_shared=args.min_shared,
            resolution=args.resolution,
            min_community=args.min_community,
            resolve_titles=not args.no_titles,
            out=Path(args.out) if args.out else None,
            verbose=not args.quiet,
        )
        return 0
    print(f"Unbekannte Aktion: {args.action}")
    return 2


def cmd_biblio(args: argparse.Namespace) -> int:
    from journal_bot import biblio
    biblio.run(
        cluster=args.cluster,
        window_years=args.window_years,
        top_pct=args.top_pct,
        min_count=args.min_count,
        verbose=not args.quiet,
    )
    return 0


def cmd_scout(args: argparse.Namespace) -> int:
    from journal_bot import scout
    scout.run(
        watchlist=Path(args.watchlist),
        window_years=args.window_years,
        limit=args.limit,
        verbose=not args.quiet,
    )
    return 0


def cmd_coverage(args: argparse.Namespace) -> int:
    from journal_bot import journal_coverage
    journal_coverage.run(
        cluster=args.cluster,
        window_years=args.window_years,
        min_citations=args.min_citations,
        verbose=not args.quiet,
    )
    return 0


def cmd_diskurs(args: argparse.Namespace) -> int:
    from journal_bot import diskurs
    from journal_bot.settings import available_clusters, journals_in_cluster

    action = args.action

    if action == "list":
        store = Store()
        stats = store.stats()
        journal_article_counts = stats.get("by_journal", {})
        print("Diskursräume:\n")
        for key, meta, count in available_clusters():
            js = journals_in_cluster(key)
            art_count = sum(journal_article_counts.get(j.short, 0) for j in js)
            print(f"  {key}")
            print(f"    {meta['name']}  ({count} Journals, {art_count} Artikel)")
            print(f"    {meta['description']}")
            shorts = ", ".join(j.short for j in js)
            print(f"    → {shorts}")
            print()
        return 0

    if action == "add":
        diskurs.add_space(args.key, args.name, args.desc)
        print(f"[diskurs] Diskursraum '{args.key}' angelegt.")
        return 0

    if action == "rename":
        updated = diskurs.rename_space(args.old, args.new)
        print(f"[diskurs] '{args.old}' → '{args.new}' ({updated} Journal-Zuordnungen aktualisiert).")
        return 0

    if action == "remove":
        affected = diskurs.remove_space(args.key)
        if affected:
            print(f"[diskurs] '{args.key}' entfernt. Betroffene Journals: {', '.join(affected)}")
        else:
            print(f"[diskurs] '{args.key}' entfernt (keine Journals betroffen).")
        return 0

    if action == "profile":
        profile = diskurs.build_profile(args.key, window_years=args.window_years)
        md = diskurs.render_profile(profile)
        print(md)
        return 0

    if action == "suggest":
        md = diskurs.suggest_new_spaces(
            window_years=args.window_years,
            verbose=not args.quiet,
        )
        print(md)
        return 0

    if action == "crosscut":
        results = diskurs.find_cross_cutting_concepts(
            window_years=args.window_years,
        )
        if not results:
            print("Keine querschneidenden Konzepte gefunden.")
            return 0
        print(f"Querschnitt-Konzepte (in ≥3 Diskursräumen):\n")
        for cc in results[:25]:
            clusters = ", ".join(f"{c['key']}({c['score']})" for c in cc["clusters"])
            print(f"  {cc['concept']:40s}  Σ{cc['total_score']:>6.1f}  "
                  f"[{cc['cluster_count']} Räume]  {clusters}")
        return 0

    if action == "assign":
        diskurs.assign_journal(args.journal, args.clusters)
        print(f"[diskurs] {args.journal} → {', '.join(args.clusters)}")
        return 0

    if action == "unassign":
        diskurs.unassign_journal(args.journal, args.cluster)
        print(f"[diskurs] {args.journal} aus '{args.cluster}' entfernt.")
        return 0

    print(f"Unbekannte Aktion: {action}")
    return 2


def cmd_journal(args: argparse.Namespace) -> int:
    from journal_bot import journals

    action = args.action

    if action == "list":
        jlist = journals.list_journals()
        for j in jlist:
            status = "✓" if j.get("enabled", True) else "✗"
            clusters = ", ".join(j.get("clusters", [])) or "(keine)"
            issn = j["url"].replace("issn:", "") if j["url"].startswith("issn:") else j["url"]
            print(f"  {status} {j['short']:12s} {j['name']}")
            print(f"    {j['type']:8s} {issn}  → {clusters}")
        print(f"\n{len(jlist)} Journals registriert.")
        return 0

    elif action == "add":
        result = journals.add_journal(
            name=args.name,
            short=args.short,
            issn=args.issn,
            clusters=args.clusters or [],
            journal_type=args.type,
        )
        print(result)
        return 0

    elif action == "remove":
        result = journals.remove_journal(args.short)
        print(result)
        return 0

    print(f"Unbekannte Aktion: {action}")
    return 2


def cmd_journal_topics(args: argparse.Namespace) -> int:
    from journal_bot.journal_topics import (
        journal_profile_status,
        refresh_journal_profiles,
        route_query_to_journal_profiles,
    )

    action = args.action

    if action == "status":
        status = journal_profile_status()
        print(f"[journal-topics] Datei: {status['path']}")
        if not status["exists"]:
            print("[journal-topics] Noch keine Profile persistiert.")
            return 0
        print(
            f"[journal-topics] Profile: {status['count']} "
            f"({status['found_count']} gefunden, {status['missing_count']} ohne OpenAlex-Profil)"
        )
        print(f"[journal-topics] Aktualisiert: {status['updated_at'] or 'unbekannt'}")
        return 0

    if action == "refresh":
        topic_limit = max(10, min(args.topic_limit, 200))
        refresh_journal_profiles(
            include_disabled=args.include_disabled,
            topic_limit=topic_limit,
        )
        status = journal_profile_status()
        print(
            f"[journal-topics] Aktualisiert: {status['found_count']} gefunden, "
            f"{status['missing_count']} ohne OpenAlex-Profil."
        )
        print(f"[journal-topics] Datei: {status['path']}")
        return 0

    if action == "rank":
        results = route_query_to_journal_profiles(args.query, limit=args.limit)
        if not results:
            print("[journal-topics] Keine Treffer. Erst `mojo journal-topics refresh` ausführen.")
            return 0
        for idx, item in enumerate(results, start=1):
            print(
                f"{idx:2d}. {item['routing']:7s} {item['score']:5.1f}  "
                f"{item['journal_name']} ({item['journal_short']}, Tier {item['journal_tier']})"
            )
            if item["matched_topics"]:
                topics = ", ".join(t["topic"] for t in item["matched_topics"][:3])
                print(f"    Topics: {topics}")
        return 0

    print(f"Unbekannte Aktion: {action}")
    return 2


def cmd_web(args: argparse.Namespace) -> int:
    from journal_bot.web.app import app
    print(f"[web] MOJO UI auf http://mojo.localhost:{args.port}")
    # debug=True würde Werkzeugs StatReloader anschalten, der jede Sekunde
    # den gesamten Projekt-Tree per os.walk durchläuft → 100 % CPU im
    # launchd-Dauerlauf. Nur explizit per --debug einschalten (manueller
    # Dev-Start), nicht in der KeepAlive-Service-Konfiguration.
    app.run(debug=args.debug, host="127.0.0.1", port=args.port)
    return 0


def cmd_backfill(args: argparse.Namespace) -> int:
    store = Store()
    abstract_backfill.run(
        store=store,
        limit=args.limit,
        journal=args.journal or None,
        dry_run=args.dry_run,
        verbose=not args.quiet,
        delay=args.delay,
    )
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    store = Store()
    s = store.stats()
    print(f"articles.db: {store.path}")
    print(f"  Total:        {s['total']}")
    print(f"  Agent-proc.:  {s['processed']}")
    print(f"  Kosten:       ${s['total_cost_usd']:.2f}")
    if s["by_journal"]:
        print("  Pro Journal:")
        for j, n in sorted(s["by_journal"].items()):
            print(f"    {j:15s} {n}")
    if s["by_verdict"]:
        print("  Pro Verdict:")
        for v, n in sorted(s["by_verdict"].items()):
            print(f"    {v:15s} {n}")
    return 0


def cmd_refs(args: argparse.Namespace) -> int:
    """`mojo refs ...` — Multi-Source-Refs-Pipeline (MOJO 2.0 §3.1)."""
    import json as _json
    from journal_bot.own_refs.build import (
        DEFAULT_DB_PATH, build, build_report, load_sources_from_profile,
        validate_pdf,
    )
    from journal_bot.own_refs.sources import FolderSource, ZoteroSource
    from journal_bot.own_refs.store import status_report

    action = getattr(args, "action", None)

    # ---- sources subcommands -------------------------------------------------
    if action == "sources":
        sub_action = getattr(args, "sub_action", None)
        profile = _load_profile()
        sources = list(profile.get("refs_sources") or [])
        if sub_action == "list":
            if not sources:
                print("(keine Refs-Quellen konfiguriert)")
                print("Hinzufügen: mojo refs sources add zotero <KEY>")
                print("            mojo refs sources add folder /pfad")
                return 0
            for s in sources:
                label = s.get("label") or ""
                if s.get("type") == "zotero":
                    print(f"  zotero:{s['key']:<12}  {label}")
                elif s.get("type") == "folder":
                    print(f"  folder:{s['path']}")
                else:
                    print(f"  ?:{s}")
            return 0
        if sub_action == "add":
            stype = args.source_type
            if stype == "zotero":
                entry = {"type": "zotero", "key": args.value}
                if args.label:
                    entry["label"] = args.label
            elif stype == "folder":
                p = Path(args.value).expanduser().resolve()
                if not p.exists() or not p.is_dir():
                    print(f"FEHLER: Folder existiert nicht oder ist kein Verzeichnis: {p}")
                    return 2
                entry = {"type": "folder", "path": str(p)}
            else:
                print(f"FEHLER: unbekannter source-type {stype!r}")
                return 2
            # idempotent: skip wenn schon drin
            for existing in sources:
                if existing.get("type") == entry["type"] and (
                    existing.get("key") == entry.get("key")
                    or existing.get("path") == entry.get("path")
                ):
                    print(f"(bereits konfiguriert: {entry})")
                    return 0
            sources.append(entry)
            profile["refs_sources"] = sources
            save_profile(profile)
            print(f"Quelle hinzugefügt: {entry}")
            return 0
        if sub_action == "remove":
            spec = args.spec
            # erlaubt: "zotero:KEY" oder "folder:/pfad"
            if ":" not in spec:
                print(f"FEHLER: Spec muss <type>:<key> sein, war: {spec!r}")
                return 2
            stype, val = spec.split(":", 1)
            before = len(sources)
            sources = [
                s for s in sources
                if not (
                    s.get("type") == stype
                    and (s.get("key") == val or s.get("path") == val)
                )
            ]
            if len(sources) == before:
                print(f"(keine passende Quelle gefunden für {spec!r})")
                return 1
            profile["refs_sources"] = sources
            save_profile(profile)
            print(f"Quelle entfernt: {spec}")
            return 0
        print("FEHLER: action 'sources' braucht subaction {list,add,remove}")
        return 2

    # ---- build ---------------------------------------------------------------
    if action == "build":
        profile = _load_profile()
        # CLI-übergebene --source-Flags haben Vorrang über profile.json
        explicit: list = []
        for spec in (args.source or []):
            if ":" not in spec:
                print(f"FEHLER: --source erwartet <type>:<value>, war: {spec!r}")
                return 2
            stype, val = spec.split(":", 1)
            if stype == "zotero":
                explicit.append(ZoteroSource(
                    collection_key=val, zotero_storage=ZOTERO_STORAGE,
                ))
            elif stype == "folder":
                explicit.append(FolderSource(folder_path=Path(val).expanduser().resolve()))
            else:
                print(f"FEHLER: unbekannter source-type {stype!r}")
                return 2
        if explicit:
            sources = explicit
        else:
            sources = load_sources_from_profile(profile, ZOTERO_STORAGE)
        if not sources:
            print(
                "FEHLER: Keine Quellen konfiguriert.\n"
                "  mojo refs sources add zotero <COLLECTION_KEY>   "
                "(Schlüssel der Zotero-Sammlung mit den eigenen Publikationen)\n"
                "  mojo refs sources add folder /pfad/zu/pdfs"
            )
            return 2
        stats = build(
            sources=sources,
            db_path=Path(args.db) if args.db else DEFAULT_DB_PATH,
            force_refresh=args.force_refresh,
            resolve_openalex=not args.no_resolve,
            resolve_text=not args.no_text_resolve,
            text_resolve_max_calls=args.text_resolve_max_calls,
            verbose=not args.quiet,
        )
        print()
        print("=== Build-Stats ===")
        print(f"  sources processed:  {stats.sources_processed}")
        print(f"  items discovered:   {stats.items_discovered}")
        print(f"    new:              {stats.items_new}")
        print(f"    updated:          {stats.items_updated}")
        print(f"    unchanged:        {stats.items_skipped_unchanged}")
        print(f"    empty-stub skip:  {stats.items_skipped_empty}")
        print(f"  PDFs extracted:     {stats.pdfs_extracted}")
        print(f"  PDFs failed:        {stats.pdfs_failed}")
        print(f"  items without PDF:  {stats.items_without_pdf}")
        print(f"  refs persisted:     {stats.refs_total}")
        print(f"  unique DOIs:        {stats.dois_total}")
        print(f"  DOIs resolved (OA): {stats.dois_resolved}")
        print(f"  text-refs total:    {stats.text_refs_total}")
        print(f"  text-refs resolved: {stats.text_refs_resolved}")
        print(f"  dupes merged:       {stats.dupes_merged}")
        if stats.sources_with_errors:
            print("  sources with errors:")
            for e in stats.sources_with_errors:
                print(f"    - {e}")
        return 0

    # ---- status --------------------------------------------------------------
    if action == "status":
        rep = status_report(Path(args.db) if args.db else DEFAULT_DB_PATH)
        print(f"DB: {rep['db_path']}")
        if not rep["exists"]:
            print("  (noch nicht angelegt — Lauf 'mojo refs build')")
            return 0
        print(f"  publications:        {rep['n_publications']}")
        print(f"  mit Volltext:        {rep['n_with_fulltext']}")
        print(f"  mit Refs:            {rep['n_with_refs']}")
        print(f"  Refs total:          {rep['n_refs_total']}")
        print(f"  Refs in OpenAlex:    {rep['n_refs_resolved_oa']}")
        print(f"  unique OA-Werke:     {rep['n_unique_oa_ids']}")
        print(f"  Quellen:")
        for s in rep["sources"]:
            print(
                f"    {s['source_type']}:{s['source_key'][:50]:<50}  "
                f"{s['n_items']:>4} items   last: {s['last_ingest']}"
            )
        return 0

    # ---- report --------------------------------------------------------------
    if action == "report":
        rep = build_report(Path(args.db) if args.db else DEFAULT_DB_PATH)
        if not rep["buckets"]:
            print("(keine Daten — Lauf 'mojo refs build')")
            return 0
        print(f"{'Source':<60} {'Bucket':<10} {'Items':>6} {'Volltext':>9} {'DOI':>5}")
        print("-" * 95)
        for b in rep["buckets"]:
            label = f"{b['source_type']}:{Path(b['source_key']).name[:50]}"
            print(
                f"{label:<60} {b['year_bucket']:<10} {b['n_items']:>6} "
                f"{b['n_with_fulltext']:>9} {b['n_with_doi']:>5}"
            )
        return 0

    # ---- export json ---------------------------------------------------------
    if action == "export":
        from journal_bot.own_refs.store import OwnRefsStore
        if args.format != "json":
            print(f"FEHLER: unsupported export-Format {args.format!r}")
            return 2
        out_path = Path(args.out).expanduser().resolve()
        with OwnRefsStore(Path(args.db) if args.db else DEFAULT_DB_PATH) as store:
            payload = {
                "publications": [
                    {
                        "canonical_id": p.canonical_id,
                        "doi": p.doi, "title": p.title, "year": p.year,
                        "venue": p.venue, "discourse": p.discourse,
                        "refs": [
                            {
                                "ref_doi": r.ref_doi, "ref_oa_id": r.ref_oa_id,
                                "ref_year": r.ref_year,
                                "resolution_state": r.resolution_state,
                            }
                            for r in store.get_pub_refs(p.canonical_id)
                        ],
                    }
                    for p in store.iter_publications()
                ],
                "all_cited_oa_ids": sorted(store.all_cited_oa_ids()),
            }
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            _json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"Geschrieben: {out_path}  "
              f"({len(payload['publications'])} pubs, "
              f"{len(payload['all_cited_oa_ids'])} unique OA-IDs)")
        return 0

    # ---- validate <pdf> ------------------------------------------------------
    if action == "validate":
        pdf = Path(args.pdf).expanduser().resolve()
        if not pdf.exists():
            print(f"FEHLER: PDF nicht gefunden: {pdf}")
            return 2
        r = validate_pdf(pdf)
        print(f"PDF: {pdf}")
        print(f"  Status:           {r['status']}")
        print(f"  Volltext-Zeichen: {r['fulltext_chars']:,}")
        print(f"  Header:           {r['refs_header_label']!r}  (line {r['refs_header_line']})")
        print(f"  Used fallback:    {r['used_fallback_section']}")
        print(f"  DOIs:             {r['n_dois']}")
        for d in r["first_dois"]:
            print(f"    - {d}")
        print(f"  Raw citations:    {r['n_raw_citations']}")
        for c in r["first_citations"]:
            print(f"    - {c}")
        if r["notes"]:
            print(f"  Notes: {r['notes']}")
        return 0

    print("FEHLER: kein action angegeben für 'refs'")
    return 2


def cmd_escalate(args: argparse.Namespace) -> int:
    """`mojo escalate ...` — Volltext-LLM-Eskalations-Slot (§2.5).

    NICHT Default. Für Items, die nach allen Cascade-Regeln (Vorfilter +
    own_coupling + adversarial veto) noch unklar sind und für die ein
    Volltext-Check sinnvoll wäre. Höchstens ~5–10 % der Items.

    Sub-Actions:
      - select: Liste Kandidaten aus articles.db (sortiert nach PrioScore)
      - fetch:  Volltext für einen Artikel beschaffen (OA → Unpaywall → Crossref)
    """
    import json as _json
    from journal_bot.escalation import (
        fetch_fulltext_for_article, select_candidates,
    )
    from journal_bot.escalation.select import summarize_pool

    action = getattr(args, "action", None)
    articles_db_path = (
        Path(args.articles_db) if getattr(args, "articles_db", "") else
        Path(__file__).resolve().parent.parent / "articles.db"
    )

    if action == "select":
        if not articles_db_path.exists():
            print(f"FEHLER: articles.db fehlt: {articles_db_path}")
            return 2
        journals = (
            [j.strip() for j in args.journal.split(",") if j.strip()]
            if args.journal else None
        )
        cands = select_candidates(
            articles_db=articles_db_path,
            limit=args.limit if args.limit > 0 else None,
            min_prio_score=args.min_prio,
            journals=journals,
            only_wrong_les=args.only_wrong_les,
        )
        if args.json:
            payload = [
                {
                    "article_id": c.article_id,
                    "journal_short": c.journal_short,
                    "title": c.title,
                    "year": c.year,
                    "doi": c.doi,
                    "openalex_id": c.openalex_id,
                    "agent_verdict": c.agent_verdict,
                    "user_verdict": c.user_verdict,
                    "selection_mode": c.selection_mode,
                    "discourse_indicator": c.discourse_indicator,
                    "own_coupling_score": c.own_coupling_score,
                    "adversarial_score": c.adversarial_score,
                    "prio_score": c.prio_score,
                    "reason": c.reason,
                }
                for c in cands
            ]
            print(_json.dumps(payload, ensure_ascii=False, indent=2))
            return 0

        summary = summarize_pool(cands)
        print("=== Eskalations-Kandidaten (Unklar-Zone) ===")
        print(f"  Gesamt:               {summary['n_total']}")
        print(f"  mit own_coupling:     {summary['n_with_own_coupling']}")
        print(f"  mit adversarial:      {summary['n_with_adversarial']}")
        print(f"  wrong-LES:            {summary['n_wrong_les']}")
        print(f"  PrioScore p50/max:    {summary['prio_score_p50']:.2f} / {summary['prio_score_max']:.2f}")
        print()
        print(f"  Pro Modus:     {summary['by_mode']}")
        print(f"  Pro Verdict:   {summary['by_verdict']}")
        print(f"  Pro Indikator: {summary['by_indicator']}")
        print(f"  Top-Journals:  {summary['by_journal_top10']}")
        print()
        if cands:
            print("=== Top-Kandidaten ===")
            for c in cands[:20]:
                print(
                    f"  [prio={c.prio_score:>5.2f}]  {c.article_id[:24]}  "
                    f"{c.journal_short:<10}  {(c.title or '')[:60]!r}"
                )
                print(f"    {c.reason}")
        return 0

    if action == "fetch":
        if not articles_db_path.exists():
            print(f"FEHLER: articles.db fehlt: {articles_db_path}")
            return 2
        # Article-Metadaten ziehen
        import sqlite3
        con = sqlite3.connect(f"file:{articles_db_path}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        try:
            row = con.execute(
                "SELECT id, title, doi, openalex_id FROM articles WHERE id = ?",
                (args.article_id,),
            ).fetchone()
        finally:
            con.close()
        if row is None:
            print(f"FEHLER: Artikel nicht in articles.db: {args.article_id}")
            return 2
        print(f"Artikel: {row['title'][:80]!r}")
        print(f"  DOI: {row['doi']}")
        print(f"  OA-ID: {row['openalex_id']}")
        result = fetch_fulltext_for_article(
            article_id=row["id"],
            openalex_id=row["openalex_id"],
            doi=row["doi"],
            verbose=True,
        )
        print()
        print("=== Fetch-Ergebnis ===")
        print(f"  Status:       {result.status}")
        print(f"  Quelle:       {result.source}")
        print(f"  PDF-URL:      {result.pdf_url}")
        print(f"  PDF-Pfad:     {result.pdf_path}")
        print(f"  Text-Pfad:    {result.txt_path}")
        print(f"  Text-Zeichen: {result.fulltext_chars:,}")
        print(f"  Cache-Hit:    {result.cache_hit}")
        if result.notes:
            print(f"  Notes:        {result.notes}")
        return 0 if result.status in ("ok", "cache_hit") else 1

    if action == "pilot-wrong-les":
        return _run_pilot_wrong_les(args, articles_db_path)

    print("FEHLER: kein action angegeben für 'escalate'")
    return 2


def _run_pilot_wrong_les(args, articles_db_path: Path) -> int:
    """§2.5 Pilot: Volltext-LLM auf Wrong-LES-Items mit Hard-Cost-Cap.

    Workflow pro Item:
      1) Volltext fetchen (Cache-Hit ist Normalfall nach erstem Lauf)
      2) Volltext-LLM-Assess (Sonnet 4.6 default, cost ~$0.04/Call)
      3) Result in Aggregat + JSON-Output

    Hard-Total-Cap stoppt vor Überschreitung.
    """
    import sqlite3
    from journal_bot.escalation import (
        assess_article_volltext,
        fetch_fulltext_for_article,
        select_candidates,
    )

    if not articles_db_path.exists():
        print(f"FEHLER: articles.db fehlt: {articles_db_path}")
        return 2

    print("=== §2.5 Pilot: Wrong-LES-Diagnose ===")
    print(f"  Modell:       {args.model}")
    print(f"  Limit:        {args.limit}")
    print(f"  Total-Cap:    ${args.max_total_usd:.2f}")
    print()

    # 1) Kandidaten auswählen (nur wrong-LES, niedrigster PrioScore zugelassen
    #    damit auch knappe Cascade-Lücken durchkommen).
    cands = select_candidates(
        articles_db=articles_db_path,
        limit=args.limit,
        min_prio_score=-99,
        only_wrong_les=True,
    )
    if not cands:
        print("Keine wrong-LES-Kandidaten gefunden.")
        return 0
    print(f"  {len(cands)} Kandidaten ausgewählt:")
    for c in cands:
        print(f"    {c.article_id[:24]} [{c.journal_short:<10}] prio={c.prio_score:>5.2f}  {c.title[:70]!r}")
    print()

    # 2) Pro Item: Volltext + Assess
    results: list[dict] = []
    total_cost = 0.0
    n_ok = n_no_fulltext = n_parse_failed = n_other = 0
    n_volltext_corrects = 0   # wo LLM tatsächlich LES bestätigt

    for i, c in enumerate(cands, 1):
        print(f"--- [{i}/{len(cands)}] {c.article_id[:24]}  {c.title[:60]!r}")

        # Article-Metadaten + Abstract aus DB ziehen (PrioScore-Felder reichen
        # für die Auswahl, aber für den LLM brauchen wir Abstract).
        con = sqlite3.connect(f"file:{articles_db_path}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        try:
            row = con.execute(
                """SELECT id, title, abstract, doi, openalex_id, year,
                          journal_short, agent_verdict, user_verdict,
                          selection_mode, discourse_indicator
                     FROM articles WHERE id = ?""",
                (c.article_id,),
            ).fetchone()
        finally:
            con.close()
        if row is None:
            print(f"    (artikel fehlt in DB, skipped)")
            n_other += 1
            continue
        article = dict(row)
        article["own_coupling_score"] = c.own_coupling_score
        article["adversarial_score"] = c.adversarial_score

        # 2a) Volltext beschaffen
        fr = fetch_fulltext_for_article(
            article_id=row["id"],
            openalex_id=row["openalex_id"],
            doi=row["doi"],
            verbose=False,
        )
        if fr.status not in ("ok", "cache_hit") or not fr.txt_path:
            print(f"    [no_fulltext] status={fr.status}, src={fr.source}")
            n_no_fulltext += 1
            results.append({
                "article_id": c.article_id, "status": "no_fulltext",
                "fetch_status": fr.status, "title": c.title,
                "journal_short": c.journal_short,
            })
            continue
        try:
            volltext = fr.txt_path.read_text(encoding="utf-8")
        except OSError as e:
            print(f"    [no_fulltext] txt-read failed: {e}")
            n_no_fulltext += 1
            continue
        print(f"    fulltext: {len(volltext):,} chars, source={fr.source}")

        # 2b) Cost-Cap-Check vor jedem Call
        if total_cost >= args.max_total_usd:
            print(f"    ⚠ Total-Cap erreicht (${total_cost:.3f}), Abbruch.")
            break

        # 2c) Volltext-LLM-Assess
        ar = assess_article_volltext(
            article=article, volltext=volltext, model=args.model, verbose=False,
        )
        total_cost += ar.cost_usd
        if ar.status == "ok":
            n_ok += 1
            if ar.would_be_verdict == "lesenswert":
                n_volltext_corrects += 1
        elif ar.status == "parse_failed":
            n_parse_failed += 1
        else:
            n_other += 1

        print(
            f"    LLM: ${ar.cost_usd:.4f}  "
            f"tokens={ar.tokens_in}/{ar.tokens_cached_read}cached/{ar.tokens_out}out  "
            f"verdict={ar.would_be_verdict}  confidence={ar.confidence:.2f}"
        )
        if ar.miss_diagnosis:
            print(f"    miss: {ar.miss_diagnosis[:200]}")
        if ar.suggested_cascade_signal:
            print(f"    signal: {ar.suggested_cascade_signal[:200]}")

        results.append({
            "article_id": c.article_id,
            "title": c.title,
            "journal_short": c.journal_short,
            "year": article.get("year"),
            "doi": article.get("doi"),
            "agent_verdict": article.get("agent_verdict"),
            "selection_mode": c.selection_mode,
            "discourse_indicator": c.discourse_indicator,
            "own_coupling_score": c.own_coupling_score,
            "adversarial_score": c.adversarial_score,
            "fulltext_source": fr.source,
            "fulltext_chars": fr.fulltext_chars,
            "assess_status": ar.status,
            "would_be_verdict": ar.would_be_verdict,
            "confidence": ar.confidence,
            "miss_diagnosis": ar.miss_diagnosis,
            "anchored_quotes": [
                {"text": q.quote, "section": q.section, "relevance": q.relevance}
                for q in ar.anchored_quotes
            ],
            "suggested_cascade_signal": ar.suggested_cascade_signal,
            "tokens_in": ar.tokens_in,
            "tokens_out": ar.tokens_out,
            "tokens_cached_read": ar.tokens_cached_read,
            "tokens_cache_write": ar.tokens_cache_write,
            "cost_usd": ar.cost_usd,
            "model": ar.model,
        })

    # 3) Zusammenfassung
    print()
    print("=== Pilot-Bilanz ===")
    print(f"  bearbeitet:        {len(results)}")
    print(f"  LLM ok:            {n_ok}")
    print(f"  Volltext LES:      {n_volltext_corrects}  "
          f"(= bestätigt User-Verdict gegen Cascade)")
    print(f"  parse_failed:      {n_parse_failed}")
    print(f"  no_fulltext:       {n_no_fulltext}")
    print(f"  sonstige Fehler:   {n_other}")
    print(f"  Total-Kosten:      ${total_cost:.4f}")
    if n_ok:
        print(f"  Avg per LLM-Call:  ${total_cost / max(1, n_ok):.4f}")

    # 4) JSON-Output schreiben
    if args.out:
        import json as _json
        out_path = Path(args.out).expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            _json.dumps({
                "model": args.model,
                "total_cost_usd": total_cost,
                "n_results": len(results),
                "n_ok": n_ok,
                "n_volltext_corrects": n_volltext_corrects,
                "results": results,
            }, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"  JSON:              {out_path}")
    return 0


def cmd_cache_report(args: argparse.Namespace) -> int:
    """Historische Cache-Hit-Rate aus llm_calls.

    Standard: letzte 7 Tage, gruppiert nach Endpoint+Modell. Mit --days N
    anderes Fenster, mit --endpoint filtern. Bei <80 % Hit-Rate auf
    cache-kritischen Endpoints (batch_screen/run_agent/assess/verify) wird
    eine ⚠-Warnung pro Zeile gesetzt.
    """
    from datetime import datetime, timedelta, timezone

    from journal_bot.llm_log import cache_hit_stats, format_cache_report

    days = max(1, int(args.days))
    since_dt = datetime.now(timezone.utc) - timedelta(days=days)
    since = since_dt.isoformat()

    endpoints = [e.strip() for e in (args.endpoint or "").split(",") if e.strip()] or None
    models = [m.strip() for m in (args.model or "").split(",") if m.strip()] or None

    stats = cache_hit_stats(since=since, endpoints=endpoints, models=models)
    if not stats:
        print(f"[cache-report] keine Calls seit {since} (Filter: "
              f"endpoint={endpoints}, model={models}).")
        return 0

    title = f"Cache-Hit-Rate · letzte {days} Tag(e)"
    # Multi-wave aggregate: strenger gegen Cold-Start-Verzerrung. Eine
    # Welle hat typischerweise 1 cold + N hot Calls; bei zwei Wellen
    # sieht batch_screen sonst false-positiv geflaggt aus.
    min_flag = 5 if days >= 2 else 2
    print(format_cache_report(stats, title=title, min_calls_for_flag=min_flag))

    # Aggregierte Bottom-Line: wo liegt das Geld?
    total = sum(r["total_cost"] for r in stats)
    total_calls = sum(r["calls"] for r in stats)
    print(f"\n[cache-report] Σ ${total:.3f} über {total_calls} Calls "
          f"({days} Tage).")
    return 0


# --------------------------------------------------------------- Parser ----


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mojo")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_ingest = sub.add_parser("ingest", help="Corpus aus Zotero-Collection bauen")
    p_ingest.add_argument("--collection", default=ZOTERO_COLLECTION)
    p_ingest.add_argument("--since", type=int, default=SINCE_YEAR)
    p_ingest.add_argument("--output", default=str(CORPUS_JSON))
    p_ingest.set_defaults(func=cmd_ingest)

    p_sum = sub.add_parser("summarize", help="Corpus mit konfiguriertem Modell summarisieren")
    p_sum.add_argument("--corpus", default=str(CORPUS_JSON))
    p_sum.add_argument("--output", default=str(SUMMARIES_JSON))
    p_sum.add_argument("--limit", type=int, default=None)
    p_sum.set_defaults(func=cmd_summarize)

    p_fetch = sub.add_parser("fetch",
                             help="Feeds pullen + enrichen → articles.db")
    p_fetch.add_argument("--quiet", action="store_true")
    p_fetch.add_argument("--since", type=int, default=None,
                         help="Backfill: Artikel ab diesem Jahr holen (z.B. 2016)")
    p_fetch.set_defaults(func=cmd_fetch)

    p_digest = sub.add_parser("digest",
                              help="Agent-Lauf: --doi X (ad-hoc) oder --next N (Batch)")
    p_digest.add_argument("--doi", help="Einzelner Artikel per DOI (ad-hoc)")
    p_digest.add_argument("--journal", default="",
                          help="Optional: Journal-Name für --doi")
    p_digest.add_argument("--next", type=int, default=1,
                          help="Batch: verarbeite N ungeprozessierte Artikel aus dem Store (Default 1)")
    p_digest.add_argument("--journals", default="",
                          help="Komma-Liste von Journal-Kürzeln zum Filtern (Batch)")
    p_digest.add_argument("--since", type=int, default=None,
                          help="Nur Artikel ab diesem Erscheinungsjahr (z.B. 2025)")
    p_digest.add_argument("--no-screen", action="store_true",
                          help="DeepSeek-Vorfilter überspringen (alle direkt zum Agenten)")
    p_digest.add_argument("--model", default=None,
                          help="Agent-Modell via OpenRouter-ID (z.B. deepseek/deepseek-v3.2, "
                               "anthropic/claude-opus-4.6)")
    p_digest.add_argument("--cost-limit", type=float, default=None,
                          help="Hartes USD-Gesamtbudget für den Batch-Lauf "
                               "(zusätzlich zu den Per-Call-Caps in agent.py).")
    p_digest.add_argument("--quiet", action="store_true")
    p_digest.add_argument("--no-weekly-summary", action="store_true",
                          help="Unterdrückt den 7-Tage-Cache-Hit-Report am Ende des Laufs.")
    p_digest.set_defaults(func=cmd_digest)

    p_trends = sub.add_parser("trends",
                              help="Aggregat-Trendanalyse pro Diskursraum")
    p_trends.add_argument("--cluster", default="",
                          help="Diskursraum-Key (siehe --list-clusters)")
    p_trends.add_argument("--list-clusters", action="store_true",
                          help="Verfügbare Diskursräume auflisten und beenden")
    p_trends.add_argument("--window-years", type=int, default=3,
                          help="Zeitfenster in Jahren (Default 3)")
    p_trends.add_argument("--journals", default="",
                          help="Ad-hoc-Override: Komma-Liste von Journal-Kürzeln")
    p_trends.add_argument("--quiet", action="store_true")
    p_trends.set_defaults(func=cmd_trends)

    p_biblio = sub.add_parser("biblio",
                              help="Bibliometrische Zitationsanalyse (kein LLM)")
    p_biblio.add_argument("--cluster", required=True,
                          help="Diskursraum-Key")
    p_biblio.add_argument("--window-years", type=int, default=3)
    p_biblio.add_argument("--top-pct", type=float, default=0.10,
                          help="Anteil der Top-Referenzen (Default 0.10 = 10%%)")
    p_biblio.add_argument("--min-count", type=int, default=2,
                          help="Mindest-Zitationszahl (Default 2)")
    p_biblio.add_argument("--quiet", action="store_true")
    p_biblio.set_defaults(func=cmd_biblio)

    p_scout = sub.add_parser("scout",
                            help="Watchlist-Journals auf Relevanz prüfen (Haiku)")
    p_scout.add_argument("--watchlist",
                         default=str(PROJECT_ROOT / "docs" / "journal_watchlist_full.md"),
                         help="Pfad zur Watchlist-Markdown-Datei")
    p_scout.add_argument("--window-years", type=int, default=3)
    p_scout.add_argument("--limit", type=int, default=None,
                         help="Nur die ersten N Kandidaten prüfen (zum Testen)")
    p_scout.add_argument("--quiet", action="store_true")
    p_scout.set_defaults(func=cmd_scout)

    p_cov = sub.add_parser("coverage",
                            help="Welche Journals werden zitiert, aber nicht getrackt?")
    p_cov.add_argument("--cluster", required=True,
                       help="Diskursraum-Key")
    p_cov.add_argument("--window-years", type=int, default=3)
    p_cov.add_argument("--min-citations", type=int, default=3,
                       help="Mindest-Zitationszahl (Default 3)")
    p_cov.add_argument("--quiet", action="store_true")
    p_cov.set_defaults(func=cmd_coverage)

    # --- diskurs ---
    p_diskurs = sub.add_parser("diskurs",
                               help="Diskursräume verwalten (list, add, rename, remove, assign, unassign)")
    p_diskurs.set_defaults(func=cmd_diskurs)
    diskurs_sub = p_diskurs.add_subparsers(dest="action", required=True)

    diskurs_sub.add_parser("list", help="Alle Diskursräume auflisten")

    p_dp = diskurs_sub.add_parser("profile", help="Datengetriebenes Profil eines Diskursraums")
    p_dp.add_argument("key", help="Diskursraum-Schlüssel")
    p_dp.add_argument("--window-years", type=int, default=3,
                       help="Zeitfenster in Jahren (Default 3)")

    p_ds = diskurs_sub.add_parser("suggest",
                                    help="LLM-gestützte Vorschläge für neue/geänderte Diskursräume")
    p_ds.add_argument("--window-years", type=int, default=3)
    p_ds.add_argument("--quiet", action="store_true")

    p_dcc = diskurs_sub.add_parser("crosscut",
                                    help="Querschnitt-Konzepte über alle Räume (kein LLM)")
    p_dcc.add_argument("--window-years", type=int, default=3)

    p_da = diskurs_sub.add_parser("add", help="Neuen Diskursraum anlegen")
    p_da.add_argument("key", help="Eindeutiger Schlüssel (z.B. kulturelle_bildung)")
    p_da.add_argument("--name", required=True, help="Anzeigename")
    p_da.add_argument("--desc", required=True, help="Kurzbeschreibung")

    p_dr = diskurs_sub.add_parser("rename", help="Diskursraum umbenennen")
    p_dr.add_argument("old", help="Alter Schlüssel")
    p_dr.add_argument("new", help="Neuer Schlüssel")

    p_drm = diskurs_sub.add_parser("remove", help="Diskursraum entfernen")
    p_drm.add_argument("key", help="Schlüssel des zu entfernenden Diskursraums")

    p_das = diskurs_sub.add_parser("assign", help="Journal einem Diskursraum zuordnen")
    p_das.add_argument("journal", help="Journal-Kürzel (z.B. ZfE)")
    p_das.add_argument("clusters", nargs="+", help="Diskursraum-Schlüssel")

    p_dua = diskurs_sub.add_parser("unassign", help="Journal aus Diskursraum entfernen")
    p_dua.add_argument("journal", help="Journal-Kürzel")
    p_dua.add_argument("cluster", help="Diskursraum-Schlüssel")

    # --- journal ---
    p_journal = sub.add_parser("journal",
                                help="Journals verwalten (list, add, remove)")
    p_journal.set_defaults(func=cmd_journal)
    journal_sub = p_journal.add_subparsers(dest="action", required=True)

    journal_sub.add_parser("list", help="Alle registrierten Journals auflisten")

    p_ja = journal_sub.add_parser("add", help="Neues Journal hinzufügen")
    p_ja.add_argument("short", help="Kurzname (z.B. SAE)")
    p_ja.add_argument("--name", required=True, help="Voller Name")
    p_ja.add_argument("--issn", required=True, help="ISSN (z.B. 0039-3541)")
    p_ja.add_argument("--clusters", nargs="*", default=[],
                       help="Diskursraum-Schlüssel (z.B. aesthetische_kulturelle_bildung)")
    p_ja.add_argument("--type", default="openalex",
                       help="Fetch-Typ (default: openalex)")

    p_jr = journal_sub.add_parser("remove", help="Journal entfernen")
    p_jr.add_argument("short", help="Kurzname des zu entfernenden Journals")

    # --- journal-topics ---
    p_jtopics = sub.add_parser(
        "journal-topics",
        help="OpenAlex-Journalprofile verwalten und für Routing ranken",
    )
    p_jtopics.set_defaults(func=cmd_journal_topics)
    jtopics_sub = p_jtopics.add_subparsers(dest="action", required=True)

    jtopics_sub.add_parser("status", help="Status der persistierten Journalprofile")

    p_jtr = jtopics_sub.add_parser("refresh", help="Journalprofile via OpenAlex aktualisieren")
    p_jtr.add_argument("--topic-limit", type=int, default=80,
                       help="Max. Topics pro Journal (Default 80)")
    p_jtr.add_argument("--include-disabled", action="store_true",
                       help="Auch deaktivierte Journals profilieren")

    p_jtk = jtopics_sub.add_parser("rank", help="Query gegen persistierte Journalprofile ranken")
    p_jtk.add_argument("query", help="Suchfrage, Abstract oder kurzer Textauszug")
    p_jtk.add_argument("--limit", type=int, default=12,
                       help="Max. Journals im Ranking (Default 12)")

    # --- mojo refs (MOJO 2.0 §3.1 — Multi-Source Refs-Pipeline) ----------
    p_refs = sub.add_parser(
        "refs",
        help="Multi-Source Refs-Pipeline (eigene Pubs → Volltext → Refs → OpenAlex)",
    )
    p_refs.set_defaults(func=cmd_refs)
    refs_sub = p_refs.add_subparsers(dest="action", required=True)

    p_rb = refs_sub.add_parser("build", help="Quellen einlesen, Refs extrahieren, DOIs auflösen")
    p_rb.add_argument(
        "--source", action="append", default=[],
        help="Ad-hoc-Quelle: 'zotero:KEY' oder 'folder:/pfad' (mehrfach erlaubt). "
             "Hat Vorrang vor 'refs_sources' aus profile.json.",
    )
    p_rb.add_argument("--force-refresh", action="store_true",
                      help="Alle PDFs neu extrahieren, auch wenn pdf_mtime unverändert")
    p_rb.add_argument("--no-resolve", action="store_true",
                      help="DOIs nicht gegen OpenAlex auflösen (offline-Modus)")
    p_rb.add_argument("--no-text-resolve", action="store_true",
                      help="Freie Refs nicht gegen OpenAlex-Search auflösen "
                           "(§2.4 — Cache ist persistent, zweiter Lauf ohne "
                           "Flag ist trotzdem schnell).")
    p_rb.add_argument("--text-resolve-max-calls", type=int, default=None,
                      help="Maximalanzahl LIVE-Calls für Free-Text-Resolve. "
                           "Cache-Hits zählen nicht. Sinnvoll für Smoke-Tests.")
    p_rb.add_argument("--db", default="",
                      help="Alternativer DB-Pfad (default: own_refs.db im Projekt)")
    p_rb.add_argument("--quiet", action="store_true")

    refs_sub.add_parser("status", help="Counts und Coverage anzeigen") \
        .add_argument("--db", default="", help="Alternativer DB-Pfad")

    refs_sub.add_parser("report", help="Coverage pro Source × Jahr-Bucket") \
        .add_argument("--db", default="", help="Alternativer DB-Pfad")

    p_rs = refs_sub.add_parser("sources", help="Quellen verwalten (add/list/remove)")
    rs_sub = p_rs.add_subparsers(dest="sub_action", required=True)
    rs_sub.add_parser("list", help="Konfigurierte Quellen anzeigen")
    p_rsa = rs_sub.add_parser("add", help="Quelle zur profile.json hinzufügen")
    p_rsa.add_argument("source_type", choices=["zotero", "folder"])
    p_rsa.add_argument("value", help="Zotero-Collection-Key oder absoluter Folder-Pfad")
    p_rsa.add_argument("--label", default="", help="Klartext-Label (nur für zotero)")
    p_rsr = rs_sub.add_parser("remove", help="Quelle aus profile.json entfernen")
    p_rsr.add_argument("spec", help="z.B. 'zotero:QM7TZT44' oder 'folder:/pfad'")

    p_re = refs_sub.add_parser("export", help="Refs-Index als JSON exportieren")
    p_re.add_argument("format", choices=["json"])
    p_re.add_argument("--out", required=True, help="Zieldatei")
    p_re.add_argument("--db", default="")

    p_rv = refs_sub.add_parser(
        "validate",
        help="Refs-Extraktion gegen ein konkretes PDF zeigen (manueller Smoke-Test)",
    )
    p_rv.add_argument("pdf", help="Pfad zu einer PDF-Datei")

    # --- mojo escalate (MOJO 2.0 §2.5 — Volltext-LLM-Eskalations-Slot) ---
    p_esc = sub.add_parser(
        "escalate",
        # »%%« ist Pflicht: argparse jagt jeden help-Text durch »% params«.
        # »10 % der« wurde als Formatanweisung »% d« gelesen und riss die
        # gesamte Hilfe mit einem TypeError ab — nicht nur die dieses Befehls.
        help="Unklar-Zone-Kandidaten auswählen und Volltext beschaffen "
             "(NICHT Default — Eskalation für ≤10 %% der Items)",
    )
    p_esc.set_defaults(func=cmd_escalate)
    esc_sub = p_esc.add_subparsers(dest="action", required=True)

    p_esc_sel = esc_sub.add_parser(
        "select", help="Kandidaten aus articles.db listen, nach PrioScore sortiert",
    )
    p_esc_sel.add_argument("--limit", type=int, default=50,
                           help="Max. Anzahl Kandidaten (Default 50, None = alle)")
    p_esc_sel.add_argument("--min-prio", type=float, default=0.0,
                           help="Untergrenze PrioScore (Default 0.0)")
    p_esc_sel.add_argument("--journal", default="",
                           help="Nur dieses Journal (Kürzel, mehrere komma-separiert)")
    p_esc_sel.add_argument("--only-wrong-les", action="store_true",
                           help="Nur user_verdict='lesenswert' ∧ agent_verdict!='lesenswert'")
    p_esc_sel.add_argument("--articles-db", default="",
                           help="Alternativer articles.db-Pfad")
    p_esc_sel.add_argument("--json", action="store_true",
                           help="JSON-Output statt Tabelle (für Skripte)")

    p_esc_fetch = esc_sub.add_parser(
        "fetch", help="Volltext für einen Artikel beschaffen (OA → Unpaywall → Crossref)",
    )
    p_esc_fetch.add_argument("article_id", help="Artikel-ID aus articles.db")
    p_esc_fetch.add_argument("--articles-db", default="",
                             help="Alternativer articles.db-Pfad")

    p_esc_pilot = esc_sub.add_parser(
        "pilot-wrong-les",
        help="Volltext-LLM-Assessment für die wrong-LES-Items "
             "(user=lesenswert, agent!=lesenswert). Hard cost-cap.",
    )
    p_esc_pilot.add_argument("--limit", type=int, default=3,
                             help="Anzahl Items (Default 3 — Pre-Batch-Smoke-Test).")
    p_esc_pilot.add_argument("--model", default="anthropic/claude-sonnet-4.6",
                             help="OpenRouter-Modell-ID. Default Sonnet 4.6.")
    p_esc_pilot.add_argument("--max-total-usd", type=float, default=2.0,
                             help="Hard Total-Cap (Default $2). Bricht ab, "
                                  "wenn kumuliert überschritten.")
    p_esc_pilot.add_argument("--out", default="",
                             help="JSON-Output-Pfad. Default: stdout-Tabelle.")
    p_esc_pilot.add_argument("--articles-db", default="",
                             help="Alternativer articles.db-Pfad")

    p_backfill = sub.add_parser("backfill",
                                help="Fehlende Abstracts nachziehen (Crossref/Playwright/Zotero)")
    p_backfill.add_argument("--limit", type=int, default=None,
                            help="Max. Anzahl Artikel (zum Testen)")
    p_backfill.add_argument("--journal", default="",
                            help="Nur dieses Journal (Kürzel, z.B. EPT)")
    p_backfill.add_argument("--dry-run", action="store_true",
                            help="Nur prüfen, nicht schreiben")
    p_backfill.add_argument("--delay", type=float, default=2.0,
                            help="Sekunden zwischen externen Requests (Default 2)")
    p_backfill.add_argument("--quiet", action="store_true")
    p_backfill.set_defaults(func=cmd_backfill)

    p_backup = sub.add_parser("backup", help="Lokales Nutzer-Backup als ZIP erstellen")
    p_backup.add_argument(
        "--output",
        default="",
        help="Zielpfad für das ZIP-Archiv (default: ./backups/mojo_user_backup_*.zip)",
    )
    p_backup.add_argument(
        "--no-digests",
        action="store_true",
        help="Digest-Ausgabeverzeichnis nicht mitsichern",
    )
    p_backup.set_defaults(func=cmd_backup)

    p_restore = sub.add_parser("restore", help="Nutzer-Backup aus ZIP wiederherstellen")
    p_restore.add_argument("archive", help="Pfad zum Backup-ZIP")
    p_restore.add_argument(
        "--dry-run",
        action="store_true",
        help="Nur prüfen und Zielpfade ausgeben, nichts schreiben",
    )
    p_restore.add_argument(
        "--no-digests",
        action="store_true",
        help="Digest-Dateien aus dem Backup nicht zurueckspielen",
    )
    p_restore.add_argument(
        "--digest-dir",
        default="",
        help="Digest-Zielpfad fuer diesen Rechner ueberschreiben",
    )
    p_restore.add_argument(
        "--zotero-storage",
        default="",
        help="zotero_storage im Profil fuer diesen Rechner ueberschreiben",
    )
    p_restore.set_defaults(func=cmd_restore)

    p_export_raw = sub.add_parser(
        "export-raw",
        help="Rohdatenpaket mit Artikeln/Abstracts ohne Bewertungen exportieren",
    )
    p_export_raw.add_argument(
        "--output",
        default="",
        help="Zielpfad fuer das ZIP-Archiv (default: ./exports/mojo_article_rohdaten_*.zip)",
    )
    p_export_raw.add_argument(
        "--since",
        type=int,
        default=None,
        help="Optional nur Artikel ab diesem Jahr exportieren",
    )
    p_export_raw.add_argument(
        "--journals",
        default="",
        help="Optional nur diese Journal-Kuerzel, komma-getrennt",
    )
    p_export_raw.set_defaults(func=cmd_export_raw)

    p_import_raw = sub.add_parser(
        "import-raw",
        help="Rohdatenpaket mit Artikeln/Abstracts importieren",
    )
    p_import_raw.add_argument("archive", help="Pfad zum Rohdaten-ZIP")
    p_import_raw.set_defaults(func=cmd_import_raw)

    p_stats = sub.add_parser("stats", help="Store-Statistik")
    p_stats.set_defaults(func=cmd_stats)

    p_cache = sub.add_parser(
        "cache-report",
        help="Cache-Hit-Rate pro Endpoint/Modell (Kostenhebel-Diagnose)",
    )
    p_cache.add_argument("--days", type=int, default=7,
                         help="Fenster in Tagen (Default 7)")
    p_cache.add_argument("--endpoint", default="",
                         help="Komma-Liste: batch_screen,assess,verify,trends,…")
    p_cache.add_argument("--model", default="",
                         help="Komma-Liste von Modell-IDs (z.B. anthropic/claude-opus-4.6)")
    p_cache.set_defaults(func=cmd_cache_report)

    p_web = sub.add_parser("web", help="Web-UI starten (localhost:5000)")
    p_web.add_argument("--port", type=int, default=5555)
    p_web.add_argument(
        "--debug",
        action="store_true",
        help="Flask-Debug-Mode mit Reloader (Dev-only, brennt CPU im KeepAlive-Service).",
    )
    p_web.set_defaults(func=cmd_web)

    # --- mojo explore (algorithmische Korpus-Erschließung; Auftrag: ------
    #     docs/mojo2_korpus_exploration_goal.md) ----------------------------
    p_explore = sub.add_parser(
        "explore",
        help="Algorithmische Korpus-Erschließung (Struktur/Trends, kein LLM)",
    )
    p_explore.set_defaults(func=cmd_explore)
    explore_sub = p_explore.add_subparsers(dest="action", required=True)

    p_etr = explore_sub.add_parser(
        "trends",
        help="Themen-Trajektorien (within-journal-dekomponiert; Korpus-Anteil nur als Kontrast)",
    )
    p_etr.add_argument("--early", default="2016-2019", help="Frühes Fenster JJJJ-JJJJ")
    p_etr.add_argument("--late", default="2022-2025", help="Spätes Fenster JJJJ-JJJJ")
    p_etr.add_argument("--score-min", type=float, default=0.5, dest="score_min",
                       help="Topic gilt ab diesem OpenAlex-score als präsent (Default 0.5)")
    p_etr.add_argument("--min-journal", type=int, default=30, dest="min_journal",
                       help="Mindest-Artikel je Journal UND Fenster fürs Panel (Default 30)")
    p_etr.add_argument("--top-n", type=int, default=25, dest="top_n",
                       help="Auf-/Absteiger je Tabelle (Default 25)")
    p_etr.add_argument("--out", default="",
                       help="Markdown-Report schreiben (leer = nur Konsolen-Summary)")
    p_etr.add_argument("--quiet", action="store_true")

    p_ecp = explore_sub.add_parser(
        "coupling",
        help="Bibliografische Kopplungs-Communities (geteilte Referenzbasis; gegen Diskursräume)",
    )
    p_ecp.add_argument("--start-year", type=int, default=None, dest="start_year",
                       help="Frühestes Jahr (leer = alle)")
    p_ecp.add_argument("--end-year", type=int, default=None, dest="end_year",
                       help="Spätestes Jahr (leer = alle)")
    p_ecp.add_argument("--max-df", type=int, default=50, dest="max_df",
                       help="Referenzen über dieser Zitationshäufigkeit = Stoppwort, gekappt (Default 50)")
    p_ecp.add_argument("--min-shared", type=int, default=2, dest="min_shared",
                       help="Kante nur ab so vielen geteilten Referenzen (Default 2)")
    p_ecp.add_argument("--resolution", type=float, default=1.0,
                       help="Louvain-Auflösung; größer → mehr, kleinere Communities (Default 1.0)")
    p_ecp.add_argument("--min-community", type=int, default=20, dest="min_community",
                       help="Nur Communities ab dieser Größe melden (Default 20)")
    p_ecp.add_argument("--no-titles", action="store_true", dest="no_titles",
                       help="Geteilte Referenzen NICHT zu Titeln auflösen (offline, kein OpenAlex-Lookup)")
    p_ecp.add_argument("--out", default="",
                       help="Markdown-Report schreiben (leer = nur Konsolen-Summary)")
    p_ecp.add_argument("--quiet", action="store_true")

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
