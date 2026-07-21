#!/usr/bin/env python3
"""Bringt der semantische Vorfilter im Zusammenspiel mit dem LLM etwas — ehrlich?

Der Filter ist an den 913 Urteilen kalibriert. Auf denselben Urteilen gemessen
wäre er geschönt. Deshalb: Modell auf 70 % bauen, auf den zurückgehaltenen 30 %
prüfen, die der Filter nie gesehen hat.

Verglichen werden zwei Wege, beide gegen das Urteil des Nutzers (verwerfen ja/
nein):

  A  LLM-Screening allein          — der heutige Weg
  B  Vorfilter + LLM-Screening     — Vorfilter verwirft die untere Zone ohne
                                     LLM, der Rest geht wie bisher ins Screening

Gemessen an denselben Testartikeln, mit EINEM Screening-Durchlauf: die vom
Vorfilter verworfenen zählen in B als »ignorieren«, die übrigen bekommen ihr
echtes Screening-Urteil. So kostet die Prüfung nur einen Durchlauf.

Kennzahlen: Übereinstimmung, verlorene Funde (lesenswert fälschlich verworfen),
eingesparte LLM-Aufrufe.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from kriterienfilter_build import (  # noqa: E402
    artikel_embeddings, eigenwerk_naehe, lade_urteile, oof_scores,
)
import journal_bot.agent as agent  # noqa: E402

BEHALTEN = ("scannen", "lesenswert", "pflichtlektuere")


def kanal_schwelle(oof, lese, maske, verlust=0.05) -> float:
    ok, ll = oof[maske], lese[maske]
    if maske.sum() < 20 or ll.sum() == 0:
        return -1.0
    order = np.argsort(ok)
    budget = max(0, int(verlust * ll.sum()))
    kum = np.cumsum(ll[order])
    i = np.searchsorted(kum, budget + 1)
    return float(ok[order[min(i, len(ok) - 1)]])


def main() -> int:
    daten = lade_urteile()
    y = np.array([d["behalten"] for d in daten])
    lese = np.array([d["lesenswert"] for d in daten])
    kanal = np.array([d["kanal"] for d in daten])
    emb = artikel_embeddings(daten)
    X = np.hstack([emb, eigenwerk_naehe(emb)])

    # Spiegelt die BETRIEBSkonfiguration: Modell auf Train, globale Schwelle aus
    # Train-OOF (nicht aus einem kleinen Calib-Teil, der von einzelnen Funden
    # getrieben wird), Bewertung auf zurückgehaltenem Test. Genau so entstehen
    # die Parameter in kriterienfilter_build.py (dort: alle Daten statt Train).
    tr, te = train_test_split(np.arange(len(daten)), test_size=0.30,
                              stratify=y, random_state=13)
    print(f"train {len(tr)} · test {len(te)} (test wird NIE gesehen)\n")

    # EXAKT die Betriebsrechnung (kriterienfilter.py, reine Parameter): Basis-LR
    # plus einzelne Platt-Sigmoid. Die Kalibrierung macht die Schwelle skalen-
    # stabil — ohne sie driftet sie (0.34 → 51 % Fund-Verlust).
    from journal_bot.kriterienfilter import platt_params
    from sklearn.model_selection import cross_val_predict

    mu, sd = X[tr].mean(0), X[tr].std(0) + 1e-9
    Xtr, Xte = (X[tr] - mu) / sd, (X[te] - mu) / sd
    base = LogisticRegression(C=1.0, max_iter=4000, class_weight="balanced").fit(Xtr, y[tr])
    dec_oof = cross_val_predict(
        LogisticRegression(C=1.0, max_iter=4000, class_weight="balanced"),
        Xtr, y[tr], cv=5, method="decision_function")
    a, b = platt_params(dec_oof, y[tr])

    def kal_prob(dec): return 1.0 / (1.0 + np.exp(-(a * dec + b)))
    oof_prob = kal_prob(dec_oof)
    g_schwelle = kanal_schwelle(oof_prob, lese[tr], np.ones(len(tr), bool))
    dec_te = Xte @ base.coef_[0] + base.intercept_[0]
    score_te = kal_prob(dec_te)
    drop_te = score_te < g_schwelle
    print(f"Kalibrierte globale Schwelle (Platt) aus Train-OOF: {g_schwelle:.3f}\n")

    # EIN Screening-Durchlauf über die Testartikel.
    con_input = []
    import sqlite3
    con = sqlite3.connect(f"file:{ROOT / 'articles.db'}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    byid = {r["id"]: r for r in con.execute(
        "SELECT id,title,journal_full,journal_short,abstract,openalex_abstract"
        " FROM articles WHERE user_verdict IS NOT NULL")}
    con.close()
    for j in te:
        r = byid[daten[j]["id"]]
        con_input.append({"id": r["id"], "title": r["title"],
                          "journal": r["journal_full"] or r["journal_short"],
                          "abstract": r["abstract"],
                          "openalex_abstract": r["openalex_abstract"]})
    print(f"Screening über {len(con_input)} Testartikel …")
    screen = agent.batch_screen(con_input, verbose=False)

    # Urteile zusammenführen.
    def verworfen_llm(aid): return screen.get(aid, {}).get("verdict") == "ignorieren"

    nutzer_drop = y[te] == 0
    a_drop = np.array([verworfen_llm(daten[te[j]]["id"]) for j in range(len(te))])
    b_drop = drop_te | a_drop  # Vorfilter-Drop ODER Screening-Drop

    def kennzahlen(pred_drop, name, llm_calls):
        stimmt = (pred_drop == nutzer_drop).mean()
        funde = lese[te]
        verloren = int(funde[pred_drop].sum())
        print(f"  {name:<26} Übereinstimmung {stimmt:.1%}  "
              f"Funde verloren {verloren}/{int(funde.sum())} "
              f"({verloren/max(1,int(funde.sum())):.0%})  LLM-Aufrufe {llm_calls}")
        return stimmt, verloren

    print(f"\n{'=' * 74}\nERGEBNIS auf {len(te)} zurückgehaltenen Urteilen\n{'=' * 74}")
    kennzahlen(a_drop, "A  LLM-Screening allein", len(te))
    kennzahlen(b_drop, "B  Vorfilter + Screening", int((~drop_te).sum()))
    print(f"\n  Vorfilter verwirft {int(drop_te.sum())}/{len(te)} "
          f"({drop_te.mean():.0%}) ohne LLM.")
    print(f"  Von diesen Vorfilter-Drops sind laut Nutzer {int((y[te][drop_te]==0).sum())}"
          f"/{int(drop_te.sum())} tatsächlich »ignorieren« "
          f"({(y[te][drop_te]==0).mean():.0%} richtig).")
    # Nur die zusätzlichen Drops, die A NICHT auch macht — der eigentliche Beitrag.
    nur_vorfilter = drop_te & ~a_drop
    if nur_vorfilter.sum():
        print(f"  Zusätzlich zu A verwirft der Vorfilter {int(nur_vorfilter.sum())} "
              f"Artikel; davon {int((y[te][nur_vorfilter]==0).sum())} richtig, "
              f"{int((y[te][nur_vorfilter]==1).sum())} Funde fälschlich.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
