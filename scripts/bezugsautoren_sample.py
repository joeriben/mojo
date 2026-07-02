"""Blindes Label-Sample aus den ungelabelten Bezug-Artikeln.

Benjamins Frage hat die Ground-Truth-Lücke aufgedeckt: 80 % der Bezug-Artikel
sind nie von ihm bewertet, also ruht "ungrounded = ohne Anbindung" allein auf
LLM-Claim-vs-Kopplung + Null-Kontrolle, nicht auf seinem Urteil.

KORREKTUR (Benjamins Einwand am Sample): Zwei Kontaminationen machen das L/S/I-
Urteil als Relevanzsignal ungültig und müssen RAUS:
  (1) Recency — MOJO ist Wochen-Scanner; ein Relevanzurteil an Alt-Artikeln ist
      ein Kategorienfehler. Nur aktuelles Material (>= MIN_YEAR).
  (2) Eigener Fußabdruck — Selbst-/Ko-Autorschaft + eigene Projekte = "muss ich
      kennen", kein Relevanzsignal; bläht die Kopplungs-Korrelation künstlich auf.
      Selbst-Autorschaft wird hier gefiltert; institutionelle Muss-Kenntnis (eigene
      Projekte, Ko-Autor:innen) markiert Benjamin in der /label-Ansicht via
      "kenne ich"-Button → landet in label_exclusions.json → hier ausgeschlossen.

Schreibt ein STRATIFIZIERTES, BLINDES Sample (über-gewichtet auf 'ungrounded' =
strittige Zelle) als:
  - bezugsautoren_sample_label.md  → reine Abstracts + Metadaten (Backup/Lesbarkeit)
  - bezugsautoren_sample_key.json  → versteckter Schlüssel (Bucket + Kopplungsdetails)
Die eigentliche Bewertung läuft über die Web-UI /label (Klick → articles.db).
"""

from __future__ import annotations

import json
import random
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
SHEET = ROOT / "bezugsautoren_sample_label.md"
KEY = ROOT / "bezugsautoren_sample_key.json"
EXCLUSIONS_FILE = ROOT / "label_exclusions.json"

SEED = 42
# Recency-Fenster fürs Interesse-Sample (SINCE_YEAR=2018 ist nur die Fetch-Grenze).
MIN_YEAR = 2024
TARGET = {"ungrounded": 18, "weak": 5, "corroborated": 8}  # über-gewichtet auf ungrounded


def llm_claims(entry_json):
    try:
        d = json.loads(entry_json or "{}")
        return [str(b["pub_id"]).strip() for b in (d.get("bezuege") or d.get("bezüge") or [])
                if isinstance(b, dict) and b.get("pub_id")]
    except json.JSONDecodeError:
        return []


def authors_str(authors_json):
    try:
        a = json.loads(authors_json or "[]")
    except json.JSONDecodeError:
        return ""
    names = []
    for x in a:
        if isinstance(x, str):
            names.append(x)
        elif isinstance(x, dict):
            names.append(x.get("name") or x.get("display_name") or "")
    names = [n for n in names if n]
    if len(names) > 4:
        return ", ".join(names[:4]) + f" u. a. ({len(names)})"
    return ", ".join(names)


