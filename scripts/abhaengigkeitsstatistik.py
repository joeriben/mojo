#!/usr/bin/env python3
"""Abhängigkeitsstatistik über die beobachteten Urteile — Trigger für den Vorfilter.

Die Auswahlregeln des Nutzers sind BEDINGT formuliert: »Fremdthematiken toleriere
ich eher, WENN sie politisch relevant sind«, »INNERHALB meiner Kernfelder werde
ich exklusiver«. Solche Regeln verschwinden, wenn man sie marginal misst — genau
das ist hier früher passiert (»politisch« lag mit 35 % auf der Grundrate). Dieses
Skript misst sie deshalb konsequent BEDINGT: nicht »wirkt Merkmal M«, sondern
»wirkt Merkmal M in Lage L anders als in Lage L'«. Das ist die Interaktion, und
sie ist die eigentliche Aussage.

Zwei Durchgänge:

  ENTDECKUNG   alle Marker × alle Lagen werden durchgerechnet, ohne Vorauswahl.
               Auch die Zusammenhänge, die niemand vermutet hat (etwa: ein
               Resilienz-/IKE-Bezug erweitert die Thementoleranz).
  PRÜFUNG      die vom Nutzer ausdrücklich benannten Regeln, an derselben Stelle
               und mit derselben Rechnung, damit gesetzte und gefundene
               Zusammenhänge vergleichbar nebeneinander stehen.

Der Kanal (screening / similarity / complementarity / citation / mixed) ist die
bekannteste Störgrösse: die Behalten-Quote schwankt über ihn von 15 % bis 85 %.
Jede Quote hier wird deshalb kanalbereinigt berichtet — verglichen wird gegen die
Erwartung aus der Kanalmischung der jeweiligen Zelle, nicht gegen die
Gesamtgrundrate.

Ausgabe: `output/abhaengigkeiten.json`, maschinenlesbar, mit n, Effekt, p und
q (Benjamini-Hochberg) je Trigger — plus einem ausdrücklichen Belastbarkeits-
Vermerk je Zeile, damit ein dünner Befund im Vorfilter nicht wie ein dicker
aussieht.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import fisher_exact

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from journal_bot.signals import _PROJECT_SIGNAL_KEYWORDS, load_key_terms  # noqa: E402

MIN_ZELLE = 12          # unter 12 Fällen wird keine Quote berichtet
MIN_TRIGGER = 20        # ein Trigger braucht Masse auf beiden Seiten der Lage
FDR = 0.10              # Benjamini-Hochberg-Niveau
BEHALTEN = ("scannen", "lesenswert", "pflichtlektuere")


# --------------------------------------------------------------- Marker -----
# Zugriffsform und Verfasstheit — im Wortlaut des Nutzers, wo er einen hat.
# »solutionistisch« ist nicht »lösungsorientiert«, »Tool-Perspektive« nicht
# »angewandt«. Die Begriffe stammen aus seinen Memos und aus den Ablehnungen.
MARKER: dict[str, list[str]] = {
    # — Verfasstheit / Zugriffsform —
    "quantitativ_standardmethodisch": [
        "quantitative", "survey", "questionnaire", "regression", "sample of",
        "statistically significant", "control group", "pre-test", "post-test",
        "randomized", "likert", "structural equation", "quasi-experimental",
        "effect size", "n =", "stichprobe", "fragebogen", "varianzanalyse",
    ],
    "tool_perspektive": [
        "implementation of", "effectiveness of", "improve learning outcomes",
        "adoption of", "acceptance model", "tam", "technology acceptance",
        "best practice", "toolkit", "integrate technology", "enhance learning",
        "instructional design", "learning gains", "teacher training program",
    ],
    "solutionistisch": [
        "solution to", "can solve", "addresses the challenge", "opportunit",
        "potential of ai to", "harness", "leverage", "unlock", "empower",
        "transform education", "revolutioni",
    ],
    "theoretisch_konstituiert": [
        "theoretical", "conceptual", "ontolog", "epistemolog", "philosoph",
        "critique", "kritik", "genealog", "hermeneutic", "phenomenolog",
        "dialectic", "theoriebildung", "begriffsarbeit",
    ],
    "medientheoretisch": [
        "media theory", "medientheor", "mediality", "medialität", "apparatus",
        "dispositif", "cultural technique", "kulturtechnik", "infrastructur",
        "operativity", "medienphilosoph",
    ],
    "neomateriell_posthuman": [
        "new materialis", "neomaterial", "posthuman", "more-than-human",
        "agential realism", "barad", "intra-action", "assemblage", "haraway",
        "multispecies", "nonhuman", "vibrant matter", "braidotti",
    ],
    "phaenomenologisch_anthropolog": [
        "phenomenolog", "phänomenolog", "lived experience", "leiblich",
        "embodiment", "anthropolog", "erfahrung", "merleau",
    ],
    "psychoanalytisch": [
        "psychoanaly", "lacan", "freud", "žižek", "zizek", "desire", "fantasy",
        "unconscious", "das unbewusste", "subjektivierung", "melancholi",
    ],
    "mainstream_psychologisch": [
        "cognitive load", "self-efficacy", "motivation scale", "big five",
        "working memory", "cognitive psychology", "self-regulated learning",
        "achievement emotion", "learning analytics dashboard", "meta-cognitive",
    ],
    # — Themenfelder / Öffnungen und Sperren —
    "dekolonial": [
        "decolonial", "dekolonial", "postcolonial", "postkolonial", "indigenous",
        "indigene", "global south", "epistemic justice", "coloniality",
    ],
    "ike_kulturerbe": [
        "cultural heritage", "kulturerbe", "intangible heritage", "unesco",
        "tradierung", "safeguarding", "heritage practice", "immaterielle",
    ],
    "resilienz": [
        "resilience", "resilienz", "sustainab", "nachhaltig", "anthropocene",
        "anthropozän", "planetary", "climate", "futurability", "vulnerab",
    ],
    "gesundheit": [
        "health care", "healthcare", "gesundheit", "clinical", "patient",
        "therapy", "medical", "nursing", "well-being intervention", "psychiatric",
    ],
    "politisch_fachpolitisch": [
        "policy", "politic", "governance", "regulation", "democra", "civic",
        "public sphere", "bildungspolit", "reform", "activism", "citizenship",
        "inequalit", "ungleichheit", "social justice",
    ],
    "aesthetisch_kuenstlerisch": [
        "aesthetic", "ästhetisch", "art education", "kunst", "artistic",
        "creative practice", "performance", "music", "dance", "theatre",
        "literary", "curator",
    ],
    "digitalitaet_ki": [
        "generative ai", "artificial intelligence", "machine learning",
        "algorithm", "digitalis", "digitalit", "datafication", "platform",
        "large language model", "chatgpt", "automation",
    ],
    # — Gattung —
    "gattung_review": ["book review", "review essay", "rezension", "reviewed by"],
    "gattung_editorial": ["editorial", "introduction to the special issue",
                          "special issue", "guest editor", "schwerpunktheft"],
}

# Vom Nutzer ausdrücklich benannte Regeln — Lage × Marker × erwartete Richtung.
GESETZTE_REGELN = [
    ("Fremdthematik toleriert, wenn fachpolitisch relevant",
     "naehe", "fremd", "politisch_fachpolitisch", "+"),
    ("Im Kernfeld entscheidet die Verfasstheit",
     "naehe", "kern", "theoretisch_konstituiert", "+"),
    ("Im Kernfeld wird standardmethodisch Empirisches strenger behandelt",
     "naehe", "kern", "quantitativ_standardmethodisch", "-"),
    ("Dekoloniales öffnet unabhängig von der Lage",
     None, None, "dekolonial", "+"),
    ("Gesundheitssystem bleibt zu, unabhängig von der Lage",
     None, None, "gesundheit", "-"),
    ("Psychoanalytisch ja, mainstream-psychologisch nein",
     None, None, "psychoanalytisch", "+"),
    ("Mainstream-psychologisch praktisch nie",
     None, None, "mainstream_psychologisch", "-"),
    ("Resilienz-/IKE-Bezug erweitert die Thementoleranz",
     "naehe", "fremd", "resilienz", "+"),
]


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").lower()
    return re.sub(r"\s+", " ", s)


def lade() -> list[dict]:
    con = sqlite3.connect(f"file:{ROOT / 'articles.db'}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    zeilen = con.execute(
        "SELECT id, title, journal_short, user_verdict, selection_mode,"
        "       abstract, openalex_abstract, openalex_topics, openalex_concepts, year"
        " FROM articles WHERE user_verdict IS NOT NULL"
    ).fetchall()
    con.close()

    key_terms = {k.lower() for k in load_key_terms() if len(k) > 4}
    projekt_worte = {w.lower() for ws in _PROJECT_SIGNAL_KEYWORDS.values() for w in ws}

    aus = []
    for r in zeilen:
        themen = []
        for feld in ("openalex_topics", "openalex_concepts"):
            try:
                themen += [e.get("name", "") for e in json.loads(r[feld] or "[]")
                           if isinstance(e, dict) and float(e.get("score") or 0) >= 0.10]
            except (json.JSONDecodeError, TypeError, ValueError):
                pass
        text = _norm(" ".join(filter(None, [
            r["title"], r["abstract"] or r["openalex_abstract"], " ".join(themen)])))

        treffer = {name for name, worte in MARKER.items()
                   if any(w in text for w in worte)}
        # Nähe zum eigenen Werk: Überlappung mit den eigenen Begriffen und den
        # Projekt-Schlüsselwörtern. Gerechnet, nicht zugewiesen.
        n_eigen = sum(1 for k in key_terms if k in text)
        n_projekt = sum(1 for w in projekt_worte if w in text)
        aus.append({
            "id": r["id"], "titel": r["title"], "journal": r["journal_short"],
            "kanal": r["selection_mode"] or "unbekannt",
            "behalten": int(r["user_verdict"] in BEHALTEN),
            "lesenswert": int(r["user_verdict"] in ("lesenswert", "pflichtlektuere")),
            "marker": treffer, "naehe_roh": n_eigen + 2 * n_projekt,
        })

    # Lage in drei Stufen, an den Terzilen der eigenen Verteilung geschnitten —
    # kein gesetzter Schwellenwert.
    werte = sorted(d["naehe_roh"] for d in aus)
    u, o = werte[len(werte) // 3], werte[2 * len(werte) // 3]
    for d in aus:
        d["naehe"] = "fremd" if d["naehe_roh"] <= u else ("kern" if d["naehe_roh"] > o else "angrenzend")
    return aus


def kanalerwartung(gruppe: list[dict], basis: dict[str, float], feld: str) -> float:
    """Erwartete Quote dieser Zelle allein aus ihrer Kanalmischung."""
    if not gruppe:
        return 0.0
    return float(np.mean([basis.get(d["kanal"], 0.0) for d in gruppe]))


def bh(p_werte: list[float], niveau: float) -> list[float]:
    """Benjamini-Hochberg: p → q. Ohne Korrektur findet man bei 18 Markern
    × 3 Lagen garantiert »Signifikantes«, das keines ist."""
    n = len(p_werte)
    if not n:
        return []
    ordnung = sorted(range(n), key=lambda i: p_werte[i])
    q = [0.0] * n
    vorher = 1.0
    for rang, i in enumerate(reversed(ordnung), start=1):
        wert = min(vorher, p_werte[i] * n / (n - rang + 1))
        q[i] = vorher = wert
    return q


def teste(gruppe_in: list[dict], gruppe_out: list[dict], basis: dict[str, float],
          feld: str) -> dict | None:
    if len(gruppe_in) < MIN_ZELLE or len(gruppe_out) < MIN_ZELLE:
        return None
    a = sum(d[feld] for d in gruppe_in)
    b = len(gruppe_in) - a
    c = sum(d[feld] for d in gruppe_out)
    e = len(gruppe_out) - c
    _, p = fisher_exact([[a, b], [c, e]])
    quote, gegen = a / len(gruppe_in), c / len(gruppe_out)
    # Doppelte Differenz: beide Gruppen gegen ihre eigene Kanalerwartung, dann
    # gegeneinander. Nur so fällt der Lage-Haupteffekt heraus — sonst sieht in
    # »kern« (54 % Grundrate) jeder Marker positiv aus und in »fremd« (21 %)
    # jeder negativ, und man misst die Lage statt des Markers.
    erw_in = kanalerwartung(gruppe_in, basis, feld)
    erw_out = kanalerwartung(gruppe_out, basis, feld)
    return {
        "n": len(gruppe_in), "n_positiv": a, "quote": round(quote, 3),
        "erwartet_aus_kanal": round(erw_in, 3),
        "vergleichsquote": round(gegen, 3),
        "vergleich_erwartet": round(erw_out, 3),
        "lift_kanalbereinigt": round((quote - erw_in) - (gegen - erw_out), 3),
        "p": p,
    }


def belastbarkeit(z: dict) -> str:
    if z["n"] < MIN_TRIGGER or z["n_positiv"] < 5:
        return "zu dünn — nicht als Trigger verwenden"
    if z.get("q", 1.0) > FDR:
        return "nicht gesichert nach Mehrfachkorrektur"
    if abs(z["lift_kanalbereinigt"]) < 0.10:
        return "gesichert, aber kleiner Effekt"
    return "belastbar"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--feld", choices=("behalten", "lesenswert"), default="behalten")
    ap.add_argument("--out", default="output/abhaengigkeiten.json")
    args = ap.parse_args()
    feld = args.feld

    daten = lade()
    basis = {}
    for k in {d["kanal"] for d in daten}:
        teil = [d for d in daten if d["kanal"] == k]
        basis[k] = float(np.mean([d[feld] for d in teil]))

    print(f"{len(daten)} Urteile · Zielgrösse »{feld}« "
          f"· Grundrate {np.mean([d[feld] for d in daten]):.1%}")
    print("Kanal-Grundraten (die Störgrösse, gegen die bereinigt wird):")
    for k, v in sorted(basis.items(), key=lambda kv: -kv[1]):
        print(f"   {k:<16} {v:>6.1%}  (n={sum(1 for d in daten if d['kanal']==k)})")
    print("\nLage-Verteilung (Terzile der Überlappung mit eigenem Werk + Projekten):")
    for lage in ("kern", "angrenzend", "fremd"):
        teil = [d for d in daten if d["naehe"] == lage]
        print(f"   {lage:<12} n={len(teil):<5} {feld} {np.mean([d[feld] for d in teil]):.1%}")

    # ---------------------------------------------------------- ENTDECKUNG --
    befunde: list[dict] = []
    for name in MARKER:
        drin = [d for d in daten if name in d["marker"]]
        raus = [d for d in daten if name not in d["marker"]]
        z = teste(drin, raus, basis, feld)
        if z:
            befunde.append({"art": "haupteffekt", "marker": name, "lage": "alle", **z})
        for lage in ("kern", "angrenzend", "fremd"):
            l_drin = [d for d in drin if d["naehe"] == lage]
            l_raus = [d for d in raus if d["naehe"] == lage]
            z = teste(l_drin, l_raus, basis, feld)
            if z:
                befunde.append({"art": "bedingt", "marker": name, "lage": lage, **z})

    for b, q in zip(befunde, bh([b["p"] for b in befunde], FDR)):
        b["q"] = q
        b["belastbarkeit"] = belastbarkeit(b)

    # Interaktion: wirkt der Marker in »kern« ANDERS als in »fremd«?
    # Das ist die eigentliche Zustandsbehauptung, nicht der Haupteffekt.
    nach_marker = defaultdict(dict)
    for b in befunde:
        if b["art"] == "bedingt":
            nach_marker[b["marker"]][b["lage"]] = b
    def _unterschied(stichprobe: list[dict], marker: str) -> float | None:
        """Lift des Markers im Kernfeld minus Lift in der Fremde, doppelte Differenz."""
        werte = {}
        for lage in ("kern", "fremd"):
            drin = [d for d in stichprobe if d["naehe"] == lage and marker in d["marker"]]
            raus = [d for d in stichprobe if d["naehe"] == lage and marker not in d["marker"]]
            z = teste(drin, raus, basis, feld)
            if z is None:
                return None
            werte[lage] = z["lift_kanalbereinigt"]
        return werte["kern"] - werte["fremd"]

    rng = np.random.default_rng(23)
    interaktionen = []
    for marker, lagen in nach_marker.items():
        if not ("kern" in lagen and "fremd" in lagen):
            continue
        beob = _unterschied(daten, marker)
        if beob is None:
            continue
        # Nullverteilung: die LAGE wird gemischt, Marker und Kanal bleiben, wo
        # sie sind. Damit steht »der Marker wirkt überall gleich« als Null.
        nul = []
        for _ in range(400):
            gemischt = [dict(d) for d in daten]
            lagen_werte = rng.permutation([d["naehe"] for d in daten])
            for d, l in zip(gemischt, lagen_werte):
                d["naehe"] = l
            u = _unterschied(gemischt, marker)
            if u is not None:
                nul.append(u)
        p_int = (
            (sum(abs(x) >= abs(beob) for x in nul) + 1) / (len(nul) + 1) if nul else 1.0
        )
        interaktionen.append({
            "marker": marker, "lift_kern": lagen["kern"]["lift_kanalbereinigt"],
            "lift_fremd": lagen["fremd"]["lift_kanalbereinigt"],
            "unterschied": round(beob, 3), "p_interaktion": round(p_int, 3),
            "n_kern": lagen["kern"]["n"], "n_fremd": lagen["fremd"]["n"],
        })
    for x, q in zip(interaktionen, bh([x["p_interaktion"] for x in interaktionen], FDR)):
        x["q_interaktion"] = round(q, 3)
    interaktionen.sort(key=lambda x: -abs(x["unterschied"]))

    print(f"\n{'=' * 78}\nENTDECKUNG — Marker mit belastbarem Effekt "
          f"(kanalbereinigt, BH-korrigiert bei q<{FDR})\n{'=' * 78}")
    print(f"{'Marker':<32}{'Lage':<12}{'n':>5}{'Quote':>8}{'ohne':>7}{'Lift':>8}{'q':>8}")
    stark = [b for b in befunde if b["belastbarkeit"] == "belastbar"]
    stark.sort(key=lambda b: -abs(b["lift_kanalbereinigt"]))
    for b in stark:
        print(f"{b['marker']:<32}{b['lage']:<12}{b['n']:>5}{b['quote']:>8.1%}"
              f"{b['vergleichsquote']:>7.1%}{b['lift_kanalbereinigt']:>+8.1%}{b['q']:>8.3f}")
    if not stark:
        print("  (keiner)")

    print(f"\n{'=' * 78}\nZUSTANDSABHÄNGIGKEIT — wirkt derselbe Marker im Kernfeld anders "
          f"als in der Fremde?\n{'=' * 78}")
    print("(Nullverteilung: Lage 400× gemischt, Marker und Kanal bleiben stehen)")
    print(f"{'Marker':<30}{'kern':>8}{'fremd':>8}{'Untersch.':>11}{'p':>7}{'q':>7}"
          f"{'n kern':>8}{'n fremd':>9}")
    for x in interaktionen[:12]:
        print(f"{x['marker']:<30}{x['lift_kern']:>+8.1%}{x['lift_fremd']:>+8.1%}"
              f"{x['unterschied']:>+11.1%}{x['p_interaktion']:>7.3f}{x['q_interaktion']:>7.3f}"
              f"{x['n_kern']:>8}{x['n_fremd']:>9}")

    print(f"\n{'=' * 78}\nPRÜFUNG — die ausdrücklich benannten Regeln, bedingt gemessen"
          f"\n{'=' * 78}")
    geprueft = []
    for beschreibung, lage_feld, lage_wert, marker, richtung in GESETZTE_REGELN:
        passend = [b for b in befunde if b["marker"] == marker
                   and b["lage"] == (lage_wert if lage_feld else "alle")]
        if not passend:
            print(f"  {beschreibung}\n      → nicht messbar (Zelle unter {MIN_ZELLE} Fällen)")
            geprueft.append({"regel": beschreibung, "ergebnis": "nicht messbar"})
            continue
        b = passend[0]
        lift = b["lift_kanalbereinigt"]
        stimmt = (lift > 0) if richtung == "+" else (lift < 0)
        print(f"  {beschreibung}")
        print(f"      n={b['n']:<4} Quote {b['quote']:.1%} gegen {b['vergleichsquote']:.1%} "
              f"ohne den Marker → Lift {lift:+.1%}, q={b['q']:.3f}")
        print(f"      Richtung {'wie behauptet' if stimmt else 'GEGENLÄUFIG'} · {b['belastbarkeit']}")
        geprueft.append({"regel": beschreibung, "marker": marker, "lage": b["lage"],
                         "lift": lift, "q": b["q"], "richtung_bestaetigt": bool(stimmt),
                         "belastbarkeit": b["belastbarkeit"]})

    ausgabe = {
        "zielgroesse": feld,
        "n_urteile": len(daten),
        "kanal_grundraten": basis,
        "befunde": sorted(befunde, key=lambda b: b["q"]),
        "interaktionen": interaktionen,
        "gesetzte_regeln": geprueft,
        "trigger": [
            {"marker": b["marker"], "lage": b["lage"], "richtung": "auf" if b["lift_kanalbereinigt"] > 0 else "ab",
             "lift": b["lift_kanalbereinigt"], "n": b["n"], "q": b["q"]}
            for b in stark
        ],
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(ausgabe, ensure_ascii=False, indent=2),
                              encoding="utf-8")
    print(f"\n{len(ausgabe['trigger'])} belastbare Trigger → {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
