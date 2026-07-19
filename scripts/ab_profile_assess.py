#!/usr/bin/env python3
"""Ändert das Werkprofil, WELCHE eigenen Arbeiten die Einschätzung heranzieht?

Die Einschätzungs-Stufe schreibt selbst keine Bezüge — sie benennt in
`candidate_reads`, welche von Benjamins Arbeiten nachzuschlagen sich lohnt.
Genau dort entsteht eine Konfabulation, bevor die Prüfstufe sie bestätigen
oder verwerfen kann. Und genau dort ist sie nachrechenbar: teilt der Artikel
Literatur mit dem benannten Werk?

Geprüft wird mit derselben Mengenoperation wie im Korpus-Audit
(`grounded_vs_llm_corpus.py`), gegen own_refs.db. Kein zweites LLM als Richter.

  belegt      Artikel teilt ≥1 Referenz mit GENAU dem benannten Werk
  danebenen   teilt Literatur mit dem Korpus, aber nicht mit dem benannten Werk
  unbelegt    teilt mit dem ganzen Korpus keine einzige Referenz
  unauflösbar pub_id steht in keiner Bibliothek

Was der Test NICHT zeigt: ob eine belegte Nennung auch inhaltlich die richtige
ist. Geteilte Literatur ist ein notwendiger, kein hinreichender Beleg.

    scripts/ab_profile_assess.py --ids 47a99a45 --laeufe 1
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import sqlite3
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from grounded_vs_llm_corpus import load_attribution, article_shared_works  # noqa: E402


def lade_artikel(praefixe: list[str]) -> list[sqlite3.Row]:
    con = sqlite3.connect(str(ROOT / "articles.db"))
    con.row_factory = sqlite3.Row
    treffer = []
    for p in praefixe:
        r = con.execute(
            "SELECT id, title, journal_full, journal_short, year, doi, url, authors_json,"
            " abstract, openalex_abstract, openalex_refs, crossref_refs"
            " FROM articles WHERE id LIKE ? LIMIT 1", (p + "%",)
        ).fetchone()
        if r is None:
            print(f"  ! kein Artikel zu {p}")
            continue
        treffer.append(r)
    return treffer


def als_eingabe(r: sqlite3.Row) -> dict:
    try:
        autoren = json.loads(r["authors_json"] or "[]")
    except json.JSONDecodeError:
        autoren = []
    return {
        "title": r["title"],
        "authors": autoren,
        "abstract": (r["abstract"] or r["openalex_abstract"] or "").strip(),
        "doi": r["doi"],
        "url": r["url"],
        "journal": r["journal_full"] or r["journal_short"],
    }


def einschaetzen(artikel: dict, *, mit_profil: bool, artikel_id: str) -> dict:
    os.environ["MOJO_PROFILE_BLOCK"] = "1" if mit_profil else "0"
    import journal_bot.settings as settings

    importlib.reload(settings)
    import journal_bot.agent as agent

    importlib.reload(agent)

    return agent.run_agent(
        artikel,
        max_iterations=1,
        verbose=False,
        allow_read=False,
        system_outro=agent.ASSESSMENT_OUTRO,
        log_endpoint="assess",
        article_id=artikel_id,
    )


def kandidaten_lesen(roh) -> list[dict]:
    """`candidate_reads` in eine einheitliche Form bringen.

    Das Einschätzungs-Modell hält sich nicht zuverlässig ans Werkzeug-Schema:
    mal Objekte {pub_id, hypothesis}, mal bloße pub_id-Strings, mal ein
    einzelnes Objekt statt einer Liste. Hier wird das eingeebnet, statt den
    Messlauf daran scheitern zu lassen — die Untreue selbst wird gezählt.
    """
    if isinstance(roh, dict):
        roh = [roh]
    if not isinstance(roh, list):
        return []
    aus: list[dict] = []
    for c in roh:
        if isinstance(c, dict) and c.get("pub_id"):
            aus.append({"pub_id": str(c["pub_id"]).strip(),
                        "hypothesis": str(c.get("hypothesis") or ""),
                        "schema_treu": True})
        elif isinstance(c, str) and c.strip():
            aus.append({"pub_id": c.strip(), "hypothesis": "", "schema_treu": False})
    return aus


def erdung(pub_ids: list[str], works: set[str], n_shared: int, zkey2cid: dict) -> Counter:
    urteil = Counter()
    for pid in pub_ids:
        cid = zkey2cid.get(pid)
        if cid is None:
            urteil["unauflösbar"] += 1
        elif cid in works:
            urteil["belegt"] += 1
        elif n_shared > 0:
            urteil["danebenen"] += 1
        else:
            urteil["unbelegt"] += 1
    return urteil


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", nargs="+", required=True, help="id-Präfixe aus articles.db")
    ap.add_argument("--laeufe", type=int, default=1)
    ap.add_argument("--nur", choices=("mit", "ohne"), default=None,
                    help="nur eine Bedingung fahren — der Cache bleibt dann warm, "
                         "wie im Betrieb; im Wechselbetrieb wirft jede Bedingung "
                         "der anderen den Cache um und verteuert beide")
    ap.add_argument("--out", default="output/ab_profile_assess.json")
    args = ap.parse_args()

    bedingungen = [("ohne", False), ("mit", True)]
    if args.nur:
        bedingungen = [b for b in bedingungen if b[0] == args.nur]

    oa2w, doi2w, zkey2cid = load_attribution()
    zeilen = lade_artikel(args.ids)
    if not zeilen:
        return 1
    print(f"{len(zeilen)} Artikel · {args.laeufe} Lauf/Läufe je Bedingung "
          f"= {2 * args.laeufe * len(zeilen)} Aufrufe\n")

    protokoll: list[dict] = []
    kosten = 0.0
    # Bedingung außen, Artikel innen: so bleibt der zwischengespeicherte
    # Systemblock über alle Artikel einer Bedingung warm. Andersherum wirft
    # jeder Wechsel den Cache um und verdreifacht die Kosten je Aufruf.
    for lauf in range(args.laeufe):
        for schluessel, flag in bedingungen:
            marke = f"Lauf {lauf + 1}, " if args.laeufe > 1 else ""
            print(f"\n{'#' * 74}\n### {marke}{schluessel} Werkprofil\n{'#' * 74}")
            for r in zeilen:
                works, n_shared = article_shared_works(r, oa2w, doi2w)
                print(f"\n{(r['title'] or '')[:72]}")
                print(f"  {r['journal_full'] or r['journal_short']} ({r['year']})"
                      f" — teilt {n_shared} Referenzen mit {len(works)} deiner Arbeiten")
                erg = einschaetzen(als_eingabe(r), mit_profil=flag, artikel_id=r["id"])
                eintrag = erg.get("entry") or {}
                kandidaten = kandidaten_lesen(eintrag.get("candidate_reads"))
                pub_ids = [c["pub_id"] for c in kandidaten]
                u = erdung(pub_ids, works, n_shared, zkey2cid)
                c = float(erg.get("est_cost_usd") or 0.0)
                kosten += c
                untreu = sum(not c_["schema_treu"] for c_ in kandidaten)
                print(f"  {eintrag.get('verdict', '?'):<14}"
                      f" ${c:.4f}  Nachschlag-Vorschläge: {len(pub_ids)}"
                      f"{'  ' + ', '.join(f'{k}={v}' for k, v in u.items()) if u else ''}"
                      f"{f'  [{untreu} ohne Schema]' if untreu else ''}")
                for cand in kandidaten:
                    pid = cand["pub_id"]
                    cid = zkey2cid.get(pid)
                    status = ("belegt" if cid in works else
                              "danebenen" if n_shared > 0 else "unbelegt") if cid else "unauflösbar"
                    print(f"        [{status}] {pid}  {cand['hypothesis'][:78]}")
                begr = str(eintrag.get("verdict_begruendung", ""))[:150]
                if begr:
                    print(f"        » {begr}")
                protokoll.append({
                    "artikel_id": r["id"], "titel": r["title"], "lauf": lauf,
                    "bedingung": schluessel, "verdict": eintrag.get("verdict"),
                    "begruendung": eintrag.get("verdict_begruendung"),
                    "candidate_reads": kandidaten, "erdung": dict(u),
                    "schema_untreu": untreu,
                    "n_shared": n_shared, "kosten_usd": c,
                })

    print(f"\n{'=' * 74}\nGesamtkosten: ${kosten:.4f}"
          f"   (${kosten / max(1, len(protokoll)):.4f} je Aufruf)")

    # Erdung je Bedingung zusammenziehen — die eigentliche Frage.
    print(f"\n{'Bedingung':<10} {'Aufrufe':>7} {'Vorschläge':>11} {'belegt':>7}"
          f" {'danebenen':>10} {'unbelegt':>9} {'unauflösb.':>11}")
    for schluessel, _ in bedingungen:
        teil = [p for p in protokoll if p["bedingung"] == schluessel]
        summe: Counter = Counter()
        for p in teil:
            summe.update(p["erdung"])
        gesamt = sum(summe.values())
        print(f"{schluessel:<10} {len(teil):>7} {gesamt:>11} {summe['belegt']:>7}"
              f" {summe['danebenen']:>10} {summe['unbelegt']:>9} {summe['unauflösbar']:>11}")
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(protokoll, ensure_ascii=False, indent=2),
                              encoding="utf-8")
    print(f"→ {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
