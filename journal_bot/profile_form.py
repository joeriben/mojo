"""Profilform — Aggregation mehrerer Werk-Fallgestalten zu einem Profil.

Nimmt N per-Dokument-Fallgestalten (`journal_bot.fallgestalt`, V/E/meta) über
EIGENE Werke und verdichtet sie zur Profilform: nicht zu einer Häufigkeits-
rangliste („Autor X kommt 12× vor"), sondern zu einem Abhängigkeitsnetz, das
eine Form ergibt — welche Quellen treten MITEINANDER auf (`cooccurrence`), mit
welcher Haltung (`sources[].stance`), und wie verschiebt sich das über die Jahre
(`sources[].shift`, `periods`). Das Profil ist periodisiert, nicht zeitlos.

`sources` ist dabei das Inventar, das Haltung und Verschiebung trägt — der
relationale Kern ist `cooccurrence` (zwei Quellen im selben Werk) plus die
Zeit-Achse. Die Sortierung nach `n_works` ist Lesereihenfolge, keine Aussage.

LESART DER KENNZAHLEN (Grenzen, damit nichts als gerechnete Gültigkeit
missverstanden wird, was Lektüre-Artefakt ist):

* Alle Knoten/Kanten stammen aus EINEM LLM-Lektüre-Pass pro Werk. Die
  Profilform rechnet über diese Lektüre — sie prüft sie nicht nach. Eine
  Quelle, die der Pass in Werk B übersehen hat, fehlt hier als Ko-Okkurrenz.
* Quell-Labels sind LLM-erzeugt und variieren („Brown (2015), *Resilience…*"
  vs. „Brown 2015"). Zum Zusammenführen über Werke hinweg wird ein `key`
  gebildet (siehe `source_key`). Das ist eine unscharfe Zusammenführung:
  jeder Eintrag führt in `label_variants` ALLE Roh-Labels mit, die auf ihn
  normalisiert wurden, und `reliability.fuzzy_matched_keys` zählt, bei wie
  vielen keys überhaupt mehr als ein Roh-Label zusammengeführt wurde. Keine
  stille Vereinheitlichung — Fehlzusammenführungen müssen sichtbar bleiben.
  Real beobachtet: zwei verschiedene eigene Arbeiten desselben Jahres
  („Jörissen 2023" / „Jörissen, Unterberg & Klepacki 2023") fallen auf
  denselben key. `label_variants` zeigt genau das.
* `beleg_failures` zählt Knoten/Kanten, deren `props.belegVerified is False` —
  die Markierung, die `fallgestalt.verify_belege()` beim gescheiterten
  Verbatim-Gate setzt. ACHTUNG: `fallgestalt.assemble_fallgestalt()` überträgt
  `properties` NUR für Knoten (V) in die exportierte JSON; Kanten (E) werden
  ohne `props` geschrieben. Aus der Fallgestalt-JSON sind daher faktisch nur
  die KNOTEN-Fails zählbar; die Kanten-Fails des Gates sind im Export nicht
  mehr enthalten. Der Zähler liest Kanten trotzdem mit (falls das Export-
  Format später `props` mitführt), aber der Wert ist heute eine Untergrenze.

Reine Funktionen: keine DB, kein Netz, keine LLM-Calls.
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter, defaultdict
from collections.abc import Iterable
from itertools import combinations
from pathlib import Path
from typing import Any

# Haltungs-Vokabular in fester Reihenfolge (= `fallgestalt.RELATION_KINDS`,
# hier geordnet, weil die Reihenfolge Gleichstände deterministisch bricht).
STANCE_KINDS: tuple[str, ...] = ("affirms", "extends", "contrasts", "reserves", "rejects")
_STANCE_RANK = {k: i for i, k in enumerate(STANCE_KINDS)}

POSITION_ID = "position:self"


class Fallgestalten(list):
    """Geladene Fallgestalten + Sammel-Warnliste der übersprungenen Dateien.

    Ist eine echte `list[dict]` (Aufrufer müssen nichts wissen); `skipped`
    trägt die Warnungen, die `build_profile_form` nach
    `reliability.skipped_files` durchreicht.
    """

    def __init__(self, items: Iterable[dict] = (), skipped: list[str] | None = None):
        super().__init__(items)
        self.skipped: list[str] = list(skipped or [])


# ── Label-Normalisierung ──────────────────────────────────────────────────

_PREFIX_RE = re.compile(r"^\s*(?:source|term|own)\s*:\s*", re.IGNORECASE)
_MARKDOWN_RE = re.compile(r"[*_`]+")
_YEAR_RE = re.compile(r"(?<!\d)(1[6-9]\d{2}|20\d{2})(?!\d)")
# Namenstoken: Buchstaben (unicode), intern Bindestrich/Apostroph erlaubt.
_NAME_RE = re.compile(r"[^\W\d_]+(?:[-'’][^\W\d_]+)*", re.UNICODE)
_NONWORD_RE = re.compile(r"[^\w]+", re.UNICODE)

# Namenszusätze, die einem Nachnamen vorangehen — ohne sie stünde „de" oder
# „van" als key da. Kleines, bewusst kurzes Set (kein Namens-Parser).
_PARTICLES = {
    "van", "von", "de", "del", "della", "di", "da", "das", "dos", "du",
    "le", "la", "ten", "ter", "den", "der", "el", "al",
}


def _fold(s: str) -> str:
    """Diakritika-freie Kleinschreibung für den key-Vergleich.

    „Rancière"/„Ranciere" und „Jörissen"/„Jorissen" sollen denselben key
    ergeben — genau die Varianz, die LLM-Labels über Werke hinweg zeigen.
    ß→ss, weil beide Schreibungen vorkommen.
    """
    s = unicodedata.normalize("NFKD", s).replace("ß", "ss")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return s.lower().strip()


def _clean_label(label: str) -> str:
    """Roh-Label für die key-Bildung säubern: id-Präfix, Markdown, Whitespace."""
    s = _PREFIX_RE.sub("", label or "")
    s = _MARKDOWN_RE.sub("", s)
    return re.sub(r"\s+", " ", s).strip()


def _leading_surname(text: str) -> str | None:
    """Führenden Nachnamen aus einem Quell-Label ziehen (mit Namenszusatz)."""
    matches = list(_NAME_RE.finditer(text))
    if not matches:
        return None
    first = matches[0].group(0)
    if _fold(first) in _PARTICLES and len(matches) > 1:
        return f"{first} {matches[1].group(0)}"
    return first


def source_key(label: str) -> str:
    """Quell-Label → Zusammenführungs-key.

    `brown:2015` aus „Brown (2015), *Resilience, Development and Global
    Change*". Ohne erkennbare Jahreszahl: nur der normalisierte Nachname.
    Ohne beides: der komplette normalisierte Labeltext. Unscharf und als
    unscharf ausgewiesen (siehe Modul-Docstring / `label_variants`).
    """
    text = _clean_label(label)
    if not text:
        return "?"
    surname = _leading_surname(text)
    year_match = _YEAR_RE.search(text)
    year = year_match.group(1) if year_match else None
    if surname and year:
        return f"{_fold(surname).replace(' ', '-')}:{year}"
    if surname:
        return _fold(surname).replace(" ", "-")
    return _NONWORD_RE.sub(" ", _fold(text)).strip() or "?"


def term_key(label: str) -> str:
    """Begriffs-Label → key.

    In-vivo-Begriffe haben kein Autor-Jahr-Muster; der key ist der
    normalisierte Volltext des Labels. Bewusst konservativ: „Cultural
    Resilience (kulturelle Resilienz)" und „Cultural Resilience" werden NICHT
    zusammengeführt. Eine Untertrennung ist sichtbar (zwei Einträge), eine
    Fehlzusammenführung wäre es nicht.
    """
    text = _clean_label(label)
    return _NONWORD_RE.sub(" ", _fold(text)).strip() or "?"


# ── Laden ─────────────────────────────────────────────────────────────────


def _parse_year(value: Any) -> int | None:
    """meta.year (String oder None) → int. Unlesbares Jahr = kein Jahr."""
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        m = re.search(r"(1[6-9]\d{2}|20\d{2})", value)
        if m:
            return int(m.group(1))
    return None


def _looks_like_fallgestalt(data: Any) -> bool:
    return (
        isinstance(data, dict)
        and isinstance(data.get("V"), list)
        and isinstance(data.get("E"), list)
    )


def load_fallgestalten(source: str | Path | Iterable[str | Path]) -> list[dict]:
    """Fallgestalt-JSONs laden. Verzeichnis → alle `*.json` darin (sortiert),
    Einzelpfad(e) → genau diese.

    Defekte oder fremde JSON werden übersprungen, nicht geworfen: das Ergebnis
    ist eine `Fallgestalten`-Liste, deren `skipped`-Feld je übersprungener
    Datei eine Klartext-Warnung trägt (`build_profile_form` reicht sie nach
    `reliability.skipped_files` durch). Ein kaputtes File darf einen Profil-
    Lauf über 30 Werke nicht abbrechen — aber es muss sichtbar bleiben.
    """
    if isinstance(source, (str, Path)):
        candidates: list[Path] = [Path(source)]
    else:
        candidates = [Path(p) for p in source]

    paths: list[Path] = []
    skipped: list[str] = []
    for cand in candidates:
        if cand.is_dir():
            paths.extend(sorted(cand.glob("*.json")))
        elif cand.exists():
            paths.append(cand)
        else:
            skipped.append(f"{cand} — Datei nicht gefunden")

    items: list[dict] = []
    for path in paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            skipped.append(f"{path} — nicht lesbar ({type(exc).__name__})")
            continue
        if not _looks_like_fallgestalt(data):
            skipped.append(f"{path} — keine Fallgestalt (V/E fehlen)")
            continue
        items.append(data)
    return Fallgestalten(items, skipped)


# ── Aggregation ───────────────────────────────────────────────────────────


def _dominant_stance(counts: Counter) -> str | None:
    """Häufigste Haltung; Gleichstand bricht nach `STANCE_KINDS`-Reihenfolge."""
    if not counts:
        return None
    return min(counts.items(), key=lambda kv: (-kv[1], _STANCE_RANK.get(kv[0], 99)))[0]


def _period_label(years: list[int]) -> str:
    lo, hi = min(years), max(years)
    return str(lo) if lo == hi else f"{lo}–{hi}"


def _count_beleg_failures(fg: dict) -> int:
    """Knoten/Kanten mit gescheitertem Verbatim-Beleg (`belegVerified is False`).

    Siehe Modul-Docstring: im heutigen Export tragen nur Knoten `props`, der
    Wert ist daher eine Untergrenze.
    """
    n = 0
    for item in list(fg.get("V") or []) + list(fg.get("E") or []):
        props = item.get("props") if isinstance(item, dict) else None
        if isinstance(props, dict) and props.get("belegVerified") is False:
            n += 1
    return n


def build_profile_form(fallgestalten: list[dict], *, period_size: int = 4) -> dict:
    """N Werk-Fallgestalten → eine Profilform (siehe Modul-Docstring).

    `period_size` = Jahre pro Periode; die Blöcke sind an der tatsächlichen
    Spanne ausgerichtet (Start = frühestes Jahr) und leere Blöcke entfallen.
    Perioden entstehen nur bei mindestens zwei verschiedenen Jahren; Werke
    ohne Jahr bleiben aus der Zeit-Achse heraus (sie erscheinen weiter in
    `substrate`, `sources` und `cooccurrence`).
    """
    works: list[dict] = []
    self_positions: list[dict] = []

    # key → aggregierter Eintrag
    src: dict[str, dict[str, Any]] = {}
    trm: dict[str, dict[str, Any]] = {}
    # key → Jahr → Counter(Haltung), für `shift` und `periods`
    stance_by_year: dict[str, dict[int, Counter]] = defaultdict(lambda: defaultdict(Counter))
    # document_id → Quell-/Begriffs-keys des Werks (für Ko-Okkurrenz + Perioden)
    keys_per_work: dict[str, set[str]] = {}
    terms_per_work: dict[str, set[str]] = {}
    year_per_work: dict[str, int | None] = {}

    # Werke nach Jahr absteigend verarbeiten: die Reihenfolge bestimmt, welches
    # Roh-Label als repräsentatives `label` gewinnt (die jüngste Formulierung
    # bei Gleichstand) und in welcher Reihenfolge `works`-Listen stehen.
    indexed = list(enumerate(fallgestalten))
    ordered = sorted(
        indexed,
        key=lambda iv: (
            _parse_year((iv[1].get("meta") or {}).get("year")) is None,
            -(_parse_year((iv[1].get("meta") or {}).get("year")) or 0),
            str((iv[1].get("meta") or {}).get("title") or ""),
        ),
    )

    for idx, fg in ordered:
        meta = fg.get("meta") or {}
        doc_id = str(meta.get("document_id") or f"(ohne Kennung #{idx})")
        year = _parse_year(meta.get("year"))
        nodes = [n for n in (fg.get("V") or []) if isinstance(n, dict)]
        edges = [e for e in (fg.get("E") or []) if isinstance(e, dict)]

        node_by_id = {str(n.get("id")): n for n in nodes}
        n_sources = sum(1 for n in nodes if n.get("type") == "source")
        n_terms = sum(1 for n in nodes if n.get("type") == "term")
        beleg_failures = _count_beleg_failures(fg)

        authors = meta.get("authors")
        works.append(
            {
                "document_id": doc_id,
                "title": meta.get("title"),
                "year": year,
                "venue": meta.get("venue"),
                "authors": [str(a) for a in authors] if isinstance(authors, list) else [],
                "n_sources": n_sources,
                "n_terms": n_terms,
                "beleg_failures": beleg_failures,
            }
        )
        year_per_work[doc_id] = year

        position = node_by_id.get(POSITION_ID) or next(
            (n for n in nodes if n.get("type") == "position"), None
        )
        if position is not None:
            self_positions.append(
                {
                    "document_id": doc_id,
                    "year": year,
                    "title": meta.get("title"),
                    "label": position.get("label"),
                }
            )

        # ── Knoten einsammeln ─────────────────────────────────────────
        work_source_keys: set[str] = set()
        work_term_keys: set[str] = set()
        key_by_node_id: dict[str, str] = {}

        for node in nodes:
            ntype = node.get("type")
            label = str(node.get("label") or "")
            props = node.get("props") if isinstance(node.get("props"), dict) else {}
            if ntype == "source":
                key = source_key(label)
                key_by_node_id[str(node.get("id"))] = key
                entry = src.setdefault(
                    key,
                    {
                        "key": key,
                        "labels": Counter(),
                        "works": [],
                        "years": set(),
                        "stance": dict.fromkeys(STANCE_KINDS, 0),
                        "sigma": {"+": 0, "-": 0},
                        "own_work": False,
                    },
                )
                entry["labels"][label] += 1
                if doc_id not in entry["works"]:
                    entry["works"].append(doc_id)
                if year is not None:
                    entry["years"].add(year)
                if props.get("ownWork"):
                    entry["own_work"] = True
                work_source_keys.add(key)
            elif ntype == "term":
                key = term_key(label)
                key_by_node_id[str(node.get("id"))] = key
                entry = trm.setdefault(
                    key,
                    {"key": key, "labels": Counter(), "works": [], "years": set()},
                )
                entry["labels"][label] += 1
                if doc_id not in entry["works"]:
                    entry["works"].append(doc_id)
                if year is not None:
                    entry["years"].add(year)
                work_term_keys.add(key)

        keys_per_work[doc_id] = work_source_keys
        terms_per_work[doc_id] = work_term_keys

        # ── Haltungen aus den Kanten ──────────────────────────────────
        for edge in edges:
            kind = edge.get("internalKind") or edge.get("kind")
            if kind not in _STANCE_RANK:
                continue
            key = key_by_node_id.get(str(edge.get("to")))
            if key is None or key not in src:
                continue
            src[key]["stance"][kind] += 1
            sigma = edge.get("sigma")
            if sigma in ("+", "-"):
                src[key]["sigma"][sigma] += 1
            if year is not None:
                stance_by_year[key][year][kind] += 1

    # ── Quellen ausformen (inkl. shift) ───────────────────────────────
    sources: list[dict] = []
    for key, entry in src.items():
        variants = list(entry["labels"].keys())
        shift = None
        per_year = stance_by_year.get(key) or {}
        dominants = [
            (y, _dominant_stance(c)) for y, c in sorted(per_year.items()) if _dominant_stance(c)
        ]
        if len(dominants) >= 2 and dominants[0][1] != dominants[-1][1]:
            shift = {
                "from": {"year": dominants[0][0], "stance": dominants[0][1]},
                "to": {"year": dominants[-1][0], "stance": dominants[-1][1]},
            }
        sources.append(
            {
                "key": key,
                "label": entry["labels"].most_common(1)[0][0],
                "n_works": len(entry["works"]),
                "works": entry["works"],
                "years": sorted(entry["years"]),
                "stance": entry["stance"],
                "sigma": entry["sigma"],
                "own_work": entry["own_work"],
                "shift": shift,
                "label_variants": variants,
            }
        )
    sources.sort(key=lambda s: (-s["n_works"], s["label"]))

    # ── Ko-Okkurrenz: DAS Abhängigkeitsnetz ───────────────────────────
    pair_works: dict[tuple[str, str], list[str]] = defaultdict(list)
    for doc_id, keys in keys_per_work.items():
        for a, b in combinations(sorted(keys), 2):
            pair_works[(a, b)].append(doc_id)
    cooccurrence = [
        {"a": a, "b": b, "weight": len(docs), "works": docs}
        for (a, b), docs in pair_works.items()
    ]
    cooccurrence.sort(key=lambda c: (-c["weight"], c["a"], c["b"]))

    # ── Begriffe ──────────────────────────────────────────────────────
    terms: list[dict] = []
    for key, entry in trm.items():
        years = sorted(entry["years"])
        terms.append(
            {
                "key": key,
                "label": entry["labels"].most_common(1)[0][0],
                "n_works": len(entry["works"]),
                "works": entry["works"],
                "years": years,
                "first_year": years[0] if years else None,
                "last_year": years[-1] if years else None,
                "label_variants": list(entry["labels"].keys()),
            }
        )
    terms.sort(key=lambda t: (-t["n_works"], t["label"]))

    # ── Zeit-Achse ────────────────────────────────────────────────────
    all_years = sorted({y for y in year_per_work.values() if y is not None})
    periods = _build_periods(
        all_years, year_per_work, keys_per_work, terms_per_work, src, stance_by_year, period_size
    )

    self_positions.sort(key=lambda p: (p["year"] is None, p["year"] or 0, p["document_id"]))

    return {
        "substrate": {
            "works": works,
            "n_works": len(works),
            "years": all_years,
            "year_span": [all_years[0], all_years[-1]] if all_years else None,
        },
        "sources": sources,
        "cooccurrence": cooccurrence,
        "terms": terms,
        "self_positions": self_positions,
        "periods": periods,
        "reliability": {
            "n_works": len(works),
            "works_with_beleg_failures": sum(1 for w in works if w["beleg_failures"] > 0),
            "total_beleg_failures": sum(w["beleg_failures"] for w in works),
            "fuzzy_matched_keys": sum(
                1 for e in list(src.values()) + list(trm.values()) if len(e["labels"]) > 1
            ),
            "skipped_files": list(getattr(fallgestalten, "skipped", [])),
        },
    }


def _build_periods(
    all_years: list[int],
    year_per_work: dict[str, int | None],
    keys_per_work: dict[str, set[str]],
    terms_per_work: dict[str, set[str]],
    src: dict[str, dict[str, Any]],
    stance_by_year: dict[str, dict[int, Counter]],
    period_size: int,
) -> list[dict]:
    """Jahre in Blöcke von `period_size` gruppieren, an der Spanne ausgerichtet.

    `new_sources`/`dropped_sources`/`new_terms` sind die Differenz zur jeweils
    VORIGEN Periode. Die erste Periode hat keine Vorgängerin — dort sind alle
    drei leer (ihre Quellen stehen vollständig in `sources`); „neu" gegenüber
    nichts wäre keine Aussage.
    """
    if len(all_years) < 2 or period_size < 1:
        return []

    start = all_years[0]
    blocks: dict[int, list[str]] = defaultdict(list)
    for doc_id, year in year_per_work.items():
        if year is not None:
            blocks[(year - start) // period_size].append(doc_id)

    periods: list[dict] = []
    prev_sources: set[str] | None = None
    prev_terms: set[str] | None = None
    for _, doc_ids in sorted(blocks.items()):
        years = sorted({year_per_work[d] for d in doc_ids if year_per_work[d] is not None})
        period_source_keys: set[str] = set()
        for d in doc_ids:
            period_source_keys |= keys_per_work.get(d, set())
        period_term_keys: set[str] = set()
        for d in doc_ids:
            period_term_keys |= terms_per_work.get(d, set())

        period_sources = []
        for key in period_source_keys:
            counts: Counter = Counter()
            for y in years:
                counts.update((stance_by_year.get(key) or {}).get(y, Counter()))
            period_sources.append(
                {
                    "key": key,
                    "label": src[key]["labels"].most_common(1)[0][0],
                    "n_works": sum(1 for d in doc_ids if key in keys_per_work.get(d, set())),
                    "stance_dominant": _dominant_stance(counts),
                }
            )
        period_sources.sort(key=lambda s: (-s["n_works"], s["label"]))

        periods.append(
            {
                "label": _period_label(years),
                "years": years,
                "n_works": len(doc_ids),
                "sources": period_sources,
                "new_sources": (
                    sorted(period_source_keys - prev_sources) if prev_sources is not None else []
                ),
                "dropped_sources": (
                    sorted(prev_sources - period_source_keys) if prev_sources is not None else []
                ),
                "new_terms": (
                    sorted(period_term_keys - prev_terms) if prev_terms is not None else []
                ),
            }
        )
        prev_sources = period_source_keys
        prev_terms = period_term_keys

    return periods
