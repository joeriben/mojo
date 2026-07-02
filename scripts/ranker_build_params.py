"""Baut ranker_params.json — eingefrorene M-E-Parameter aus dem Gold-Set.

Rechnet auf den User-Verdikten in articles.db (Ground Truth, kein LLM):
  1. rich_sim live für alle Gold-Artikel (all-MiniLM-L6-v2 gegen die
     Opus-Summaries; identische Text-Rezeptur wie die 50er-Serie).
  2. EB-Journal-Prior (k=5) + globale Keep-Rate G über das Gold-Set.
  3. Eingefrorene z-Parameter (Min/Max von rich, Prior-Lift, mc) — der
     Wochenlauf skaliert damit, nie within-wave.
  4. t_lo = min(finaler mc über alle Gold-LES) − ε: das sicher-DROP-Band
     verliert per Konstruktion kein einziges Gold-LES (iter_46; hier über
     ALLE Gold-LES statt nur blinde → konservativer).

Output: ranker_params.json (Projektroot, gitignored — enthält persönliche
Journal-Keep-Raten) + Report mit Drop-Band-Anteil auf dem blinden Gold-Strom.
Idempotent, $0, ~1 min (Embedding von ~500 Texten).

Usage:
  .venv/bin/python scripts/ranker_build_params.py
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from journal_bot import ranker as rk
from journal_bot.citation_tracker import find_citations, load_authored_all
from journal_bot.signals import load_signal_resources, signal_own_coupling
from journal_bot.store import Store

KEEP = {"lesenswert", "scannen", "pflichtlektuere"}
LES = {"lesenswert", "pflichtlektuere"}


def main() -> int:
    store = Store()
    with store._conn() as c:
        ids = [
            r["id"]
            for r in c.execute(
                "SELECT id FROM articles WHERE user_verdict IS NOT NULL "
                "AND user_verdict != ''"
            )
        ]
    gold = [store.get(i) for i in ids]
    gold = [sa for sa in gold if sa is not None]
    if len(gold) < 100:
        print(f"Zu wenig Gold-Verdikte ({len(gold)}) — Abbruch.")
        return 1
    print(f"Gold-Set: {len(gold)} Artikel mit user_verdict")

    # 1) rich_sim live
    pub_emb = rk.Ranker._pub_embeddings(rk.SUMMARIES_JSON, rk.EMB_CACHE_DIR)
    r = rk.Ranker({"z": {}, "t_lo": 0.0}, pub_emb)
    rich = r.rich_sims(gold)

    # 2) EB-Prior + G
    pairs = [(sa.journal_short, int(sa.user_verdict in KEEP)) for sa in gold]
    prior, g = rk.eb_journal_prior(pairs, k=5)

    # 3) biblio-Flags (own_coupling ≥ 1 ∨ citation ≥ 1)
    resources = load_signal_resources()
    authored = load_authored_all()
    own_idx = resources.get("own_refs_index")
    biblio = {}
    for sa in gold:
        cites = sa.citation_hits or (
            find_citations(sa.crossref_refs, authored) if sa.crossref_refs else []
        )
        coup = signal_own_coupling(sa.crossref_refs, sa.openalex_refs, own_idx)
        biblio[sa.id] = bool(cites) or coup.get("n_union", 0) >= 1

    # 4) z-Parameter einfrieren + mc + t_lo
    rich_min, rich_max = float(rich.min()), float(rich.max())
    lifts = [max(0.0, prior.get(sa.journal_short, g) - g) for sa in gold]
    lift_max = max(lifts) or 1e-9
    z = lambda v, lo, hi: min(1.0, max(0.0, (v - lo) / (hi - lo + 1e-9)))
    mc_pre = [
        z(float(rich[i]), rich_min, rich_max) + 0.5 * z(lifts[i], 0.0, lift_max)
        for i in range(len(gold))
    ]
    mc_min, mc_max = min(mc_pre), max(mc_pre)
    finals = [
        (1.0 if biblio[sa.id] else 0.0) + z(mc_pre[i], mc_min, mc_max)
        for i, sa in enumerate(gold)
    ]
    les_scores = [
        finals[i] for i, sa in enumerate(gold) if sa.user_verdict in LES
    ]
    t_lo = (min(les_scores) - 1e-9) if les_scores else 0.0

    # Report: Drop-Band auf dem blinden Gold-Strom (selection_mode=screening)
    blind = [i for i, sa in enumerate(gold) if sa.selection_mode == "screening"]
    n_drop_blind = sum(1 for i in blind if finals[i] < t_lo)
    keep_dropped = sum(
        1 for i in blind
        if finals[i] < t_lo and gold[i].user_verdict in KEEP
    )
    les_dropped = sum(
        1 for i in blind
        if finals[i] < t_lo and gold[i].user_verdict in LES
    )

    params = {
        "params_version": rk.PARAMS_VERSION,
        "built_at": datetime.now(timezone.utc).isoformat(),
        "model": rk.MODEL_NAME,
        "n_gold": len(gold),
        "n_gold_blind": len(blind),
        "global_keep_rate": round(g, 4),
        "journal_prior": {j: round(v, 4) for j, v in sorted(prior.items())},
        "z": {
            "rich_min": round(rich_min, 6),
            "rich_max": round(rich_max, 6),
            "lift_max": round(lift_max, 6),
            "mc_min": round(mc_min, 6),
            "mc_max": round(mc_max, 6),
        },
        "t_lo": round(t_lo, 6),
        "t_lo_source": "min finaler mc über alle Gold-LES − 1e-9 (iter_46, konservativ)",
        "summaries_hash": rk.summaries_hash(),
    }
    rk.RANKER_PARAMS_JSON.write_text(
        json.dumps(params, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nGeschrieben: {rk.RANKER_PARAMS_JSON}")
    print(f"  G={g:.3f} · Journals im Prior: {len(prior)} · t_lo={t_lo:.4f}")
    print(f"  Drop-Band blind: {n_drop_blind}/{len(blind)} "
          f"({100 * n_drop_blind / max(1, len(blind)):.0f}%) · "
          f"keep darin: {keep_dropped} · LES darin: {les_dropped} (muss 0 sein)")
    if les_dropped:
        print("  ⚠ LES im Drop-Band — Parameter NICHT verwenden (Kalibrierfehler).")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
