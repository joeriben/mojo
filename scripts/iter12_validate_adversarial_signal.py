"""§2.2 Live-Verifikation: adversariales Blind-Spot-Signal auf articles.db.

Misst:
  1) Größe und Zusammensetzung des Adversarial-Sets (trigger_refs \\ benjamin)
  2) Per-Verdict-Verteilung des IDF-gewichteten Adversarial-Scores
  3) Wirkung der Schwellen ADVERSARIAL_WEAK_SCORE / ADVERSARIAL_STRONG_SCORE
  4) Wrong-LES-Recovery (Artikel, die user=LES aber agent != LES, durch
     adversarial-Veto-Up gerettet werden würden)
  5) Top-Beispiele für STRONG-Lifts

Keine Schreib-Operationen, nur Diagnostik.
"""

from __future__ import annotations

import json
import sqlite3
import statistics
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from journal_bot.adversarial.corpus_freq import load_or_compute_adversarial_corpus_freq
from journal_bot.adversarial.trigger_refs import load_or_compute_adversarial_index
from journal_bot.own_refs.index import load_own_refs_index
from journal_bot.signals import (
    ADVERSARIAL_STRONG_SCORE, ADVERSARIAL_WEAK_SCORE, signal_adversarial_blindspot,
)

ARTICLES_DB = PROJECT_ROOT / "articles.db"
OWN_REFS_DB = PROJECT_ROOT / "own_refs.db"
TRIGGER_DIR = PROJECT_ROOT / "backtest_data" / "trigger_bibliographies"


