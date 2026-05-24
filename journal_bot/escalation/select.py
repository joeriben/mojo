"""Auswahl der Unklar-Zone-Kandidaten aus articles.db.

Definition Unklar-Zone (post-cascade):
  - selection_mode in (complementarity, similarity, mixed, screening) — also
    NICHT citation (User hat Eigenwerk getroffen) und NICHT trigger
    (Trigger-Autor garantiert Eskalation auf andere Weise).
  - agent_verdict in (scannen, ignorieren) — also nicht schon lesenswert
    (das geht ohne LLM-Volltext durch).
  - Mit Signal-Restspannung: entweder discourse_indicator ≥ schwacher_indikator
    ODER own_coupling/adversarial-Score > 0.

Wir scoren jeden Kandidaten mit einem PrioScore aus:
  + own_coupling.score (IDF, MOJO 2.0 §2.1b)
  + adversarial.score  (IDF, MOJO 2.0 §2.2)
  + 0.5 wenn discourse_indicator=starker_indikator
  + 0.2 wenn agent_verdict=scannen (eher LES als IGN, knapper Fall)
  − 0.5 wenn agent_verdict=ignorieren (klares IGN, weniger Eskalations-Bedarf)

PrioScore ist ein PRAGMATISCHER Sortierhinweis, keine Wahrheit. Die LLM-
Eskalation läuft danach genau in dieser Reihenfolge — die besten Kandidaten
zuerst, damit ein Budget-Cap (`--limit N`) die wertvollsten Items abbildet.

Signal-Scores werden LIVE aus articles.openalex_refs + own_refs.db berechnet
(via signal_own_coupling/signal_adversarial_blindspot), NICHT aus dem
gespeicherten agent_entry_json — sonst würden Bestands-Items, die vor §2.1
verarbeitet wurden, nie eskaliert.

Keine LLM-Calls. Reine SQL + JSON-Decoding + Signal-Berechnung.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass
class EscalationCandidate:
    """Ein Artikel, der nach Cascade-Regeln noch unklar ist."""
    article_id: str
    journal_short: str
    title: str
    year: int | None
    doi: str | None
    openalex_id: str | None
    agent_verdict: str | None
    user_verdict: str | None
    selection_mode: str | None
    discourse_indicator: str | None
    own_coupling_score: float
    adversarial_score: float
    prio_score: float
    reason: str                       # menschenlesbare Begründung


_ELIGIBLE_MODES = ("complementarity", "similarity", "mixed", "screening")
_ELIGIBLE_VERDICTS = ("scannen", "ignorieren")


def _parse_openalex_refs(raw_json: str | None) -> list[str]:
    """JSON-Liste der OpenAlex-Refs aus articles.openalex_refs parsen."""
    if not raw_json:
        return []
    try:
        d = json.loads(raw_json)
    except (json.JSONDecodeError, TypeError):
        return []
    if isinstance(d, list):
        return [str(x) for x in d if x]
    return []


def _compute_prio_score(
    verdict: str | None,
    indicator: str | None,
    own_score: float,
    adv_score: float,
) -> float:
    s = own_score + adv_score
    if indicator == "starker_indikator":
        s += 0.5
    if verdict == "scannen":
        s += 0.2
    elif verdict == "ignorieren":
        s -= 0.5
    return round(s, 3)


def _build_reason(
    verdict: str | None,
    indicator: str | None,
    mode: str | None,
    own_score: float,
    adv_score: float,
) -> str:
    parts: list[str] = []
    if mode:
        parts.append(f"mode={mode}")
    if indicator and indicator != "kein_indikator":
        parts.append(indicator)
    if own_score > 0:
        parts.append(f"own_coupling={own_score:.2f}")
    if adv_score > 0:
        parts.append(f"adversarial={adv_score:.2f}")
    if verdict:
        parts.append(f"agent={verdict}")
    return ", ".join(parts) if parts else "(keine Signale)"


def select_candidates(
    articles_db: Path,
    limit: int | None = None,
    min_prio_score: float = 0.0,
    journals: Iterable[str] | None = None,
    only_wrong_les: bool = False,
    own_refs_db: Path | None = None,
) -> list[EscalationCandidate]:
    """Liefere die Unklar-Zone-Kandidaten, sortiert nach PrioScore absteigend.

    Args:
        articles_db: Pfad zu articles.db.
        limit: Maximale Anzahl Kandidaten (None = alle).
        min_prio_score: Untergrenze. PrioScore < dieser Wert wird verworfen.
        journals: Nur diese journal_short. None = alle.
        only_wrong_les: Wenn True, nur Items mit user_verdict='lesenswert'
            UND agent_verdict != 'lesenswert' — der klassische Recovery-Fall.
        own_refs_db: Pfad zur own_refs.db für Signal-Live-Berechnung.
            Default: <PROJECT_ROOT>/own_refs.db.

    Returns:
        Liste, sortiert nach PrioScore absteigend.
    """
    if not articles_db.exists():
        return []

    # Signal-Bausteine einmalig laden (cache-freundlich).
    from journal_bot.own_refs.corpus_freq import load_or_compute_corpus_freq
    from journal_bot.own_refs.index import load_own_refs_index
    from journal_bot.adversarial.corpus_freq import (
        load_or_compute_adversarial_corpus_freq,
    )
    from journal_bot.adversarial.trigger_refs import (
        load_or_compute_adversarial_index,
    )
    from journal_bot.signals import (
        signal_adversarial_blindspot, signal_own_coupling,
    )

    if own_refs_db is None:
        own_refs_db = Path(__file__).resolve().parents[2] / "own_refs.db"
    trigger_dir = Path(__file__).resolve().parents[2] / "backtest_data" / "trigger_bibliographies"

    own_idx = load_own_refs_index(own_refs_db)
    try:
        own_freq = load_or_compute_corpus_freq(
            articles_db, own_idx, own_refs_db=own_refs_db,
        )
    except Exception:
        own_freq = None
    try:
        adv_idx = load_or_compute_adversarial_index(
            trigger_dir, own_idx, own_refs_db=own_refs_db,
        )
    except Exception:
        from journal_bot.adversarial.trigger_refs import AdversarialIndex
        adv_idx = AdversarialIndex()
    try:
        adv_freq = load_or_compute_adversarial_corpus_freq(
            articles_db, adv_idx, own_refs_db=own_refs_db,
        )
    except Exception:
        adv_freq = None

    con = sqlite3.connect(f"file:{articles_db}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        sql = """
            SELECT id, journal_short, title, year, doi, openalex_id,
                   agent_verdict, user_verdict, selection_mode,
                   discourse_indicator, openalex_refs
              FROM articles
             WHERE agent_processed_at IS NOT NULL
               AND selection_mode IN ({modes})
               AND agent_verdict IN ({verdicts})
        """.format(
            modes=",".join("?" * len(_ELIGIBLE_MODES)),
            verdicts=",".join("?" * len(_ELIGIBLE_VERDICTS)),
        )
        params: list = list(_ELIGIBLE_MODES) + list(_ELIGIBLE_VERDICTS)
        if journals:
            jl = list(journals)
            sql += " AND journal_short IN (" + ",".join("?" * len(jl)) + ")"
            params += jl
        if only_wrong_les:
            sql += " AND user_verdict = 'lesenswert' "
        rows = con.execute(sql, params).fetchall()
    finally:
        con.close()

    out: list[EscalationCandidate] = []
    for r in rows:
        oa_refs = _parse_openalex_refs(r["openalex_refs"])
        # signal_own_coupling((crossref_refs, openalex_refs, idx, freq)
        # crossref_refs ist hier None — wir nutzen nur OpenAlex-Refs, das
        # ist konsistent mit der LIVE-Validierung in iter11i.
        own_sig = signal_own_coupling(None, oa_refs, own_idx, own_freq)
        adv_sig = signal_adversarial_blindspot(oa_refs, adv_idx, adv_freq)
        own_s = float(own_sig.get("score", 0.0) or 0.0) if own_sig else 0.0
        adv_s = float(adv_sig.get("score", 0.0) or 0.0) if adv_sig else 0.0
        prio = _compute_prio_score(
            verdict=r["agent_verdict"],
            indicator=r["discourse_indicator"],
            own_score=own_s,
            adv_score=adv_s,
        )
        if prio < min_prio_score:
            continue
        out.append(EscalationCandidate(
            article_id=r["id"],
            journal_short=r["journal_short"] or "",
            title=r["title"] or "",
            year=r["year"],
            doi=r["doi"],
            openalex_id=r["openalex_id"],
            agent_verdict=r["agent_verdict"],
            user_verdict=r["user_verdict"],
            selection_mode=r["selection_mode"],
            discourse_indicator=r["discourse_indicator"],
            own_coupling_score=own_s,
            adversarial_score=adv_s,
            prio_score=prio,
            reason=_build_reason(
                r["agent_verdict"], r["discourse_indicator"],
                r["selection_mode"], own_s, adv_s,
            ),
        ))

    out.sort(key=lambda c: c.prio_score, reverse=True)
    if limit is not None:
        return out[:limit]
    return out


def summarize_pool(candidates: list[EscalationCandidate]) -> dict:
    """Aggregat-Statistik über eine Kandidatenliste (für CLI-Print)."""
    from collections import Counter
    by_mode: Counter = Counter()
    by_verdict: Counter = Counter()
    by_indicator: Counter = Counter()
    by_journal: Counter = Counter()
    n_with_own = sum(1 for c in candidates if c.own_coupling_score > 0)
    n_with_adv = sum(1 for c in candidates if c.adversarial_score > 0)
    n_wrong_les = sum(
        1 for c in candidates
        if c.user_verdict == "lesenswert" and c.agent_verdict != "lesenswert"
    )
    for c in candidates:
        by_mode[c.selection_mode or "(none)"] += 1
        by_verdict[c.agent_verdict or "(none)"] += 1
        by_indicator[c.discourse_indicator or "(none)"] += 1
        by_journal[c.journal_short] += 1
    return {
        "n_total": len(candidates),
        "n_with_own_coupling": n_with_own,
        "n_with_adversarial": n_with_adv,
        "n_wrong_les": n_wrong_les,
        "by_mode": dict(by_mode.most_common()),
        "by_verdict": dict(by_verdict.most_common()),
        "by_indicator": dict(by_indicator.most_common()),
        "by_journal_top10": dict(by_journal.most_common(10)),
        "prio_score_p50": (
            sorted(c.prio_score for c in candidates)[len(candidates) // 2]
            if candidates else 0.0
        ),
        "prio_score_max": max((c.prio_score for c in candidates), default=0.0),
    }
