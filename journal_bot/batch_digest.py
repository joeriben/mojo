"""Shared batch-digest runner for CLI and web backfill scans."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from journal_bot import agent as agent_mod
from journal_bot import digest
from journal_bot.citation_tracker import find_citations, load_authored_all
from journal_bot.settings import JOURNALS, MODEL_AGENT
from journal_bot.store import Store, StoredArticle

LogFn = Callable[[str], None]


@dataclass
class BatchDigestResult:
    total_candidates: int = 0
    screened_out: int = 0
    screened_in: int = 0
    auto_passed: int = 0
    c_tier_only: int = 0
    processed_articles: int = 0
    total_cost_usd: float = 0.0
    aborted: bool = False
    abort_reason: str = ""
    errors: list[str] = field(default_factory=list)


def _is_junk_title(title: str) -> bool:
    t = (title or "").strip().lower()
    junk = [
        "issue information", "correction", "erratum", "retraction",
        "corrigendum", "table of contents", "editorial board",
        "reviewer acknowledgement", "books received", "index",
    ]
    return any(t == j or t.startswith(j + ":") or t.startswith(j + " ") for j in junk)


def _log(logger: LogFn | None, verbose: bool, message: str) -> None:
    if verbose and logger:
        logger(message)


def run_batch_digest(
    pending: list[StoredArticle],
    store: Store,
    *,
    model: str | None = None,
    no_screen: bool = False,
    verbose: bool = True,
    logger: LogFn | None = print,
    cost_limit_usd: float | None = None,
) -> BatchDigestResult:
    """Run the existing screening + assess/verify pipeline on pending articles."""
    result = BatchDigestResult(total_candidates=len(pending))
    model = model or MODEL_AGENT

    if not pending:
        _log(logger, verbose, "[digest] Keine ungeprozessierten Artikel im Scope.")
        return result

    _log(
        logger,
        verbose,
        f"[digest] {len(pending)} Artikel gefunden "
        f"(Agent-Modell: {model}; Screening: {agent_mod.MODEL_SCREEN})",
    )

    junk = [sa for sa in pending if _is_junk_title(sa.title)]
    if junk:
        _log(logger, verbose, f"[digest] {len(junk)} Nicht-Artikel entfernt (Corrections, Issue Info etc.)")
        pending = [sa for sa in pending if not _is_junk_title(sa.title)]

    def _has_abstract(sa: StoredArticle) -> bool:
        return bool((sa.abstract or "").strip() or (sa.openalex_abstract or "").strip())

    no_data = [sa for sa in pending if not _has_abstract(sa)]
    with_data = [sa for sa in pending if _has_abstract(sa)]

    if no_data:
        catchwords = agent_mod.build_catchwords()
        cw_hits: list[StoredArticle] = []
        cw_miss: list[StoredArticle] = []
        for sa in no_data:
            matches = agent_mod.title_matches_catchwords(sa.title, catchwords)
            if matches:
                cw_hits.append(sa)
            else:
                cw_miss.append(sa)

        for sa in cw_miss:
            store.update_agent_result(
                sa.id,
                verdict="ignorieren",
                entry={
                    "kernthese": "(kein Abstract verfügbar)",
                    "bezuege": [],
                    "bemerkenswert": [],
                    "theoretisch_methodisch": "",
                    "verdict": "ignorieren",
                    "verdict_begruendung": "Kein Abstract, Titel ohne spezifischen Bezug.",
                },
                citation_hits=[],
                tokens_in=0,
                tokens_out=0,
                tokens_cached_read=0,
                tokens_cache_write=0,
                cost_usd=0.0,
                iterations=0,
                selection_mode="screening",
                discourse_indicator="kein_indikator",
            )

        triage_scannen: list[StoredArticle] = []
        triage_ignore: list[StoredArticle] = []
        for sa in cw_hits:
            triage_result = agent_mod.triage_article(
                {
                    "title": sa.title,
                    "journal": sa.journal_full or sa.journal_short,
                    "abstract": "",
                },
                verbose=False,
            )
            if triage_result.get("triage") == "ignorieren":
                triage_ignore.append(sa)
                store.update_agent_result(
                    sa.id,
                    verdict="ignorieren",
                    entry={
                        "kernthese": "(kein Abstract, Triage: ignorieren)",
                        "bezuege": [],
                        "bemerkenswert": [],
                        "theoretisch_methodisch": "",
                        "verdict": "ignorieren",
                        "verdict_begruendung": triage_result.get("grund", "Triage: ignorieren"),
                    },
                    citation_hits=[],
                    tokens_in=0,
                    tokens_out=0,
                    tokens_cached_read=0,
                    tokens_cache_write=0,
                    cost_usd=triage_result.get("cost_usd", 0.0),
                    iterations=0,
                    selection_mode="screening",
                    discourse_indicator="kein_indikator",
                )
            else:
                triage_scannen.append(sa)
                store.update_agent_result(
                    sa.id,
                    verdict="scannen",
                    entry={
                        "kernthese": "(kein Abstract, Triage: relevant)",
                        "bezuege": [],
                        "bemerkenswert": [],
                        "theoretisch_methodisch": "",
                        "verdict": "scannen",
                        "verdict_begruendung": triage_result.get(
                            "grund",
                            "Triage: relevant, kein Abstract für tiefere Analyse.",
                        ),
                    },
                    citation_hits=[],
                    tokens_in=0,
                    tokens_out=0,
                    tokens_cached_read=0,
                    tokens_cache_write=0,
                    cost_usd=triage_result.get("cost_usd", 0.0),
                    iterations=0,
                    selection_mode="screening",
                    discourse_indicator="schwacher_indikator",
                )

        _log(logger, verbose, f"\n[digest] Ohne Abstract: {len(no_data)} Artikel")
        _log(logger, verbose, f"  → {len(cw_miss)} ohne Catchword-Hit → ignorieren (0 Kosten)")
        _log(logger, verbose, f"  → {len(cw_hits)} mit Catchword-Hit → Haiku-Triage")
        _log(logger, verbose, f"    → {len(triage_scannen)} scannen, {len(triage_ignore)} ignorieren")
        pending = with_data

    trigger_authors = ["macgilchrist", "jarke", "wendy chun", "wendy hui kyong"]
    authored_all = load_authored_all()
    auto_pass: list[tuple[StoredArticle, str]] = []
    screen_candidates: list[StoredArticle] = []

    for sa in pending:
        refs = sa.crossref_refs or []
        citation_hits = find_citations(refs, authored_all) if refs else []
        authors_blob = " ".join(sa.authors).lower()
        is_trigger = any(t in authors_blob for t in trigger_authors)

        if citation_hits or is_trigger:
            reason: list[str] = []
            if citation_hits:
                reason.append(f"zitiert Forscher*in ({len(citation_hits)}×)")
            if is_trigger:
                reason.append("Trigger-Autor*in")
            auto_pass.append((sa, " + ".join(reason)))
        else:
            screen_candidates.append(sa)

    result.auto_passed = len(auto_pass)
    if auto_pass:
        _log(logger, verbose, f"\n[digest] Auto-Pass ({len(auto_pass)} Artikel):")
        for sa, reason in auto_pass:
            journal_name = sa.journal_full or sa.journal_short
            _log(logger, verbose, f"  ★ {journal_name}: {sa.title[:60]} [{reason}]")

    if not no_screen and len(screen_candidates) > 1:
        screen_input = [
            {
                "id": sa.id,
                "title": sa.title,
                "journal": sa.journal_full or sa.journal_short,
                "abstract": sa.abstract,
                "openalex_abstract": sa.openalex_abstract,
            }
            for sa in screen_candidates
        ]
        try:
            screen_results = agent_mod.batch_screen(screen_input, verbose=verbose)
        except agent_mod.CacheNotHitError as exc:
            result.aborted = True
            result.abort_reason = f"Prompt-Cache greift im Screening nicht: {exc}"
            _log(logger, verbose, f"[digest] ABBRUCH: {result.abort_reason}")
            return result

        passed = [
            sa
            for sa in screen_candidates
            if screen_results[sa.id]["verdict"] == "weitergeben"
        ]
        filtered = [
            sa
            for sa in screen_candidates
            if screen_results[sa.id]["verdict"] == "ignorieren"
        ]
        result.screened_in = len(passed)
        result.screened_out = len(filtered)

        if filtered:
            _log(logger, verbose, f"\n[digest] Aussortiert ({len(filtered)} Artikel):")
            for sa in filtered:
                grund = screen_results[sa.id].get("grund", "")[:60]
                journal_name = sa.journal_full or sa.journal_short
                _log(logger, verbose, f"  ⊘ {journal_name}: {sa.title[:65]}")
                if grund:
                    _log(logger, verbose, f"    → {grund}")
                store.update_agent_result(
                    sa.id,
                    verdict="ignorieren",
                    entry={
                        "kernthese": "(Screening: ignorieren)",
                        "bezuege": [],
                        "bemerkenswert": [],
                        "theoretisch_methodisch": "",
                        "verdict": "ignorieren",
                        "verdict_begruendung": f"Screening: {grund}",
                    },
                    citation_hits=[],
                    tokens_in=0,
                    tokens_out=0,
                    tokens_cached_read=0,
                    tokens_cache_write=0,
                    cost_usd=0.0,
                    iterations=0,
                    selection_mode="screening",
                    discourse_indicator="kein_indikator",
                )

        _log(
            logger,
            verbose,
            f"\n[digest] Screening: {len(passed)} weitergeben, {len(filtered)} aussortiert",
        )
    else:
        passed = screen_candidates
        result.screened_in = len(passed)

    tier_by_short = {j.short: j.tier for j in JOURNALS}

    to_analyze = [sa for sa, _ in auto_pass]
    for sa in passed:
        tier = tier_by_short.get(sa.journal_short, "B")
        if tier != "C":
            to_analyze.append(sa)

    c_only = [sa for sa in passed if tier_by_short.get(sa.journal_short, "B") == "C"]
    result.c_tier_only = len(c_only)
    if c_only:
        _log(logger, verbose, f"[digest] C-Tier: {len(c_only)} Artikel nur gescreent, kein Agent")
        for sa in c_only:
            store.update_agent_result(
                sa.id,
                verdict="scannen",
                entry={
                    "kernthese": "(C-Tier: nur Screening, kein Agent)",
                    "bezuege": [],
                    "bemerkenswert": [],
                    "theoretisch_methodisch": "",
                    "verdict": "scannen",
                    "verdict_begruendung": "C-Tier: Screening-Pass, keine Agent-Analyse.",
                },
                citation_hits=[],
                tokens_in=0,
                tokens_out=0,
                tokens_cached_read=0,
                tokens_cache_write=0,
                cost_usd=0.0,
                iterations=0,
                selection_mode="screening",
                discourse_indicator="schwacher_indikator",
            )

    if not to_analyze:
        _log(logger, verbose, "[digest] Keine Artikel für Agent-Analyse übrig.")
        return result

    cost_check_after = 3
    max_cost_per_article = 0.15

    _log(
        logger,
        verbose,
        f"\n[digest] === Agent ({len(to_analyze)} Artikel, {model}, assess→verify) ===",
    )
    for index, sa in enumerate(to_analyze, 1):
        if (
            cost_limit_usd is not None
            and result.processed_articles > 0
            and result.total_cost_usd > 0
        ):
            avg_cost = result.total_cost_usd / result.processed_articles
            projected_next = max(avg_cost, 0.01)
            if result.total_cost_usd + projected_next > cost_limit_usd:
                result.aborted = True
                result.abort_reason = (
                    f"Kostenlimit ${cost_limit_usd:.2f} erreicht "
                    f"(bisher ${result.total_cost_usd:.3f})."
                )
                _log(logger, verbose, f"[digest] ABBRUCH: {result.abort_reason}")
                return result

        journal_name = sa.journal_full or sa.journal_short
        _log(logger, verbose, f"\n[digest] --- {index}/{len(to_analyze)} --- {journal_name} · {sa.title[:75]}")
        try:
            article_result = digest.process_article(
                sa,
                store,
                verbose=verbose,
                model=model,
                mode="assess_verify",
            )
            cost = article_result["agent_result"].get("est_cost_usd", 0.0)
            result.total_cost_usd += cost
            result.processed_articles += 1
            verdict = (article_result["agent_result"].get("entry") or {}).get("verdict", "?")
            _log(logger, verbose, f"[digest] ✓ {verdict}  (${cost:.3f})")
        except agent_mod.CacheNotHitError as exc:
            result.aborted = True
            result.abort_reason = f"Prompt-Cache greift nicht: {exc}"
            _log(logger, verbose, f"\n[digest] ABBRUCH: {result.abort_reason}")
            _log(
                logger,
                verbose,
                f"[digest] Bisher: {result.processed_articles} Artikel, ${result.total_cost_usd:.3f}",
            )
            return result
        except Exception as exc:
            msg = f"{sa.id}: {exc}"
            result.errors.append(msg)
            _log(logger, verbose, f"[digest] FEHLER bei {sa.id}: {exc}")
            continue

        if index == cost_check_after and result.total_cost_usd > 0:
            avg_cost = result.total_cost_usd / index
            projected = avg_cost * len(to_analyze)
            if avg_cost > max_cost_per_article:
                result.aborted = True
                result.abort_reason = (
                    f"Kosten-Warnung: ${avg_cost:.3f}/Artikel, "
                    "Prompt-Caching scheint nicht zu funktionieren."
                )
                _log(logger, verbose, f"\n[digest] ⚠ KOSTEN-WARNUNG: ${avg_cost:.3f}/Artikel "
                                       f"(erwartet <${max_cost_per_article:.2f})")
                _log(logger, verbose, f"[digest] Hochrechnung: ${projected:.2f} für {len(to_analyze)} Artikel")
                _log(logger, verbose, f"[digest] ABBRUCH nach {index} Artikeln. "
                                       f"Bisherige Kosten: ${result.total_cost_usd:.3f}")
                return result
            _log(
                logger,
                verbose,
                f"[digest] ✓ Kosten-Check: ${avg_cost:.3f}/Artikel — "
                f"Cache ok, Hochrechnung: ${projected:.2f}",
            )

        if cost_limit_usd is not None and result.total_cost_usd >= cost_limit_usd:
            result.aborted = True
            result.abort_reason = (
                f"Kostenlimit ${cost_limit_usd:.2f} nach {result.processed_articles} "
                f"Artikeln erreicht ({result.total_cost_usd:.3f})."
            )
            _log(logger, verbose, f"[digest] ABBRUCH: {result.abort_reason}")
            return result

    _log(logger, verbose, f"\n[digest] Gesamtkosten: ${result.total_cost_usd:.3f}")
    return result
