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
    print(f"[web] MOJO UI auf http://localhost:{args.port}")
    app.run(debug=True, port=args.port)
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

    p_web = sub.add_parser("web", help="Web-UI starten (localhost:5000)")
    p_web.add_argument("--port", type=int, default=5555)
    p_web.set_defaults(func=cmd_web)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
