"""H7-Fallgestalt-Runner über AUSGEWÄHLTE eigene Publikationen (SARAH-Port).

Verallgemeinert `scripts/h7_fallgestalt_verify.py` (fest auf das Verifikations-
Dokument JK26 verdrahtet) auf eine frei wählbare Auswahl: listet die
volltext-vorhandenen Publikationen aus `own_refs.db` und lässt die per Selektor
genannten durch den co-präsenten Werk-Positionierungs-Pass
(`journal_bot.fallgestalt.run_document_profile_h7`) laufen. Pro Dokument wird
die Fallgestalt-JSON (V/E/meta) geschrieben und eine kompakte Zusammenfassung
ausgegeben.

Aufrufe:
    python scripts/h7_run.py --list
        Alle volltext-vorhandenen Publikationen tabellarisch (KEIN LLM-Call).

    python scripts/h7_run.py "cultural resilience"
        Analysiert die eine Publikation, deren Titel den Teilstring enthält.

    python scripts/h7_run.py hash:6839b2118380813f "prompt interception"
        Mehrere Selektoren: exakte canonical_id ODER Titel-Teilstring, gemischt.

    python scripts/h7_run.py --years 2024
        Alle 2024er-Publikationen mit Volltext (Batch — fragt vorher nach Kosten).

    python scripts/h7_run.py --years 2019,2022,2024-2026
        Jahres-Spec kombinierbar: Einzeljahre + Bereiche, komma-getrennt.

    python scripts/h7_run.py --years 2023-2026 "resilience"
        Jahres-Auswahl UND Einzelwerk kombiniert (Vereinigung, dedupliziert).

    python scripts/h7_run.py --route mimo --out output/fallgestalt "resilience"
        Route und Ausgabeverzeichnis explizit.

Auswahl-Achsen: primär `--years` (Profile verschieben sich über die Jahre),
alternativ/zusätzlich positionale Einzelwerk-Selektoren. Jahres-Spec akzeptiert
Einzeljahr (`2024`), Bereich (`2020-2026`, beide Enden inklusive) und Mix
(`2019,2022,2024-2026`); Werke ohne `year` fallen NICHT in eine Jahres-Auswahl.

Selektor-Regel: jedes positionale Argument ist ENTWEDER eine exakte
`canonical_id` ODER ein Titel-Teilstring (case-insensitive). Ein mehrdeutiger
Teilstring (>1 Treffer) wird NICHT geraten, sondern mit den Kandidaten gemeldet
und übersprungen — die übrigen Selektoren laufen weiter. `--years` und
positionale Selektoren sind kombinierbar (Vereinigung, dedupliziert nach
canonical_id).

Kosten-Schranke: sobald die aufgelöste Auswahl mehr als 1 Werk umfasst, wird VOR
dem ersten LLM-Call die Liste (Jahr · Titel) + Anzahl + geschätzte Gesamtkosten
gezeigt und interaktiv „ja" abgefragt (--yes überspringt die Rückfrage). Ein
einzelnes Werk läuft ohne Rückfrage.

Kosten: `run_document_profile_h7` loggt NICHT in articles.db/llm_log und gibt
kein Provider-Kosten-Feld zurück — nur Tokens. Die ausgewiesenen $-Werte sind
daher eine Schätzung aus der Preistabelle (`ROUTES[route]` × Tokens, dieselbe
Formel wie `multi_provider.extract_stats` im Fallback). Cache-Rabatte sind darin
nicht erfasst → die Schätzung ist eine Obergrenze, echte Kosten ggf. niedriger.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from itertools import groupby
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from journal_bot.fallgestalt import assemble_fallgestalt, run_document_profile_h7
from journal_bot.multi_provider import ROUTES

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = PROJECT_ROOT / "own_refs.db"
DEFAULT_OUT = PROJECT_ROOT / "output" / "fallgestalt"

# Haltungs-Kanten (interne edgeKind, wie run_document_profile_h7 sie zurückgibt —
# die MoJo-2-wertige Abbildung passiert erst in assemble_fallgestalt).
STANCE = {"affirms", "extends", "contrasts", "reserves", "rejects"}


# ── Datenzugriff ───────────────────────────────────────────────────────────


def load_publications(db_path: Path) -> list[dict]:
    """Alle Publikationen mit nicht-leerem fulltext_path, neueste zuerst.

    Wirft SystemExit mit handlungsanweisender Meldung, wenn die DB fehlt, die
    Tabelle nicht existiert oder keine analysierbare Zeile vorhanden ist.
    """
    if not db_path.exists():
        raise SystemExit(
            f"own_refs.db nicht gefunden ({db_path}).\n"
            "  → Erst die Eigenwerk-Refs-Pipeline bauen (scripts/bezugsautoren_build.py "
            "bzw. journal_bot/own_refs.py), die own_refs.db erzeugt."
        )
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT canonical_id, title, year, venue, authors_json, "
            "fulltext_path, fulltext_chars "
            "FROM publications "
            "WHERE fulltext_path IS NOT NULL AND TRIM(fulltext_path) != '' "
            "ORDER BY (year IS NULL), year DESC, title ASC"
        ).fetchall()
    except sqlite3.OperationalError as exc:
        raise SystemExit(
            f"Tabelle 'publications' in {db_path} nicht lesbar: {exc}\n"
            "  → own_refs.db scheint unvollständig; Eigenwerk-Pipeline erneut laufen lassen."
        )
    finally:
        conn.close()
    if not rows:
        raise SystemExit(
            "Keine Publikation mit hinterlegtem Volltext in own_refs.db.\n"
            "  → Volltext-Extraktion (fulltext_path) fehlt für alle Einträge; "
            "erst die Volltext-Pipeline über die Zotero-PDFs laufen lassen."
        )
    return [dict(r) for r in rows]


def parse_authors(raw: str | None) -> list:
    """authors_json robust in eine Liste überführen (fehlt/kaputt → [])."""
    if not raw:
        return []
    try:
        val = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    return val if isinstance(val, list) else []


def pub_year(pub: dict) -> int | None:
    """Jahr robust als int (fehlt/nicht-numerisch → None)."""
    y = pub.get("year")
    if y is None:
        return None
    try:
        return int(y)
    except (ValueError, TypeError):
        return None


# ── Auswahl-Auflösung ──────────────────────────────────────────────────────


def resolve_selectors(selectors: list[str], pubs: list[dict]) -> tuple[list[dict], list[str]]:
    """Selektoren → (ausgewählte Publikationen, Fehlermeldungen).

    Pro Selektor: erst exakte canonical_id, sonst Titel-Teilstring
    (case-insensitive). Mehrdeutiger Teilstring → nicht raten, Kandidaten
    melden, überspringen. Kein Treffer → deutliche Meldung. Duplikate über
    mehrere Selektoren werden zusammengefasst (Reihenfolge bleibt erhalten).
    """
    selected: list[dict] = []
    errors: list[str] = []
    seen: set[str] = set()

    def take(pub: dict) -> None:
        if pub["canonical_id"] not in seen:
            seen.add(pub["canonical_id"])
            selected.append(pub)

    for sel in selectors:
        exact = [p for p in pubs if p["canonical_id"] == sel]
        if len(exact) == 1:
            take(exact[0])
            continue

        needle = sel.lower()
        hits = [p for p in pubs if needle in (p["title"] or "").lower()]
        if len(hits) == 1:
            take(hits[0])
        elif len(hits) == 0:
            errors.append(f"  ✗ Kein Treffer für Selektor {sel!r} (weder canonical_id noch Titel-Teilstring).")
        else:
            lines = "\n".join(
                f"      - {p['canonical_id']}  {trunc(p['title'], 60)}" for p in hits
            )
            errors.append(
                f"  ✗ Selektor {sel!r} ist mehrdeutig ({len(hits)} Treffer) — übersprungen. "
                f"Bitte präzisieren (canonical_id oder eindeutiger Teilstring):\n{lines}"
            )
    return selected, errors


def parse_years_spec(spec: str) -> set[int]:
    """Jahres-Spec → Menge von Jahren.

    Akzeptiert komma-getrennt kombinierbar: Einzeljahr (`2024`), Bereich
    (`2020-2026`, beide Enden inklusive), Mix (`2019,2022,2024-2026`). Wirft
    ValueError mit deutscher Meldung bei Unsinn (nicht-parsbar, Start > Ende).
    """
    years: set[int] = set()
    for raw in spec.split(","):
        token = raw.strip()
        if not token:
            continue
        if "-" in token:
            parts = token.split("-")
            if len(parts) != 2 or not parts[0].strip().isdigit() or not parts[1].strip().isdigit():
                raise ValueError(
                    f"Ungültiger Bereich {token!r} — erwartet JAHR-JAHR, z.B. 2020-2026."
                )
            lo, hi = int(parts[0].strip()), int(parts[1].strip())
            if lo > hi:
                raise ValueError(
                    f"Bereich {token!r}: Startjahr {lo} liegt nach Endjahr {hi}."
                )
            years.update(range(lo, hi + 1))
        elif token.isdigit():
            years.add(int(token))
        else:
            raise ValueError(
                f"Ungültige Jahresangabe {token!r} — erwartet Jahreszahl (2024) "
                "oder Bereich (2020-2026)."
            )
    if not years:
        raise ValueError("Leere Jahresangabe.")
    return years


def select_by_years(years: set[int], pubs: list[dict]) -> list[dict]:
    """Alle volltext-vorhandenen Publikationen, deren Jahr in `years` liegt.
    Werke ohne Jahr (NULL) fallen NICHT in eine Jahres-Auswahl."""
    return [p for p in pubs if (y := pub_year(p)) is not None and y in years]


# ── Ausgabe-Helfer ─────────────────────────────────────────────────────────


def trunc(s: str | None, n: int) -> str:
    s = (s or "").replace("\n", " ").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def sanitize_id(canonical_id: str) -> str:
    """canonical_id filesystem-sicher machen (hash:6839… → hash_6839…)."""
    return "".join(c if (c.isalnum() or c in "._-") else "_" for c in canonical_id)


def print_listing(pubs: list[dict]) -> None:
    """Volltext-Publikationen nach Jahr gruppiert (absteigend, neueste zuerst),
    mit Jahres-Spanne im Kopf. Rein lesend — kein LLM-Call, keine Kosten."""
    years_present = sorted({y for p in pubs if (y := pub_year(p)) is not None})
    n_with_year = sum(1 for p in pubs if pub_year(p) is not None)
    if years_present:
        head = f"Jahre: {years_present[0]}–{years_present[-1]}, {n_with_year} mit Volltext"
    else:
        head = "kein Werk mit Jahresangabe"
    print(f"\n{len(pubs)} Publikationen mit Volltext in own_refs.db · {head}\n")

    # pubs sind vorsortiert (year DESC, title ASC, NULL zuletzt) → groupby je Jahr.
    counter = 0
    for year, group in groupby(pubs, key=pub_year):
        members = list(group)
        label = str(year) if year is not None else "ohne Jahr"
        print(f"  {label}  ({len(members)})")
        for p in members:
            counter += 1
            print(f"     {counter:>3}  {trunc(p['title'], 66):<66}  {p['canonical_id']}")
    print()


def estimate_cost(route_key: str, tokens_in: int, tokens_out: int) -> float:
    """Preistabellen-Schätzung (dieselbe Formel wie multi_provider.extract_stats
    im Fallback). KEIN Provider-Ist-Wert — Cache-Rabatte nicht erfasst."""
    route = ROUTES[route_key]
    return (
        tokens_in / 1_000_000 * route.input_usd_per_mtok
        + tokens_out / 1_000_000 * route.output_usd_per_mtok
    )


# Kalibriert an EINER ungedeckelten Messung (2026-07-18, „Prompt Interception",
# 52 258 Zeichen Volltext, Route mimo): 40 293 Eingabe- und 45 413 Ausgabe-Tokens.
# Die vorherigen Werte (chars/4 bzw. pauschal 2500 Ausgabe-Tokens) unterschätzten
# um Faktor 2,8 bzw. 18 und ließen einen $16-Batch wie $2.25 aussehen. Der
# Ausgabe-Anteil ist beim Reasoning-Modell weitgehend längenunabhängig (Denken
# dominiert), deshalb als Pauschale je Dokument geführt.
_TOKENS_IN_PER_CHAR = 0.77
_TOKENS_OUT_PER_DOC = 45_000


def estimate_selection_cost(selected: list[dict], route) -> float:
    """Vorab-Kostenschätzung für eine Auswahl aus der Preistabelle.

    Basis ist EINE gemessene Route (mimo); nicht-reasoning-Routen liegen im
    Ausgabe-Anteil deutlich darunter. KEIN Provider-Ist-Wert, Cache-Rabatte
    nicht erfasst, Retries bei Degenerat/Beleg-Fail erhöhen die realen Calls
    → als Schätzung (≈) zu lesen."""
    total_chars = sum(int(p.get("fulltext_chars") or 0) for p in selected)
    est_in = total_chars * _TOKENS_IN_PER_CHAR
    est_out = _TOKENS_OUT_PER_DOC * len(selected)
    return (
        est_in / 1_000_000 * route.input_usd_per_mtok
        + est_out / 1_000_000 * route.output_usd_per_mtok
    )


def confirm_batch(selected: list[dict], route) -> bool:
    """Kosten-Schranke für Mehrfachauswahl (>1 Werk): aufgelöste Liste
    (Jahr · gekürzter Titel), Anzahl, Call-Zahl und geschätzte Gesamtkosten
    zeigen, dann interaktiv „ja" abfragen. True = fortfahren, sonst Abbruch."""
    est_cost = estimate_selection_cost(selected, route)
    print(
        f"\nAufgelöste Auswahl: {len(selected)} Werke → {len(selected)} LLM-Calls "
        f"(je bis zu 4 Versuche bei Degenerat/Beleg-Fail).\n"
        f"  Route: {route.label} (${route.input_usd_per_mtok}/${route.output_usd_per_mtok} pro Mtok)"
    )
    for p in selected:
        y = pub_year(p)
        year = str(y) if y is not None else "—"
        print(f"    {year:>4}  {trunc(p['title'], 66)}")
    print(
        f"  Geschätzte Gesamtkosten (Schätzung aus Preistabelle, Untergrenze): ≈${est_cost:.2f}\n"
    )
    answer = input("  Fortfahren? 'ja' eingeben: ").strip().lower()
    if answer != "ja":
        print("Abgebrochen — kein LLM-Call.")
        return False
    return True


