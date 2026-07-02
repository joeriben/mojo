#!/usr/bin/env python3
"""Proto-Indikator: compute the SOURCE-TOPOLOGY between K and two candidates.

NOT a read, a computation. For each pair (K<->Bettinger, K<->MacGilchrist):
  - parse the real reference lists (first-author surname + year),
  - canonicalize surnames (diacritic-stripped, lowercased),
  - set ops: shared = K ∩ cand, cand_only = cand \\ K, K_only = K \\ cand,
  - multiplicity = distinct cited works per first-author surname,
  - cites-you = does cand cite Jörissen / Marotzki anywhere in its refs,
  - K body citation DENSITY = #(surname directly followed by a year) in K's
    running text (resolves against the bib; excludes the bare word problem).

Honesty notes printed inline: set-ops are at FIRST-AUTHOR grain (a known
under-count for co-authored shared sources); shared is therefore augmented by a
co-author-inclusive substring pass and reported separately.
"""
import re, unicodedata
from pathlib import Path

K_MD   = Path("/tmp/benchmark_jklk.md")          # K full text; bib = lines 74-124, body = 1-72
BETT   = Path("/tmp/bettinger2022.txt")          # refs from line 712
MACG   = Path("/tmp/macgilchrist2021.txt")       # refs from line 332

YEAR = re.compile(r"(?:19|20)\d{2}")

def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.replace("ß", "ss")
    return re.sub(r"\s+", " ", s).strip().lower()

def first_author_surname(entry: str) -> str:
    # entry begins "Surname, Initial..." or "Surname/Co..." -> take up to first comma/slash
    head = re.split(r"[,/]", entry.strip(), maxsplit=1)[0]
    return norm(head)

def year_of(entry: str):
    m = YEAR.search(entry)
    return m.group(0) if m else None

# ---- K bibliography (one entry per line) -------------------------------------
k_lines = K_MD.read_text(encoding="utf-8").splitlines()
k_bib_raw = [l for l in k_lines[73:124] if l.strip()]            # lines 74-124
k_body = "\n".join(k_lines[0:72])

def parse_oneline_bib(lines):
    works = []   # (surname, year, raw)
    for l in lines:
        if not YEAR.search(l):
            continue
        works.append((first_author_surname(l), year_of(l), l.strip()))
    return works

# ---- candidate refs: entry-start at col0 + comma, continuation indented -------
def parse_block_bib(path: Path, start_line: int):
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    body = lines[start_line:]                # 0-based; start_line = index of "References"/"Literatur"
    entries, cur = [], ""
    for l in lines[start_line+1:]:
        if re.match(r"^[A-ZÄÖÜ][^,\n]{0,45},", l):      # new entry start
            if cur:
                entries.append(cur)
            cur = l.strip()
        elif l.strip() and re.match(r"^\s+\S", l):       # indented continuation
            cur += " " + l.strip()
        else:                                             # blank / page header -> flush
            if cur:
                entries.append(cur); cur = ""
    if cur:
        entries.append(cur)
    works = []
    for e in entries:
        y = year_of(e)
        if not y:            # page headers, stray lines
            continue
        works.append((first_author_surname(e), y, e))
    return works, "\n".join(lines[start_line:])

k_works = parse_oneline_bib(k_bib_raw)
b_works, b_refs_text = parse_block_bib(BETT, 711)     # line 712 -> index 711
m_works, m_refs_text = parse_block_bib(MACG, 331)     # line 332 -> index 331

SELF = {"jorissen", "klepacki", "marotzki"}           # K authors + co-author (own-trajectory)

def author_set(works):
    return {s for s, y, e in works if s}

def multiplicity(works):
    d = {}
    for s, y, e in works:
        d.setdefault(s, set()).add(y)
    return {s: len(ys) for s, ys in d.items()}

def pair(name, c_works, c_refs_text):
    K = author_set(k_works)
    C = author_set(c_works)
    shared = sorted(K & C)
    cand_only = sorted(C - K)
    k_only = sorted(K - C)
    mK, mC = multiplicity(k_works), multiplicity(c_works)
    cnorm = norm(c_refs_text)
    # co-author-augmented shared: K first-authors that appear ANYWHERE in cand refs
    aug = sorted(s for s in (K - C) if s and re.search(r"\b"+re.escape(s)+r"\b", cnorm))
    cites_you = sorted(t for t in ["jorissen", "marotzki"] if re.search(r"\b"+t+r"\b", cnorm))
    print(f"\n{'='*72}\n{name}\n{'='*72}")
    print(f"|K works|={len(k_works)} |K authors|={len(K)}   "
          f"|cand works|={len(c_works)} |cand authors|={len(C)}")
    print(f"\nSHARED authors (first-author grain)  n={len(shared)}:")
    for s in shared:
        print(f"   {s:<26} mult_K={mK.get(s,0)}  mult_cand={mC.get(s,0)}")
    print(f"\nSHARED via co-author augmentation (K first-author appears in cand refs) n={len(aug)}:")
    print("   " + (", ".join(aug) if aug else "—"))
    print(f"\nCITES-YOU (Jörissen/Marotzki in cand refs): {cites_you or '—'}")
    print(f"\nCAND-ONLY authors with mult_cand>=2 (disjoint, multiply-cited) :")
    for s in sorted(cand_only, key=lambda x: -mC.get(x,0)):
        if mC.get(s,0) >= 2:
            print(f"   {s:<26} mult_cand={mC.get(s,0)}")
    return dict(shared=shared, cand_only=cand_only, k_only=k_only, mC=mC)

