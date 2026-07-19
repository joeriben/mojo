"""Die Korrekturen des Nutzers als Prompt-Block.

Der Bestand enthält 913 Urteile aus der Oberfläche, 217 davon widersprechen
einer ausformulierten Begründung des Agenten, 53 tragen ein Memo im Wortlaut
des Nutzers. Bis hierher erreichte nichts davon irgendeinen Prompt — die Felder
kamen nur in Export- und Anzeigepfaden vor. Der Agent begann jede Woche neu.

Dieses Modul legt das Material daneben, so wie man eine wissenschaftliche
Hilfskraft an ihren ersten Vorschlägen korrigiert: erst die Ansagen, die der
Nutzer selbst formuliert hat, dann die Fälle, in denen er ein Urteil samt
Begründung umgestossen hat.

Drei Dinge sind dabei entscheidend:

1. **Der Wortlaut bleibt deutsch.** »solutionistisch« ist nicht
   »lösungsorientiert«, »reduktionistische Tool-Perspektive« nicht »applied«.
   Übersetzt man die Memos, übersetzt man die Unterscheidung weg.

2. **Drei Akte, nicht zwei Klassen.** Unter »behalten« liegen Anschluss an ein
   laufendes Projekt, Aufheben als Material und Aufheben als GEGENBELEG. Das
   letzte sieht in jedem Merkmal aus wie die Wegwerf-Klasse; wer es zusammen mit
   den anderen als »gut« vorführt, lehrt das Gegenteil.

3. **Ein Teil bleibt draussen.** `TEIL_BLOCK` legt fest, welcher Anteil der
   Widersprüche in den Block darf; der Rest ist die zurückgehaltene Menge, an
   der geprüft wird, ob der Block überhaupt etwas trägt. Ohne diese Trennung
   misst man den Block an dem, was in ihm steht.

Epistemischer Status: das sind beobachtete Urteile des Nutzers, keine Rechnung
und keine Ableitung. Der Block sagt das im Kopf, damit das Modell die Beispiele
nicht als Regelmenge überdehnt.
"""

from __future__ import annotations

import json
import sqlite3
import zlib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB = PROJECT_ROOT / "articles.db"

TEIL_BLOCK = 0.67          # Anteil der Widersprüche, der in den Block darf
MAX_WIDERSPRUECHE = 30     # der Block ist Teil des Cache-Präfixes, nicht endlos
MAX_BEGRUENDUNG = 210      # Zeichen je Begründung — der Fehlschluss, nicht der Aufsatz
MAX_TITEL = 88

# Die Umkehrungen sind das schärfste Material: der Agent hat nicht danebengelegen,
# sondern ins Gegenteil. Sie kommen zuerst in den Block.
UMKEHRUNG = {("lesenswert", "ignorieren"), ("ignorieren", "lesenswert")}

VERDICT_KLARTEXT = {
    "ignorieren": "drop",
    "scannen": "scan",
    "lesenswert": "read",
    "pflichtlektuere": "must-read",
}


def _split(artikel_id: str) -> bool:
    """Gehört dieser Fall in den Block (True) oder in die Prüfmenge (False)?

    Deterministisch über die Artikel-ID, damit dieselbe Trennung bei jedem Lauf
    und in jedem Prozess herauskommt — sonst prüft man gegen eine Menge, die
    beim nächsten Aufruf schon im Block steht.
    """
    return (zlib.crc32(artikel_id.encode()) % 100) < int(TEIL_BLOCK * 100)


def _kuerzen(text: str, n: int) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[: n - 1].rsplit(" ", 1)[0] + "…"


def lade_material(db: Path = DB) -> dict:
    """Memos und Widersprüche aus dem Bestand holen, getrennt nach Block/Prüfung."""
    if not db.exists():
        return {"memos": [], "block": [], "pruefung": []}
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row

    memos = [
        {"verdict": r["user_verdict"], "memo": " ".join((r["user_memo"] or "").split()),
         "titel": r["title"]}
        for r in con.execute(
            "SELECT user_verdict, user_memo, title FROM articles"
            " WHERE TRIM(COALESCE(user_memo,'')) != '' AND user_verdict IS NOT NULL"
        )
    ]

    block, pruefung = [], []
    for r in con.execute(
        "SELECT id, title, journal_full, journal_short, user_verdict, agent_verdict,"
        "       user_memo, agent_entry_json FROM articles"
        " WHERE user_verdict IS NOT NULL AND agent_verdict IS NOT NULL"
        "   AND user_verdict != agent_verdict AND agent_entry_json NOT IN ('')"
    ):
        try:
            begr = (json.loads(r["agent_entry_json"]) or {}).get("verdict_begruendung") or ""
        except (json.JSONDecodeError, TypeError):
            continue
        if not begr.strip():
            continue
        fall = {
            "id": r["id"],
            "titel": r["title"] or "",
            "journal": r["journal_full"] or r["journal_short"] or "",
            "nutzer": r["user_verdict"],
            "agent": r["agent_verdict"],
            "begruendung": begr,
            "memo": " ".join((r["user_memo"] or "").split()),
            "umkehrung": (r["user_verdict"], r["agent_verdict"]) in UMKEHRUNG,
        }
        (block if _split(r["id"]) else pruefung).append(fall)
    con.close()
    return {"memos": memos, "block": block, "pruefung": pruefung}