# ── Analyse eines Dokuments ────────────────────────────────────────────────


def analyze_one(pub: dict, route_key: str, out_dir: Path) -> dict | None:
    """Einen H7-Pass ausführen, Fallgestalt-JSON schreiben, Zusammenfassung
    drucken. Rückgabe: {tokens_in, tokens_out, cost} für die Laufsumme, oder
    None bei übersprungenem Dokument (fehlender Volltext)."""
    ft_path = Path(pub["fulltext_path"])
    if not ft_path.exists():
        print(f"  ✗ Volltext-Datei fehlt für {pub['canonical_id']}: {ft_path} — übersprungen.")
        return None
    try:
        fulltext = ft_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"  ✗ Volltext für {pub['canonical_id']} nicht lesbar ({exc}) — übersprungen.")
        return None

    authors = parse_authors(pub["authors_json"])

    t0 = time.time()
    read = run_document_profile_h7(fulltext, route_key=route_key)
    secs = time.time() - t0

    meta = {
        "document_id": pub["canonical_id"],
        "title": pub["title"],
        "authors": authors,
        "year": str(pub["year"]) if pub["year"] else None,
        "venue": pub["venue"],
        "disc": None,
    }
    fg = assemble_fallgestalt(meta, read["nodes"], read["edges"])

    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{sanitize_id(pub['canonical_id'])}.json"
    out_file.write_text(json.dumps(fg, ensure_ascii=False, indent=2), encoding="utf-8")

    # Kennzahlen aus den geparsten Knoten/Kanten
    src = [n for n in read["nodes"] if n["nodeType"] == "source" and not n["properties"].get("ownWork")]
    own = [n for n in read["nodes"] if n["nodeType"] == "source" and n["properties"].get("ownWork")]
    terms = [n for n in read["nodes"] if n["nodeType"] == "term"]
    stance_edges = [e for e in read["edges"] if e["edgeKind"] in STANCE]
    sig_plus = sum(1 for e in stance_edges if e["sigma"] == "+")
    sig_minus = sum(1 for e in stance_edges if e["sigma"] == "-")

    tin = read["tokens"]["input"]
    tout = read["tokens"]["output"]
    cost = estimate_cost(route_key, tin, tout)

    print(
        f"  ✓ {trunc(pub['title'], 52)}\n"
        f"      {len(read['nodes'])} Knoten/{len(read['edges'])} Kanten · "
        f"{len(src)} externe Quellen/{len(terms)} Begriffe/{len(own)} eigene · "
        f"Haltung σ +{sig_plus}/−{sig_minus} · "
        f"{tin}→{tout} tok · ≈${cost:.4f} · {secs:.1f}s · "
        f"unparsed={len(read['unparsed'])}"
    )
    if read["unparsed"]:
        print(f"      unparsed-Zeilen: {read['unparsed']}")
    if read.get("belegFailures"):
        print(f"      Beleg-Fails (nicht verbatim im Text): {len(read['belegFailures'])}")
    print(f"      → {out_file}")

    return {"tokens_in": tin, "tokens_out": tout, "cost": cost}


