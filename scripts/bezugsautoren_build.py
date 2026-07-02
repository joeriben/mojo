"""Bezugsautoren-Build + Abgleich auf Autor-Ebene.

Baut die Bezugsautoren-DB für die Erstautoren einer Artikelmenge (10 neueste +
10 meistzitierte Werke je Autor) und rechnet die Kopplung gegen Benjamins
Korpus auf der breiteren Autor-Basis — im Vergleich zur Artikel-Ebene.

Fokus: die 224 Artikel mit LLM-Werk-Bezug-Behauptungen (das Audit-Material).
Frage: Verschiebt die Autor-Ebene das Bild corroborated/weak/ungrounded? Rettet
sie die konfabulierten Fälle (Artikel koppelt 0, Autor-Œuvre koppelt)?

Usage:
  python scripts/bezugsautoren_build.py --limit 15      # Verifikation
  python scripts/bezugsautoren_build.py --claims        # alle 224 Bezug-Artikel
  python scripts/bezugsautoren_build.py \
      --verdicts lesenswert,scannen,pflichtlektuere     # Skalierung les/scn (~80 min)
  python scripts/bezugsautoren_build.py \
      --repair-empty --throttle 1.0                     # leere Œuvres neu ziehen
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from journal_bot import bezugsautoren as bz
from journal_bot.signals import _normalize_doi_local, _normalize_oa_id

ARTICLES_DB = ROOT / "articles.db"
OWN_REFS_DB = ROOT / "own_refs.db"


def load_attribution():
    con = sqlite3.connect(str(OWN_REFS_DB)); con.row_factory = sqlite3.Row
    oa2works: dict[str, set[str]] = defaultdict(set)
    doi2works: dict[str, set[str]] = defaultdict(set)
    for r in con.execute("SELECT canonical_id, ref_doi, ref_oa_id FROM pub_refs"):
        if r["ref_oa_id"]:
            oa2works[_normalize_oa_id(r["ref_oa_id"])].add(r["canonical_id"])
        if r["ref_doi"]:
            doi2works[_normalize_doi_local(r["ref_doi"])].add(r["canonical_id"])
    oa2works.pop("", None); doi2works.pop("", None)
    zkey2cid = {r["source_item_id"]: r["canonical_id"]
                for r in con.execute("SELECT canonical_id, source_item_id FROM source_refs")
                if r["source_item_id"]}
    con.close()
    return dict(oa2works), dict(doi2works), zkey2cid


def llm_claims(entry_json):
    try:
        bezs = (json.loads(entry_json or "{}").get("bezuege")
                or json.loads(entry_json or "{}").get("bezüge") or [])
    except json.JSONDecodeError:
        return []
    return [str(b["pub_id"]).strip() for b in bezs
            if isinstance(b, dict) and b.get("pub_id")]


def article_oa_refs(row):
    out = set()
    if row["openalex_refs"]:
        try:
            out = {_normalize_oa_id(x) for x in json.loads(row["openalex_refs"]) if x}
        except json.JSONDecodeError:
            pass
    out.discard("")
    return out


def works_for_refs(shared_oa, oa2works):
    w = set()
    for h in shared_oa:
        w |= oa2works.get(h, set())
    return w


def classify(claims, works_hit, n_shared, zkey2cid):
    """corroborated/weak/ungrounded je Claim auf gegebener Basis."""
    c = Counter()
    for pid in claims:
        cid = zkey2cid.get(pid)
        if cid is None:
            c["bad-pubid"] += 1
        elif cid in works_hit:
            c["corroborated"] += 1
        elif n_shared > 0:
            c["weak-anchor"] += 1
        else:
            c["ungrounded"] += 1
    return c


MAX_CONSECUTIVE_FAILURES = 10


def repair_empty(limit: int = 0) -> int:
    """Autoren mit leerem Œuvre (Rate-Limit-Vorfall 2026-07-02) neu ziehen.

    Idempotent: erfolgreiche Autoren verschwinden aus der Zielmenge. Bricht
    nach MAX_CONSECUTIVE_FAILURES Folge-Fehlern laut ab (Limit steht noch).
    """
    con_bz = sqlite3.connect(str(bz.DEFAULT_DB)); con_bz.row_factory = sqlite3.Row
    bz.init_db(con_bz)
    aids = [r["author_oa_id"] for r in con_bz.execute(
        "SELECT author_oa_id FROM authors "
        "WHERE n_works_fetched=0 OR n_works_fetched IS NULL ORDER BY author_oa_id"
    )]
    if limit:
        aids = aids[:limit]
    print(f"Repair: {len(aids)} Autoren mit leerem Œuvre "
          f"(Throttle {bz.THROTTLE_SECONDS}s, UA: {bz.USER_AGENT})")
    client = bz.make_client()
    ok = fail = streak = 0
    try:
        for i, aid in enumerate(aids, 1):
            try:
                n = bz.refresh_author(con_bz, client, aid, force=True)
                ok += 1; streak = 0
                if ok % 100 == 0:
                    print(f"  … {i}/{len(aids)} repariert={ok} fehlgeschlagen={fail}")
            except bz.WorksFetchError as exc:
                fail += 1; streak += 1
                if streak >= MAX_CONSECUTIVE_FAILURES:
                    print(f"\nABBRUCH nach {streak} Folge-Fehlern (Rate-Limit steht "
                          f"vermutlich noch): {exc}")
                    print(f"Bisher repariert: {ok}, fehlgeschlagen: {fail}. "
                          f"Später einfach erneut starten (idempotent).")
                    return 1
    finally:
        client.close(); con_bz.close()
    print(f"\nFertig: {ok} repariert, {fail} fehlgeschlagen.")
    return 0 if fail == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--claims", action="store_true", help="alle Bezug-Artikel")
    ap.add_argument("--verdicts", default="",
                    help="Scope per agent_verdict, kommasepariert "
                         "(z.B. lesenswert,scannen,pflichtlektuere)")
    ap.add_argument("--repair-empty", action="store_true",
                    help="Autoren mit 0 gespeicherten Werken neu ziehen "
                         "(Reparatur nach Rate-Limit-Vorfall)")
    ap.add_argument("--throttle", type=float, default=0.0,
                    help="Throttle in Sekunden überschreiben (Repair: z.B. 1.0)")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    if args.throttle > 0:
        bz.THROTTLE_SECONDS = args.throttle

    if args.repair_empty:
        return repair_empty(limit=args.limit)

    oa2works, doi2works, zkey2cid = load_attribution()
    own_oa = set(oa2works)

    con = sqlite3.connect(str(ARTICLES_DB)); con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT id, title, journal_short, openalex_id, agent_verdict, "
        "openalex_refs, agent_entry_json FROM articles "
        "WHERE openalex_id IS NOT NULL AND openalex_id!=''"
    ).fetchall()
    con.close()
    verdicts = {v.strip() for v in args.verdicts.split(",") if v.strip()}
    if verdicts:
        targets = [r for r in rows if (r["agent_verdict"] or "") in verdicts]
        scope = f"agent_verdict ∈ {sorted(verdicts)}"
    else:
        # Bezug-Artikel = mit ≥1 Werk-Behauptung
        targets = [r for r in rows if llm_claims(r["agent_entry_json"])]
        scope = "Artikel mit LLM-Werk-Bezug"
    if args.limit:
        targets = targets[:args.limit]
    print(f"Ziel: {len(targets)} Artikel [{scope}] (von {len(rows)} mit OpenAlex-ID)")

    con_bz = sqlite3.connect(str(bz.DEFAULT_DB)); con_bz.row_factory = sqlite3.Row
    bz.init_db(con_bz)
    client = bz.make_client()

    art_audit = Counter(); auth_audit = Counter()
    rescued = []          # Artikel: 0 Kopplung auf Artikel-Ebene, >0 auf Autor-Ebene
    n_done = 0
    streak = 0            # Folge-Fehler → lauter Abbruch statt stiller Leer-Œuvres
    for r in targets:
        try:
            res = bz.build_for_article(con_bz, client, r["id"], r["openalex_id"], force=args.force)
            streak = 0
        except bz.WorksFetchError as exc:
            streak += 1
            if streak >= MAX_CONSECUTIVE_FAILURES:
                print(f"\nABBRUCH nach {streak} Folge-Fehlern (Rate-Limit?): {exc}")
                print("Lauf ist idempotent — später einfach erneut starten.")
                client.close(); con_bz.close()
                return 1
            res = None
        n_done += 1
        if n_done % 25 == 0:
            print(f"  … {n_done}/{len(targets)}")
        claims = llm_claims(r["agent_entry_json"])

        # Artikel-Ebene
        art_oa = article_oa_refs(r)
        art_shared = art_oa & own_oa
        art_works = works_for_refs(art_shared, oa2works)
        art_audit += classify(claims, art_works, len(art_shared), zkey2cid)

        # Autor-Ebene
        if res is None:
            auth_refs = set(); auth_shared = set(); auth_works = set()
        else:
            auth_refs = bz.author_ref_set(con_bz, res.author_oa_id)
            auth_shared = auth_refs & own_oa
            auth_works = works_for_refs(auth_shared, oa2works)
        auth_audit += classify(claims, auth_works, len(auth_shared), zkey2cid)

        if len(art_shared) == 0 and len(auth_shared) > 0:
            rescued.append((r["journal_short"], (r["title"] or "")[:60],
                            res.display_name if res else "?", len(auth_shared), len(auth_works)))

        if args.verbose:
            nm = res.display_name if res else "?"
            print(f"  [{r['journal_short']}] {(r['title'] or '')[:54]}")
            print(f"     Autor: {nm} | Artikel-Kopplung={len(art_shared)} "
                  f"→ Autor-Kopplung={len(auth_shared)} (über {len(auth_works)} Werke)")
    client.close(); con_bz.close()

    def show(name, c):
        tot = sum(c[k] for k in ("corroborated", "weak-anchor", "ungrounded", "bad-pubid"))
        print(f"\n{name} (von {tot} Werk-Behauptungen):")
        for k in ("corroborated", "weak-anchor", "ungrounded", "bad-pubid"):
            print(f"   {k:<13}: {c[k]:>4}  ({100*c[k]/max(1,tot):4.1f}%)")

    print(f"\n{'='*70}\nABGLEICH: Artikel-Ebene vs. Autor-Ebene\n{'='*70}")
    show("ARTIKEL-EBENE (alte Basis)", art_audit)
    show("AUTOR-EBENE (neue Basis: 10 neueste + 10 meistzit.)", auth_audit)
    print(f"\nGerettet durch Autor-Ebene (Artikel koppelt 0, Autor koppelt >0): {len(rescued)}")
    for j, t, nm, ns, nw in rescued[:20]:
        print(f"   [{j}] {t}  — {nm}: {ns} Refs / {nw} Werke")
    return 0


if __name__ == "__main__":
    sys.exit(main())
