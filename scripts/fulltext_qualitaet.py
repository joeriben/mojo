#!/usr/bin/env python3
"""Rückmeldung zur Volltext-Qualität der eigenen Publikationen.

Motiv (Benjamin 2026-07-18): Für die Werkanalyse (H7-Fallgestalt) zählt der
Wortlaut, nicht Seitenzahl oder Schlussredaktion. PDF-Extraktion beschädigt ihn
auf zwei Weisen, die kein Schalter behebt:

  Spaltenverschränkung — `pdftotext -layout` erhält das physische Layout und
  legt bei zweispaltigem Satz die Spalten zeilenweise ineinander. Der Text
  enthält dann keinen einzigen zusammenhängenden Satz. (`-layout` steht dort
  mit Absicht: der Literaturlisten-Parser braucht die Einrückung.)

  OCR-Schäden — gescannte PDFs liefern Zeichensalat („spezit." statt
  „spezifische", „undWek" statt „und Welt", „SCHONINGH" statt „Schöningh").

Statt einen besseren Extraktor zu bauen, meldet dieses Skript zurück, wo ein
offenes Original gebraucht wird — und ob eines auffindbar ist. Die eigenen
Texte liegen meist als .docx/.odt vor; `own_refs.extract` liest sie inzwischen
direkt (OPEN_DOC_SUFFIXES).

Aufruf:
    python3 scripts/fulltext_qualitaet.py [--suchpfad PFAD ...] [--alle]
"""

from __future__ import annotations

import argparse
import os
import re
import sqlite3
import sys
import unicodedata
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from journal_bot.own_refs.extract import OPEN_DOC_SUFFIXES, OPEN_TEXT_SUFFIXES  # noqa: E402

DEFAULT_SUCHPFADE = [
    Path("/Users/joerissen/FAUbox/Zotero/storage"),
]
OFFENE_SUFFIXE = OPEN_DOC_SUFFIXES | OPEN_TEXT_SUFFIXES

# Ab hier gilt ein Volltext als für die Werkanalyse unbrauchbar. Kalibriert an
# den 73 Volltexten (2026-07-18): Median Spaltenrinne 2,9 %, aber 12 Werke
# ≥30 % — und bei „Post Internet Art Education" (78 %) scheiterten 29 von 29
# Belegen, weil kein zusammenhängender Satz existiert.
SCHWELLE_SPALTEN = 0.30
SCHWELLE_TRENN = 4.0    # Trennstriche am Zeilenende je 1000 Zeichen
SCHWELLE_KLEBER = 2.0   # fehlende Wortzwischenräume je 1000 Zeichen


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def messen(text: str) -> dict:
    """Drei Schadensmaße, alle rein strukturell (kein LLM, keine Wörterbücher)."""
    zeilen = [z for z in text.split("\n") if len(z.strip()) > 40]
    k = max(len(text) / 1000, 1e-9)
    return {
        "spalten": sum(1 for z in zeilen if re.search(r"\S {4,}\S", z)) / max(len(zeilen), 1),
        "trenn": len(re.findall(r"-\s*\n", text)) / k,
        "kleber": len(re.findall(r"[a-zäöüß][A-ZÄÖÜ]", text)) / k,
    }


def befund(m: dict) -> list[str]:
    aus = []
    if m["spalten"] >= SCHWELLE_SPALTEN:
        aus.append(f"Spalten verschränkt ({m['spalten']*100:.0f}% der Zeilen)")
    if m["trenn"] >= SCHWELLE_TRENN:
        aus.append(f"stark getrennt ({m['trenn']:.1f}/1000)")
    if m["kleber"] >= SCHWELLE_KLEBER:
        aus.append(f"Wortzwischenräume fehlen ({m['kleber']:.1f}/1000) — Scan/OCR")
    return aus


def offene_originale(pfade: list[Path]) -> list[tuple[str, Path]]:
    """Alle offenen Dokumente unter den Suchpfaden, mit gefaltetem Dateinamen."""
    treffer = []
    for wurzel in pfade:
        if not wurzel.exists():
            continue
        for p in wurzel.rglob("*"):
            if p.suffix.lower() in OFFENE_SUFFIXE and p.is_file():
                treffer.append((_fold(p.stem), p))
    return treffer


def passt(titel: str, dateiname: str) -> bool:
    """Grobe Titelübereinstimmung.

    Zwei gemeinsame Wörter ab 5 Zeichen genügen, wenn eines davon lang (≥8) ist
    — Dateinamen tragen oft nur den Kurztitel („Jörissen - Beobachtungen der
    Realität 070625.odt" gegen „Beobachtungen der Realität: Die Frage nach der
    Wirklichkeit im Zeitalter …"). Mit einer Drei-Wort-Schwelle fiel genau
    dieser Fall durch. Lieber ein Kandidat zu viel: die Ausgabe ist ein
    Vorschlag zum Nachsehen, keine automatische Ersetzung.
    """
    t = {w for w in _fold(titel).split() if len(w) >= 5}
    d = {w for w in dateiname.split() if len(w) >= 5}
    gemeinsam = t & d
    if len(gemeinsam) >= 3:
        return True
    return len(gemeinsam) == 2 and any(len(w) >= 8 for w in gemeinsam)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--suchpfad", action="append", type=Path, default=None,
                    help="Wo nach offenen Originalen gesucht wird (mehrfach möglich).")
    ap.add_argument("--alle", action="store_true", help="Auch unbeschädigte Werke listen.")
    args = ap.parse_args()
    pfade = args.suchpfad or DEFAULT_SUCHPFADE

    con = sqlite3.connect(PROJECT_ROOT / "own_refs.db")
    zeilen = con.execute(
        "SELECT canonical_id, title, year, fulltext_path FROM publications "
        "WHERE fulltext_path IS NOT NULL AND fulltext_path != ''"
    ).fetchall()

    print(f"Suche offene Originale in: {', '.join(str(p) for p in pfade)}")
    originale = offene_originale(pfade)
    print(f"{len(originale)} offene Dokumente gefunden.\n")

    beschaedigt, geprueft = [], 0
    for cid, titel, jahr, pfad in zeilen:
        if not pfad or not os.path.exists(pfad):
            continue
        text = Path(pfad).read_text(encoding="utf-8", errors="replace")
        if len(text) < 2000:
            continue
        geprueft += 1
        maengel = befund(messen(text))
        if maengel or args.alle:
            kandidaten = [p for name, p in originale if passt(titel, name)]
            beschaedigt.append((titel, jahr, maengel, kandidaten))

    beschaedigt.sort(key=lambda r: (not r[2], -(len(r[3]) > 0), str(r[1])))
    mit, ohne = 0, 0
    for titel, jahr, maengel, kandidaten in beschaedigt:
        if not maengel:
            continue
        print(f"{jahr}  {titel[:72]}")
        for m in maengel:
            print(f"        ✗ {m}")
        if kandidaten:
            mit += 1
            for k in kandidaten[:2]:
                print(f"        → offenes Original vorhanden: {k}")
        else:
            ohne += 1
            print("        → kein offenes Original gefunden — Manuskript bitte bereitstellen")
        print()

    n = mit + ohne
    print(f"{geprueft} Volltexte geprüft · {n} beschädigt "
          f"({mit} mit auffindbarem Original, {ohne} ohne).")
    if ohne:
        print("\nFür die ohne Original: .docx/.odt/.txt in einen Ordner legen und als Quelle")
        print("eintragen (`mojo refs sources add folder <PFAD>`) — offene Formate gewinnen")
        print("dort gegen das PDF. Auf Seitenzahlen und Schlussredaktion kommt es nicht an.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
