#!/usr/bin/env python3
"""Wie viel des A/B-Unterschieds ist Eigenstreuung des Screenings?

Dieselben Artikel mehrfach in jeder Bedingung. Bewegt sich ein Artikel schon in
identischer Bedingung von Lauf zu Lauf, ist er als Beleg für die Wirkung des
Werkprofils wertlos. Nur Artikel, die in einer Bedingung stabil sind und in der
anderen stabil anders, tragen etwas.

    scripts/ab_profile_stabilitaet.py --laeufe 4
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ab_profile_block import hole_artikel, screene  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=25)
    ap.add_argument("--offset", type=int, default=25)
    ap.add_argument("--laeufe", type=int, default=4, help="Wiederholungen je Bedingung")
    ap.add_argument("--out", default="output/ab_profile_stabilitaet.json")
    args = ap.parse_args()

    artikel = hole_artikel(args.n, args.offset)
    if not artikel:
        print("Keine unbearbeiteten Artikel mit Abstract gefunden.")
        return 1
    print(f"{len(artikel)} Artikel · {args.laeufe} Läufe je Bedingung "
          f"= {2 * args.laeufe} Calls\n")

    urteile: dict[str, dict[str, list]] = {a["id"]: {"ohne": [], "mit": []} for a in artikel}
    for i in range(args.laeufe):
        for schluessel, flag in (("ohne", False), ("mit", True)):
            print(f"Lauf {i + 1}/{args.laeufe} — {schluessel} Profil")
            res = screene(artikel, mit_profil=flag)
            for a in artikel:
                urteile[a["id"]][schluessel].append((res.get(a["id"]) or {}).get("verdict"))

    n = len(artikel)
    quote = lambda xs: sum(x == "weitergeben" for x in xs) / len(xs)  # noqa: E731

    # Nicht »in beiden Bedingungen identisch stabil« als Maßstab nehmen: die
    # Bedingung ohne Profil ist die wackelige, das Kriterium würde die Wirkung
    # gerade dort wegdefinieren, wo sie am deutlichsten ist. Maßstab ist die
    # Verschiebung der Weitergabe-Quote über die Läufe.
    stabil_ohne = sum(len(set(urteile[a["id"]]["ohne"])) == 1 for a in artikel)
    stabil_mit = sum(len(set(urteile[a["id"]]["mit"])) == 1 for a in artikel)
    runter = [a for a in artikel
              if quote(urteile[a["id"]]["mit"]) < quote(urteile[a["id"]]["ohne"])]
    hoch = [a for a in artikel
            if quote(urteile[a["id"]]["mit"]) > quote(urteile[a["id"]]["ohne"])]
    eindeutig = [a for a in runter if quote(urteile[a["id"]]["mit"]) == 0.0]

    print(f"\n{'=' * 66}")
    print(f"In sich stabil über {args.laeufe} Läufe:   ohne {stabil_ohne}/{n}   mit {stabil_mit}/{n}")
    print(f"Weitergabe-Quote sinkt mit Profil: {len(runter)}/{n}   steigt: {len(hoch)}/{n}")
    print(f"Davon in allen {args.laeufe} Läufen mit Profil aussortiert: {len(eindeutig)}")
    for a in eindeutig:
        print(f"   {quote(urteile[a['id']]['ohne']):.2f} → 0.00   {a['title'][:64]}")

    # Wie oft steht ein Artikel je Bedingung auf welchem Urteil — zeigt, ob
    # die Bewegung eine Tendenz ist oder ein Münzwurf.
    print(f"\n{'=' * 66}\nJe Artikel: Anteil »weitergeben« über die Läufe")
    print(f"{'ohne':>6} {'mit':>6}   Titel")
    for a in artikel:
        u = urteile[a["id"]]
        q = lambda xs: sum(x == "weitergeben" for x in xs) / len(xs)  # noqa: E731
        marke = "  ←" if q(u["ohne"]) != q(u["mit"]) else ""
        print(f"{q(u['ohne']):>6.2f} {q(u['mit']):>6.2f}   {a['title'][:58]}{marke}")

    schwankt = Counter()
    for a in artikel:
        for k in ("ohne", "mit"):
            schwankt[k] += len(set(urteile[a["id"]][k])) > 1
    print(f"\nSchwankt in identischer Bedingung: ohne {schwankt['ohne']}/{n}, mit {schwankt['mit']}/{n}")

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(
        {"n": n, "laeufe": args.laeufe, "belastbar": belastbar,
         "urteile": {a["id"]: {**urteile[a["id"]], "titel": a["title"]} for a in artikel}},
        ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n→ {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