# ── CLI ────────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="H7-Fallgestalt-Analyse über ausgewählte eigene Publikationen (own_refs.db).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Auswahl-Achsen: --years (Jahr/Zeitraum) und/oder positionale Selektoren\n"
            "(canonical_id ODER Titel-Teilstring, case-insensitive) — kombinierbar.\n"
            "Ohne Auswahl oder mit --list wird nur die Liste gezeigt (kein LLM-Call).\n"
            "Ab 2 Werken: Liste + geschätzte Kosten + „ja\"-Rückfrage (--yes überspringt)."
        ),
    )
    parser.add_argument(
        "selectors",
        nargs="*",
        help="Zu analysierende Einzelwerke: exakte canonical_id oder Titel-Teilstring.",
    )
    parser.add_argument(
        "--years",
        default=None,
        metavar="SPEC",
        help="Jahres-Auswahl: Einzeljahr (2024), Bereich (2020-2026, inkl.) oder "
        "Mix (2019,2022,2024-2026). Mit positionalen Selektoren kombinierbar.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Alle volltext-vorhandenen Publikationen nach Jahr gruppiert listen (kein LLM-Call).",
    )
    parser.add_argument(
        "--route",
        default="mimo",
        help=f"Modell-Route (Default: mimo). Gültig: {', '.join(sorted(ROUTES))}.",
    )
    parser.add_argument(
        "--out",
        default=None,
        help=f"Ausgabeverzeichnis für die Fallgestalt-JSONs (Default: {DEFAULT_OUT}).",
    )
    parser.add_argument(
        "--all-fulltext",
        action="store_true",
        help="ALLE volltext-vorhandenen Publikationen analysieren (Batch — fragt vorher nach Bestätigung).",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Kosten-Rückfrage bei Mehrfachauswahl überspringen (für Skripting).",
    )
    args = parser.parse_args()

    pubs = load_publications(DB_PATH)

    if args.route not in ROUTES:
        print(f"Unbekannte Route {args.route!r}. Gültige Keys: {', '.join(sorted(ROUTES))}")
        sys.exit(2)

    # Reine Auflistung (auch der Default ohne jegliche Selektion)
    if args.list or (not args.selectors and not args.all_fulltext and not args.years):
        print_listing(pubs)
        if not args.list:
            print(
                "Nutzung — Auswahl-Achsen:\n"
                "  • Jahr/Zeitraum:  python scripts/h7_run.py --years 2024\n"
                "                    python scripts/h7_run.py --years 2019,2022,2024-2026\n"
                '  • Einzelwerk:     python scripts/h7_run.py "cultural resilience"\n'
                "                    python scripts/h7_run.py hash:6839b2118380813f\n"
                '  • kombiniert:     python scripts/h7_run.py --years 2023-2026 "resilience"\n'
                "Optionen: --route <key>, --out <dir>, --all-fulltext (Batch), --yes (ohne Rückfrage).\n"
            )
        return

    out_dir = Path(args.out) if args.out else DEFAULT_OUT
    if not out_dir.is_absolute():
        out_dir = PROJECT_ROOT / out_dir

    route = ROUTES[args.route]

    # Auswahl bestimmen (Vereinigung von Jahres- und Einzelwerk-Achse,
    # dedupliziert nach canonical_id; Reihenfolge bleibt erhalten).
    if args.all_fulltext:
        selected = list(pubs)
    else:
        selected = []
        seen: set[str] = set()

        if args.years:
            try:
                years = parse_years_spec(args.years)
            except ValueError as exc:
                print(f"Ungültige --years-Angabe {args.years!r}: {exc}")
                sys.exit(2)
            for p in select_by_years(years, pubs):
                if p["canonical_id"] not in seen:
                    seen.add(p["canonical_id"])
                    selected.append(p)

        if args.selectors:
            pos_selected, errors = resolve_selectors(args.selectors, pubs)
            for e in errors:
                print(e)
            for p in pos_selected:
                if p["canonical_id"] not in seen:
                    seen.add(p["canonical_id"])
                    selected.append(p)

        if not selected:
            what = []
            if args.years:
                what.append(f"Jahre {args.years!r}")
            if args.selectors:
                what.append("Selektoren " + ", ".join(repr(s) for s in args.selectors))
            joined = " und ".join(what) if what else "die Auswahl"
            print(
                f"Kein volltext-vorhandenes Werk für {joined} gefunden — nichts zu tun.\n"
                "  → python scripts/h7_run.py --list zeigt die vorhandenen Jahre/Werke."
            )
            return

    # Kosten-Schranke (Projektkardinal): ab 2 Werken die aufgelöste Liste +
    # geschätzte Gesamtkosten zeigen und „ja" abfragen (--yes überspringt).
    if len(selected) > 1 and not args.yes:
        if not confirm_batch(selected, route):
            return

    print(
        f"\nH7-Fallgestalt · Route {route.label} · {len(selected)} Dokument(e) · Ausgabe: {out_dir}\n"
        "Kosten = Schätzung aus Preistabelle (Route × Tokens); run_document_profile_h7 gibt\n"
        "keine Provider-Kosten zurück, Cache-Rabatte sind nicht erfasst → Obergrenze.\n"
    )

    total_in = total_out = 0
    total_cost = 0.0
    n_ok = 0
    for pub in selected:
        res = analyze_one(pub, args.route, out_dir)
        if res:
            total_in += res["tokens_in"]
            total_out += res["tokens_out"]
            total_cost += res["cost"]
            n_ok += 1

    n_skipped = len(selected) - n_ok
    if len(selected) > 1:
        print(
            f"\n{n_ok} Werke verarbeitet · geschätzte Gesamtkosten ≈ ${total_cost:.4f} "
            f"· {n_skipped} Werke übersprungen  ({total_in}→{total_out} tok)"
        )
    else:
        print(
            f"\nΣ {n_ok}/{len(selected)} Dokument analysiert · {total_in}→{total_out} tok · "
            f"geschätzte Kosten (Preistabelle, Obergrenze): ≈${total_cost:.4f}"
        )


if __name__ == "__main__":
    main()
