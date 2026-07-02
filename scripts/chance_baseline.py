"""Zufallsboden für die 3-Klassen-Macro-F1 (Benjamins Frage: ist 0,588 ~ Zufall 0,5?).

0,5 ist die Schwelle für BINÄRE Accuracy. Die Triage-Zahl ist Macro-F1 über drei
Klassen (LES/SCAN/IGN) bei schiefer Verteilung. Dieses Skript misst empirisch, was
verschiedene Zufalls-/Trivial-Strategien an Macro-F1 erreichen — der ehrliche Boden.
"""

from __future__ import annotations

import sqlite3
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from sklearn.metrics import f1_score

ROOT = Path(__file__).resolve().parent.parent
ARTICLES_DB = ROOT / "articles.db"
TRIALS = 2000
RNG = np.random.default_rng(42)

# Referenzwerte aus den Iterationen
ALGO = 0.588
OPUS = 0.677


def main() -> int:
    con = sqlite3.connect(str(ARTICLES_DB))
    rows = con.execute(
        "SELECT user_verdict FROM articles WHERE user_verdict IS NOT NULL AND user_verdict!=''"
    ).fetchall()
    con.close()
    # 3-Klassen: pflichtlektuere → lesenswert
    m = {"pflichtlektuere": "lesenswert"}
    y = [m.get(r[0], r[0]) for r in rows if r[0] in
         ("lesenswert", "scannen", "ignorieren", "pflichtlektuere")]
    classes = ["lesenswert", "scannen", "ignorieren"]
    y = [v for v in y if v in classes]
    y_arr = np.array(y)
    n = len(y_arr)
    dist = Counter(y)
    probs = np.array([dist[c] / n for c in classes])
    print(f"Ground-Truth-Labels: n={n}")
    for c in classes:
        print(f"   {c:<12}: {dist[c]:>4}  ({100*dist[c]/n:.0f}%)")
    print()

    def macro(y_pred):
        return f1_score(y_arr, y_pred, labels=classes, average="macro", zero_division=0)

    # 1) Majority (immer IGN)
    maj_class = max(classes, key=lambda c: dist[c])
    maj = macro(np.array([maj_class] * n))

    # 2) Uniform random (1/3 je Klasse)
    uni = np.mean([macro(RNG.choice(classes, size=n)) for _ in range(TRIALS)])

    # 3) Stratified random (nach Klassen-Häufigkeit)
    strat = np.mean([macro(RNG.choice(classes, size=n, p=probs)) for _ in range(TRIALS)])

    print(f"{'Strategie':<28} {'Macro-F1':>9}")
    print("-" * 40)
    print(f"{'Majority (immer ' + maj_class[:3] + '.)':<28} {maj:>9.3f}")
    print(f"{'Uniform-Zufall (1/3)':<28} {uni:>9.3f}")
    print(f"{'Stratifiziert-Zufall':<28} {strat:>9.3f}")
    print(f"{'— Algorithmus (Iter 11)':<28} {ALGO:>9.3f}")
    print(f"{'— Opus':<28} {OPUS:>9.3f}")
    print(f"{'— perfekt':<28} {1.0:>9.3f}")
    floor = max(maj, uni, strat)
    print(f"\nZufalls-/Trivialboden ≈ {floor:.3f}  (NICHT 0,5).")
    print(f"Algo liegt {ALGO-floor:+.3f} über dem Boden, erreicht {100*ALGO/OPUS:.0f}% von Opus.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