def best_abstract(row):
    ab = (row["abstract"] or "").strip()
    if ab and not ab.startswith("{"):
        return ab
    oa = (row["openalex_abstract"] or "").strip()
    if oa and not oa.startswith("{"):
        return oa
    return ""


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
    cid_meta = {r["canonical_id"]: (r["title"], r["year"])
                for r in con_o.execute("SELECT canonical_id, title, year FROM publications")}
    con_o.close()

    excluded_ids = set()
    if EXCLUSIONS_FILE.exists():
        try:
            excluded_ids = set(json.loads(EXCLUSIONS_FILE.read_text(encoding="utf-8")).keys())
        except (json.JSONDecodeError, OSError):
            pass

    con_bz = sqlite3.connect(str(bz.DEFAULT_DB)); con_bz.row_factory = sqlite3.Row
    seed = {r["article_id"]: r["author_oa_id"]
            for r in con_bz.execute("SELECT article_id, author_oa_id FROM author_seed WHERE role='first_author'")}

    con = sqlite3.connect(str(ARTICLES_DB)); con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT id, title, authors_json, journal_full, journal_short, year, abstract, "
        "openalex_abstract, agent_entry_json FROM articles "
        "WHERE agent_entry_json IS NOT NULL AND openalex_id IS NOT NULL AND openalex_id!='' "
        "AND (user_verdict IS NULL OR user_verdict='')"
    ).fetchall()
    con.close()

    # Nur ungelabelte Bezug-Artikel mit Erstautor, Abstract, aktuell, extern
    pool = []
    n_old = n_self = n_excl = 0
    for r in rows:
        if not (llm_claims(r["agent_entry_json"]) and r["id"] in seed):
            continue
        if not best_abstract(r):
            continue
        try:
            yr = int(str(r["year"])[:4])
        except (ValueError, TypeError):
            yr = 0
        if yr < MIN_YEAR:
            n_old += 1; continue
        au = (r["authors_json"] or "").lower()
        if "örissen" in au or "orissen" in au:  # Selbst-Autorschaft
            n_self += 1; continue
        if r["id"] in excluded_ids:             # manuell als "kenne ich" markiert
            n_excl += 1; continue
        aid = seed[r["id"]]
        shared = bz.author_ref_set(con_bz, aid) & own_oa
        wh = set().union(*[oa2works[h] for h in shared]) if shared else set()
        idf = bz.coupling_idf(shared, cf)
        claims = llm_claims(r["agent_entry_json"])
        hit_cids = [zkey2cid.get(p) for p in claims if zkey2cid.get(p) in wh]
        if hit_cids:
            bucket = "corroborated"
        elif idf >= bz.AUTHOR_COUPLING_WEAK:
            bucket = "weak"
        else:
            bucket = "ungrounded"
        pool.append({"row": r, "bucket": bucket, "idf": round(idf, 2), "year": yr,
                     "shared_n": len(shared), "hit_cids": hit_cids})
    con_bz.close()

    dist = Counter(p["bucket"] for p in pool)
    print(f"Gefiltert raus: {n_old} alt (<{MIN_YEAR}), {n_self} selbst-autoriert, "
          f"{n_excl} manuell ausgeschlossen.")
    print(f"Sauberer Pool (>= {MIN_YEAR}, extern, ungelabelt): {len(pool)}")
    print("Bucket-Verteilung:", dict(dist))

    rng = random.Random(SEED)
    chosen = []
    for bucket, k in TARGET.items():
        cand = [p for p in pool if p["bucket"] == bucket]
        rng.shuffle(cand)
        chosen.extend(cand[:k])
    rng.shuffle(chosen)  # Reihenfolge mischen → Bucket nicht ablesbar
    print(f"Gewählt: {len(chosen)} ({dict(Counter(p['bucket'] for p in chosen))})\n")

    # Label-Sheet (blind, Backup)
    lines = ["# Bezug-Sample — blinde Relevanz-Bewertung", "",
             f"{len(chosen)} aktuelle (>= {MIN_YEAR}), externe Artikel mit LLM-Werk-Bezug, "
             "die du noch nie bewertet hast. Kopplungs-Bucket verborgen — Urteil nur am Abstract. "
             "(Eigentliche Bewertung über die Web-UI /label.)", "",
             "**Bitte je Eintrag:** `L` = lesenswert · `S` = scannen · `I` = ignorieren · "
             "`⊘` = kenne ich / Pflicht (raus aus der Wertung).", "", "---", ""]
    key = []
    for i, p in enumerate(chosen, 1):
        r = p["row"]
        journal = r["journal_full"] or r["journal_short"] or "—"
        lines += [f"## {i}",
                  f"**Titel:** {r['title']}",
                  f"**Autor(en):** {authors_str(r['authors_json']) or '—'}",
                  f"**Journal:** {journal} ({r['year'] or '—'})", "",
                  best_abstract(r), "",
                  "**Urteil:** ___", "", "---", ""]
        key.append({"n": i, "id": r["id"], "title": r["title"], "journal": journal,
                    "year": p["year"], "bucket": p["bucket"], "idf": p["idf"],
                    "shared_n": p["shared_n"],
                    "hit_works": [{"cid": c, "title": cid_meta.get(c, ("?", "?"))[0],
                                   "year": cid_meta.get(c, ("?", "?"))[1]} for c in p["hit_cids"]]})

    SHEET.write_text("\n".join(lines), encoding="utf-8")
    KEY.write_text(json.dumps(key, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"→ Label-Sheet: {SHEET}")
    print(f"→ Schlüssel:   {KEY}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
