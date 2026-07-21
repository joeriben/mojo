#!/usr/bin/env python3
"""Ehrlichkeitsprüfung des semantischen Vorfilters, bevor er verdrahtet wird.

Zwei Fallen, die der Bau-Lauf noch offen lässt:

1. **Schwellen auf denselben Daten gewählt wie gemessen.** Die Zonen wurden auf
   den OOF-Scores aller 913 kalibriert und dann auf denselben 913 bewertet — ein
   milder Optimismus. Hier werden Schwellen auf einer Hälfte gewählt und auf der
   anderen bewertet.

2. **Gemischter Kanal.** Die Behalten-Quote schwankt über den Kanal von 15 % bis
   85 %. Der Betriebsfall neuer Wochenartikel ist der Screening-Kanal. Der
   Auto-Verwerf-Wert wird deshalb PRO Kanal ausgewiesen, nicht nur gemittelt.

Beides frei (nur lokales Embedding), reproduziert aus dem Cache des Bau-Laufs.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from kriterienfilter_build import (  # noqa: E402
    artikel_embeddings, eigenwerk_naehe, lade_urteile, oof_scores,
)


def schwellen_aus(oof: np.ndarray, y: np.ndarray, lese: np.ndarray,
                  max_lese_verlust=0.05, keep_dichte=0.80):
    order = np.argsort(oof)
    max_verlust = max(1, int(max_lese_verlust * lese.sum()))
    kum = np.cumsum(lese[order])
    idx = np.searchsorted(kum, max_verlust + 1)
    u = oof[order[min(idx, len(oof) - 1)]]
    kand = [t for t in np.quantile(oof, np.linspace(0.5, 0.98, 40))
            if (oof >= t).sum() >= 15 and y[oof >= t].mean() >= keep_dichte]
    o = min(kand) if kand else float(oof.max() + 1)
    return u, o


def main() -> int:
    daten = lade_urteile()
    y = np.array([d["behalten"] for d in daten])
    lese = np.array([d["lesenswert"] for d in daten])
    kanal = np.array([d["kanal"] for d in daten])
    emb = artikel_embeddings(daten)
    X = np.hstack([emb, eigenwerk_naehe(emb)])

    # --- (1) Held-out-Schwellen: kalibrieren auf A, bewerten auf B -------------
    rng = np.random.default_rng(5)
    idx = rng.permutation(len(daten))
    A, B = idx[: len(idx) // 2], idx[len(idx) // 2:]
    oof_A = oof_scores(X[A], y[A])
    u, o = schwellen_aus(oof_A, y[A], lese[A])

    # Auf B mit einem Modell scoren, das B nie gesehen hat (auf A trainiert).
    from sklearn.linear_model import LogisticRegression
    m = LogisticRegression(C=1.0, max_iter=3000, class_weight="balanced").fit(X[A], y[A])
    score_B = m.predict_proba(X[B])[:, 1]
    drop_B = score_B < u
    print("(1) Schwellen auf Hälfte A gewählt, auf Hälfte B bewertet — kein "
          "Selbstbezug:")
    print(f"    Auto-Verwerfen {drop_B.mean():.0%} der Artikel · "
          f"verliert {int(lese[B][drop_B].sum())}/{int(lese[B].sum())} lesenswert "
          f"= {lese[B][drop_B].sum()/max(1,lese[B].sum()):.1%}")
    print(f"    Trefferdichte im Wegwurf {y[B][drop_B].mean():.1%} gegen "
          f"{y[B].mean():.1%} gesamt\n")

    # --- (2) Auto-Verwerfen PRO Kanal, Schwelle aus dem Rest ------------------
    oof_all = oof_scores(X, y)
    u_all, _ = schwellen_aus(oof_all, y, lese)
    print(f"(2) Auto-Verwerfen je Kanal (globale Schwelle {u_all:.3f}):")
    print(f"    {'Kanal':<16}{'n':>5}{'behalten':>10}{'verworfen':>11}"
          f"{'lesenswert-Verlust':>20}{'Dichte Wegwurf':>16}")
    for k in sorted(set(kanal), key=lambda z: -(kanal == z).sum()):
        m_ = kanal == k
        if m_.sum() < 20:
            continue
        d = m_ & (oof_all < u_all)
        vlese = int(lese[m_ & (oof_all < u_all)].sum())
        glese = int(lese[m_].sum())
        print(f"    {k:<16}{m_.sum():>5}{y[m_].mean():>9.0%}"
              f"{d.sum():>7} ({d.sum()/m_.sum():>3.0%}){vlese:>10}/{glese:<3} "
              f"= {vlese/max(1,glese):>4.0%}{y[d].mean() if d.sum() else 0:>13.0%}")

    # Was der Screening-Kanal allein sagt — der Betriebsfall.
    scr = kanal == "screening"
    d_scr = scr & (oof_all < u_all)
    print(f"\n    Betriebsfall Screening-Kanal: von {scr.sum()} Artikeln würden "
          f"{d_scr.sum()} ohne LLM verworfen,")
    print(f"    dabei {int(lese[d_scr].sum())} von {int(lese[scr].sum())} "
          f"lesenswert verloren; Screening-Grundrate behalten {y[scr].mean():.0%}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
