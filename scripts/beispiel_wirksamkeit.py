#!/usr/bin/env python3
"""Hilft es dem Screening, die ähnlichsten früheren Urteile des Nutzers zu sehen?

Der treueste Weg, ein Auswahlmodell »aus den Daten« abzuleiten, ist nicht, dem
Modell abstrakte Regeln vorzuhalten, sondern die tatsächlichen Entscheidungen:
zu jedem neuen Artikel die semantisch nächsten schon beurteilten Artikel mit dem
echten Urteil des Nutzers. Der Regeltest (`regeln_wirksamkeit.py`) hat gezeigt,
dass hand­geschriebene Regeln nur auf ihren Zielfällen wirken (+8 pp) und
anderswo leicht schaden (−2 pp), global also neutral. Beispiel-Abruf ist die
Alternative: kein Text über den Nutzer, sondern seine Urteile selbst.

Sauberkeit:

* **Kein Leck.** Nachbarn kommen ausschliesslich aus dem Trainingsteil; der
  Testteil wird nie als Nachbar von sich selbst oder eines anderen Testartikels
  gezogen. Titelgleiche Treffer (neu beurteiltes Duplikat) fallen raus.
* **Rauschgrenze.** Jede Bedingung läuft mehrfach; ein Unterschied zählt erst
  über der Schwankung derselben Bedingung mit sich selbst.
* **Beide Urteilsseiten.** Gemessen wird Übereinstimmung UND verlorene Funde
  (»lesenswert« fälschlich verworfen) — ein Modell, das alles wegwirft, gewinnt
  hier nichts.

    scripts/beispiel_wirksamkeit.py --test 40 --laeufe 1 --nur beispiele  # Kostenprobe
    scripts/beispiel_wirksamkeit.py --test 250 --laeufe 3                 # voller Lauf
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import statistics
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import journal_bot.agent as agent  # noqa: E402
from kriterienfilter_build import artikel_embeddings, lade_urteile  # noqa: E402

BEHALTEN = ("scannen", "lesenswert", "pflichtlektuere")
LESE = ("lesenswert", "pflichtlektuere")

# Was der Nutzer über die Beispiele erfährt — als Zusatz zum Systemprompt, nur
# in den Beispiel-Bedingungen. Englisch wie der übrige Prompt.
BEISPIEL_HINWEIS = (
    "\n\n=== NEAREST PAST DECISIONS ===\n"
    "For most articles the batch shows a line 'Frühere Urteile des Nutzers zu "
    "ähnlichen Artikeln:' listing this user's OWN past decisions on the "
    "semantically most similar articles, each as \"title\" -> verdict. These are "
    "the strongest available evidence of how THIS user judges this region of the "
    "literature — weight them above generic topical impressions. They are "
    "examples, not rules: a given article may still warrant a different call, and "
    "the neighbours can disagree among themselves. Verdicts: ignorieren = drop, "
    "scannen/lesenswert/pflichtlektuere = keep (increasing interest)."
)


def _display_felder() -> dict[str, sqlite3.Row]:
    con = sqlite3.connect(f"file:{ROOT / 'articles.db'}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    rows = {r["id"]: r for r in con.execute(
        "SELECT id, title, journal_full, journal_short, abstract, openalex_abstract,"
        "       user_verdict, user_memo FROM articles WHERE user_verdict IS NOT NULL")}
    con.close()
    return rows


def _norm_titel(t: str | None) -> str:
    return "".join(ch for ch in (t or "").lower() if ch.isalnum())


def beispiel_block(nachbar_ids: list[str], disp: dict, *, kmax: int) -> str:
    """Die nächsten Urteile in eine knappe Few-Shot-Zeile bringen."""
    teile = []
    for nid in nachbar_ids[:kmax]:
        r = disp[nid]
        titel = (r["title"] or "")[:75].replace("\n", " ").strip()
        verdikt = r["user_verdict"]
        memo = (r["user_memo"] or "").strip().replace("\n", " ")
        zeile = f'"{titel}" -> {verdikt}'
        if memo and len(memo) <= 60:
            zeile += f' ({memo})'
        teile.append(zeile)
    if not teile:
        return ""
    return "Frühere Urteile des Nutzers zu ähnlichen Artikeln: " + " | ".join(teile)


def screene(eingabe: list[dict], system_prompt: str, model: str,
            budget: float, verbose: bool) -> tuple[dict[str, dict], float]:
    """Ein Screening-Durchlauf mit explizitem Systemprompt; nutzt die robusten
    Primitiven aus agent.py (Nachforderung fehlender Zeilen, Einzel-Hardcap)."""
    client = agent.build_client()
    ergebnis: dict[str, dict] = {}
    kosten = 0.0
    for i in range(0, len(eingabe), 25):
        batch = eingabe[i:i + 25]
        nr = i // 25 + 1
        raw, cost, _usage, dump = agent._screen_request(
            client, system_prompt, agent._format_screen_batch(batch), model)
        kosten += cost
        if cost > agent._MAX_SINGLE_BATCH_COST_USD:
            raise RuntimeError(f"Einzel-Batch zu teuer: ${cost:.3f}")
        ergebnis.update(agent._parse_screen_lines(raw, batch))
        fehlt = [a for a in batch if a["id"] not in ergebnis]
        if fehlt:
            zusatz, _rest = agent._screen_retry_missing(
                client, system_prompt, model, fehlt, ergebnis,
                batch_num=nr, verbose=verbose)
            kosten += zusatz
        if kosten > budget:
            raise RuntimeError(f"Budget überschritten: ${kosten:.3f} > ${budget:.3f}")
        if verbose:
            print(f"    Batch {nr}: {len(batch)} Artikel, kumuliert ${kosten:.3f}")
    return ergebnis, kosten


def kennzahlen(erg: dict, test: list[dict]) -> dict:
    stimmt = sum((erg.get(t["id"], {}).get("verdict") == "ignorieren")
                 == (t["nutzer_drop"]) for t in test) / len(test)
    funde = [t for t in test if t["lesenswert"]]
    verloren = sum(erg.get(t["id"], {}).get("verdict") == "ignorieren" for t in funde)
    vert = sum(1 for v in erg.values() if v.get("verdict") == "vertiefen")
    return {"uebereinstimmung": stimmt,
            "funde_verloren": verloren, "funde_gesamt": len(funde),
            "vertiefen": vert}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", type=int, default=250)
    ap.add_argument("--k", type=int, default=6, help="Anzahl Nachbar-Beispiele")
    ap.add_argument("--laeufe", type=int, default=3)
    ap.add_argument("--nur", choices=("basis", "beispiele", "beide"), default=None)
    ap.add_argument("--budget", type=float, default=8.0)
    ap.add_argument("--out", default="output/beispiel_wirksamkeit.json")
    args = ap.parse_args()

    daten = lade_urteile()                       # ORDER BY id → Cache-Treffer
    emb = artikel_embeddings(daten)
    disp = _display_felder()
    y = np.array([d["behalten"] for d in daten])
    ids = [d["id"] for d in daten]

    # Stratifizierter Train/Test-Split auf behalten/verwerfen.
    rng = np.random.RandomState(13)
    test_idx = []
    for kl in (0, 1):
        pool = np.where(y == kl)[0]
        rng.shuffle(pool)
        n = int(round(args.test * len(pool) / len(y)))
        test_idx.extend(pool[:n].tolist())
    test_idx = sorted(test_idx)
    test_set = set(test_idx)
    train_idx = np.array([i for i in range(len(daten)) if i not in test_set])
    emb_train = emb[train_idx]
    print(f"train {len(train_idx)} · test {len(test_idx)} "
          f"(Nachbarn NUR aus train, titelgleiche raus)\n")

    # Testeingabe + Beispielblöcke bauen.
    test = []
    for i in test_idx:
        r = disp[ids[i]]
        titel_i = _norm_titel(r["title"])
        sim = emb[i] @ emb_train.T
        order = np.argsort(sim)[::-1]
        nachbarn = []
        for j in order:
            gi = int(train_idx[j])
            if _norm_titel(disp[ids[gi]]["title"]) == titel_i:
                continue                          # Leck: dasselbe Werk erneut
            nachbarn.append(ids[gi])
            if len(nachbarn) >= args.k:
                break
        naehe = float(np.sort(sim)[::-1][:args.k].mean())
        test.append({
            "id": ids[i], "title": r["title"],
            "journal": r["journal_full"] or r["journal_short"],
            "abstract": r["abstract"], "openalex_abstract": r["openalex_abstract"],
            "beispiele": beispiel_block(nachbarn, disp, kmax=args.k),
            "nutzer_drop": r["user_verdict"] == "ignorieren",
            "lesenswert": r["user_verdict"] in LESE,
            "naehe": naehe,
        })

    basis_prompt = agent.build_system_prompt(
        json.loads((ROOT / "summaries.json").read_text())["summaries"],
        profile_block=agent._profile_block(),
        regel_block=None,
    ) + agent.SCREENING_SUFFIX
    regel_prompt = agent.build_system_prompt(
        json.loads((ROOT / "summaries.json").read_text())["summaries"],
        profile_block=agent._profile_block(),
        regel_block=agent._regel_block(),
    ) + agent.SCREENING_SUFFIX

    # (Schlüssel, Systemprompt, Beispiele mitschicken?)
    bedingungen = [
        ("basis", basis_prompt, False),
        ("beispiele", basis_prompt + BEISPIEL_HINWEIS, True),
        ("beide", regel_prompt + BEISPIEL_HINWEIS, True),
    ]
    if args.nur:
        bedingungen = [b for b in bedingungen if b[0] == args.nur]

    def eingabe_fuer(mit_beispiele: bool) -> list[dict]:
        return [{k: (t[k] if not (k == "beispiele" and not mit_beispiele) else "")
                 for k in ("id", "title", "journal", "abstract",
                           "openalex_abstract", "beispiele")} for t in test]

    print(f"{len(bedingungen)} Bedingungen × {args.laeufe} Läufe × {len(test)} "
          f"= {len(bedingungen) * args.laeufe * len(test)} Prüfungen\n")

    laeufe: dict[str, list[dict]] = {}
    gesamtkosten = 0.0
    for schluessel, prompt, mit_b in bedingungen:
        laeufe[schluessel] = []
        eingabe = eingabe_fuer(mit_b)
        for lauf in range(args.laeufe):
            print(f"### {schluessel} — Lauf {lauf + 1}/{args.laeufe}")
            erg, kosten = screene(eingabe, prompt, agent.MODEL_SCREEN,
                                  budget=args.budget - gesamtkosten, verbose=True)
            gesamtkosten += kosten
            laeufe[schluessel].append(erg)
            print(f"    fertig, ${kosten:.3f} (gesamt ${gesamtkosten:.3f})")

    print(f"\n{'=' * 74}\nRAUSCHGRENZE UND WIRKUNG (n={len(test)})\n{'=' * 74}")
    print(f"{'Bedingung':<12}{'Übereinstimmung':>22}{'Funde verloren':>20}{'»vertiefen«':>14}")
    zus = {}
    for schluessel in laeufe:
        kz = [kennzahlen(e, test) for e in laeufe[schluessel]]
        u = [k["uebereinstimmung"] for k in kz]
        vl = [k["funde_verloren"] for k in kz]
        streu = statistics.stdev(u) if len(u) > 1 else 0.0
        zus[schluessel] = {"u_mittel": statistics.mean(u), "u_streu": streu,
                           "u_werte": u, "verloren": vl,
                           "funde_gesamt": kz[0]["funde_gesamt"]}
        sp = f"{min(u):.1%}–{max(u):.1%}" if len(u) > 1 else ""
        vl_txt = f"{statistics.mean(vl):.1f}/{kz[0]['funde_gesamt']}"
        print(f"{schluessel:<12}{statistics.mean(u):>13.1%} ±{streu:.1%} {sp:>9}"
              f"{vl_txt:>20}{str(vl):>14}")

    if "basis" in zus:
        rausch = max(v["u_streu"] for v in zus.values())
        print(f"\n  Rauschgrenze (grösste Streuung einer Bedingung): ±{rausch:.1%}")
        for s in zus:
            if s == "basis":
                continue
            d = zus[s]["u_mittel"] - zus["basis"]["u_mittel"]
            dv = statistics.mean(zus[s]["verloren"]) - statistics.mean(zus["basis"]["verloren"])
            marke = "ÜBER Rauschen" if abs(d) > 2 * rausch else "im Rauschen"
            print(f"  {s:<12} Übereinstimmung {d:+.1%} ({marke}), "
                  f"Funde verloren {dv:+.1f}")

    # Aufschlüsselung nach Nachbarschafts-Klarheit: wo die Nachbarn nah sind,
    # sollten Beispiele am ehesten helfen.
    if "beispiele" in laeufe and "basis" in laeufe:
        med = statistics.median(t["naehe"] for t in test)
        print(f"\n{'=' * 74}\nNACH NACHBARSCHAFTS-KLARHEIT (Median-Nähe {med:.3f})\n{'=' * 74}")
        for name, teil in (("nahe Nachbarn", [t for t in test if t["naehe"] >= med]),
                           ("ferne Nachbarn", [t for t in test if t["naehe"] < med])):
            b = statistics.mean(kennzahlen(e, teil)["uebereinstimmung"] for e in laeufe["basis"])
            x = statistics.mean(kennzahlen(e, teil)["uebereinstimmung"] for e in laeufe["beispiele"])
            print(f"  {name:<16} n={len(teil):<4} basis {b:.1%}  beispiele {x:.1%}  ({x - b:+.1%})")

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps({
        "n_test": len(test), "k": args.k, "laeufe": args.laeufe,
        "kosten": gesamtkosten, "zusammenfassung": zus,
        "test": [{**{k: t[k] for k in ("id", "title", "nutzer_drop", "lesenswert", "naehe")},
                  **{s: [e.get(t["id"]) for e in laeufe[s]] for s in laeufe}}
                 for t in test],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n→ {args.out}  (${gesamtkosten:.3f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
