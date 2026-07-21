"""Auswahlregeln des Nutzers — als Daten, nicht als Code.

Die Regeln, nach denen jemand Beiträge verwirft oder aufhebt, gehören dieser
Person. Sie stehen deshalb in `regeln.json` neben `profile.json` und nirgends
in `journal_bot`. Ausgeliefert wird das Verfahren, nicht ein bestimmtes
Ergebnis: ein frischer Clone hat keine Regeln, und die Vorprüfung läuft dann
unverändert wie bisher.

## Typ und Platz sind Teil der Regel

Eine Regel ist kein freier Satz. Ohne Typ und Position entstehen
Scheinwidersprüche: »dekoloniales öffnet meine Interessenfelder« und »aber
niemals Richtung Gesundheitsversorgung« widersprechen sich nur, solange man sie
als ungeordnete Menge liest. Geordnet ist der Fall bei der ersten Regel
entschieden, und die Öffnung erreicht ihn nie.

    terminale_sperre    verwirft endgültig — keine Öffnung hebt sie auf
    aufhebbare_sperre   verwirft, kann durch eine spätere Öffnung gehoben werden
    oeffnung            hebt eine aufhebbare Sperre auf »vertiefen«
    verengung           hebt den Massstab in einem Bereich
    kalibrierung        misst gegen eine benannte Bezugsgrösse

Die Reihenfolge wird als Position geführt und beim Rendern eingehalten.
Dieselbe Sperre an Platz 1 statt Platz 2 ist eine ANDERE Regel — an 1 ist sie
unhintergehbar, an 2 lässt sie sich öffnen.

## Wortlaut

Der Wortlaut gehört dem Nutzer und wird nicht übersetzt und nicht geglättet.
»reduktionistische Tool-Perspektive« ist nicht »angewandt«, »solutionistisch«
nicht »lösungsorientiert«. Die Regeln gehen deshalb wörtlich in den Prompt, auch
wenn der Rest des Blocks englisch ist.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REGELN_JSON = PROJECT_ROOT / "regeln.json"

TYPEN = (
    "terminale_sperre",
    "aufhebbare_sperre",
    "oeffnung",
    "verengung",
    "kalibrierung",
)

# Wie der Typ im Prompt erscheint. Bewusst als Handlungsanweisung formuliert:
# das Modell soll nicht über Typen nachdenken, sondern tun, was dort steht.
TYP_ANWEISUNG = {
    "terminale_sperre": (
        "DROP. This is final — no later rule lifts it, however the article is "
        "framed and whatever method it uses."
    ),
    "aufhebbare_sperre": (
        "DROP, unless a later opening rule applies to this article."
    ),
    "oeffnung": (
        "An article caught by a liftable block above, or foreign in subject "
        "matter only, is NOT dropped when this applies. Mark it vertiefen."
    ),
    "verengung": (
        "Raise the standard here. Proximity is not a reason to pass something "
        "through — judge how the object is taken up."
    ),
    "kalibrierung": (
        "Judge against the stated reference, not against the field in general."
    ),
}

# Der dritte Weg. »vertiefen« heisst nicht durchwinken, sondern weiterreichen
# mit dem ausdrücklichen Auftrag, an der Öffnung zu prüfen.
WEGE = ("weitergeben", "vertiefen", "ignorieren")


@dataclass
class Regel:
    id: str
    typ: str
    position: int
    wortlaut: str
    aktiv: bool = True
    herkunft: str = ""
    belege: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.typ not in TYPEN:
            raise ValueError(f"unbekannter Regeltyp: {self.typ!r} (erlaubt: {TYPEN})")
        if not str(self.wortlaut).strip():
            raise ValueError(f"Regel {self.id!r} hat keinen Wortlaut")

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "typ": self.typ, "position": self.position,
            "wortlaut": self.wortlaut, "aktiv": self.aktiv,
            "herkunft": self.herkunft, "belege": list(self.belege),
        }


def lade_regeln(pfad: Path = REGELN_JSON) -> list[Regel]:
    """Regeln laden und nach Position ordnen; leere Liste, wenn keine da sind.

    Fehler bleiben folgenlos: eine kaputte oder fehlende Datei darf den
    Wochenlauf nicht anhalten, sie lässt ihn nur ohne Regeln laufen.
    """
    if not pfad.exists():
        return []
    try:
        roh = json.loads(pfad.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    regeln = []
    for eintrag in roh.get("regeln") or []:
        try:
            regeln.append(Regel(
                id=str(eintrag["id"]), typ=str(eintrag["typ"]),
                position=int(eintrag.get("position", 999)),
                wortlaut=str(eintrag["wortlaut"]),
                aktiv=bool(eintrag.get("aktiv", True)),
                herkunft=str(eintrag.get("herkunft", "")),
                belege=list(eintrag.get("belege") or []),
            ))
        except (KeyError, ValueError, TypeError):
            continue
    return sortiere(regeln)


def sortiere(regeln: list[Regel]) -> list[Regel]:
    """Nach Position, bei Gleichstand nach Typ-Rang.

    Der Typ-Rang ist die Rückfalllinie, damit eine Öffnung nie vor der Sperre
    landet, die sie aufheben soll — auch dann nicht, wenn jemand zwei Regeln
    dieselbe Position gegeben hat.
    """
    rang = {t: i for i, t in enumerate(TYPEN)}
    return sorted(regeln, key=lambda r: (r.position, rang.get(r.typ, 99), r.id))


def speichere_regeln(regeln: list[Regel], pfad: Path = REGELN_JSON) -> None:
    pfad.write_text(
        json.dumps(
            {"version": 1, "regeln": [r.as_dict() for r in sortiere(regeln)]},
            ensure_ascii=False, indent=2,
        ) + "\n",
        encoding="utf-8",
    )


def build_regel_block(regeln: list[Regel] | None = None) -> str | None:
    """Die aktiven Regeln als Prompt-Block; None, wenn keine vorliegen.

    None statt leerem String, damit der Aufrufer den Block ganz weglassen kann
    und keine leere Überschrift in den Prompt schreibt.
    """
    if regeln is None:
        regeln = lade_regeln()
    aktive = [r for r in sortiere(regeln) if r.aktiv]
    if not aktive:
        return None

    zeilen = [
        "",
        "--- THIS RESEARCHER'S OWN TRIAGE RULES ---",
        "These are their rules, in their words, in the order they gave them.",
        "Work through them IN ORDER. A rule can only be lifted by a later rule",
        "that says so. Once a final block applies, you are done with that article",
        "— do not keep looking for a reason to pass it through.",
        "Do not decide by topical overlap: a topic label does not tell you how a",
        "text is constituted, and the constitution is what these rules are about.",
        "",
    ]
    for i, r in enumerate(aktive, start=1):
        zeilen.append(f"  {i}. [{r.typ}] «{r.wortlaut}»")
        zeilen.append(f"     → {TYP_ANWEISUNG[r.typ]}")
    zeilen += [
        "",
        "When no rule speaks to an article, fall back to the general judgement",
        "below. Passing something through costs one analysis; missing it costs",
        "the find.",
    ]
    return "\n".join(zeilen)


def erklaere_wege() -> str:
    """Kurze Beschreibung der drei Ausgänge für den Prompt."""
    return (
        "weitergeben — worth a full analysis\n"
        "vertiefen   — a block applied, but an opening rule lifted it: pass it on\n"
        "              WITH that tension named, so the analysis checks it\n"
        "ignorieren  — a final block applied, or nothing speaks for it"
    )
