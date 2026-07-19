#!/usr/bin/env python3
"""Das gelernte Kriterium über den unbeurteilten Bestand legen — und blind prüfen.

Angepasst wird auf den 913 Urteilen aus der Oberfläche. Bewertet wird der
gesamte unbeurteilte Bestand. Die Prüfung läuft gegen eine Quelle, die das
Modell nie gesehen hat und die auf einem völlig anderen Weg entstanden ist:
Benjamins eigene Zotero-Bibliothek.

Ein unbeurteilter Artikel, der in Zotero liegt, ist von ihm irgendwann per
gezielter Recherche gefunden und aufgehoben worden — ein Ja aus einem anderen
Prozess, Jahre daneben. Rankt das Modell diese Artikel über die übrigen, dann
überträgt das Kriterium. Rankt es sie nicht, dann nicht.

Verglichen wird INNERHALB der Zeitschrift: sonst misst man, aus welchen
Zeitschriften er überhaupt schöpft, nicht welche Beiträge er darin nimmt.
Von MOJO selbst nach Zotero exportierte Artikel sind ausgeschlossen
(Rückkopplung).

Zotero wird ausschliesslich lesend geöffnet (immutable=1).
"""

from __future__ import annotations

import re
import sqlite3
import sys
import unicodedata
from collections import Counter
from pathlib import Path

import numpy as np
from scipy.stats import mannwhitneyu
from sklearn.linear_model import LogisticRegression

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
ZOTERO = Path("/Users/joerissen/FAUbox/Zotero/zotero.sqlite")

from zustandsabhaengigkeit_test import lade, matrix, MIN_MERKMAL  # noqa: E402


def norm_doi(s: str | None) -> str:
    if not s:
        return ""
    s = s.strip().lower()
    s = re.sub(r"^(https?://)?(dx\.)?doi\.org/", "", s)
    return s.removeprefix("doi:").strip()


def norm_titel(s: str | None) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "", s.lower())[:90]


def zotero_index() -> tuple[set[str], set[str]]:
    """DOIs und normalisierte Titel der persönlichen Bibliothek (ohne Papierkorb)."""
    con = sqlite3.connect(f"file:{ZOTERO}?immutable=1", uri=True)
    q = """
      SELECT f.fieldName, idv.value
      FROM items i
      JOIN libraries l    ON i.libraryID = l.libraryID AND l.type = 'user'
      JOIN itemData idt   ON idt.itemID = i.itemID
      JOIN itemDataValues idv ON idv.valueID = idt.valueID
      JOIN fields f       ON f.fieldID = idt.fieldID
      WHERE f.fieldName IN ('DOI','title')
        AND i.itemID NOT IN (SELECT itemID FROM deletedItems)
    """
    dois: set[str] = set()
    titel: set[str] = set()
    for feld, wert in con.execute(q):
        if feld == "DOI":
            d = norm_doi(wert)
            if d:
                dois.add(d)
        else:
            t = norm_titel(wert)
            if len(t) > 25:
                titel.add(t)
    con.close()
    return dois, titel


def unbeurteilte() -> list[dict]:
    from zustandsabhaengigkeit_test import TOPIC_SCHWELLE
    import json

    con = sqlite3.connect(f"file:{ROOT / 'articles.db'}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    zeilen = con.execute(
        "SELECT id, title, journal_short, journal_full, doi, year, zotero_key,"
        "       openalex_topics, openalex_concepts, crossref_refs"
        " FROM articles WHERE user_verdict IS NULL"
        "   AND openalex_topics NOT IN ('','[]')"
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
            "id": r["id"], "titel": r["title"], "journal": r["journal_short"],
            "journal_voll": r["journal_full"] or r["journal_short"],
            "doi": norm_doi(r["doi"]), "titel_norm": norm_titel(r["title"]),
            "jahr": r["year"] or 0, "export": bool(r["zotero_key"]),
            "merkmale": merkmale, "n_refs": n_refs,
        })
    return aus


def main() -> int:
    lern = lade()
    hf = Counter(m for x in lern for m in x["merkmale"])
    vok = sorted(m for m, n in hf.items() if n >= MIN_MERKMAL)
    Xl = matrix(lern, vok)
    yl = np.array([x["behalten"] for x in lern])
    modell = LogisticRegression(C=0.3, max_iter=2000, class_weight="balanced")
    modell.fit(Xl, yl)
    print(f"angepasst auf {len(lern)} Urteilen · {len(vok)} Merkmale\n")

    ziel = unbeurteilte()
    Xz = matrix(ziel, vok)
    p = modell.predict_proba(Xz)[:, 1]
    for d, s in zip(ziel, p):
        d["score"] = float(s)

    dois, titel = zotero_index()
    print(f"Zotero (persönliche Bibliothek, ohne Papierkorb): "
          f"{len(dois)} DOIs, {len(titel)} Titel\n")
    for d in ziel:
        d["zotero"] = bool((d["doi"] and d["doi"] in dois)
                           or (d["titel_norm"] and d["titel_norm"] in titel))

    prüf = [d for d in ziel if not d["export"]]
    n_z = sum(d["zotero"] for d in prüf)
    print(f"{len(prüf)} unbeurteilte Artikel · davon {n_z} in Zotero "
          f"({n_z / len(prüf):.2%})\n")

    # --- Der Test: innerhalb der Zeitschrift, Zotero-Treffer gegen den Rest ---
    print("Innerhalb der Zeitschrift: rankt das Modell die Zotero-Artikel oben?")
    print(f"{'Zeitschrift':<14}{'n':>7}{'in Zotero':>11}{'AUC':>8}")
    print("-" * 40)
    zeilen, gewicht = [], 0
    for j in {d["journal"] for d in prüf}:
        teil = [d for d in prüf if d["journal"] == j]
        pos = [d["score"] for d in teil if d["zotero"]]
        neg = [d["score"] for d in teil if not d["zotero"]]
        if len(pos) < 8 or len(neg) < 8:
            continue
        auc = mannwhitneyu(pos, neg).statistic / (len(pos) * len(neg))
        zeilen.append((j, len(teil), len(pos), auc))
        gewicht += len(teil)
    for j, n, npos, a in sorted(zeilen, key=lambda t: -t[1]):
        print(f"{j:<14}{n:>7}{npos:>11}{a:>8.3f}")
    if zeilen:
        print("-" * 40)
        print(f"{'gewichtet':<14}{gewicht:>7}{sum(z[2] for z in zeilen):>11}"
              f"{sum(n * a for _, n, _, a in zeilen) / gewicht:>8.3f}")

    ausgabe = ROOT / "output" / "kriterium_scores.tsv"
    ausgabe.parent.mkdir(exist_ok=True)
    with ausgabe.open("w", encoding="utf-8") as fh:
        fh.write("score\tzotero\tjahr\tzeitschrift\ttitel\tid\n")
        for d in sorted(prüf, key=lambda d: -d["score"]):
            fh.write(f"{d['score']:.4f}\t{int(d['zotero'])}\t{d['jahr']}\t"
                     f"{d['journal_voll']}\t{(d['titel'] or '').replace(chr(9), ' ')}\t{d['id']}\n")
    print(f"\n→ {ausgabe.relative_to(ROOT)} ({len(prüf)} Artikel, absteigend bewertet)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
