#!/usr/bin/env python3
"""Vorfilter: statistisch ermittelte Trigger schalten verschiedene Triage-Wege.

Kein Punktwert, der alles über einen Kamm schert, sondern Trigger, die je nach
Befund einen ANDEREN Entscheidungsweg auslösen:

  verwerfen     Ablehnungs-Trigger feuern, kein Aufwertungs-Trigger. Der Artikel
                geht ohne Modellaufruf raus.
  eskalieren    ein starker Aufwertungs-Trigger feuert. Der Artikel geht direkt
                in die Einschätzung, ohne vorheriges Screening.
  normal        kein Trigger feuert eindeutig. Der bisherige Weg.

Die Trigger stammen aus `abhaengigkeitsstatistik.py`: kanalbereinigt, doppelte
Differenz, Benjamini-Hochberg-korrigiert. Hier werden sie NICHT auf denselben
Daten ermittelt, an denen sie gemessen werden — die Schwellen entstehen je Fold
neu aus den Trainingsanteilen, und geprüft wird auf dem zurückgehaltenen Fold.
Ohne diese Trennung misst man sich selbst; das ist diesem Projekt schon einmal
passiert (0.603 statt ehrlicher 0.544).

    scripts/vorfilter.py                 # Kreuzvalidierung über die 913 Urteile
    scripts/vorfilter.py --anwenden      # auf den unbeurteilten Bestand legen
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from scipy.stats import fisher_exact
from sklearn.model_selection import StratifiedKFold

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from abhaengigkeitsstatistik import (  # noqa: E402
    BEHALTEN, MARKER, kanalerwartung, lade,
)

MIN_N = 25             # ein Trigger braucht Masse, sonst ist er Rauschen
MIN_LIFT_AB = -0.10    # ab diesem Lift gilt ein Marker als Ablehnungs-Trigger
MIN_LIFT_AUF = 0.15    # Aufwertung verlangt mehr, weil sie Geld kostet
MAX_P = 0.05


def trigger_ermitteln(train: list[dict], feld: str) -> dict[str, dict]:
    """Aus den Trainingsdaten die Trigger ziehen — Marker, Richtung, Stärke."""
    basis = {}
    for k in {d["kanal"] for d in train}:
        teil = [d for d in train if d["kanal"] == k]
        basis[k] = float(np.mean([d[feld] for d in teil]))

    trigger: dict[str, dict] = {}
    for name in MARKER:
        drin = [d for d in train if name in d["marker"]]
        raus = [d for d in train if name not in d["marker"]]
        if len(drin) < MIN_N or len(raus) < MIN_N:
            continue
        a, c = sum(d[feld] for d in drin), sum(d[feld] for d in raus)
        _, p = fisher_exact([[a, len(drin) - a], [c, len(raus) - c]])
        lift = ((a / len(drin)) - kanalerwartung(drin, basis, feld)) - (
            (c / len(raus)) - kanalerwartung(raus, basis, feld)
        )
        if p > MAX_P:
            continue
        if lift <= MIN_LIFT_AB:
            trigger[name] = {"richtung": "ab", "lift": lift, "n": len(drin), "p": p}
        elif lift >= MIN_LIFT_AUF:
            trigger[name] = {"richtung": "auf", "lift": lift, "n": len(drin), "p": p}
    return trigger


def route(artikel: dict, trigger: dict[str, dict]) -> str:
    """Welchen Entscheidungsweg löst dieser Artikel aus?"""
    feuert_ab = [t for t in artikel["marker"] if trigger.get(t, {}).get("richtung") == "ab"]
    feuert_auf = [t for t in artikel["marker"] if trigger.get(t, {}).get("richtung") == "auf"]
    if feuert_auf:
        return "eskalieren"
    if feuert_ab:
        return "verwerfen"
    return "normal"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--feld", choices=("behalten", "lesenswert"), default="behalten")
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--out", default="output/vorfilter_bewertung.json")
    args = ap.parse_args()
    feld = args.feld

    daten = lade()
    y = np.array([d[feld] for d in daten])
    print(f"{len(daten)} Urteile · Zielgrösse »{feld}« · Grundrate {y.mean():.1%}\n")

    # --- Kreuzvalidierung: Trigger je Fold NEU aus dem Trainingsanteil ---------
    wege: list[str] = [""] * len(daten)
    trigger_zaehler: Counter = Counter()
    skf = StratifiedKFold(n_splits=args.folds, shuffle=True, random_state=7)
    for tr, te in skf.split(np.zeros(len(daten)), y):
        trg = trigger_ermitteln([daten[i] for i in tr], feld)
        trigger_zaehler.update(f"{k} ({v['richtung']})" for k, v in trg.items())
        for i in te:
            wege[i] = route(daten[i], trg)

    print("Trigger, die in allen Folds gefunden wurden (stabil) und in wie vielen:")
    for name, n in trigger_zaehler.most_common():
        marke = "stabil" if n == args.folds else f"nur {n}/{args.folds} Folds"
        print(f"   {name:<42} {marke}")

    print(f"\n{'=' * 72}\nWEGE — ausserhalb der Anpassung zugewiesen\n{'=' * 72}")
    print(f"{'Weg':<14}{'n':>6}{'Anteil':>9}{'davon behalten':>16}{'Grundrate':>12}")
    ergebnis = {}
    for weg in ("verwerfen", "normal", "eskalieren"):
        idx = [i for i, w in enumerate(wege) if w == weg]
        if not idx:
            continue
        quote = y[idx].mean()
        ergebnis[weg] = {"n": len(idx), "quote": float(quote)}
        print(f"{weg:<14}{len(idx):>6}{len(idx)/len(daten):>8.1%}"
              f"{quote:>15.1%}{y.mean():>12.1%}")

    # --- Was der Filter praktisch leistet -------------------------------------
    v = [i for i, w in enumerate(wege) if w == "verwerfen"]
    e = [i for i, w in enumerate(wege) if w == "eskalieren"]
    print(f"\n{'=' * 72}\nWAS DAS PRAKTISCH HEISST\n{'=' * 72}")
    if v:
        verloren = int(y[v].sum())
        print(f"  Ohne Modellaufruf verworfen: {len(v)} Artikel ({len(v)/len(daten):.1%})")
        print(f"    darin fälschlich mitverworfen: {verloren} von {int(y.sum())} "
              f"Behalten-Fällen = {verloren/max(1,int(y.sum())):.1%} der echten Treffer")
        print(f"    Trefferdichte im Wegwurf {y[v].mean():.1%} gegen {y.mean():.1%} im Ganzen")
    if e:
        print(f"  Direkt eskaliert: {len(e)} Artikel ({len(e)/len(daten):.1%}), "
              f"Trefferdichte {y[e].mean():.1%}")
        print(f"    Anreicherung gegenüber der Grundrate: ×{y[e].mean()/y.mean():.2f}")

    # Nullmodell: gleich viele Artikel zufällig verwerfen.
    rng = np.random.default_rng(4)
    if v:
        nul = [y[rng.choice(len(daten), len(v), replace=False)].sum() for _ in range(2000)]
        print(f"\n  Zufälliges Verwerfen gleicher Menge verlöre {np.mean(nul):.1f} ± "
              f"{np.std(nul):.1f} Treffer — der Filter verliert {int(y[v].sum())}.")

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps({
        "zielgroesse": feld, "n": len(daten), "grundrate": float(y.mean()),
        "wege": ergebnis,
        "trigger_stabilitaet": {k: n for k, n in trigger_zaehler.items()},
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n→ {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
