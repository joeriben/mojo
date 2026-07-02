"""Kombination mehrerer Triage-Stimmen (algorithmisch + LLM) zu EINEM Urteil.

Entscheidung Benjamin (2026-05-30), auf der richtigen Achse — nicht
{lesenswert} vs Rest, sondern BEHALTEN {lesenswert, scannen, pflichtlektuere}
vs WEGWERFEN {ignorieren}:

  - Konsens behalten (alle Stimmen behalten) → stärkstes Signal, sicher behalten.
  - Konsens wegwerfen (alle wegwerfen)        → sicheres Rauschen, einziger Fall
                                                in dem wirklich verworfen wird.
  - Dissens (Stimmen uneins)                  → geflaggt. Recall-schützend
                                                BEHALTEN (was damit weiter
                                                geschieht, entscheidet Benjamin).

Formal: BEHALTEN = ODER über alle Behalten-Stimmen (Vereinigung → senkt den
Falsch-Negativ-Bestand), WEGWERFEN = UND über alle Wegwerf-Stimmen (Schnitt →
nur wo alle partiell orthogonalen Signale dasselbe Rauschen sehen).

N Stimmen statt zwei: empirisch (2026-05-30) liefert die Kombination ihre
FN-Senkung nur, wenn die Stimmen ECHT orthogonal sind (M9-ML + LLM: FN 40→20).
Kategoriale Handregeln reproduzieren das nicht. Eine zweite billige LLM einer
anderen Modellfamilie ist die natürliche dritte orthogonale Stimme — deshalb
ist der Kombinierer nicht auf zwei Stimmen festgenagelt. Konfidenz skaliert mit
der Zustimmungszahl (3/3 > 2/3).

Warum Dissens nicht „der eine korrigiert den anderen": auf den Dissens-Fällen
ist KEINE Stimme verlässlich richtig (Iter 13: Veto-Regeln netto 0). Dissens ist
Information, kein zu überstimmender Fehler — er wird sichtbar gemacht.

Kein LLM-Call, keine I/O. Reine Funktion über bereits vorhandene Verdikte.
"""

from __future__ import annotations

from dataclasses import dataclass

KEEP = frozenset({"lesenswert", "scannen", "pflichtlektuere"})
DISCARD = frozenset({"ignorieren"})

# Schärfe-Ordnung für ein Anzeige-Label (Sortierung im Digest)
_SEVERITY = {"pflichtlektuere": 3, "lesenswert": 2, "scannen": 1, "ignorieren": 0}


def _keep_vote(verdict: str | None) -> bool | None:
    """True=behalten, False=wegwerfen, None=kein Signal/unbekanntes Label."""
    if not isinstance(verdict, str):
        return None
    v = verdict.strip().lower()
    if v in KEEP:
        return True
    if v in DISCARD:
        return False
    return None  # leer oder unbekanntes Label zählt nicht als Stimme


def _sharpest(verdicts) -> str:
    cand = [v for v in verdicts if isinstance(v, str) and v.strip()]
    return max(cand, key=lambda v: _SEVERITY.get(v.strip().lower(), -1), default="")


@dataclass(frozen=True)
class CombinedTriage:
    decision: str        # "behalten" | "wegwerfen"
    state: str           # "konsens_behalten" | "konsens_wegwerfen" | "dissens" | "ein_signal"
    consensus: bool      # True wenn alle vorhandenen Stimmen übereinstimmen
    flagged: bool        # True bei Dissens / nur einer Stimme (UI-Hinweis)
    n_keep: int          # Anzahl Behalten-Stimmen
    n_votes: int         # Anzahl vorhandener (verwertbarer) Stimmen
    display_label: str   # schärfstes der Verdikte (für Sortierung)
    note: str            # kurze deutsche Begründung

    @property
    def keep(self) -> bool:
        return self.decision == "behalten"

    @property
    def agreement(self) -> float:
        """Zustimmungsgrad 0..1 (für UI-Gradation 3/3 > 2/3)."""
        return self.n_keep / self.n_votes if self.n_votes else 0.0


def combine_votes(verdicts) -> CombinedTriage:
    """Kombiniere beliebig viele Triage-Verdikte zu Entscheidung + Konfidenz.

    verdicts: Iterable von Labels aus {lesenswert, scannen, pflichtlektuere,
    ignorieren} oder None/"" (zählt nicht). Reihenfolge egal.
    """
    verdicts = list(verdicts)
    votes = [_keep_vote(v) for v in verdicts]
    present = [v for v in votes if v is not None]
    n_votes = len(present)
    n_keep = sum(1 for v in present if v)
    label = _sharpest(verdicts)

    if n_votes == 0:
        return CombinedTriage(
            "behalten", "ein_signal", consensus=False, flagged=True,
            n_keep=0, n_votes=0, display_label=label,
            note="keine verwertbare Triage — recall-schützend behalten")

    if n_votes == 1:
        keep = present[0]
        return CombinedTriage(
            "behalten" if keep else "wegwerfen", "ein_signal",
            consensus=False, flagged=True, n_keep=n_keep, n_votes=1,
            display_label=label if keep else "ignorieren",
            note="nur eine Stimme vorhanden — unsicher")

    if n_keep == n_votes:
        return CombinedTriage(
            "behalten", "konsens_behalten", consensus=True, flagged=False,
            n_keep=n_keep, n_votes=n_votes, display_label=label,
            note=f"alle {n_votes} Stimmen behalten — stärkstes Signal")
    if n_keep == 0:
        return CombinedTriage(
            "wegwerfen", "konsens_wegwerfen", consensus=True, flagged=False,
            n_keep=0, n_votes=n_votes, display_label="ignorieren",
            note=f"alle {n_votes} Stimmen wegwerfen — sicheres Rauschen")
    return CombinedTriage(
        "behalten", "dissens", consensus=False, flagged=True,
        n_keep=n_keep, n_votes=n_votes, display_label=label,
        note=f"Dissens {n_keep}/{n_votes} behalten — recall-schützend behalten")


def combine_triage(cascade_verdict: str | None, llm_verdict: str | None) -> CombinedTriage:
    """Zwei-Stimmen-Spezialfall (Cascade + LLM) — Bequemlichkeits-Wrapper."""
    return combine_votes([cascade_verdict, llm_verdict])
