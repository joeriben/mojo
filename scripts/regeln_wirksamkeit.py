#!/usr/bin/env python3
"""Greifen die hinterlegten Regeln in der groben Vorprüfung — und wie stark?

Die Regeln sind kein Code-Zweig. Sie stehen als geordneter Block im
Systemprompt, und ein Modell liest sie. Ob sie wirken, ist deshalb keine
Eigenschaft des Programms, sondern eine Messung.

Zwei Dinge macht dieses Skript, die der erste Anlauf nicht konnte:

1. **Die Rauschgrenze bestimmen.** Dieselbe Bedingung läuft mehrfach. Ein
   Unterschied zwischen den Bedingungen zählt erst, wenn er grösser ist als die
   Schwankung derselben Bedingung mit sich selbst. Im ersten Anlauf schwankte
   »mit Regeln« zwischen 25/26 und 24/26, während der Unterschied zu »ohne« bei
   einem Artikel lag — daraus war nichts abzuleiten.

2. **Auch prüfen, ob die Regeln anderswo etwas kaputtmachen.** Die Hälfte des
   Testsatzes sind Artikel, bei denen eine Regel feuern müsste; die andere
   Hälfte ist eine Zufallsstichprobe aus allen Urteilen. Ein Regelblock, der
   seine Fälle trifft und dafür den Rest verschlechtert, hat nichts gewonnen.

Die Stichwortsuche dient AUSSCHLIESSLICH der Auswahl der Testfälle. Sie ist
nicht das Verfahren — das Verfahren ist der Regelblock im Prompt.

    scripts/regeln_wirksamkeit.py --anzahl 26 --laeufe 1 --nur mit   # Kostenprobe
    scripts/regeln_wirksamkeit.py --anzahl 200 --laeufe 3            # voller Lauf
"""

from __future__ import annotations

import argparse
import json
import random
import sqlite3
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import journal_bot.agent as agent  # noqa: E402

BEHALTEN = ("scannen", "lesenswert", "pflichtlektuere")

# Auswahl der Testfälle je Regel — Stichworte NUR zur Auswahl.
PROBEN = [
    ("R1 Sperre Versorgung/Gesundheit",
     "lower(title) LIKE '%health%' OR lower(title) LIKE '%nursing%'"
     " OR lower(title) LIKE '%care%' OR lower(title) LIKE '%clinical%'"
     " OR lower(title) LIKE '%patient%' OR lower(title) LIKE '%urban plan%'"),
    ("R2 Sperre psych+quant+Kompetenz",
     "lower(title) LIKE '%competenc%' OR lower(title) LIKE '%self-efficacy%'"
     " OR lower(title) LIKE '%motivation%' OR lower(title) LIKE '%cognitive load%'"
     " OR lower(title) LIKE '%questionnaire%' OR lower(title) LIKE '%scale%'"),
    ("R3 Öffnung dekolonial/politisch",
     "lower(title) LIKE '%decolon%' OR lower(title) LIKE '%indigenous%'"
     " OR lower(title) LIKE '%postcolon%' OR lower(title) LIKE '%polic%'"
     " OR lower(title) LIKE '%democra%'"),
    ("R4 Verengung Gerät statt Gegenstand",
     "lower(title) LIKE '%virtual reality%' OR lower(title) LIKE '%headset%'"
     " OR lower(title) LIKE '%immersive%' OR lower(title) LIKE '%avatar%'"),
    ("R5 Verengung Tradition",
     "lower(title) LIKE '%psycholog%' OR lower(title) LIKE '%psychoanaly%'"),
    ("R6 Kalibrierung Medienpädagogik",
     "lower(title) LIKE '%media literac%' OR lower(title) LIKE '%digital literac%'"
     " OR lower(title) LIKE '%digital skills%' OR lower(title) LIKE '%medienbildung%'"),
]

FELDER = ("id", "title", "journal", "abstract", "openalex_abstract")


def _zeile(r: sqlite3.Row, regel: str) -> dict:
    return {
        "id": r["id"], "title": r["title"],
        "journal": r["journal_full"] or r["journal_short"],
        "abstract": r["abstract"], "openalex_abstract": r["openalex_abstract"],
        "regel": regel, "nutzer": r["user_verdict"],
        "memo": (r["user_memo"] or "").strip(),
    }