def _auswahl(faelle: list[dict]) -> list[dict]:
    """Aus den Widersprüchen die lehrreichsten ziehen, beide Richtungen gleich stark.

    Umkehrungen zuerst; danach wird abwechselnd aus »Agent war zu grosszügig«
    und »Agent war zu streng« genommen, damit der Block nicht in eine Richtung
    zieht. Ein Block aus lauter »du warst zu streng« macht den Agenten
    grosszügig, und das ist kein besseres Urteil, sondern ein verschobenes.
    """
    rang = {"ignorieren": 0, "scannen": 1, "lesenswert": 2, "pflichtlektuere": 3}
    zu_grosszuegig = [f for f in faelle if rang[f["nutzer"]] < rang[f["agent"]]]
    zu_streng = [f for f in faelle if rang[f["nutzer"]] > rang[f["agent"]]]
    for gruppe in (zu_grosszuegig, zu_streng):
        # Umkehrungen nach vorn, danach die mit eigenem Memo — dort steht sein Wortlaut.
        gruppe.sort(key=lambda f: (not f["umkehrung"], not f["memo"], f["id"]))

    aus: list[dict] = []
    for a, b in zip(zu_streng, zu_grosszuegig):
        aus += [a, b]
    rest = zu_streng[len(zu_grosszuegig):] or zu_grosszuegig[len(zu_streng):]
    aus += rest
    return aus[:MAX_WIDERSPRUECHE]


def build_korrektur_block(material: dict | None = None) -> str | None:
    """Den Korrektur-Block bauen; None, wenn kein Material vorliegt."""
    m = material if material is not None else lade_material()
    memos, faelle = m["memos"], _auswahl(m["block"])
    if not memos and not faelle:
        return None

    ablehnungen = [x for x in memos if x["verdict"] == "ignorieren" and x["memo"]]
    zusagen = [x for x in memos if x["verdict"] in ("lesenswert", "pflichtlektuere") and x["memo"]]
    scans = [x for x in memos if x["verdict"] == "scannen" and x["memo"]]

    lines: list[str] = [
        "",
        "--- WHAT THIS RESEARCHER HAS CORRECTED ---",
        f"Observed judgements from the interface: {len(memos)} carry a note in his own",
        "words, and below them are cases where he overruled a predecessor's reasoning.",
        "These are his decisions as recorded — not a computation, not a rule set derived",
        "from them. Read them as instances. Do not generalise past what they show.",
        "His notes stay in German verbatim: the distinctions live in his wording, and a",
        "translation loses them.",
        "",
        "THREE DIFFERENT ACTS HIDE BEHIND KEEPING SOMETHING. Do not collapse them:",
        "  (a) it connects to a project he is currently running — this is what most of",
        "      his read-worthy notes actually name, not a quality of the article;",
        "  (b) it is useful material for a question he is working on;",
        "  (c) it is kept as a COUNTER-EXAMPLE, precisely because it is reductive, in",
        "      order to argue against it. Such an article looks exactly like the drop",
        "      class. Keeping it is not praise. Say which of the three you mean.",
    ]

    if ablehnungen:
        lines += ["", "What he says when he drops something (verbatim):"]
        for x in ablehnungen:
            lines.append(f"  «{_kuerzen(x['memo'], 120)}»")

    if zusagen:
        lines += [
            "",
            "What he says when something is read-worthy (verbatim) — note how rarely this",
            "describes the article at all, and how often it names a destination:",
        ]
        for x in zusagen[:18]:
            lines.append(f"  «{_kuerzen(x['memo'], 120)}»")

    if scans:
        lines += ["", "What he says when he keeps something to scan (verbatim):"]
        for x in scans[:14]:
            lines.append(f"  «{_kuerzen(x['memo'], 120)}»")

    if faelle:
        lines += [
            "",
            f"Cases where he overruled the reasoning ({len(faelle)} of "
            f"{len(m['block']) + len(m['pruefung'])} on record; the rest are held back to",
            "test whether this block helps at all). The quoted reason was the verdict that",
            "he then corrected:",
        ]
        for f in faelle:
            richtung = (
                "he was MORE generous"
                if {"ignorieren": 0, "scannen": 1, "lesenswert": 2, "pflichtlektuere": 3}[f["nutzer"]]
                > {"ignorieren": 0, "scannen": 1, "lesenswert": 2, "pflichtlektuere": 3}[f["agent"]]
                else "he was STRICTER"
            )
            lines.append("")
            lines.append(f"  {_kuerzen(f['titel'], MAX_TITEL)}")
            lines.append(
                f"    said {VERDICT_KLARTEXT.get(f['agent'], f['agent'])}:"
                f" «{_kuerzen(f['begruendung'], MAX_BEGRUENDUNG)}»"
            )
            lines.append(
                f"    he judged {VERDICT_KLARTEXT.get(f['nutzer'], f['nutzer'])}"
                f" — {richtung}." + (f" His note: «{_kuerzen(f['memo'], 100)}»" if f["memo"] else "")
            )

    lines.append("")
    return "\n".join(lines)
