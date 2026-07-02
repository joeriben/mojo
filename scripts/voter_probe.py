"""Schritt 1: Cheap-LLM-Voter-Sondierung auf 15 gelabelten Artikeln / 3 Diskursräumen.

Testet den BINÄREN Voter (weitergeben/ignorieren), symmetrisch — beide Modelle
dieselbe Frage. Variable unter Test: die Lenience-Klausel ist RAUS ("im Zweifel
weitergeben"), das Kriterium ist auf Auseinandersetzung-statt-Vokabular geschärft.
Sonst minimal verändert ggü. dem Vorlauf, damit before/after vergleichbar bleibt.
Feld-Modus: Ein-Pass-über-die-3-Räume vs. fokussiert-pro-Diskursraum.

Zwei Stimmen: deepseek/deepseek-v3.2 + google/gemini-3.5-flash.
Grounding config-getrieben aus DISCOURSE_SPACES (diskursraeume.json) — kein Name,
keine Institution, kein Zitat-Kriterium. Kombination via journal_bot.combine.

Zweck: (a) EXAKTE Kosten pro Call/Modell/Design messen; (b) Augenschein, ob der
binäre Voter ohne Lenience noch sättigt; (c) erster Diskriminations-Blick gegen
user_verdict (n=15 — Indikation, kein Urteil). HARTER Kosten-Cap. Schreibt nichts.
"""

from __future__ import annotations

import json
import re
import sqlite3
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from journal_bot.combine import combine_votes
from journal_bot.llm_client import build_client
from journal_bot.settings import DISCOURSE_SPACES, JOURNALS

ARTICLES_DB = ROOT / "articles.db"
OUT = ROOT / "voter_probe_result.json"

SPACES = ["digitale_kultur", "medienpaed", "aesthetische_kulturelle_bildung"]
MODEL_A = "deepseek/deepseek-v3.2"      # Stimme A — selber binärer Prompt
MODEL_B = "google/gemini-3.5-flash"     # Stimme B — selber binärer Prompt
KEEP = {"lesenswert", "scannen", "pflichtlektuere"}

PER_CALL_CAP = 0.01      # $ — Abbruch, falls ein einzelner Call teurer ist
TOTAL_CAP = 0.50         # $ — Gesamt-Abbruch
PRICE = {  # Fallback nur, falls OpenRouter keinen cost meldet ($/Mio in,out)
    "deepseek/deepseek-v3.2": (0.27, 0.40),
    "google/gemini-3.5-flash": (0.30, 2.50),
}


# ── Prompts (config-getrieben, unpersönlich) ─────────────────────────────────

def _space_line(s: str) -> str:
    return f"{DISCOURSE_SPACES[s]['name']}: {DISCOURSE_SPACES[s]['description']}"


def _field(spaces, single):
    if single:
        return _space_line(single), "this space"
    return ("\n".join(f"- {_space_line(s)}" for s in spaces), "at least one of these spaces")


def prompt_sym(spaces, single=None):
    field, scope = _field(spaces, single)
    head = "The following discourse space is defined as:" if single else \
           "The following discourse spaces are defined as:"
    return (f"{head}\n{field}\n\n"
            "You receive the title, journal and abstract of a new article. Decide whether the "
            f"article engages the questions, concepts or problems that define {scope} — including "
            "from another discipline. Engagement means taking those questions up, not merely "
            "sharing the vocabulary or sitting in an adjacent topic.\n\n"
            'Answer with exactly one word first — "weitergeben" or "ignorieren" — then "—" and a '
            "reason in ≤15 words. Judge what the article does, not what it is about.\n"
            "weitergeben: it engages this field.  ignorieren: it does not.")


def user_payload(a):
    return (f"Journal: {a['journal']}\nTitel: {a['title']}\n"
            f"Abstract: {(a['abstract'] or '(kein Abstract)')[:2000]}")


# ── Sample ───────────────────────────────────────────────────────────────────

