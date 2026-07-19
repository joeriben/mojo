#!/usr/bin/env python3
"""A/B-Vergleich: ändert das Werkprofil im Systemblock die Screening-Urteile?

Dieselben Artikel zweimal durch das Screening — einmal ohne, einmal mit dem
H7-Werkprofil im Systemblock. Verglichen wird, welche Artikel ihr Urteil
wechseln und in welche Richtung.

Was der Test NICHT zeigt: ob das geänderte Urteil besser ist. Dafür braucht es
Benjamins Blind-Label. Der Test beantwortet allein die Vorfrage — bewegt der
Block überhaupt etwas, oder ist er wirkungslos.

    scripts/ab_profile_block.py --n 25
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from journal_bot.store import Store  # noqa: E402


def hole_artikel(n: int, offset: int = 0) -> list[dict]:
    """Die nächsten n unbearbeiteten Artikel — dieselbe Reihenfolge wie im Lauf.

    `offset` überspringt die vordersten; so lässt sich ein zweiter Batch auf
    anderen Artikeln fahren statt denselben noch einmal.
    """
    store = Store()
    pending = store.find_unprocessed(limit=n + offset)[offset:]
    out = []
    for sa in pending:
        abstract = (sa.abstract or sa.openalex_abstract or "").strip()
        if not abstract:
            continue
        out.append({
            "id": sa.id,
            "title": sa.title,
            "journal": sa.journal_full or sa.journal_short,
            "abstract": abstract,
        })
    return out


def screene(artikel: list[dict], *, mit_profil: bool) -> dict[str, dict]:
    """Screening in einer der beiden Bedingungen.

    Das Flag wird über die Umgebung gesetzt und settings neu geladen, weil
    PROFILE_BLOCK_ENABLED beim Import ausgewertet wird.
    """
    import importlib

    os.environ["MOJO_PROFILE_BLOCK"] = "1" if mit_profil else "0"
    import journal_bot.settings as settings

    importlib.reload(settings)
    import journal_bot.agent as agent

    importlib.reload(agent)

    blk = agent._profile_block()
    print(f"  Werkprofil im Prompt: {'ja' if blk else 'nein'}"
          f"{f' (~{len(blk) // 4} Tokens)' if blk else ''}")
    return agent.batch_screen(artikel, verbose=False)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=25, help="Artikel je Bedingung (Default 25 = ein Batch)")
    ap.add_argument("--offset", type=int, default=0)
    ap.add_argument("--out", default="output/ab_profile_block.json")
    args = ap.parse_args()

    artikel = hole_artikel(args.n, args.offset)
    if not artikel:
        print("Keine unbearbeiteten Artikel mit Abstract gefunden.")
        return 1
    print(f"{len(artikel)} Artikel, je zweimal gescreent.\n")

    print("A — ohne Werkprofil (Ist-Zustand)")
    ohne = screene(artikel, mit_profil=False)
    print("\nB — mit Werkprofil")
    mit = screene(artikel, mit_profil=True)

    wechsel, gleich = [], 0
    richtung: Counter = Counter()
    for a in artikel:
        va = (ohne.get(a["id"]) or {}).get("verdict")
        vb = (mit.get(a["id"]) or {}).get("verdict")
        if va == vb:
            gleich += 1
            continue
        richtung[f"{va} → {vb}"] += 1
        wechsel.append({
            "id": a["id"], "titel": a["title"], "journal": a["journal"],
            "ohne": va, "mit": vb,
            "grund_ohne": (ohne.get(a["id"]) or {}).get("grund"),
            "grund_mit": (mit.get(a["id"]) or {}).get("grund"),
        })

    n = len(artikel)
    print(f"\n{'=' * 62}\n{n} Artikel · {gleich} gleich · {len(wechsel)} gewechselt "
          f"({100 * len(wechsel) / n:.0f} %)")
    for k, v in richtung.most_common():
        print(f"   {k}: {v}")
    zaehl = lambda d: Counter((d.get(a["id"]) or {}).get("verdict") for a in artikel)  # noqa: E731
    print(f"\n   ohne Profil: {dict(zaehl(ohne))}")
    print(f"   mit Profil:  {dict(zaehl(mit))}")

    if wechsel:
        print(f"\n{'=' * 62}\nGewechselte Artikel:")
        for w in wechsel:
            print(f"\n  {w['titel'][:78]}")
            print(f"    {w['journal']}")
            print(f"    ohne: {w['ohne']:<12} {(w['grund_ohne'] or '')[:110]}")
            print(f"    mit:  {w['mit']:<12} {(w['grund_mit'] or '')[:110]}")

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(
        json.dumps({"n": n, "gleich": gleich, "wechsel": wechsel}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n→ {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
