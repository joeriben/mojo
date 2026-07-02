"""Algorithmische Korpus-Erschließung — MOJO-Fähigkeiten über articles.db.

Familie additiver, rein algorithmischer Methoden, mit denen MOJO Struktur und
Bewegung in seinem Korpus erschließt. Auftrag + bindende Disziplin:
docs/mojo2_korpus_exploration_goal.md.

Fähigkeiten:
- Themen-Trajektorien (within-journal-dekomponiert) — `trajectories`
- Bibliografische Kopplungs-Communities (geteilte Referenzbasis) — `coupling`
"""
from journal_bot.corpus_explore import coupling, trajectories
from journal_bot.corpus_explore.coupling import (
    BaseRef,
    CouplingCommunity,
    CouplingResult,
    compute_coupling_communities,
)
from journal_bot.corpus_explore.trajectories import (
    TopicTrajectory,
    TrajectoryResult,
    compute_trajectories,
    render_report,
    run,
)

__all__ = [
    "trajectories",
    "coupling",
    "TopicTrajectory",
    "TrajectoryResult",
    "compute_trajectories",
    "render_report",
    "run",
    "BaseRef",
    "CouplingCommunity",
    "CouplingResult",
    "compute_coupling_communities",
]
