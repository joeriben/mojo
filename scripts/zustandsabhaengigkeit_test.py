#!/usr/bin/env python3
"""Hängt das Auswahlkriterium vom Ort ab — abgeleitet, nicht gesetzt?

Die These „im Kernfeld zählt etwas anderes als an der Peripherie" ist eine
Interaktionsbehauptung: dasselbe Merkmal hat je nach Zeitschrift ein anderes
Gewicht. Das ist prüfbar, ohne irgendeine Struktur vorher zu setzen.

Für jede Zeitschrift mit genug Urteilen wird ausserhalb der Anpassung
vorhergesagt, mit drei Modellen:

  A  nur die Basisrate der Zeitschrift          (das Nullmodell, AUC 0.675)
  B  ein global angepasstes Merkmalsmodell      (ein Kriterium für alle)
  C  ein je Zeitschrift angepasstes Modell      (Kriterium wechselt mit dem Ort)

Schlägt C das Modell B, dann wechselt das Kriterium mit dem Ort — und die
Gewichte aus C sagen, wie. Schlägt es B nicht, gibt es ein Kriterium und die
Zustandsthese fällt. Beides ist ein Ergebnis.

Merkmale kommen ausschliesslich aus OpenAlex (Topics, Concepts) und aus der
Literaturliste. Kein Modellaufruf, keine gesetzte Kategorie, keine
Selbstauskunft.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold

ROOT = Path(__file__).resolve().parent.parent
MIN_URTEILE = 45          # unter dieser Zahl ist lokales Anpassen sinnlos
MIN_MERKMAL = 8           # Merkmal muss oft genug vorkommen
TOPIC_SCHWELLE = 0.10


def lade() -> list[dict]:
    con = sqlite3.connect(f"file:{ROOT / 'articles.db'}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    zeilen = con.execute(
        "SELECT id, journal_short, user_verdict, openalex_topics, openalex_concepts,"
        "       openalex_refs, crossref_refs, year, selection_mode"
        " FROM articles WHERE user_verdict IS NOT NULL"
    ).fetchall()
    con.close()

    aus = []
    for r in zeilen:
        merkmale = set()
        for feld, praefix in (("openalex_topics", "T"), ("openalex_concepts", "C")):
            try:
                for e in json.loads(r[feld] or "[]"):
                    if isinstance(e, dict) and float(e.get("score") or 0) >= TOPIC_SCHWELLE:
                        merkmale.add(f"{praefix}:{e.get('name')}")
            except (json.JSONDecodeError, TypeError, ValueError):
                pass
        try:
            n_refs = len(json.loads(r["crossref_refs"] or "[]"))
        except json.JSONDecodeError:
            n_refs = 0
        aus.append({
            "id": r["id"],
            "journal": r["journal_short"],
            "kanal": r["selection_mode"] or "unbekannt",
            "behalten": int(r["user_verdict"] in ("scannen", "lesenswert", "pflichtlektuere")),
            "merkmale": merkmale,
            "n_refs": n_refs,
            "jahr": r["year"] or 0,
        })
    return aus


def matrix(daten: list[dict], vokabular: list[str]) -> np.ndarray:
    idx = {m: i for i, m in enumerate(vokabular)}
    X = np.zeros((len(daten), len(vokabular) + 2))
    for i, d in enumerate(daten):
        for m in d["merkmale"]:
            j = idx.get(m)
            if j is not None:
                X[i, j] = 1.0
        X[i, -2] = np.log1p(d["n_refs"])
        X[i, -1] = (d["jahr"] - 2015) / 10.0 if d["jahr"] else 0.0
    return X


def oof(X: np.ndarray, y: np.ndarray, folds: int = 5, C: float = 0.3) -> np.ndarray:
    """Vorhersage ausserhalb der Anpassung — je Fall aus einem Modell,
    das diesen Fall nie gesehen hat."""
    p = np.zeros(len(y))
    if len(np.unique(y)) < 2:
        return p + y.mean()
    k = min(folds, int(min(np.bincount(y))))
    if k < 2:
        return p + y.mean()
    for tr, te in StratifiedKFold(n_splits=k, shuffle=True, random_state=17).split(X, y):
        if len(np.unique(y[tr])) < 2:
            p[te] = y[tr].mean()
            continue
        m = LogisticRegression(C=C, max_iter=2000, class_weight="balanced")
        m.fit(X[tr], y[tr])
        p[te] = m.predict_proba(X[te])[:, 1]
    return p


def main() -> int:
    daten = lade()
    y_all = np.array([d["behalten"] for d in daten])
    print(f"{len(daten)} Urteile · {y_all.mean():.1%} behalten "
          f"· {len({d['journal'] for d in daten})} Zeitschriften\n")

    haeufig = Counter(m for d in daten for m in d["merkmale"])
    vokabular = sorted(m for m, n in haeufig.items() if n >= MIN_MERKMAL)
    print(f"{len(vokabular)} Merkmale mit ≥{MIN_MERKMAL} Vorkommen "
          f"(aus {len(haeufig)} beobachteten)\n")

    X_all = matrix(daten, vokabular)
    journale = [d["journal"] for d in daten]

    # --- Modell B: ein Kriterium für alle, ausserhalb der Anpassung -----------
    p_global = oof(X_all, y_all)

    zaehl = Counter(journale)
    kandidaten = [j for j, n in zaehl.items() if n >= MIN_URTEILE]
    kandidaten.sort(key=lambda j: -zaehl[j])

    print(f"{'Zeitschrift':<14}{'n':>5}{'behalten':>10}"
          f"{'A Basisrate':>13}{'B global':>10}{'C lokal':>9}{'C−B':>8}")
    print("-" * 69)

    zeilen_erg = []
    for j in kandidaten:
        maske = np.array([x == j for x in journale])
        y = y_all[maske]
        if len(np.unique(y)) < 2:
            continue
        Xj = X_all[maske]

        # A: Basisrate ist innerhalb einer Zeitschrift konstant → AUC 0.5.
        #    Der Wert steht nur da, um die Bezugsgrösse sichtbar zu halten.
        auc_a = 0.5
        auc_b = roc_auc_score(y, p_global[maske])
        auc_c = roc_auc_score(y, oof(Xj, y))
        zeilen_erg.append((j, len(y), y.mean(), auc_b, auc_c))
        print(f"{j:<14}{len(y):>5}{y.mean():>9.1%}"
              f"{auc_a:>13.3f}{auc_b:>10.3f}{auc_c:>9.3f}{auc_c - auc_b:>+8.3f}")

    if zeilen_erg:
        gew = sum(n for _, n, _, _, _ in zeilen_erg)
        mb = sum(n * b for _, n, _, b, _ in zeilen_erg) / gew
        mc = sum(n * c for _, n, _, _, c in zeilen_erg) / gew
        print("-" * 69)
        print(f"{'gewichtet':<14}{gew:>5}{'':>9}{'':>13}{mb:>10.3f}{mc:>9.3f}{mc - mb:>+8.3f}")

    # --- Welche Merkmale tragen wo? Nur wenn C überhaupt etwas kann. ---------
    print("\nStärkste Merkmale je Zeitschrift (auf allen Daten der Zeitschrift "
          "angepasst — beschreibend, nicht geprüft):")
    for j, n, _, _, _ in zeilen_erg:
        maske = np.array([x == j for x in journale])
        y, Xj = y_all[maske], X_all[maske]
        lokal = [i for i in range(len(vokabular)) if Xj[:, i].sum() >= 5]
        if len(np.unique(y)) < 2 or not lokal:
            continue
        m = LogisticRegression(C=0.3, max_iter=2000, class_weight="balanced")
        m.fit(Xj, y)
        w = [(m.coef_[0][i], vokabular[i], int(Xj[:, i].sum())) for i in lokal]
        w.sort(key=lambda t: -abs(t[0]))
        oben = ", ".join(f"{name.split(':', 1)[1][:34]} {koef:+.2f} (n={k})"
                         for koef, name, k in w[:3])
        print(f"  {j:<12} {oben}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