def main() -> int:
    if not ARTICLES_DB.exists():
        sys.exit(f"articles.db fehlt: {ARTICLES_DB}")
    if not OWN_REFS_DB.exists():
        sys.exit(f"own_refs.db fehlt: {OWN_REFS_DB}")
    if not TRIGGER_DIR.exists():
        sys.exit(f"Trigger-Bibliographien fehlen: {TRIGGER_DIR}")

    own_idx = load_own_refs_index(OWN_REFS_DB)
    adv = load_or_compute_adversarial_index(TRIGGER_DIR, own_idx, own_refs_db=OWN_REFS_DB)
    freq = load_or_compute_adversarial_corpus_freq(ARTICLES_DB, adv, own_refs_db=OWN_REFS_DB)

    print("=== Adversarial-Index ===")
    print(f"  {adv.summary}")
    print(f"  {freq.summary}")
    print(f"  Schwellen: WEAK={ADVERSARIAL_WEAK_SCORE:.2f}  STRONG={ADVERSARIAL_STRONG_SCORE:.2f}")
    print()

    con = sqlite3.connect(str(ARTICLES_DB))
    con.row_factory = sqlite3.Row
    rows = con.execute(
        """
        SELECT id, title, user_verdict, agent_verdict,
               openalex_refs, selection_mode, discourse_indicator
          FROM articles
        """
    ).fetchall()
    con.close()

    scores = {"lesenswert": [], "scannen": [], "ignorieren": [], "(no verdict)": []}
    n_strong = n_weak = 0
    strong_lifts: list[dict] = []
    weak_lifts_count = 0
    selection_modes_changed = Counter()
    wrong_les_recovered_strong = 0
    wrong_les_recovered_weak = 0
    wrong_les_total = 0
    bestseller_examples: list[dict] = []

    for r in rows:
        oa = []
        if r["openalex_refs"]:
            try:
                oa = json.loads(r["openalex_refs"])
            except json.JSONDecodeError:
                pass
        sig = signal_adversarial_blindspot(oa, adv, freq)
        score = float(sig.get("score", 0.0))
        verdict = r["user_verdict"] or r["agent_verdict"] or ""
        bucket = verdict if verdict in scores else "(no verdict)"
        scores[bucket].append(score)

        # Bestseller-Hits demonstrieren (kleiner Score, viele Hits)
        n_hits = int(sig.get("n_hits", 0))
        if n_hits >= 2 and score < ADVERSARIAL_WEAK_SCORE and len(bestseller_examples) < 3:
            bestseller_examples.append({
                "id": r["id"][:24],
                "n_hits": n_hits,
                "score": round(score, 3),
            })

        if score >= ADVERSARIAL_STRONG_SCORE:
            n_strong += 1
            if r["discourse_indicator"] != "starker_indikator":
                selection_modes_changed[(r["selection_mode"] or "none", verdict)] += 1
                if len(strong_lifts) < 5:
                    strong_lifts.append({
                        "id": r["id"][:24],
                        "title": (r["title"] or "")[:80],
                        "verdict": verdict,
                        "selection_mode": r["selection_mode"],
                        "score": round(score, 3),
                        "n_hits": n_hits,
                    })
        elif score >= ADVERSARIAL_WEAK_SCORE:
            n_weak += 1
            if r["discourse_indicator"] not in ("starker_indikator", "schwacher_indikator"):
                weak_lifts_count += 1

        # Wrong-LES (user=LES, agent != LES)
        if r["user_verdict"] == "lesenswert" and (r["agent_verdict"] or "") != "lesenswert":
            wrong_les_total += 1
            if score >= ADVERSARIAL_STRONG_SCORE:
                wrong_les_recovered_strong += 1
            elif score >= ADVERSARIAL_WEAK_SCORE:
                wrong_les_recovered_weak += 1

    print("=== Per-Verdict Score-Statistik ===")
    for v in ["lesenswert", "scannen", "ignorieren"]:
        s = sorted(scores[v])
        nz = [x for x in s if x > 0]
        if not nz:
            continue
        median = statistics.median(nz)
        print(f"  {v:<12} N={len(s):>5}  nonzero={len(nz):>5}  median={median:.2f}  max={max(s):.2f}")
    print()

    print("=== Schwellen-Wirkung ===")
    for thr, label in [(ADVERSARIAL_WEAK_SCORE, "WEAK"),
                       (ADVERSARIAL_STRONG_SCORE, "STRONG")]:
        les_hit = sum(1 for x in scores["lesenswert"] if x >= thr)
        ign_hit = sum(1 for x in scores["ignorieren"] if x >= thr)
        les_r = les_hit / max(1, len(scores["lesenswert"]))
        ign_r = ign_hit / max(1, len(scores["ignorieren"]))
        ratio = les_r / ign_r if ign_r else float("inf")
        print(f"  Score ≥ {thr:.2f} ({label}): "
              f"LES {les_hit}/{len(scores['lesenswert'])} ({100*les_r:.1f}%)  "
              f"IGN {ign_hit}/{len(scores['ignorieren'])} ({100*ign_r:.1f}%)  "
              f"Ratio {ratio:.1f}x")
    print()

    print("=== Cascade-Lifts (produktiv) ===")
    print(f"  STRONG (score ≥ {ADVERSARIAL_STRONG_SCORE:.2f}): {n_strong} Artikel betroffen")
    print(f"    davon Lift zu starker_indikator: {sum(selection_modes_changed.values())}")
    print(f"  WEAK   (score ≥ {ADVERSARIAL_WEAK_SCORE:.2f}, <STRONG): {n_weak} Artikel betroffen")
    print(f"    davon Lift zu schwacher_indikator: {weak_lifts_count}")
    print()

    print("=== Wrong-LES-Recovery (User=LES, Agent != LES) ===")
    print(f"  Wrong-LES insgesamt: {wrong_les_total}")
    print(f"  Recovery STRONG: {wrong_les_recovered_strong}")
    print(f"  Recovery WEAK:   {wrong_les_recovered_weak}")
    print()

    if bestseller_examples:
        print("=== Bestseller-Demonstration (Hits, aber Score < WEAK) ===")
        for ex in bestseller_examples:
            print(f"  id={ex['id']:<26}  n_hits={ex['n_hits']:>2}  score={ex['score']:.2f}")
        print()

    if strong_lifts:
        print("=== Beispiele für STRONG-Lifts ===")
        for ex in strong_lifts:
            print(f"  id={ex['id']:<26}  verdict={ex['verdict']:<11}  "
                  f"score={ex['score']:.2f}  n_hits={ex['n_hits']}")
            print(f"    title: {ex['title']}")
        print()

    if selection_modes_changed:
        print("=== STRONG-Lifts nach (alter_mode, verdict) ===")
        for (mode, verdict), n in selection_modes_changed.most_common(10):
            print(f"  ({mode:<14}, {verdict:<11}) → n={n}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
