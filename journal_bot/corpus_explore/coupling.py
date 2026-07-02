"""Bibliografische Kopplungs-Communities im MOJO-Korpus — geteilte Referenzbasis.

Clustert die ref-tragenden Artikel danach, welche Werke sie GEMEINSAM zitieren
(bibliografische Kopplung, Kessler 1963), quer zu Journal und Vokabular, und
hält die Cluster gegen die 7 Diskursräume (diskursraeume.json). Rein
algorithmisch, kein LLM.

Disziplin (docs/mojo2_korpus_exploration_goal.md), strukturell eingebaut:
- Handlung: STRUKTURIEREN + VERANKERN. Die Kopplung ist GEERDET — zwei Artikel
  sind gekoppelt, weil sie dasselbe Werk zitieren (belegte geteilte Zitation),
  NICHT über Vektor-/Text-Ähnlichkeit. Darum darf die Struktur als Befund
  sprechen. Die Diskursraum-Komposition verankert jede Community im bestehenden
  7-Raum-Schema. Kein Relevanz-Urteil, keine Priorisierung von Artikeln.
- IDF-Gewichtung + DF-Cap: vielzitierte Werke (Feld-Kanon, „Zitations-
  Stoppwörter") koppeln alles mit allem und werden gekappt (`max_df`); seltene
  geteilte Referenzen tragen das Signal (idf = log(N/df)). `min_shared` ≥ 2
  unterbindet Zufallskanten aus einer einzigen geteilten Referenz.
- Konditionierung: personalisierte Watchlist — die Kopplungsstruktur ist die des
  kuratierten Stroms, *wie er den User erreicht*, nie neutrale Feld-Struktur.
- `year` (nie `fetched_at`): alle Journals wurden retrospektiv gefetcht.
- Determinismus: fester Louvain-Seed → reproduzierbar auf gleichen Daten.

`compute_coupling_communities()` ist offline und deterministisch. Titel-
Auflösung der geteilten Referenzen (OpenAlex-Lookup) ist eine optionale,
gecachte Anreicherung in `run()`/`render_report()`, kein Teil der Berechnung.
"""
from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path
from typing import Any

from journal_bot import settings
from journal_bot.store import Store

# Default-Schwellen (überschreibbar via run()/compute_coupling_communities()).
MIN_DF = 2            # Referenz muss von >= so vielen Artikeln zitiert sein, um zu koppeln
MAX_DF = 50           # Referenzen über dieser Zitationshäufigkeit = Stoppwort, gekappt
MIN_SHARED = 2        # Kante nur ab so vielen GETEILTEN (gekappten) Referenzen
RESOLUTION = 1.0      # Louvain-Auflösung (größer → mehr, kleinere Communities)
SEED = 42             # fester Seed → reproduzierbar
MIN_COMMUNITY = 20    # nur Communities ab dieser Größe werden als Befund gemeldet
SCORE_MIN = 0.5       # Topic gilt ab diesem OpenAlex-score als präsent
TOP_JOURNALS = 6
TOP_TOPICS = 8
TOP_REFS = 8
BRIDGE_MIN = 0.25     # ab diesem Anteil zählt ein Diskursraum als in der Community vertreten

# „deutsche" ist im diskursraeume.json selbst als sprach-/cross-cutting markiert,
# kein thematischer Raum — aus der Cross-Feld-Diagnose ausgenommen, aber in der
# Komposition weiter ausgewiesen.
LANGUAGE_SPACES = {"deutsche"}


