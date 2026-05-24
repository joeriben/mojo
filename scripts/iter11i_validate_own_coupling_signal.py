"""§2.1 Live-Verifikation: produktive own_coupling-Veto-Up auf articles.db.

Ersetzt den Backtest-Befund aus `iter11_add_own_coupling_features.py`:
- Backtest las Refs-Wolke aus `backtest_data/own_bibliography/refs_resolved.json`
  (Snapshot, 275 OA-IDs, einmaliger 109-PDF-Snapshot).
- Diese Validierung liest die Wolke aus `own_refs.db` (Produktiv-Index,
  multi-source, additiv-inkrementell, MOJO 2.0 §1).

Ausgabe:
  1) Index-Summary (oa_ids, dois, n_pubs)
  2) Article-Refs-Coverage (wie viele Artikel haben openalex_refs / crossref_refs)
  3) Per-Klasse Hit-Rate für `f_own_coupling_union ≥ 1` (LES/SCN/IGN)
  4) Veto-Up-Wirkung: wieviele Artikel würden durch die neue Regel von
     `discourse_indicator != starker_indikator` → `starker_indikator` heben?
  5) Optional: Drift-Check zwischen Snapshot-Wolke und Produktiv-Index.

Keine Schreib-Operationen — pure Diagnostik.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from journal_bot.own_refs.corpus_freq import load_or_compute_corpus_freq
from journal_bot.own_refs.index import load_own_refs_index
from journal_bot.signals import (
    OWN_COUPLING_STRONG_SCORE, OWN_COUPLING_WEAK_SCORE, signal_own_coupling,
)


ARTICLES_DB = PROJECT_ROOT / "articles.db"
OWN_REFS_DB = PROJECT_ROOT / "own_refs.db"
SNAPSHOT = PROJECT_ROOT / "backtest_data" / "own_bibliography" / "refs_resolved.json"


def _load_articles() -> list[dict]:
    con = sqlite3.connect(str(ARTICLES_DB))
    con.row_factory = sqlite3.Row
    rows = con.execute(
        """
        SELECT id, title, agent_verdict, user_verdict,
               openalex_refs, crossref_refs,
               selection_mode, discourse_indicator
          FROM articles
         WHERE openalex_refs IS NOT NULL OR crossref_refs IS NOT NULL
        """
    ).fetchall()
    con.close()
    out = []
    for r in rows:
        oa = []
        if r["openalex_refs"]:
            try:
                xs = json.loads(r["openalex_refs"])
                oa = [x for x in xs if isinstance(x, str)]
            except Exception:
                pass
        crefs = []
        if r["crossref_refs"]:
            try:
                xs = json.loads(r["crossref_refs"])
                crefs = [x for x in xs if isinstance(x, dict)]
            except Exception:
                pass
        # user_verdict ist Ground-Truth (wenn vorhanden), agent_verdict ist
        # der Agent-Output. Iter-11 misst die Wirkung gegen user_verdict.
        verdict = r["user_verdict"] or r["agent_verdict"] or ""
        out.append({
            "id": r["id"],
            "title": r["title"],
            "verdict": verdict,
            "verdict_source": "user" if r["user_verdict"] else ("agent" if r["agent_verdict"] else "none"),
            "selection_mode": r["selection_mode"] or "",
            "discourse_indicator": r["discourse_indicator"] or "",
            "openalex_refs": oa,
            "crossref_refs": crefs,
        })
    return out


def main() -> int:
    if not ARTICLES_DB.exists():
        sys.exit(f"articles.db fehlt: {ARTICLES_DB}")
    if not OWN_REFS_DB.exists():
        sys.exit(f"own_refs.db fehlt: {OWN_REFS_DB} — erst `mojo refs build` laufen lassen.")

    idx = load_own_refs_index(OWN_REFS_DB)
    freq = load_or_compute_corpus_freq(ARTICLES_DB, idx)
    print("=== Refs-Index (produktiv, aus own_refs.db) ===")
    print(f"  {idx.summary}")
    print(f"  {freq.summary}")
    print(f"  Schwellen: WEAK={OWN_COUPLING_WEAK_SCORE:.2f}  STRONG={OWN_COUPLING_STRONG_SCORE:.2f}")
    print()

    arts = _load_articles()
    n_total_db = sqlite3.connect(str(ARTICLES_DB)).execute(
        "SELECT COUNT(*) FROM articles"
    ).fetchone()[0]
    print(f"=== Article-Refs-Coverage (articles.db: {n_total_db} total) ===")
    n_with_oa = sum(1 for a in arts if a["openalex_refs"])
    n_with_cr = sum(1 for a in arts if a["crossref_refs"])
    n_either = len(arts)
    print(f"  mit openalex_refs:  {n_with_oa:>6} ({100*n_with_oa/n_total_db:.1f} %)")
    print(f"  mit crossref_refs:  {n_with_cr:>6} ({100*n_with_cr/n_total_db:.1f} %)")
    print(f"  mit min. einem:     {n_either:>6} ({100*n_either/n_total_db:.1f} %)")
    print()

    # Per-Article Coupling-Scores berechnen
    scores_by_verdict: dict[str, list[float]] = {
        "lesenswert": [], "scannen": [], "ignorieren": [], "(no verdict)": []
    }
    n_weak = 0
    n_strong = 0
    lifts_strong = 0
    lifts_weak = 0
    selection_mode_changes_strong = Counter()
    selection_mode_changes_weak = Counter()
    examples_strong: list[dict] = []
    examples_bestseller: list[dict] = []

    for a in arts:
        sig = signal_own_coupling(a["crossref_refs"], a["openalex_refs"], idx, freq)
        score = float(sig.get("score", 0.0))
        bucket = a["verdict"] or "(no verdict)"
        scores_by_verdict.setdefault(bucket, []).append(score)

        # Bestseller-Demonstrationsfälle (n_union ≥ 1, aber Score unter WEAK)
        if sig.get("n_union", 0) >= 1 and score < OWN_COUPLING_WEAK_SCORE and len(examples_bestseller) < 5:
            examples_bestseller.append({
                "id": a["id"][:30],
                "score": round(score, 3),
                "hits": (sig.get("oa_hits", []) + sig.get("doi_hits", []))[:2],
            })

        if score >= OWN_COUPLING_STRONG_SCORE:
            n_strong += 1
            if a["discourse_indicator"] != "starker_indikator":
                lifts_strong += 1
                selection_mode_changes_strong[(a["selection_mode"], a["verdict"])] += 1
                if len(examples_strong) < 5:
                    examples_strong.append({
                        "id": a["id"][:30],
                        "verdict": a["verdict"],
                        "selection_mode": a["selection_mode"],
                        "score": round(score, 3),
                        "oa_hits": sig.get("oa_hits", [])[:3],
                        "doi_hits": sig.get("doi_hits", [])[:3],
                    })
        elif score >= OWN_COUPLING_WEAK_SCORE:
            n_weak += 1
            if a["discourse_indicator"] not in ("starker_indikator", "schwacher_indikator"):
                lifts_weak += 1
                selection_mode_changes_weak[(a["selection_mode"], a["verdict"])] += 1

    print("=== Per-Verdict Score-Statistik (IDF-gewichtet) ===")
    print(f"{'Verdict':<18}{'N total':>10}{'N weak':>10}{'N strong':>10}{'LES/IGN':>10}")
    les = scores_by_verdict.get("lesenswert", [])
    ign = scores_by_verdict.get("ignorieren", [])
    for thr, label in [(OWN_COUPLING_WEAK_SCORE, "weak"), (OWN_COUPLING_STRONG_SCORE, "strong")]:
        les_hit = sum(1 for x in les if x >= thr)
        ign_hit = sum(1 for x in ign if x >= thr)
        les_r = les_hit / max(1, len(les))
        ign_r = ign_hit / max(1, len(ign))
        ratio = les_r / ign_r if ign_r else float("inf")
        print(f"  Score ≥ {thr:.2f} ({label}): LES {les_hit}/{len(les)} ({100*les_r:.1f}%)  "
              f"IGN {ign_hit}/{len(ign)} ({100*ign_r:.1f}%)  Ratio {ratio:.1f}x")
    print()

    print("=== Veto-Up-Wirkung (IDF-gewichtet, §2.1b) ===")
    print(f"  Artikel mit Score ≥ STRONG ({OWN_COUPLING_STRONG_SCORE:.2f}): {n_strong:>6}")
    print(f"  Davon Lift zu starker_indikator:              {lifts_strong:>6}")
    print(f"  Artikel mit Score ≥ WEAK ({OWN_COUPLING_WEAK_SCORE:.2f}) <STRONG: {n_weak:>6}")
    print(f"  Davon Lift zu schwacher_indikator:            {lifts_weak:>6}")
    print()
    print("  Vergleich zur primitiven Pre-§2.1b-Regel (n_union ≥ 1):")
    print(f"    Damals: 969 Artikel, 623 davon zu starker_indikator gehoben.")
    print(f"    Jetzt:  {n_strong} starker + {n_weak} schwacher = {n_strong+n_weak} insgesamt.")
    print()

    if examples_bestseller:
        print("=== Bestseller-Hits, die jetzt KEINEN Lift mehr triggern ===")
        for ex in examples_bestseller:
            print(f"  id={ex['id']:<30}  score={ex['score']:.3f} (unter WEAK)  hits={ex['hits']}")
        print()

    if examples_strong:
        print("=== Beispiele für Score≥STRONG (echte Lifts) ===")
        for ex in examples_strong:
            print(f"  id={ex['id']:<30}  verdict={ex['verdict']:<11}  score={ex['score']:.3f}")
            if ex["oa_hits"]:
                print(f"    oa: {ex['oa_hits']}")
            if ex["doi_hits"]:
                print(f"    doi: {ex['doi_hits']}")
        print()

    if selection_mode_changes_strong:
        print("=== STRONG-Lifts nach (alter_mode, verdict) ===")
        for (mode, verdict), n in selection_mode_changes_strong.most_common(10):
            print(f"  ({mode or 'none':<14}, {verdict or 'none':<11}) → n={n}")
        print()


    # Drift-Check gegen Snapshot
    if SNAPSHOT.exists():
        snap = json.loads(SNAPSHOT.read_text())
        snap_oa = {x.rsplit("/", 1)[-1] for x in (snap.get("all_own_ref_oa_ids") or []) if x}
        snap_doi = {d.lower().rstrip(".") for d in (snap.get("all_own_ref_dois") or []) if d}
        only_snap_oa = snap_oa - idx.oa_ids
        only_prod_oa = idx.oa_ids - snap_oa
        print("=== Drift-Check: Snapshot vs. Produktiv-Index ===")
        print(f"  Snapshot OA: {len(snap_oa):>6}  Prod OA: {len(idx.oa_ids):>6}")
        print(f"  Snapshot DOI: {len(snap_doi):>6}  Prod DOI: {len(idx.dois):>6}")
        print(f"  ∩ OA-IDs:       {len(snap_oa & idx.oa_ids):>6}")
        print(f"  nur Snapshot OA:{len(only_snap_oa):>6}")
        print(f"  nur Prod OA:    {len(only_prod_oa):>6}")
        if only_snap_oa:
            print(f"    Beispiele snap-only: {sorted(only_snap_oa)[:3]}")
        if only_prod_oa:
            print(f"    Beispiele prod-only: {sorted(only_prod_oa)[:3]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
