#!/usr/bin/env python3
"""Trägt der Korrektur-Block? Gemessen an den zurückgehaltenen Widersprüchen.

`journal_bot/korrekturen.py` legt zwei Drittel der 217 überstimmten Urteile in
den Systemblock und hält ein Drittel zurück. Diese zurückgehaltenen Fälle sind
der einzige ehrliche Prüfstein: dort hat der Nutzer ein Urteil samt Begründung
umgestossen, und der Block hat den Fall nie gesehen.

Gefragt wird nicht »ist die Einschätzung besser geworden«, sondern genau:
rückt das Urteil auf die Seite, auf die der Nutzer es gerückt hat?

  Treffer      neues Urteil == Urteil des Nutzers
  Abstand      mittlerer Rangabstand zum Urteil des Nutzers (0 = gleich)
  Richtung     Anteil der Fälle, die sich zum Nutzer hin bewegen

Beide Bedingungen laufen bedingungsweise (erst alle ohne, dann alle mit), damit
der zwischengespeicherte Systemblock warm bleibt. Im Wechselbetrieb wirft jede
Bedingung der anderen den Cache um und verdreifacht die Kosten je Aufruf.

    scripts/ab_korrekturblock.py --grenze 3        # Kostenprobe, 3 Fälle
    scripts/ab_korrekturblock.py                   # alle zurückgehaltenen
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from journal_bot.korrekturen import lade_material  # noqa: E402

RANG = {"ignorieren": 0, "scannen": 1, "lesenswert": 2, "pflichtlektuere": 3}


def artikel_laden(ids: list[str]) -> dict[str, dict]:
    con = sqlite3.connect(f"file:{ROOT / 'articles.db'}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    marker = ",".join("?" * len(ids))
    aus = {}
    for r in con.execute(
        f"SELECT id, title, authors_json, abstract, openalex_abstract, doi, url,"
        f" journal_full, journal_short FROM articles WHERE id IN ({marker})", ids
    ):
        try:
            autoren = json.loads(r["authors_json"] or "[]")
        except json.JSONDecodeError:
            autoren = []
        aus[r["id"]] = {
            "title": r["title"], "authors": autoren,
            "abstract": (r["abstract"] or r["openalex_abstract"] or "").strip(),
            "doi": r["doi"], "url": r["url"],
            "journal": r["journal_full"] or r["journal_short"],
        }
    con.close()
    return aus


def einschaetzen(artikel: dict, *, mit_korrektur: bool, artikel_id: str) -> dict:
    os.environ["MOJO_KORREKTUR_BLOCK"] = "1" if mit_korrektur else "0"
    import journal_bot.settings as settings

    importlib.reload(settings)
    import journal_bot.agent as agent

    importlib.reload(agent)
    return agent.run_agent(
        artikel, max_iterations=1, verbose=False, allow_read=False,
        system_outro=agent.ASSESSMENT_OUTRO, log_endpoint="assess",
        article_id=artikel_id,
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--grenze", type=int, default=None,
                    help="nur die ersten N Fälle — für die Kostenprobe")
    ap.add_argument("--nur", choices=("mit", "ohne"), default=None)
    ap.add_argument("--out", default="output/ab_korrekturblock.json")
    args = ap.parse_args()

    faelle = sorted(lade_material()["pruefung"], key=lambda f: f["id"])
    if args.grenze:
        faelle = faelle[: args.grenze]
    artikel = artikel_laden([f["id"] for f in faelle])
    faelle = [f for f in faelle if f["id"] in artikel]

    bedingungen = [("ohne", False), ("mit", True)]
    if args.nur:
        bedingungen = [b for b in bedingungen if b[0] == args.nur]

    print(f"{len(faelle)} zurückgehaltene Widersprüche · {len(bedingungen)} Bedingung(en)"
          f" = {len(faelle) * len(bedingungen)} Aufrufe\n")

    protokoll, kosten = [], 0.0
    for schluessel, flag in bedingungen:
        print(f"\n{'#' * 72}\n### {schluessel} Korrektur-Block\n{'#' * 72}")
        for f in faelle:
            erg = einschaetzen(artikel[f["id"]], mit_korrektur=flag, artikel_id=f["id"])
            eintrag = erg.get("entry") or {}
            neu = eintrag.get("verdict") or "?"
            c = float(erg.get("est_cost_usd") or 0.0)
            kosten += c
            treffer = neu == f["nutzer"]
            print(f"  {f['titel'][:58]:<58} ${c:.4f}")
            print(f"     früher {f['agent']:<12} → jetzt {neu:<14}"
                  f" er: {f['nutzer']:<14} {'TREFFER' if treffer else ''}")
            protokoll.append({
                "id": f["id"], "bedingung": schluessel, "titel": f["titel"],
                "agent_frueher": f["agent"], "nutzer": f["nutzer"], "neu": neu,
                "begruendung_neu": eintrag.get("verdict_begruendung"), "kosten_usd": c,
            })

    print(f"\n{'=' * 72}\nGesamt ${kosten:.4f}  (${kosten / max(1, len(protokoll)):.4f} je Aufruf)\n")
    print(f"{'Bedingung':<10}{'n':>5}{'Treffer':>10}{'Abstand':>10}{'zum Nutzer hin':>17}")
    for schluessel, _ in bedingungen:
        teil = [p for p in protokoll if p["bedingung"] == schluessel and p["neu"] in RANG]
        if not teil:
            continue
        treffer = sum(p["neu"] == p["nutzer"] for p in teil) / len(teil)
        abstand = sum(abs(RANG[p["neu"]] - RANG[p["nutzer"]]) for p in teil) / len(teil)
        hin = sum(
            abs(RANG[p["neu"]] - RANG[p["nutzer"]]) < abs(RANG[p["agent_frueher"]] - RANG[p["nutzer"]])
            for p in teil
        ) / len(teil)
        print(f"{schluessel:<10}{len(teil):>5}{treffer:>9.1%}{abstand:>10.2f}{hin:>16.1%}")

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(protokoll, ensure_ascii=False, indent=2),
                              encoding="utf-8")
    print(f"→ {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