def build_sample():
    j2c = {j.short: set(getattr(j, "clusters", []) or []) for j in JOURNALS}
    con = sqlite3.connect(str(ARTICLES_DB)); con.row_factory = sqlite3.Row
    rows = con.execute(
        "SELECT id, journal_short, journal_full, title, abstract, user_verdict "
        "FROM articles WHERE user_verdict IS NOT NULL AND user_verdict!='' "
        "AND abstract IS NOT NULL AND length(abstract)>120 ORDER BY id"
    ).fetchall()
    con.close()
    picked, seen = [], set()
    for sp in SPACES:
        keep = [r for r in rows if r["id"] not in seen and sp in j2c.get(r["journal_short"], set())
                and r["user_verdict"] in KEEP]
        disc = [r for r in rows if r["id"] not in seen and sp in j2c.get(r["journal_short"], set())
                and r["user_verdict"] not in KEEP]
        chosen = keep[:3] + disc[:2]
        if len(chosen) < 5:  # auffüllen
            chosen += [r for r in (keep[3:] + disc[2:]) if r not in chosen][:5 - len(chosen)]
        for r in chosen:
            seen.add(r["id"])
            picked.append({"id": r["id"], "home_space": sp, "journal": r["journal_full"] or r["journal_short"],
                           "title": r["title"], "abstract": r["abstract"],
                           "user_verdict": r["user_verdict"], "truth_keep": r["user_verdict"] in KEEP})
    return picked


# ── LLM-Call mit Cost-Cap ─────────────────────────────────────────────────────

_client = None
_spent = [0.0]


def _cost_from(resp, model):
    u = resp.usage
    c = 0.0
    try:
        d = u.model_dump() if hasattr(u, "model_dump") else {}
        c = float(d.get("cost") or 0.0)
    except Exception:
        d = {}
    if c == 0.0:
        pin, pout = PRICE.get(model, (1.0, 1.0))
        c = (getattr(u, "prompt_tokens", 0) or 0) / 1e6 * pin + \
            (getattr(u, "completion_tokens", 0) or 0) / 1e6 * pout
    return c


def call(model, system, user):
    global _client
    if _client is None:
        _client = build_client()
    resp = _client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
        temperature=0.0, max_tokens=200,
        extra_body={"usage": {"include": True}},
    )
    raw = (resp.choices[0].message.content or "").strip()
    cost = _cost_from(resp, model)
    if cost > PER_CALL_CAP:
        raise RuntimeError(f"COST-CAP: Einzel-Call ${cost:.4f} > ${PER_CALL_CAP} ({model}). Abbruch.")
    _spent[0] += cost
    if _spent[0] > TOTAL_CAP:
        raise RuntimeError(f"COST-CAP: Gesamt ${_spent[0]:.4f} > ${TOTAL_CAP}. Abbruch.")
    return raw, cost


# vocab[0] ("weitergeben") ist der Parser-Default bei unparsebarem Output ⇒ recall-
# schützend AUF PARSER-EBENE (nicht im Prompt — dort steht keine Lenience mehr).
VOCAB = {"sym": ("weitergeben", "ignorieren")}


def first_word(raw, role="sym"):
    """Früheste Wortgrenzen-Übereinstimmung aus dem Vokabular."""
    t = raw.strip().lower()
    vocab = VOCAB[role]
    best, best_pos = None, 10 ** 9
    for tok in vocab:
        m = re.search(rf"\b{re.escape(tok)}\b", t)
        if m and m.start() < best_pos:
            best, best_pos = tok, m.start()
    return best or vocab[0]


