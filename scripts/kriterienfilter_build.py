#!/usr/bin/env python3
"""Semantischer Vorfilter auf MiniLM-Embeddings, kalibriert an den 913 Urteilen.

Der Unterschied zu allem bisher Versuchten: kein Regex, keine OpenAlex-Etiketten
(die quer zu den Unterscheidungen des Nutzers schneiden und bei 45 % der Artikel
fehlen), sondern die dichte Bedeutungsrepräsentation von Titel + Abstract. Die
läuft ohne DOI und trifft damit auch die Kernzeitschriften.

Gemessen wird ausschliesslich AUSSERHALB der Anpassung und gegen zwei ehrliche
Vergleichsgrössen:

  Nullmodell      reine Zeitschriften-Basisrate (AUC 0.675, dokumentiert)
  OpenAlex-Themen frühere Übertragung auf ungesehene Zeitschrift: AUC 0.695

Zwei Schnitte, weil der Kanal die Behalten-Quote von 15 % auf 85 % zieht:

  OOF            5-fach, stratifiziert — die Alltagsleistung
  Zeitschrift-
  weise (LOJO)   trainiere auf allen anderen, sage die ungesehene Zeitschrift
                 vorher, AUC IN ihr gerechnet — der ehrliche Übertragungswert

Ausgabe: `output/kriterienfilter_eval.json` plus, wenn der Wert trägt, die
Parameter für den Betriebsfilter (`kriterienfilter_params.json`).
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from journal_bot import textembed  # noqa: E402

BEHALTEN = ("scannen", "lesenswert", "pflichtlektuere")
EMB_CACHE = ROOT / "output" / "kriterienfilter_emb.npz"
PUB_CACHE = ROOT / "output" / "kriterienfilter_pubemb.npy"


def lade_urteile() -> list[dict]:
    con = sqlite3.connect(f"file:{ROOT / 'articles.db'}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    zeilen = con.execute(
        "SELECT id, title, journal_short, selection_mode, user_verdict,"
        "       abstract, openalex_abstract FROM articles"
        " WHERE user_verdict IS NOT NULL ORDER BY id"
    ).fetchall()
    con.close()
    aus = []
    for r in zeilen:
        text = f"{r['title'] or ''}. {(r['abstract'] or r['openalex_abstract'] or '')}"
        aus.append({
            "id": r["id"], "text": text.strip(),
            "journal": r["journal_short"],
            "kanal": r["selection_mode"] or "unbekannt",
            "behalten": int(r["user_verdict"] in BEHALTEN),
            "lesenswert": int(r["user_verdict"] in ("lesenswert", "pflichtlektuere")),
        })
    return aus


def artikel_embeddings(daten: list[dict]) -> np.ndarray:
    ids = [d["id"] for d in daten]
    if EMB_CACHE.exists():
        cache = np.load(EMB_CACHE, allow_pickle=True)
        if list(cache["ids"]) == ids:
            print(f"[emb] Cache getroffen ({len(ids)} Artikel)")
            return cache["emb"]
    print(f"[emb] Bette {len(ids)} Artikel ein …")
    emb = textembed.encode([d["text"] for d in daten])
    EMB_CACHE.parent.mkdir(parents=True, exist_ok=True)
    np.savez(EMB_CACHE, ids=np.array(ids), emb=emb)
    return emb


def eigenwerk_naehe(emb: np.ndarray) -> np.ndarray:
    """Kosinus-Ähnlichkeit jedes Artikels zum eigenen Werk (max + Mittel der Top-5)."""
    summaries = json.loads((ROOT / "summaries.json").read_text())["summaries"]
    from journal_bot.ranker import rich_pub_texts

    if PUB_CACHE.exists():
        pub = np.load(PUB_CACHE)
    else:
        pub = textembed.encode(rich_pub_texts(summaries))
        np.save(PUB_CACHE, pub)
    sim = emb @ pub.T  # (n_art, n_pub), beide normiert → Kosinus
    top = np.sort(sim, axis=1)[:, ::-1]
    return np.stack([top[:, 0], top[:, :5].mean(axis=1)], axis=1)


def oof_scores(X: np.ndarray, y: np.ndarray, C: float = 1.0, folds: int = 5) -> np.ndarray:
    p = np.zeros(len(y))
    skf = StratifiedKFold(n_splits=folds, shuffle=True, random_state=17)
    for tr, te in skf.split(X, y):
        m = LogisticRegression(C=C, max_iter=3000, class_weight="balanced")
        m.fit(X[tr], y[tr])
        p[te] = m.predict_proba(X[te])[:, 1]
    return p


def lojo_auc(X: np.ndarray, y: np.ndarray, journ: list[str], min_n=25, min_pos=8) -> tuple:
    """Leave-one-journal-out: AUC in der ungesehenen Zeitschrift gerechnet."""
    j = np.array(journ)
    zeilen, gew = [], 0
    for name in sorted(set(journ), key=lambda z: -(j == z).sum()):
        te = j == name
        if te.sum() < min_n or y[te].sum() < min_pos or (1 - y[te]).sum() < min_pos:
            continue
        m = LogisticRegression(C=1.0, max_iter=3000, class_weight="balanced")
        m.fit(X[~te], y[~te])
        a = roc_auc_score(y[te], m.predict_proba(X[te])[:, 1])
        zeilen.append((name, int(te.sum()), a)); gew += te.sum()
    return zeilen, (sum(n * a for _, n, a in zeilen) / gew if gew else 0.0)


def main() -> int:
    daten = lade_urteile()
    y = np.array([d["behalten"] for d in daten])
    journ = [d["journal"] for d in daten]
    print(f"{len(daten)} Urteile · behalten {y.mean():.1%}\n")

    emb = artikel_embeddings(daten)
    naehe = eigenwerk_naehe(emb)
    X_emb = emb
    X_kombi = np.hstack([emb, naehe])

    print(f"{'Merkmalsatz':<34}{'OOF-AUC':>10}{'LOJO-AUC':>10}   Vergleich")
    print("-" * 72)
    print(f"{'Nullmodell (Zeitschrift-Basisrate)':<34}{'—':>10}{'0.675':>10}   dokumentiert")
    print(f"{'OpenAlex-Themen (früher)':<34}{'—':>10}{'0.695':>10}   dokumentiert")

    ergebnis = {"n": len(daten), "grundrate": float(y.mean()), "saetze": {}}
    for name, X in (("MiniLM 384-dim", X_emb), ("MiniLM + Eigenwerk-Nähe", X_kombi)):
        oof = oof_scores(X, y)
        auc_oof = roc_auc_score(y, oof)
        _, auc_lojo = lojo_auc(X, y, journ)
        ergebnis["saetze"][name] = {"oof_auc": auc_oof, "lojo_auc": auc_lojo}
        besser = "  ← schlägt Themen" if auc_lojo > 0.695 else ""
        print(f"{name:<34}{auc_oof:>10.3f}{auc_lojo:>10.3f}{besser}")

    # Bester Satz für die Zonen-Kalibrierung.
    X = X_kombi
    oof = oof_scores(X, y)
    lese = np.array([d["lesenswert"] for d in daten])

    # Drei Zonen auf den OOF-Scores: sicher verwerfen / unsicher / sicher behalten.
    # Nebenbedingung: die untere Schwelle darf höchstens 5 % der »lesenswert«
    # verlieren — Funde zu halten ist teurer als etwas Schrott mitzunehmen.
    order = np.argsort(oof)
    max_verlust = max(1, int(0.05 * lese.sum()))
    kum_lese = np.cumsum(lese[order])
    idx = np.searchsorted(kum_lese, max_verlust + 1)
    u_schwelle = oof[order[min(idx, len(oof) - 1)]]
    # Obere Schwelle: wo die OOF-Trefferdichte über 80 % steigt.
    o_kand = [t for t in np.quantile(oof, np.linspace(0.5, 0.98, 40))
              if y[oof >= t].mean() >= 0.80 and (oof >= t).sum() >= 15]
    o_schwelle = min(o_kand) if o_kand else float(oof.max() + 1)

    verwerf = oof < u_schwelle
    keep = oof >= o_schwelle
    unsicher = ~verwerf & ~keep
    print(f"\n{'=' * 72}\nZONEN (auf OOF-Scores, recall-schonend kalibriert)\n{'=' * 72}")
    for name, maske in (("sicher verwerfen", verwerf), ("unsicher (→ LLM)", unsicher),
                        ("sicher behalten", keep)):
        n = int(maske.sum())
        if not n:
            continue
        print(f"  {name:<20} {n:>4} Artikel ({n/len(daten):>5.1%})  "
              f"davon behalten {y[maske].mean():.1%}  lesenswert {lese[maske].mean():.1%}")
    verloren = int(lese[verwerf].sum())
    print(f"\n  Auto-Verwerfen spart {int(verwerf.sum())} LLM-Aufrufe "
          f"({verwerf.mean():.0%}) und verliert dabei {verloren}/{int(lese.sum())} "
          f"»lesenswert« = {verloren/max(1,int(lese.sum())):.1%}")
    ergebnis["zonen"] = {
        "u_schwelle": float(u_schwelle), "o_schwelle": float(o_schwelle),
        "auto_drop_anteil": float(verwerf.mean()),
        "lesenswert_verlust": verloren / max(1, int(lese.sum())),
    }

    (ROOT / "output" / "kriterienfilter_eval.json").write_text(
        json.dumps(ergebnis, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n→ output/kriterienfilter_eval.json")

    _emit_params(daten, X, y, oof)
    return 0


def _emit_params(daten, X, y, oof) -> None:
    """Betriebsparameter schreiben: Endmodell auf ALLEN Urteilen + kanal-sichere
    Auto-Verwerf-Schwellen (≤5 % lesenswert-Verlust je Kanal), aus den OOF-Scores
    bestimmt (nicht in-sample). Der Wochenlauf lädt daraus, ohne neu zu rechnen.
    """
    from sklearn.linear_model import LogisticRegression

    lese = np.array([d["lesenswert"] for d in daten])
    kanal = np.array([d["kanal"] for d in daten])

    from sklearn.model_selection import cross_val_predict

    from journal_bot.kriterienfilter import platt_params

    mu = X.mean(axis=0)
    sd = X.std(axis=0) + 1e-9
    Xs = (X - mu) / sd
    modell = LogisticRegression(C=1.0, max_iter=4000, class_weight="balanced").fit(Xs, y)
    # Platt-Kalibrierung aus OOF-Entscheidungswerten — macht die Schwelle
    # skalenstabil (ohne sie 0.34 → 51 % Fund-Verlust; mit ihr held-out 18 %).
    dec_oof = cross_val_predict(
        LogisticRegression(C=1.0, max_iter=4000, class_weight="balanced"),
        Xs, y, cv=5, method="decision_function")
    platt_a, platt_b = platt_params(dec_oof, y)
    prob_oof = 1.0 / (1.0 + np.exp(-(platt_a * dec_oof + platt_b)))

    def schwelle_bei(oof_scores_, maske, verlust=0.05) -> float:
        ok, ll = oof_scores_[maske], lese[maske]
        if maske.sum() < 20 or ll.sum() == 0:
            return -1.0
        order = np.argsort(ok)
        budget = max(0, int(verlust * ll.sum()))
        kum = np.cumsum(ll[order])
        i = np.searchsorted(kum, budget + 1)
        return float(ok[order[min(i, len(ok) - 1)]])

    # GLOBALE Schwelle auf den KALIBRIERTEN OOF-Wahrscheinlichkeiten. Kanalweise
    # Schwellen übertrugen nicht (held-out 56 % Fund-Verlust); die globale,
    # kalibrierte trägt: +1.9 pp Übereinstimmung, −22 % LLM-Aufrufe, +1 Fund
    # (Rauschen), 92 % der Verwürfe korrekt (scripts/kriterienfilter_validate.py).
    global_schwelle = schwelle_bei(prob_oof, np.ones(len(y), bool))

    params = {
        "model_name": textembed.MODEL_NAME,
        "feature": "minilm384 + [own_sim_max, own_sim_top5mean]",
        "standardize": {"mean": mu.tolist(), "std": sd.tolist()},
        "coef": modell.coef_[0].tolist(),
        "intercept": float(modell.intercept_[0]),
        "platt_a": platt_a,
        "platt_b": platt_b,
        "schwelle": global_schwelle,
        "kalibrierung": ("Platt-kalibriert, globale Schwelle ≤5 % lesenswert-"
                         "Verlust aus OOF; held-out: +1.9 pp Übereinstimmung, "
                         "−22 % LLM-Aufrufe, 92 % Verwürfe korrekt"),
    }
    (ROOT / "kriterienfilter_params.json").write_text(
        json.dumps(params, ensure_ascii=False, indent=2), encoding="utf-8")
    # Publikations-Embeddings für die Eigenwerk-Nähe zur Inferenzzeit.
    summaries = json.loads((ROOT / "summaries.json").read_text())["summaries"]
    from journal_bot.ranker import rich_pub_texts
    if not PUB_CACHE.exists():
        np.save(PUB_CACHE, textembed.encode(rich_pub_texts(summaries)))
    np.save(ROOT / "kriterienfilter_pub.npy", np.load(PUB_CACHE))
    print(f"→ kriterienfilter_params.json ({len(schwellen)} Kanal-Schwellen), "
          f"kriterienfilter_pub.npy")
    return None


if __name__ == "__main__":
    raise SystemExit(main())
