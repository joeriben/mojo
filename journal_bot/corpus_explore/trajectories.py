"""Themen-Trajektorien im MOJO-Korpus — within-journal-dekomponiert.

Erschliesst, welche OpenAlex-Topics ueber die Zeit im kuratierten Journal-Strom
an Anteil gewinnen oder verlieren. Rein algorithmisch, kein LLM.

Disziplin (docs/mojo2_korpus_exploration_goal.md), strukturell eingebaut:
- Within-Journal-Dekomposition ist der EINZIGE Befund-Pfad. Die Journal-Volumina
  sind ungleich und zeitlich dynamisch; der reine Korpus-Anteil ueberzeichnet
  jede Bewegung (Kompositions-Effekt). Der Korpus-Anteil wird nur als
  ausdruecklich etikettierter Kompositions-Kontrast gefuehrt, nie als Trend.
  Es gibt keine Funktion, die den naiven Korpus-Trend als Befund zurueckgibt.
- `year` (nie `fetched_at`): alle Journals wurden retrospektiv gefetcht.
- Konditionierung: personalisierte Journal-Watchlist = der Diskurs, wie er den
  User erreicht, nie neutrale Feld-Wahrheit. Jede Ausgabe traegt sie mit.
- Handlung: STRUKTURIEREN + PRIORISIEREN — Kandidat-Trends, kein Urteil.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from journal_bot.store import Store

# Default-Fenster und Schwellen (ueberschreibbar via run()/compute_trajectories()).
DEFAULT_EARLY = (2016, 2019)
DEFAULT_LATE = (2022, 2025)
SCORE_MIN = 0.5             # Topic gilt ab diesem OpenAlex-score als praesent
MIN_JOURNAL = 30           # Mindest-Artikel je Journal UND Fenster fuer Within-Decomp
MIN_PANEL = 3              # ein balanciertes Panel braucht so viele Journals
MIN_TOTAL = 40            # Mindest-Gesamtvorkommen ueber beide Fenster
TOP_N = 25


def _topic_names(raw: Any, score_min: float) -> list[str]:
    """Topic-Namen ueber Score-Schwelle aus einem openalex_topics-Wert.

    Tolerant gegen Strukturvarianten (name / display_name; score optional).
    """
    if not raw:
        return []
    out: list[str] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            score = float(item.get("score", 0) or 0)
        except (TypeError, ValueError):
            score = 0.0
        if score < score_min:
            continue
        name = (item.get("name") or item.get("display_name") or "").strip()
        if name and name not in out:
            out.append(name)
    return out


def _in_window(year: int | None, window: tuple[int, int]) -> bool:
    return year is not None and window[0] <= year <= window[1]


@dataclass
class TopicTrajectory:
    """Ein Topic und seine Bewegung zwischen frueh und spaet.

    `within_delta` ist DER BEFUND (gleichgewichtetes Mittel der Anteils-Deltas
    ueber das balancierte Journal-Panel). Die `composition_*`-Felder sind
    ausdruecklich KEIN Befund — nur der Kompositions-Kontrast, der sichtbar
    macht, wie stark der rohe Korpus-Anteil die Bewegung ueberzeichnet.
    """

    name: str
    total: int                          # Gesamtvorkommen ueber beide Fenster
    within_delta: float                 # <- Befund: gleichgew. Within-Journal-Delta
    panel_size: int                     # Journals im balancierten Panel
    per_journal: list[tuple[str, float, float]] = field(default_factory=list)
    composition_early: float = 0.0      # Kontrast (kein Befund)
    composition_late: float = 0.0
    composition_delta: float = 0.0


@dataclass
class TrajectoryResult:
    early: tuple[int, int]
    late: tuple[int, int]
    score_min: float
    min_journal: int
    panel: list[str]                    # balanciertes Journal-Panel (Within-Decomp)
    per_year_with_topic: dict[int, int]
    risers: list[TopicTrajectory]
    fallers: list[TopicTrajectory]
    n_articles: int
    n_topics_reported: int


def compute_trajectories(
    store: Store | None = None,
    *,
    early: tuple[int, int] = DEFAULT_EARLY,
    late: tuple[int, int] = DEFAULT_LATE,
    score_min: float = SCORE_MIN,
    min_journal: int = MIN_JOURNAL,
    min_panel: int = MIN_PANEL,
    min_total: int = MIN_TOTAL,
    top_n: int = TOP_N,
) -> TrajectoryResult:
    """Themen-Trajektorien, within-journal-dekomponiert.

    Balanciertes Panel: nur Journals, die in BEIDEN Fenstern >= `min_journal`
    Artikel mit Topic haben, gehen in die Dekomposition ein (gleichgewichtet).
    So traegt kein Journal-Volumen-Sprung in den Befund.
    """
    store = store or Store()
    lo, hi = min(early[0], late[0]), max(early[1], late[1])
    articles = store.find_in_window(start_year=lo, end_year=hi)

    # den[w][journal] = Artikel mit >=1 Topic in Fenster w
    # num[w][topic][journal] = Artikel mit diesem Topic in Fenster w
    den: dict[str, dict[str, int]] = {"early": defaultdict(int), "late": defaultdict(int)}
    num: dict[str, dict[str, dict[str, int]]] = {
        "early": defaultdict(lambda: defaultdict(int)),
        "late": defaultdict(lambda: defaultdict(int)),
    }
    corpus_den = {"early": 0, "late": 0}
    corpus_num: dict[str, dict[str, int]] = {"early": defaultdict(int), "late": defaultdict(int)}
    total_count: dict[str, int] = defaultdict(int)
    per_year_with_topic: dict[int, int] = defaultdict(int)

    for a in articles:
        names = _topic_names(a.openalex_topics, score_min)
        if not names:
            continue
        if a.year is not None:
            per_year_with_topic[a.year] += 1
        if _in_window(a.year, early):
            w = "early"
        elif _in_window(a.year, late):
            w = "late"
        else:
            continue
        j = a.journal_short
        den[w][j] += 1
        corpus_den[w] += 1
        for t in names:
            num[w][t][j] += 1
            corpus_num[w][t] += 1
            total_count[t] += 1

    # Balanciertes Panel: in beiden Fenstern hinreichend belegte Journals.
    panel = sorted(
        j for j in (set(den["early"]) & set(den["late"]))
        if den["early"][j] >= min_journal and den["late"][j] >= min_journal
    )

    trajectories: list[TopicTrajectory] = []
    for t in set(num["early"]) | set(num["late"]):
        if total_count[t] < min_total or len(panel) < min_panel:
            continue
        per_journal: list[tuple[str, float, float]] = []
        deltas: list[float] = []
        for j in panel:
            se = num["early"][t].get(j, 0) / den["early"][j]
            sl = num["late"][t].get(j, 0) / den["late"][j]
            per_journal.append((j, se, sl))
            deltas.append(sl - se)
        within = sum(deltas) / len(deltas)
        ce = corpus_num["early"].get(t, 0) / corpus_den["early"] if corpus_den["early"] else 0.0
        cl = corpus_num["late"].get(t, 0) / corpus_den["late"] if corpus_den["late"] else 0.0
        per_journal.sort(key=lambda x: -(x[2] - x[1]))
        trajectories.append(TopicTrajectory(
            name=t, total=total_count[t], within_delta=within, panel_size=len(panel),
            per_journal=per_journal,
            composition_early=ce, composition_late=cl, composition_delta=cl - ce,
        ))

    trajectories.sort(key=lambda tr: tr.within_delta)
    fallers = trajectories[:top_n]
    risers = list(reversed(trajectories[-top_n:]))
    return TrajectoryResult(
        early=early, late=late, score_min=score_min, min_journal=min_journal,
        panel=panel, per_year_with_topic=dict(sorted(per_year_with_topic.items())),
        risers=risers, fallers=fallers,
        n_articles=len(articles), n_topics_reported=len(trajectories),
    )


def _pct(x: float) -> str:
    return f"{100 * x:.2f}%"


def _table(rows: list[TopicTrajectory]) -> str:
    lines = [
        "| Topic | n | within-Δ (Befund) | Komp-Δ (Kontrast) |",
        "|---|--:|--:|--:|",
    ]
    for r in rows:
        lines.append(
            f"| {r.name} | {r.total} | {100 * r.within_delta:+.2f} pp "
            f"| {100 * r.composition_delta:+.2f} pp |"
        )
    return "\n".join(lines)


def render_report(result: TrajectoryResult) -> str:
    e, l = result.early, result.late
    o: list[str] = []
    o.append("# Themen-Trajektorien im MOJO-Korpus\n")
    o.append(
        "**Erzeugt von** `journal_bot.corpus_explore.trajectories` (rein algorithmisch, kein LLM). "
        "**Handlung:** strukturieren + priorisieren — Kandidat-Trends, kein Urteil.\n"
    )
    o.append("## Konditionierung\n")
    o.append(
        "Der Korpus ist die vollständige Erhebung einer **personalisierten Journal-Watchlist** — "
        "alle Werte sind Anteile innerhalb dieses kuratierten Stroms, *der Diskurs, wie er den User "
        "erreicht*, **nie** neutrale Feld-Wahrheit.\n"
    )
    o.append("## Befund vs. Kontrast\n")
    o.append(
        f"**within-Δ ist der Befund**: gleichgewichtetes Mittel der Anteils-Deltas über ein "
        f"**balanciertes Journal-Panel** ({len(result.panel)} Journals mit ≥ {result.min_journal} "
        f"Artikeln in *beiden* Fenstern). Damit trägt kein Journal-Volumen-Sprung in den Trend. "
        f"**Komp-Δ ist KEIN Befund** — der rohe Korpus-Anteil, nur als Kontrast gezeigt: liegt er "
        f"deutlich über within-Δ, ist die scheinbare Bewegung Komposition (Watchlist-Mix), nicht "
        f"Diffusion.\n"
    )
    o.append(
        f"**Fenster:** früh {e[0]}–{e[1]} · spät {l[0]}–{l[1]} · topic-score ≥ {result.score_min} · "
        f"min. Artikel/Journal/Fenster = {result.min_journal}. "
        f"Artikel im Zeitraum mit ≥ 1 Topic: {result.n_articles}. "
        f"Topics über Schwelle: {result.n_topics_reported}.\n"
    )
    o.append("**Panel:** " + ", ".join(result.panel) + ".\n")
    o.append(
        "**Artikel mit ≥ 1 Topic je Jahr:** "
        + ", ".join(f"{y}:{n}" for y, n in result.per_year_with_topic.items())
        + ".\n"
    )
    o.append(f"## Aufsteiger (Top {len(result.risers)}, nach within-Δ)\n")
    o.append(_table(result.risers))
    o.append(f"\n## Absteiger (Top {len(result.fallers)}, nach within-Δ)\n")
    o.append(_table(result.fallers))
    return "\n".join(o)


def _console_summary(result: TrajectoryResult, n: int = 12) -> str:
    lines = [
        f"Panel: {len(result.panel)} Journals | Topics gemeldet: {result.n_topics_reported} "
        f"| Artikel: {result.n_articles}",
        f"(within-Δ = Befund, Komp-Δ = Kompositions-Kontrast, kein Befund)",
        "",
        f"AUFSTEIGER (Top {n}, nach within-Δ):",
    ]
    for r in result.risers[:n]:
        lines.append(
            f"  within {100 * r.within_delta:+6.2f}pp  (komp {100 * r.composition_delta:+6.2f}pp)  "
            f"n={r.total:<4}  {r.name}"
        )
    lines.append("")
    lines.append(f"ABSTEIGER (Top {n}, nach within-Δ):")
    for r in result.fallers[:n]:
        lines.append(
            f"  within {100 * r.within_delta:+6.2f}pp  (komp {100 * r.composition_delta:+6.2f}pp)  "
            f"n={r.total:<4}  {r.name}"
        )
    return "\n".join(lines)


def run(
    *,
    early: tuple[int, int] = DEFAULT_EARLY,
    late: tuple[int, int] = DEFAULT_LATE,
    score_min: float = SCORE_MIN,
    min_journal: int = MIN_JOURNAL,
    top_n: int = TOP_N,
    out: Path | None = None,
    store: Store | None = None,
    verbose: bool = True,
) -> TrajectoryResult:
    """Berechnet die Trajektorien und gibt sie aus (stdout und/oder Datei)."""
    result = compute_trajectories(
        store, early=early, late=late, score_min=score_min,
        min_journal=min_journal, top_n=top_n,
    )
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_report(result), encoding="utf-8")
    if verbose:
        print(_console_summary(result))
        if out is not None:
            print(f"\nReport → {out}")
    return result