if __name__ == "__main__":
    sample = build_sample()
    print(f"Sample: {len(sample)} Artikel über {len(SPACES)} Räume — "
          f"behalten {sum(a['truth_keep'] for a in sample)}, "
          f"wegwerfen {sum(not a['truth_keep'] for a in sample)}")
    for a in sample:
        print(f"  [{a['home_space'][:14]:<14}] {a['user_verdict']:<12} {a['title'][:60]}")

    # Tasks bauen: (article_idx, variant, model, role, space|None, system)
    tasks = []
    for i, a in enumerate(sample):
        u = user_payload(a)
        # symmetrisch, binär — beide Modelle dieselbe Frage
        tasks.append((i, "sym_onepass", MODEL_A, "sym", None, prompt_sym(SPACES), u))
        tasks.append((i, "sym_onepass", MODEL_B, "sym", None, prompt_sym(SPACES), u))
        for s in SPACES:
            tasks.append((i, "sym_perspace", MODEL_A, "sym", s, prompt_sym(SPACES, s), u))
            tasks.append((i, "sym_perspace", MODEL_B, "sym", s, prompt_sym(SPACES, s), u))

    print(f"\n{len(tasks)} Calls geplant. Starte (Cap ${PER_CALL_CAP}/Call, ${TOTAL_CAP} gesamt)…")
    results = {}
    cost_by = defaultdict(float)
    aborted = None

    def run(t):
        i, variant, model, role, space, system, u = t
        raw, c = call(model, system, u)
        return t, raw, c

    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(run, t): t for t in tasks}
        done = 0
        for fut in as_completed(futs):
            try:
                t, raw, c = fut.result()
            except Exception as e:
                aborted = str(e)
                break
            i, variant, model, role, space, system, u = t
            results.setdefault(i, {}).setdefault(variant, {}).setdefault(model, {})[space or "_"] = \
                {"role": role, "word": first_word(raw, role), "raw": raw[:160], "cost": c}
            cost_by[(variant, model)] += c
            done += 1
            if done % 40 == 0:
                print(f"  … {done}/{len(tasks)}  (Σ ${_spent[0]:.4f})")

    if aborted:
        print(f"\n!!! ABGEBROCHEN: {aborted}\n  bis dahin ausgegeben: ${_spent[0]:.4f}")
        sys.exit(1)

    # ── Auswertung ──
    def model_keep(rec_for_model):
        """rec_for_model: {space: {word,...}} für EIN Modell. keep-vote (bool).
        per-space: behält, wenn IRGENDEIN Raum 'weitergeben' sagt (Union über Räume)."""
        words = [v["word"] for v in rec_for_model.values()]
        return any(w == "weitergeben" for w in words)

    print(f"\n{'='*70}\nKOSTEN (gesamt ${_spent[0]:.4f}, {len(tasks)} Calls)")
    per_model = defaultdict(float)
    for (variant, model), c in sorted(cost_by.items()):
        per_model[model] += c
    for m in (MODEL_A, MODEL_B):
        n = sum(1 for t in tasks if t[2] == m)
        print(f"  {m:<28} ${per_model[m]:.4f}  ({n} Calls, ø ${per_model[m]/n:.5f}/Call)")
    print(f"  → ø Kosten/Artikel (alle 4 Designs, beide Modelle): ${_spent[0]/len(sample):.4f}")

    print(f"\n{'Design':<16} {'FN':>3} {'Recall':>7} {'Präz':>6} {'weggew.':>8}  Diskrimination (n=15)")
    print("-" * 68)
    summary = {}
    for variant in ("sym_onepass", "sym_perspace"):
        fn = tp = kept = 0
        for i, a in enumerate(sample):
            rec = results.get(i, {}).get(variant, {})
            if MODEL_A not in rec or MODEL_B not in rec:
                continue
            ka = model_keep(rec[MODEL_A])
            kb = model_keep(rec[MODEL_B])
            dec = combine_votes(["scannen" if ka else "ignorieren",
                                 "scannen" if kb else "ignorieren"])
            keep = dec.keep
            if keep:
                kept += 1
                if a["truth_keep"]:
                    tp += 1
            elif a["truth_keep"]:
                fn += 1
        nkeep = sum(a["truth_keep"] for a in sample)
        recall = 100 * (nkeep - fn) / nkeep if nkeep else 0
        prec = 100 * tp / kept if kept else 0
        summary[variant] = {"fn": fn, "recall": recall, "prec": prec, "kept": kept}
        print(f"{variant:<16} {fn:>3} {recall:>6.0f}% {prec:>5.0f}% {len(sample)-kept:>6}/{len(sample)}")

    OUT.write_text(json.dumps(
        {"sample": [{k: a[k] for k in ("id", "home_space", "user_verdict", "title")} for a in sample],
         "cost_total": _spent[0], "cost_by_model": dict(per_model),
         "summary": summary, "results": {str(i): r for i, r in results.items()}},
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\nDetails (inkl. roher Outputs) → {OUT.name}")