def _topic_names(raw: Any, score_min: float) -> list[str]:
    """Topic-Namen über Score-Schwelle aus einem openalex_topics-Wert.

    Identische Logik wie in trajectories.py: tolerant gegen Strukturvarianten.
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


def _bare_ref(r: str) -> str:
    """`https://openalex.org/W123` | `W123` → `W123`."""
    return (r or "").rstrip("/").rsplit("/", 1)[-1].strip()


def load_journal_discourse_map(
    path: Path | None = None,
) -> tuple[dict[str, list[str]], dict[str, str]]:
    """journal_short → [discourse-space-keys] und space-key → Anzeigename.

    Aus der kanonischen diskursraeume.json (settings.DISKURSRAEUME_JSON). Bei
    fehlender Datei: leeres Mapping (Diskursraum-Verankerung entfällt sichtbar).
    """
    path = path or settings.DISKURSRAEUME_JSON
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, {}
    clusters = data.get("journal_clusters", {}) or {}
    names = {
        k: (v.get("name") or k)
        for k, v in (data.get("discourse_spaces", {}) or {}).items()
    }
    return clusters, names


@dataclass
class BaseRef:
    """Eine geteilte Referenz, die eine Community bindet (geerdeter Fingerprint)."""

    ref_id: str
    within_count: int            # Artikel der Community, die dieses Werk zitieren
    within_share: float          # within_count / Community-Größe
    global_df: int               # Artikel im GANZEN Korpus, die es zitieren
    title: str | None = None     # optionale OpenAlex-Auflösung
    year: int | None = None


@dataclass
class CouplingCommunity:
    """Eine Kopplungs-Community und ihre geerdete Charakterisierung.

    Alle Felder beschreiben STRUKTUR (wer mit wem über geteilte Zitation
    gekoppelt ist) und VERANKERN sie (Journals, Diskursräume, sauberes Topic-
    Vokabular, gemeinsame Referenzbasis) — kein Relevanz-Urteil.
    """

    cid: int                                       # stabile Ordinal-ID (1 = größte)
    size: int
    article_ids: list[str]
    top_journals: list[tuple[str, int, float]]     # (journal, n, share)
    n_journals: int
    journal_concentration: float                   # Anteil des größten Journals
    discourse_composition: list[tuple[str, float]] # (space-key, share) absteigend; share-Summe > 1 (Mehrfach-Mapping)
    n_unmapped: int                                 # Artikel ohne Diskursraum-Mapping
    cross_field: bool                               # >= 2 THEMATISCHE Räume je >= BRIDGE_MIN
    top_topics: list[tuple[str, int, float]]        # (topic, n, share) — sauberes Vokabular
    year_median: float | None
    year_iqr: tuple[int, int] | None
    intellectual_base: list[BaseRef] = field(default_factory=list)


@dataclass
class CouplingResult:
    # Parameter (für Reproduzierbarkeit im Report ausgewiesen)
    min_df: int
    max_df: int
    min_shared: int
    resolution: float
    seed: int
    min_community: int
    score_min: float
    # Graph-Statistik
    n_articles_total: int          # ref-tragende Artikel im Fenster
    n_nodes: int                   # Artikel mit >= 1 Kante
    n_edges: int
    n_refs_kept: int               # koppelnde Referenzen (df in [min_df, max_df])
    modularity: float
    n_communities_total: int       # alle Louvain-Communities
    communities: list[CouplingCommunity]   # nur >= min_community, nach Größe absteigend
    year_range: tuple[int | None, int | None]
    discourse_space_names: dict[str, str]


def _median_iqr(years: list[int]) -> tuple[float | None, tuple[int, int] | None]:
    ys = sorted(y for y in years if y is not None)
    if not ys:
        return None, None
    n = len(ys)
    med = ys[n // 2] if n % 2 else (ys[n // 2 - 1] + ys[n // 2]) / 2
    q1 = ys[max(0, int(round(0.25 * (n - 1))))]
    q3 = ys[min(n - 1, int(round(0.75 * (n - 1))))]
    return float(med), (q1, q3)


def compute_coupling_communities(
    store: Store | None = None,
    *,
    start_year: int | None = None,
    end_year: int | None = None,
    min_df: int = MIN_DF,
    max_df: int = MAX_DF,
    min_shared: int = MIN_SHARED,
    resolution: float = RESOLUTION,
    seed: int = SEED,
    min_community: int = MIN_COMMUNITY,
    score_min: float = SCORE_MIN,
    top_journals: int = TOP_JOURNALS,
    top_topics: int = TOP_TOPICS,
    top_refs: int = TOP_REFS,
    bridge_min: float = BRIDGE_MIN,
    discourse_path: Path | None = None,
) -> CouplingResult:
    """Bibliografische Kopplungs-Communities, geerdet auf geteilte Zitation.

    Pipeline (rein algorithmisch, deterministisch):
    1. Lade ref-tragende Artikel; baue inverse Liste Referenz → Artikel.
    2. Filtere koppelnde Referenzen auf df ∈ [min_df, max_df] (Stoppwort-Kappung).
    3. Akkumuliere Kantengewicht w(A,B) = Σ idf(r) über geteilte gekappte Refs;
       Kante nur, wenn >= `min_shared` solcher Refs geteilt werden.
    4. Louvain-Community-Detection (fester Seed) auf dem gewichteten Graphen.
    5. Charakterisiere jede Community >= `min_community`: Journals, Diskursraum-
       Komposition, sauberes Topic-Vokabular, Jahr, geteilte Referenzbasis.
    """
    import networkx as nx
    from networkx.algorithms.community import louvain_communities, modularity

    store = store or Store()
    # Nach id sortiert → stabile Knoten-Indizes unabhängig von SQL-Tie-Order.
    articles = sorted(
        store.find_in_window(start_year=start_year, end_year=end_year),
        key=lambda a: a.id,
    )

    # 1. ref-tragende Artikel + inverse Liste
    arts: list[dict] = []
    ref_to_idx: dict[str, list[int]] = defaultdict(list)
    years_seen: list[int] = []
    for a in articles:
        refs = {_bare_ref(r) for r in (a.openalex_refs or []) if r}
        refs.discard("")
        if not refs:
            continue
        idx = len(arts)
        arts.append({
            "id": a.id,
            "journal": a.journal_short,
            "year": a.year,
            "topics": _topic_names(a.openalex_topics, score_min),
            "refs": refs,
        })
        if a.year is not None:
            years_seen.append(a.year)
        for r in refs:
            ref_to_idx[r].append(idx)

    n_total = len(arts)
    global_df = {r: len(idxs) for r, idxs in ref_to_idx.items()}

    # 2. koppelnde Referenzen + IDF
    idf: dict[str, float] = {}
    for r, df in global_df.items():
        if min_df <= df <= max_df:
            idf[r] = math.log(n_total / df) if n_total > df else 0.0
    n_refs_kept = len(idf)

    # 3. gewichtete Kanten via inverser Liste (nur gekappte Refs)
    pair_w: dict[tuple[int, int], float] = defaultdict(float)
    pair_c: dict[tuple[int, int], int] = defaultdict(int)
    for r, w in idf.items():
        idxs = ref_to_idx[r]
        for a, b in combinations(idxs, 2):
            key = (a, b) if a < b else (b, a)
            pair_w[key] += w
            pair_c[key] += 1

    # Kanten in sortierter Reihenfolge einfügen → deterministische Adjazenz,
    # damit Louvain (ordnungs-sensitiv) bei festem Seed reproduzierbar ist;
    # sonst leckt die Set-/Dict-Iterationsordnung (PYTHONHASHSEED) in das Ergebnis.
    edges = sorted(
        (a, b, pair_w[(a, b)]) for (a, b), c in pair_c.items() if c >= min_shared
    )
    G = nx.Graph()
    G.add_nodes_from(sorted({x for a, b, _ in edges for x in (a, b)}))
    for a, b, w in edges:
        G.add_edge(a, b, weight=w)

    # 4. Louvain (deterministisch)
    if G.number_of_edges():
        comms = louvain_communities(G, weight="weight", seed=seed, resolution=resolution)
        mod = modularity(G, comms, weight="weight")
    else:
        comms = []
        mod = 0.0
    comms = sorted(comms, key=len, reverse=True)

    # 5. Charakterisierung (nur Communities >= min_community)
    j_disc, space_names = load_journal_discourse_map(discourse_path)
    communities: list[CouplingCommunity] = []
    cid = 0
    for members in comms:
        if len(members) < min_community:
            continue
        cid += 1
        m = [arts[i] for i in members]
        size = len(m)

        jc = Counter(x["journal"] for x in m)
        top_j = [(j, n, n / size) for j, n in jc.most_common(top_journals)]
        journal_conc = jc.most_common(1)[0][1] / size if jc else 0.0

        disc = Counter()
        n_unmapped = 0
        for x in m:
            spaces = j_disc.get(x["journal"])
            if not spaces:
                n_unmapped += 1
                continue
            for s in spaces:
                disc[s] += 1
        disc_comp = sorted(((s, n / size) for s, n in disc.items()), key=lambda t: -t[1])
        thematic = [s for s, sh in disc_comp if sh >= bridge_min and s not in LANGUAGE_SPACES]
        cross_field = len(thematic) >= 2

        tc = Counter()
        for x in m:
            for t in x["topics"]:
                tc[t] += 1
        top_t = [(t, n, n / size) for t, n in tc.most_common(top_topics)]

        med, iqr = _median_iqr([x["year"] for x in m])

        # geteilte Referenzbasis: within-community DF über ALLE Refs (geerdeter
        # Fingerprint), annotiert mit globalem DF, damit Feld-Kanon sichtbar bleibt.
        within = Counter()
        for x in m:
            for r in x["refs"]:
                within[r] += 1
        base = [
            BaseRef(ref_id=r, within_count=n, within_share=n / size,
                    global_df=global_df.get(r, n))
            for r, n in within.most_common(top_refs) if n >= 2
        ]

        communities.append(CouplingCommunity(
            cid=cid, size=size, article_ids=sorted(x["id"] for x in m),
            top_journals=top_j, n_journals=len(jc), journal_concentration=journal_conc,
            discourse_composition=disc_comp, n_unmapped=n_unmapped, cross_field=cross_field,
            top_topics=top_t, year_median=med, year_iqr=iqr, intellectual_base=base,
        ))

    yr_lo = min(years_seen) if years_seen else None
    yr_hi = max(years_seen) if years_seen else None
    return CouplingResult(
        min_df=min_df, max_df=max_df, min_shared=min_shared, resolution=resolution,
        seed=seed, min_community=min_community, score_min=score_min,
        n_articles_total=n_total, n_nodes=G.number_of_nodes(), n_edges=G.number_of_edges(),
        n_refs_kept=n_refs_kept, modularity=mod, n_communities_total=len(comms),
        communities=communities, year_range=(yr_lo, yr_hi),
        discourse_space_names=space_names,
    )


def resolve_base_titles(result: CouplingResult, *, verbose: bool = False) -> None:
    """Füllt `BaseRef.title`/`.year` über den gecachten OpenAlex-Resolver (in-place).

    Optionale Anreicherung; bleibt ohne Netz ein No-Op-Versuch (Titel = None).
    """
    from journal_bot.own_refs.oa_titles import resolve_oa_titles

    ids = {b.ref_id for c in result.communities for b in c.intellectual_base}
    if not ids:
        return
    titles = resolve_oa_titles(ids, verbose=verbose)
    for c in result.communities:
        for b in c.intellectual_base:
            info = titles.get(b.ref_id) or {}
            b.title = info.get("title")
            b.year = info.get("year")


def _ref_label(b: BaseRef) -> str:
    if b.title:
        yr = f", {b.year}" if b.year else ""
        return f"{b.title}{yr}"
    return f"OA:{b.ref_id}"


def _community_block(c: CouplingCommunity, space_names: dict[str, str]) -> str:
    o: list[str] = []
    yr = ""
    if c.year_median is not None and c.year_iqr is not None:
        yr = f" · Jahr-Median {c.year_median:.0f} (IQR {c.year_iqr[0]}–{c.year_iqr[1]})"
    tag = " · **cross-field**" if c.cross_field else ""
    o.append(f"### C{c.cid} — {c.size} Artikel · {c.n_journals} Journals{yr}{tag}\n")

    jstr = ", ".join(f"{j} {100*sh:.0f}%" for j, n, sh in c.top_journals)
    o.append(f"**Journals** (Konz. größtes {100*c.journal_concentration:.0f}%): {jstr}\n")

    if c.discourse_composition:
        dstr = ", ".join(
            f"{space_names.get(s, s)} {100*sh:.0f}%" for s, sh in c.discourse_composition
        )
        extra = f" · {c.n_unmapped} ohne Mapping" if c.n_unmapped else ""
        o.append(f"**Diskursräume** (Mehrfach-Mapping, Summe > 100%): {dstr}{extra}\n")

    if c.top_topics:
        tstr = ", ".join(f"{t} ({100*sh:.0f}%)" for t, n, sh in c.top_topics)
        o.append(f"**Topics** (sauberes Vokabular): {tstr}\n")

    if c.intellectual_base:
        o.append("**Geteilte Referenzbasis** (within-Community / global zitiert):\n")
        for b in c.intellectual_base:
            o.append(
                f"- {_ref_label(b)} — {b.within_count}/{c.size} der Community "
                f"({100*b.within_share:.0f}%), korpusweit {b.global_df}×"
            )
        o.append("")
    return "\n".join(o)


def render_report(result: CouplingResult) -> str:
    o: list[str] = []
    o.append("# Bibliografische Kopplungs-Communities im MOJO-Korpus\n")
    o.append(
        "**Erzeugt von** `journal_bot.corpus_explore.coupling` (rein algorithmisch, kein LLM). "
        "**Handlung:** strukturieren + verankern. Zwei Artikel sind gekoppelt, weil sie "
        "**dasselbe Werk zitieren** (belegte geteilte Zitation), nicht über Text-Ähnlichkeit — "
        "darum spricht die Struktur als Befund. **Kein** Relevanz-Urteil über Artikel.\n"
    )
    o.append("## Konditionierung\n")
    o.append(
        "Der Korpus ist die vollständige Erhebung einer **personalisierten Journal-Watchlist**. "
        "Die Kopplungsstruktur ist die *dieses kuratierten Stroms* — der Diskurs, wie er den "
        "User erreicht —, **nie** neutrale Feld-Struktur.\n"
    )
    o.append("## Methode\n")
    o.append(
        f"Kantengewicht = Σ idf(r) über geteilte Referenzen mit Korpus-df ∈ "
        f'[{result.min_df}, {result.max_df}] (vielzitierte Werke als "Zitations-Stoppwörter" '
        f"gekappt); Kante nur ab {result.min_shared} geteilten solchen Referenzen. "
        f"Community-Detection: Louvain (Auflösung {result.resolution}, Seed {result.seed}, "
        f"deterministisch). **cross-field** = Community spannt ≥ 2 thematische Diskursräume "
        f'mit je ≥ {100*BRIDGE_MIN:.0f}% Anteil (Sprach-Raum "deutsche" ausgenommen).\n'
    )
    lo, hi = result.year_range
    win = f"{lo}–{hi}" if lo and hi else "alle Jahre"
    o.append(
        f"**Daten:** {result.n_articles_total} ref-tragende Artikel ({win}); "
        f"koppelnde Referenzen: {result.n_refs_kept}. "
        f"**Graph:** {result.n_nodes} Knoten, {result.n_edges} Kanten. "
        f"**Louvain:** {result.n_communities_total} Communities (Modularität "
        f"{result.modularity:.3f}); davon {len(result.communities)} mit ≥ "
        f"{result.min_community} Artikeln (unten).\n"
    )
    o.append(f"## Communities (≥ {result.min_community} Artikel, nach Größe)\n")
    for c in result.communities:
        o.append(_community_block(c, result.discourse_space_names))
    return "\n".join(o)


def _console_summary(result: CouplingResult) -> str:
    lines = [
        f"Graph: {result.n_nodes} Knoten / {result.n_edges} Kanten "
        f"(koppelnde Refs: {result.n_refs_kept}) | "
        f"Louvain: {result.n_communities_total} Communities, Modularität {result.modularity:.3f}",
        f"Gemeldet (>= {result.min_community} Artikel): {len(result.communities)}",
        "(Kopplung = geteilte Zitation, GEERDET; keine Vektor-Ähnlichkeit, kein Urteil)",
        "",
    ]
    for c in result.communities:
        top_j = c.top_journals[0][0] if c.top_journals else "?"
        top_t = c.top_topics[0][0] if c.top_topics else "?"
        tag = " [cross-field]" if c.cross_field else ""
        lines.append(
            f"  C{c.cid:<2} n={c.size:<5} {c.n_journals:>2}J  top={top_j:<12} "
            f"„{top_t}\"{tag}"
        )
    return "\n".join(lines)


def run(
    *,
    start_year: int | None = None,
    end_year: int | None = None,
    min_df: int = MIN_DF,
    max_df: int = MAX_DF,
    min_shared: int = MIN_SHARED,
    resolution: float = RESOLUTION,
    seed: int = SEED,
    min_community: int = MIN_COMMUNITY,
    resolve_titles: bool = True,
    out: Path | None = None,
    store: Store | None = None,
    verbose: bool = True,
) -> CouplingResult:
    """Berechnet die Kopplungs-Communities und gibt sie aus (stdout und/oder Datei)."""
    result = compute_coupling_communities(
        store, start_year=start_year, end_year=end_year, min_df=min_df, max_df=max_df,
        min_shared=min_shared, resolution=resolution, seed=seed, min_community=min_community,
    )
    if resolve_titles and result.communities:
        resolve_base_titles(result, verbose=verbose)
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_report(result), encoding="utf-8")
    if verbose:
        print(_console_summary(result))
        if out is not None:
            print(f"\nReport → {out}")
    return result