SPALTEN = ("SELECT id, title, journal_full, journal_short, abstract,"
           " openalex_abstract, user_verdict, user_memo FROM articles")


def testfaelle(gesamt: int) -> list[dict]:
    """Halb Regelfälle, halb Zufall — beides mit bekanntem Urteil."""
    con = sqlite3.connect(f"file:{ROOT / 'articles.db'}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    aus, gesehen = [], set()

    je_regel = max(1, (gesamt // 2) // len(PROBEN))
    for regel, wo in PROBEN:
        # Beide Urteilsseiten ziehen: ein Testsatz aus lauter »ignorieren«
        # belohnt ein Modell, das alles wegwirft.
        for filter_ in (f"user_verdict IN {BEHALTEN}", "user_verdict = 'ignorieren'"):
            n = 0
            for r in con.execute(
                f"{SPALTEN} WHERE user_verdict IS NOT NULL AND ({wo}) AND {filter_}"
                f" ORDER BY id", ()
            ):
                if n >= je_regel // 2 + 1:
                    break
                if r["id"] in gesehen:
                    continue
                gesehen.add(r["id"])
                aus.append(_zeile(r, regel))
                n += 1

    rest = [r for r in con.execute(f"{SPALTEN} WHERE user_verdict IS NOT NULL ORDER BY id")
            if r["id"] not in gesehen]
    random.Random(11).shuffle(rest)
    for r in rest[: max(0, gesamt - len(aus))]:
        aus.append(_zeile(r, "— Zufallsstichprobe"))
    con.close()
    return aus


def uebereinstimmung(ergebnis: dict, faelle: list[dict]) -> float:
    """Anteil der Fälle, in denen Verwerfen/Behalten mit dem Nutzer übereinstimmt."""
    treffer = sum(
        (ergebnis.get(f["id"], {}).get("verdict") == "ignorieren")
        == (f["nutzer"] == "ignorieren")
        for f in faelle
    )
    return treffer / len(faelle) if faelle else 0.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--anzahl", type=int, default=200)
    ap.add_argument("--laeufe", type=int, default=3)
    ap.add_argument("--nur", choices=("mit", "ohne"), default=None)
    ap.add_argument("--out", default="output/regeln_wirksamkeit.json")
    args = ap.parse_args()

    faelle = testfaelle(args.anzahl)
    eingabe = [{k: f[k] for k in FELDER} for f in faelle]
    regelfaelle = [f for f in faelle if not f["regel"].startswith("—")]
    zufall = [f for f in faelle if f["regel"].startswith("—")]
    print(f"{len(faelle)} Testfälle — {len(regelfaelle)} zu den Regeln, "
          f"{len(zufall)} Zufallsstichprobe")
    print(f"{sum(f['nutzer'] in BEHALTEN for f in faelle)} behalten / "
          f"{sum(f['nutzer'] == 'ignorieren' for f in faelle)} verworfen")

    bedingungen = [("mit", True), ("ohne", False)]
    if args.nur:
        bedingungen = [b for b in bedingungen if b[0] == args.nur]
    print(f"{args.laeufe} Läufe je Bedingung = "
          f"{len(bedingungen) * args.laeufe * len(faelle)} Artikel-Prüfungen\n")

    echt = agent._regel_block
    laeufe: dict[str, list[dict]] = defaultdict(list)
    # Bedingung aussen, Läufe innen: der zwischengespeicherte Systemblock bleibt
    # über alle Läufe einer Bedingung warm. Andersherum wirft jeder Wechsel den
    # Cache um.
    for schluessel, mit_regeln in bedingungen:
        agent._regel_block = echt if mit_regeln else (lambda: None)
        for lauf in range(args.laeufe):
            print(f"{'#' * 70}\n### {schluessel} Regelblock — Lauf {lauf + 1}\n{'#' * 70}")
            laeufe[schluessel].append(agent.batch_screen(eingabe, verbose=True))
    agent._regel_block = echt

    print(f"\n{'=' * 70}\nRAUSCHGRENZE UND WIRKUNG\n{'=' * 70}")
    print(f"{'Bedingung':<10}{'Läufe':>7}{'Übereinstimmung':>28}{'»vertiefen«':>14}")
    zusammen = {}
    for schluessel in laeufe:
        werte = [uebereinstimmung(e, faelle) for e in laeufe[schluessel]]
        vert = [sum(1 for v in e.values() if v["verdict"] == "vertiefen")
                for e in laeufe[schluessel]]
        streu = statistics.stdev(werte) if len(werte) > 1 else 0.0
        zusammen[schluessel] = {"werte": werte, "mittel": statistics.mean(werte),
                                "streuung": streu, "vertiefen": vert}
        spanne = f"{min(werte):.1%}–{max(werte):.1%}" if len(werte) > 1 else ""
        print(f"{schluessel:<10}{len(werte):>7}{statistics.mean(werte):>17.1%}"
              f" ±{streu:.1%} {spanne:>9}{str(vert):>14}")

    if len(zusammen) == 2:
        d = zusammen["mit"]["mittel"] - zusammen["ohne"]["mittel"]
        rausch = max(zusammen["mit"]["streuung"], zusammen["ohne"]["streuung"])
        print(f"\n  Unterschied mit − ohne: {d:+.1%}")
        print(f"  Rauschgrenze (grösste Streuung einer Bedingung mit sich selbst): "
              f"±{rausch:.1%}")
        print("  → " + ("Der Unterschied liegt ÜBER der Rauschgrenze."
                        if abs(d) > 2 * rausch else
                        "Der Unterschied liegt INNERHALB des Rauschens — "
                        "aus diesen Läufen ist keine Wirkung ableitbar."))

        for name, teil in (("Regelfälle", regelfaelle), ("Zufallsstichprobe", zufall)):
            if not teil:
                continue
            m = statistics.mean([uebereinstimmung(e, teil) for e in laeufe["mit"]])
            o = statistics.mean([uebereinstimmung(e, teil) for e in laeufe["ohne"]])
            print(f"    {name:<20} mit {m:.1%}  ohne {o:.1%}  ({m - o:+.1%}, n={len(teil)})")

    print(f"\n{'=' * 70}\nJE REGEL — trifft der Block, wofür er gedacht ist?\n{'=' * 70}")
    for regel in sorted({f["regel"] for f in faelle}):
        teil = [f for f in faelle if f["regel"] == regel]
        zeile = f"  {regel:<38} n={len(teil):<4}"
        for schluessel in ("mit", "ohne"):
            if schluessel in laeufe:
                w = statistics.mean([uebereinstimmung(e, teil) for e in laeufe[schluessel]])
                zeile += f" {schluessel} {w:.0%} "
        print(zeile)

    # Wo hat der Block etwas verändert, und in welche Richtung?
    if len(zusammen) == 2:
        print(f"\n{'=' * 70}\nVERÄNDERTE FÄLLE (mehrheitlich über die Läufe)\n{'=' * 70}")
        def mehrheit(schluessel: str, aid: str) -> str:
            stimmen = Counter(e.get(aid, {}).get("verdict", "—") for e in laeufe[schluessel])
            return stimmen.most_common(1)[0][0]
        besser = schlechter = 0
        for f in faelle:
            m, o = mehrheit("mit", f["id"]), mehrheit("ohne", f["id"])
            if m == o:
                continue
            richtig = (m == "ignorieren") == (f["nutzer"] == "ignorieren")
            besser, schlechter = besser + richtig, schlechter + (not richtig)
            print(f"  {'✓' if richtig else '✗'} {f['nutzer']:<11}{o:<13}→ {m:<13}"
                  f"{f['title'][:40]}")
        print(f"\n  {besser} zum Urteil des Nutzers hin, {schlechter} davon weg.")

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps({
        "n": len(faelle), "laeufe": args.laeufe,
        "zusammenfassung": {k: {kk: vv for kk, vv in v.items()} for k, v in zusammen.items()},
        "faelle": [{**f, **{s: [e.get(f["id"]) for e in laeufe[s]] for s in laeufe}}
                   for f in faelle],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n→ {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