print("K first-author multiplicity (distinct works), mult>=2:")
mK = multiplicity(k_works)
for s in sorted(mK, key=lambda x: -mK[x]):
    if mK[s] >= 2:
        tag = " [SELF]" if s in SELF else ""
        print(f"   {s:<26} {mK[s]}{tag}")

# ---- K body citation DENSITY (proper: surname directly followed by a year) ----
print("\nK BODY citation-event density (surname + nearby year), operative cands:")
probe = ["barad","brown","latour","wulf","haraway","ranciere","schatzki",
         "puig de la bellacasa","gosnell","bohme","anders","jorissen","klepacki"]
kb = norm(k_body)
for s in probe:
    # surname, optional spaces/comma/paren, then a 19xx/20xx year within a few chars
    pat = re.compile(r"\b"+re.escape(s)+r"\b[\s,(]{0,3}(?:19|20)\d{2}")
    raw = len(re.findall(r"\b"+re.escape(s)+r"\b", kb))
    cited = len(pat.findall(kb))
    tag = " [SELF]" if s.split()[0] in SELF else ""
    print(f"   {s:<24} raw_substring={raw:<3} citation_events={cited}{tag}")

b = pair("K  ↔  BETTINGER 2022", b_works, b_refs_text)
m = pair("K  ↔  MACGILCHRIST 2021", m_works, m_refs_text)

# ---- M4 MUST-KNOW: run the rule over the FULL disjoint-operative set ----------
# Functionality proof, not cherry-pick. Rule: a cand-only source that is (a) operative
# in the candidate (mult_cand>=2) AND (b) absent from Benjamin's WHOLE cited corpus
# (own_refs.pub_refs, 6244 refs) is a Must-Know suggestion. The test is PRECISION:
# does the rule stay quiet on the non-candidates, or does it propose junk?
import sqlite3
OWN = Path(__file__).resolve().parent.parent / "own_refs.db"
print(f"\n{'='*72}\nM4 MUST-KNOW — Regel über die VOLLE disjunkt-operative Menge (Präzisionstest)\n{'='*72}")
if not OWN.exists():
    print("   own_refs.db not found")
else:
    oc = sqlite3.connect(str(OWN))
    def corpus_hits(surname):
        return oc.execute("select count(*) from pub_refs where lower(ref_text) like ?",
                          (f"%{surname}%",)).fetchone()[0]
    def must_know(name, res, self_author):
        print(f"\n--- {name} ---")
        cand_only, mC = res['cand_only'], res['mC']
        cands = sorted([s for s in cand_only if mC.get(s, 0) >= 2], key=lambda x: -mC[x])
        for s in cands:
            n = corpus_hits(s)
            short = " [substring-unsicher <5]" if len(s) < 5 else ""
            slf   = " [Kandidaten-Selbstautor]" if s == self_author else ""
            verdict = "★ MUST-KNOW" if n == 0 else f"gefiltert (Korpus={n})"
            print(f"   {s:<22} mult_cand={mC[s]}  corpus={n:<4} {verdict}{short}{slf}")
    must_know("MacGilchrist 2021", m, "macgilchrist")
    must_know("Bettinger 2022",    b, "bettinger")
    print("\n   Sanity (Heimat-Terrain, muss gefiltert sein): "
          + ", ".join(f"{s}={corpus_hits(s)}" for s in ["barad","haraway","schatzki","koller"]))

    # ---- O5 DISCIPLINE-GATE proxy: candidate field-proximity via corpus overlap --
    # The must-know rule must only fire for IN-FIELD candidates. Field-proximity proxy =
    # fraction of the candidate's authors that Benjamin has cited anywhere. High = in-field.
    # NOTE: this tests the ADMIT direction only (both candidates are in-field); the REJECT
    # direction (a far-field candidate's must-knows suppressed) is untested for lack of one.
    print(f"\n{'='*72}\nO5 DISCIPLINE-GATE (proxy) — Feld-Nähe = Anteil Kandidaten-Autoren, die Benjamin je zitiert\n{'='*72}")
    def disc_overlap(name, works):
        A = [s for s in author_set(works) if len(s) >= 5]   # >=5ch: substring-LIKE safer
        present = [s for s in A if corpus_hits(s) > 0]
        frac = len(present) / max(1, len(A))
        print(f"   {name:<16} authors(>=5ch)={len(A):<3} in_corpus={len(present):<3} field-overlap={frac:.0%}")
    disc_overlap("MacGilchrist", m_works)
    disc_overlap("Bettinger", b_works)
