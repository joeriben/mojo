"""Werkprofil als Prompt-Block für Screening und Assessment.

`summaries.json` sagt, WORÜBER der Nutzer geschrieben hat — Titel, Themen,
genannte Denker*innen. Es sagt nicht, WIE er sich zu ihnen verhält. Genau das
steht in den H7-Fallgestalten: pro Quelle eine Haltung, über die Jahre auch
deren Wechsel; dazu die selbst geprägten Begriffe und die Selbstpositionen der
einzelnen Texte.

Dieses Modul verdichtet die vorhandene Profilform (`profile_form.py`) zu einem
Textblock für den Systemprompt. Der Block ist Teil des zwischengespeicherten
Präfixes — er kostet einmal Tokens, danach nichts mehr pro Artikel.

Epistemischer Status: der Block stammt aus maschineller Lektüre, nicht aus
Rechnung. Er sagt das im Kopf ausdrücklich, damit das Modell ihn nicht als
Messung liest und daraus Sicherheiten ableitet, die er nicht trägt.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FALLGESTALT_DIR = PROJECT_ROOT / "output" / "fallgestalt"

# Haltungs-Vokabular der Fallgestalt → Prompt-Englisch. Bewusst nah am
# Original: »extends« ist nicht »agrees«, »reserves« nicht »rejects«.
STANCE_EN = {
    "affirms": "builds on",
    "extends": "extends",
    "contrasts": "sets apart from",
    "reserves": "takes up with reservations",
    "rejects": "rejects",
}

MAX_SOURCES = 40
MAX_TERMS = 30
MAX_POSITIONS = 12
MIN_WORKS = 2  # unter 2 Texten ist eine »wiederkehrende« Quelle keine


def _dominant(stance: dict[str, int]) -> str | None:
    if not stance:
        return None
    top = max(stance.items(), key=lambda kv: kv[1])
    return top[0] if top[1] > 0 else None


def build_profile_block(
    profile_form: dict[str, Any] | None = None,
    *,
    fallgestalt_dir: Path = FALLGESTALT_DIR,
) -> str | None:
    """Den Werkprofil-Block bauen; None, wenn keine Lektüren vorliegen.

    None statt leerem String, damit der Aufrufer den Block weglassen kann,
    ohne eine leere Überschrift in den Prompt zu schreiben.
    """
    if profile_form is None:
        from journal_bot.profile_form import build_profile_form, load_fallgestalten

        fg = load_fallgestalten(fallgestalt_dir)
        if not fg:
            return None
        profile_form = build_profile_form(fg)

    sources = profile_form.get("sources") or []
    n_works = len(profile_form.get("self_positions") or [])
    if not sources:
        return None

    lines: list[str] = [
        "",
        "--- HOW THIS RESEARCHER POSITIONS THEMSELVES ---",
        f"Derived from machine readings of {n_works} of their own full texts. This is READ,",
        "not computed: a language model read each text and named the sources it takes up,",
        "with what stance, and the terms it coins. Treat it as evidence about their",
        "intellectual posture, NOT as a measurement. It tells you HOW they relate to",
        "positions — which the summaries above cannot tell you, since those only say what",
        "the texts are ABOUT.",
        "",
        "Use it to judge whether an article meets this researcher on the level of its",
        "approach, not only its topic. An article on a topic they write about, but from a",
        "posture they set themselves apart from, is not automatically relevant.",
        "",
        "On genre, two different cases — do not collapse them:",
        "  A book review or review essay is not an independent contribution. Whatever the",
        "  reviewed author has to say reaches this researcher through that author's own",
        "  articles, which are screened on their own terms. Drop reviews.",
        "  An editorial or an introduction to a special issue does carry an argument: it",
        "  argues why this constellation of problems, why now. Do not dismiss it as being",
        "  without an argument. But it frames rather than carries, and is rarely a",
        "  first-rank find — weigh it as framing.",
    ]

    # Wiederkehrende fremde Quellen mit Haltung. Eigene Arbeiten bleiben
    # draußen: sie stehen schon im Publikationsindex oben.
    fremd = [
        s for s in sources
        if not s.get("own_work") and (s.get("n_works") or 0) >= MIN_WORKS
    ]
    fremd.sort(key=lambda s: -(s.get("n_works") or 0))
    mit_haltung = [(s, _dominant(s.get("stance") or {})) for s in fremd]
    mit_haltung = [(s, d) for s, d in mit_haltung if d]
    if mit_haltung:
        lines += ["", "Recurring sources and the stance taken toward them:"]
        for s, dom in mit_haltung[:MAX_SOURCES]:
            jahre = s.get("years") or []
            spanne = (
                f"{min(jahre)}–{max(jahre)}" if len(jahre) > 1 else (str(jahre[0]) if jahre else "")
            )
            lines.append(
                f"  {s['label']} — {STANCE_EN.get(dom, dom)}"
                f" (in {s['n_works']} texts{', ' + spanne if spanne else ''})"
            )

    # Haltungswechsel — das Stärkste, was das Profil trägt: dieselbe Quelle,
    # andere Haltung. Zeigt Bewegung, nicht nur Bestand.
    shifts = [s for s in sources if s.get("shift")]
    if shifts:
        lines += [
            "",
            "Stances that changed over the years (same source, different posture):",
        ]
        for s in shifts:
            sh = s["shift"]
            von, nach = sh.get("from") or {}, sh.get("to") or {}
            lines.append(
                f"  {s['label']}: {STANCE_EN.get(von.get('stance'), von.get('stance'))}"
                f" ({von.get('year')}) → {STANCE_EN.get(nach.get('stance'), nach.get('stance'))}"
                f" ({nach.get('year')})"
            )

    terms = [t for t in (profile_form.get("terms") or []) if (t.get("n_works") or 0) >= MIN_WORKS]
    terms.sort(key=lambda t: -(t.get("n_works") or 0))
    if terms:
        lines += [
            "",
            "Terms they coin or carry as their own (an article using these in a different",
            "sense is worth flagging):",
            "  " + "; ".join(t["label"] for t in terms[:MAX_TERMS]),
        ]

    positions = profile_form.get("self_positions") or []
    if positions:
        lines += ["", "What their own texts set out to do (one line per text):"]
        for p in sorted(positions, key=lambda p: -(p.get("year") or 0))[:MAX_POSITIONS]:
            lines.append(f"  [{p.get('year') or '?'}] {p.get('label', '').strip()}")

    lines.append("")
    return "\n".join(lines)
