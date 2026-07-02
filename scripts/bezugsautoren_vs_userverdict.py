"""Kreuzvalidierung: Autor-Kopplungs-Urteil × Benjamins eigene user_verdicts.

Benjamins Frage: Wie habe ICH die "zufallskorrigiert ungrounded" Artikel selbst
bewertet? Bisher ist "ungrounded" nur gegen die Null-Kontrolle validiert
(statistisch), nicht gegen das menschliche Urteil. Dieses Skript kreuzt das
Autor-Kopplungs-Urteil (corroborated/weak/ungrounded, IDF-Schwelle WEAK=1.0)
gegen `user_verdict` der Bezug-Artikel.
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

from journal_bot import bezugsautoren as bz
from journal_bot.own_refs.corpus_freq import load_or_compute_corpus_freq
from journal_bot.own_refs.index import load_own_refs_index
from journal_bot.signals import _normalize_oa_id

ARTICLES_DB = ROOT / "articles.db"
OWN_REFS_DB = ROOT / "own_refs.db"


def llm_claims(entry_json):
    try:
        d = json.loads(entry_json or "{}")
        return [str(b["pub_id"]).strip() for b in (d.get("bezuege") or d.get("bezüge") or [])
                if isinstance(b, dict) and b.get("pub_id")]
    except json.JSONDecodeError:
        return []


def main() -> int:
    own = load_own_refs_index(OWN_REFS_DB)
    own_oa = own.oa_ids
    cf = load_or_compute_corpus_freq(ARTICLES_DB, own)
    con_o = sqlite3.connect(str(OWN_REFS_DB)); con_o.row_factory = sqlite3.Row
    oa2works = defaultdict(set)
    for r in con_o.execute("SELECT canonical_id, ref_oa_id FROM pub_refs"):
        if r["ref_oa_id"]:
            oa2works[_normalize_oa_id(r["ref_oa_id"])].add(r["canonical_id"])
    oa2works.pop("", None)
    zkey2cid = {r["source_item_id"]: r["canonical_id"]
                for r in con_o.execute("SELECT canonical_id, source_item_id FROM source_refs")
                if r["source_item_id"]}
    con_o.close()

    con_bz = sqlite3.connect(str(bz.DEFAULT_DB)); con_bz.row_factory = sqlite3.Row
    seed = {r["article_id"]: r["author_oa_id"]
            for r in con_bz.execute("SELECT article_id, author_oa_id FROM author_seed WHERE role='first_author'")}

    con = sqlite3.connect(str(ARTICLES_DB)); con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT id, user_verdict, agent_verdict, agent_entry_json FROM articles "
        "WHERE agent_entry_json IS NOT NULL AND openalex_id IS NOT NULL AND openalex_id!=''"
    ).fetchall()
    con.close()
    claim_rows = [r for r in rows if llm_claims(r["agent_entry_json"]) and r["id"] in seed]

    # Coverage: wie viele Bezug-Artikel hat Benjamin überhaupt bewertet?
    uv = Counter((r["user_verdict"] or "(nie bewertet)") for r in claim_rows)
    print(f"Bezug-Artikel gesamt: {len(claim_rows)}")
    print("user_verdict-Abdeckung:")
    for k, v in uv.most_common():
        print(f"   {k:<16}: {v}")
    labeled = [r for r in claim_rows if r["user_verdict"]]
    print(f"\n→ von dir tatsächlich bewertet: {len(labeled)} "
          f"({100*len(labeled)/len(claim_rows):.0f}%)\n")

    # Artikel-Status auf Autor-Basis (IDF WEAK=1.0)
    def status(r):
        aid = seed[r["id"]]
        shared = bz.author_ref_set(con_bz, aid) & own_oa
        wh = set().union(*[oa2works[h] for h in shared]) if shared else set()
        idf = bz.coupling_idf(shared, cf)
        claims = llm_claims(r["agent_entry_json"])
        if any(zkey2cid.get(p) in wh for p in claims):
            return "corroborated"
        return "weak" if idf >= bz.AUTHOR_COUPLING_WEAK else "ungrounded"

    # Kreuztabelle nur über die bewerteten
    ct = defaultdict(Counter)
    for r in labeled:
        ct[status(r)][r["user_verdict"]] += 1
    con_bz.close()

    if not labeled:
        print("KEINE der Bezug-Artikel sind von dir bewertet → 'ungrounded' ist NICHT "
              "gegen dein Urteil validiert, nur gegen die Null-Kontrolle.")
        return 0

    verdicts = ["lesenswert", "scannen", "ignorieren", "pflichtlektuere"]
    print(f"{'Autor-Kopplung':<16} | " + " ".join(f"{v[:9]:>10}" for v in verdicts) + f" {'Σ':>5}")
    print("-" * 70)
    for st in ("corroborated", "weak", "ungrounded"):
        row = ct[st]
        tot = sum(row.values())
        print(f"{st:<16} | " + " ".join(f"{row.get(v,0):>10}" for v in verdicts) + f" {tot:>5}")
    print()
    # Kernfrage: was sagte Benjamin zu den 'ungrounded'?
    ung = ct["ungrounded"]; ung_tot = sum(ung.values())
    if ung_tot:
        les = ung.get("lesenswert", 0) + ung.get("pflichtlektuere", 0)
        print(f"Von {ung_tot} 'ungrounded' Bezug-Artikeln, die du bewertet hast:")
        print(f"   lesenswert/pflicht: {les}  ({100*les/ung_tot:.0f}%)")
        print(f"   scannen:            {ung.get('scannen',0)}")
        print(f"   ignorieren:         {ung.get('ignorieren',0)}  ({100*ung.get('ignorieren',0)/ung_tot:.0f}%)")
        print("\nLesart: hoher 'ignorieren'-Anteil → 'ungrounded' deckt sich mit deinem Urteil.")
        print("        hoher 'lesenswert'-Anteil → Kopplung verfehlt Relevanz, die du siehst.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
