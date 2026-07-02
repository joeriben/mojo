"""Korpus-Audit: alle vorhandenen LLM-Analysen gegen grounded Bibliografie.

Motiv (Benjamin 2026-05-30): MOJO-1-Kommentare behaupten Werk-Bezüge
("erweitert / parallelisiert Jörissen X"), die bibliografisch teils nicht
gedeckt sind (Bsp. indigene Sprachen: 0 geteilte Refs, trotzdem 2 Bezüge).
Dieser Lauf prüft ALLE gespeicherten LLM-Analysen (agent_entry_json) gegen
die nachprüfbare geteilte Literatur aus own_refs.db.

Pro LLM-Werk-Behauptung (bezuege[].pub_id, ein Zotero-Key):
  - corroborated  : Artikel teilt ≥1 Referenz mit GENAU diesem Werk
  - weak-anchor   : Artikel teilt Refs mit IRGENDEINEM deiner Werke, aber
                    nicht mit dem benannten
  - ungrounded    : Artikel teilt 0 Referenzen mit deinem Korpus (reine
                    thematische Konfabulation)
  - bad-pubid     : pub_id nicht in deiner Bibliothek auflösbar

Kein LLM. Kein Netzwerk (Titel werden für die Aggregat-Statistik nicht
gebraucht). Reine Set-Operationen gegen own_refs.db.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from journal_bot.signals import _normalize_doi_local, _normalize_oa_id

ARTICLES_DB = ROOT / "articles.db"
OWN_REFS_DB = ROOT / "own_refs.db"


def load_attribution():
    con = sqlite3.connect(str(OWN_REFS_DB))
    con.row_factory = sqlite3.Row
    oa2works: dict[str, set[str]] = defaultdict(set)
    doi2works: dict[str, set[str]] = defaultdict(set)
    for r in con.execute("SELECT canonical_id, ref_doi, ref_oa_id FROM pub_refs"):
        if r["ref_oa_id"]:
            oa2works[_normalize_oa_id(r["ref_oa_id"])].add(r["canonical_id"])
        if r["ref_doi"]:
            doi2works[_normalize_doi_local(r["ref_doi"])].add(r["canonical_id"])
    oa2works.pop("", None)
    doi2works.pop("", None)
    zkey2cid: dict[str, str] = {}
    for r in con.execute("SELECT canonical_id, source_item_id FROM source_refs"):
        if r["source_item_id"]:
            zkey2cid[r["source_item_id"]] = r["canonical_id"]
    con.close()
    return dict(oa2works), dict(doi2works), zkey2cid


def article_shared_works(row, oa2works, doi2works) -> tuple[set[str], int]:
    """works_hit (canonical_ids) + Anzahl distinkter geteilter Referenzen."""
    works: set[str] = set()
    n_shared = 0
    if row["openalex_refs"]:
        try:
            oa = {_normalize_oa_id(x) for x in json.loads(row["openalex_refs"]) if x}
        except json.JSONDecodeError:
            oa = set()
        for h in oa & oa2works.keys():
            works |= oa2works[h]
            n_shared += 1
    if row["crossref_refs"]:
        try:
            dois = set()
            for x in json.loads(row["crossref_refs"]):
                if isinstance(x, dict):
                    d = _normalize_doi_local(x.get("doi"))
                    if d.startswith("10."):
                        dois.add(d)
        except json.JSONDecodeError:
            dois = set()
        for d in dois & doi2works.keys():
            works |= doi2works[d]
            n_shared += 1
    return works, n_shared


def llm_claims(entry_json: str | None) -> list[str]:
    if not entry_json:
        return []
    try:
        e = json.loads(entry_json)
    except json.JSONDecodeError:
        return []
    bez = e.get("bezuege") or e.get("bezüge") or []
    out = []
    if isinstance(bez, list):
        for b in bez:
            if isinstance(b, dict) and b.get("pub_id"):
                out.append(str(b["pub_id"]).strip())
    return out


def main() -> int:
    oa2works, doi2works, zkey2cid = load_attribution()
    print(f"own_refs: {len(oa2works)} OA-Refs, {len(doi2works)} DOI-Refs über "
          f"{len(set(zkey2cid.values()))} Werke; {len(zkey2cid)} Zotero-Keys gemappt")

    con = sqlite3.connect(str(ARTICLES_DB))
    con.row_factory = sqlite3.Row
    cur = con.execute(
        "SELECT id, title, journal_short, agent_verdict, user_verdict, "
        "openalex_refs, crossref_refs, citation_hits_json, agent_entry_json "
        "FROM articles WHERE agent_entry_json IS NOT NULL"
    )

    n = 0
    overlap_bucket = Counter()         # 0 / 1-4 / 5+
    cites_you = 0
    n_with_claims = 0
    claim_verdict = Counter()          # corroborated / weak / ungrounded / bad-pubid
    total_claims = 0
    fully_confab = 0                   # Artikel: ≥1 Claim, aber n_shared==0
    confab_examples = []               # (id, journal, title, pub_ids)
    missed_examples = []               # grounded reich, aber LLM nannte keinen Bezug
    grounded_some_no_claim = 0

    for row in cur:
        n += 1
        if n % 3000 == 0:
            print(f"  … {n} verarbeitet")
        works, n_shared = article_shared_works(row, oa2works, doi2works)
        overlap_bucket["0" if n_shared == 0 else ("1-4" if n_shared <= 4 else "5+")] += 1
        if row["citation_hits_json"] and row["citation_hits_json"] not in ("[]", "null"):
            cites_you += 1

        claims = llm_claims(row["agent_entry_json"])
        if claims:
            n_with_claims += 1
            article_has_grounding = n_shared > 0
            if not article_has_grounding and len(confab_examples) < 25:
                confab_examples.append(
                    (row["id"][:16], row["journal_short"], (row["title"] or "")[:70], claims))
            if not article_has_grounding:
                fully_confab += 1
            for pid in claims:
                total_claims += 1
                cid = zkey2cid.get(pid)
                if cid is None:
                    claim_verdict["bad-pubid"] += 1
                elif cid in works:
                    claim_verdict["corroborated"] += 1
                elif n_shared > 0:
                    claim_verdict["weak-anchor"] += 1
                else:
                    claim_verdict["ungrounded"] += 1
        else:
            # LLM nennt keinen Bezug, aber Bibliografie hätte welche — verpasst
            if n_shared >= 5:
                grounded_some_no_claim += 1
                if len(missed_examples) < 15:
                    missed_examples.append(
                        (row["id"][:16], row["journal_short"], (row["title"] or "")[:70],
                         n_shared, len(works), row["agent_verdict"]))
    con.close()

    print(f"\n{'='*78}\nKORPUS-AUDIT: {n} LLM-Analysen\n{'='*78}")
    print("\n— Bibliografische Anbindung an deinen Korpus (alle Analysen) —")
    for k in ("0", "1-4", "5+"):
        c = overlap_bucket[k]
        print(f"   geteilte Refs {k:>4}: {c:>6}  ({100*c/max(1,n):4.1f}%)")
    print(f"   zitiert dich direkt:   {cites_you:>6}  ({100*cites_you/max(1,n):4.1f}%)")

    print("\n— LLM-Werk-Bezüge (die expliziten 'erweitert X'-Behauptungen) —")
    print(f"   Analysen mit ≥1 Werk-Bezug: {n_with_claims}")
    print(f"   Werk-Behauptungen gesamt:   {total_claims}")
    if total_claims:
        for k in ("corroborated", "weak-anchor", "ungrounded", "bad-pubid"):
            c = claim_verdict[k]
            print(f"     {k:<13}: {c:>5}  ({100*c/total_claims:4.1f}%)")
    print(f"   Analysen mit Bezug ABER 0 geteilte Refs (reine Konfabulation): "
          f"{fully_confab}/{n_with_claims} "
          f"({100*fully_confab/max(1,n_with_claims):.1f}%)")
    print(f"   Analysen OHNE Bezug, aber ≥5 geteilte Refs (LLM verpasst Anbindung): "
          f"{grounded_some_no_claim}")

    if confab_examples:
        print("\n— Beispiele: LLM behauptet Werk-Bezug, 0 bibliografische Deckung —")
        for aid, j, t, pids in confab_examples[:15]:
            print(f"   [{j}] {t}")
            print(f"        id={aid}  behauptet: {', '.join(pids)}")
    if missed_examples:
        print("\n— Beispiele: dichte geteilte Literatur, aber LLM nennt keinen Bezug —")
        for aid, j, t, ns, nw, av in missed_examples:
            print(f"   [{j}] {t}  ({ns} Refs / {nw} Werke, verdict={av})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
