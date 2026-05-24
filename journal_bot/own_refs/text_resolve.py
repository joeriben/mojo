"""Free-Text-Refs → OpenAlex-Work-ID via Search-API + Levenshtein-Match.

Zweite Resolution-Stufe nach `resolve.py` (DOI-Resolver). Für Refs, die im
PDF-Extract keinen DOI hatten — typischerweise Pre-2010-Sammelband- und
Monographie-Einträge —, parsen wir Autor + Jahr + Titel heuristisch aus dem
Roh-Text und fragen `https://api.openalex.org/works?search=…` an. Beste
Kandidaten werden über `difflib.SequenceMatcher` auf den Titel gematcht.

Akzeptanz-Bedingungen (konservativ, kein LLM):
  - Levenshtein-Ratio auf normalisiertem Titel ≥ 0.85
  - Year-Match: ±1 (Pre-Prints, Online-First-Versionen)
  - First-Author-Lastname muss in der OA-Autorenliste vorkommen (substring,
    case-insensitive — robust gegen "von" / "de la" / Initial-Reihenfolge)

Cache: `.own_refs_cache/text_oa/<sha1(parsed_signature)>.json`. Negative
Ergebnisse werden ebenfalls gecacht (`{}`), damit ein zweiter Lauf nicht
nochmal anfragt. Cache-Key ist nur die geparste Signatur — solange Parser
und Normalisierung gleich bleiben, ist der Cache deterministisch.

Polite-Pool: `mailto`-Parameter + `User-Agent`-Header, 0.12s Throttle.

KEINE LLM-Calls. Reine Regex + HTTP + difflib.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Iterable

import httpx

from journal_bot.own_refs.identity import normalize_text

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TEXT_CACHE_DIR = PROJECT_ROOT / ".own_refs_cache" / "text_oa"

POLITE_MAILTO = "mojo@localhost"
USER_AGENT = f"mojo/1.0 own_refs/text (mailto:{POLITE_MAILTO})"
THROTTLE_SECONDS = 0.12

# Konservative Match-Schwellen — falsche Resolves würden den own_coupling-
# und adversarial-Score systematisch verunreinigen.
MIN_TITLE_RATIO = 0.85
YEAR_TOLERANCE = 1                # ±1 Jahr (Online-First / Pre-Print)
MIN_TITLE_QUERY_CHARS = 5         # "Netzwerke", "Cyberland" — Monographien
                                  # mit Einwort-Titel sind valide OA-Anker
                                  # solange Autor + Jahr stimmen.


# -- Datenklassen -------------------------------------------------------------


@dataclass
class ParsedRef:
    """Heuristisch geparste Felder aus einer freien Citation."""
    first_author_lastname: str   # "Barad"
    year: int | None             # 2007
    title: str                   # "Meeting the universe halfway"
    raw: str                     # full original text


@dataclass
class TextResolvedRef:
    """Resolution-Ergebnis nach Levenshtein-Match."""
    oa_id: str | None            # "https://openalex.org/W..." oder None
    matched_title: str | None
    matched_year: int | None
    matched_doi: str | None
    score: float                 # 0.0–1.0
    cache_hit: bool = False


# -- Parser -------------------------------------------------------------------

# Hauptmuster: "(YYYY)" — APA. Optionales Suffix-Letter (2020a, 2020b).
# Erlaubt auch "(YYYY, Month Day)" / "(YYYY/Heft 1)" — Inhalt darf alles
# außer ")" enthalten. Year wird im erfassten Match referenziert.
_YEAR_PAREN_RE = re.compile(r"\((1[89]\d{2}|20\d{2})[a-z]?[^)]*\)")

# Fallback: Year als Jahres-Token irgendwo im Text. Eher unzuverlässig, daher
# nur als zweite Wahl — und wir nehmen die ERSTE Jahreszahl im Text, weil
# spätere Jahreszahlen oft Heftnummern/Volumes sind ("(2020)" ist sicherer
# als das nackte "1998" weiter hinten).
_YEAR_BARE_RE = re.compile(r"\b(1[89]\d{2}|20\d{2})[a-z]?\b")

# Tokens, die wir NICHT als Autor-Nachnamen akzeptieren.
_AUTHOR_BLOCKLIST = {
    "et", "al", "ed", "eds", "hrsg", "in",
    "the", "and", "or", "of", "for", "to",
    "abruf", "abgerufen", "retrieved",
}

# Initial-Punkt-Muster: "A.", "A.B.", "B.J."
_INITIAL_RE = re.compile(r"^[A-Z]\.([A-Z]\.)*$")


def _strip_initials(token: str) -> str:
    """'B.' / 'B.J.' → '' ; 'Jörissen' → 'Jörissen'."""
    if _INITIAL_RE.match(token):
        return ""
    return token


def _clean_title_candidate(s: str) -> str:
    """Titel-Bereinigung: Soft-Hyphenation aufheben, Leerzeichen normalisieren."""
    # Soft-Hyphen am Zeilenumbruch (artiﬁcial → artificial): hier nur das
    # bekannte pdftotext-Artefakt "wort- wort" → "wortwort" mappen, wenn es
    # so aussieht wie ein zusammenhängendes Wort.
    s = re.sub(r"(\w)-\s+(\w)", r"\1\2", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip(" .,;:")


def parse_ref_text(raw: str) -> ParsedRef | None:
    """Heuristik: Autor + Jahr + Titel aus einer freien Citation extrahieren.

    Liefert ``None``, wenn weder Jahr noch Titel-Kandidat brauchbar gefunden
    werden. Konservativ: lieber kein Match als ein falscher.
    """
    if not raw or len(raw) < 20:
        return None
    text = raw.strip()

    # 1) Jahr finden — bevorzugt in Parens, sonst erstes nacktes Jahr.
    m = _YEAR_PAREN_RE.search(text)
    if m:
        year = int(m.group(1))
        before_year = text[:m.start()].strip(" .,;")
        after_year = text[m.end():].strip(" .,;")
    else:
        m = _YEAR_BARE_RE.search(text)
        if not m:
            return None
        year = int(m.group(1))
        before_year = text[:m.start()].strip(" .,;")
        after_year = text[m.end():].strip(" .,;")

    # 2) Autor: erstes Komma-Token vor dem Jahr ist üblicherweise der
    #    Nachname. "Barad, K." → "Barad" ; "Barad K." → "Barad" ;
    #    "Alkemeyer, T., Buschmann, N., …" → "Alkemeyer".
    first_author = _extract_first_author(before_year)
    if not first_author:
        return None

    # 3) Titel: alles ab dem Jahr, abgeschnitten am ersten "."-Endeund
    #    Stop vor "In:", "https://", "Verlag", "Press" etc.
    title = _extract_title(after_year)
    if not title or len(title) < MIN_TITLE_QUERY_CHARS:
        return None

    return ParsedRef(
        first_author_lastname=first_author,
        year=year,
        title=title,
        raw=raw,
    )


def _extract_first_author(before_year: str) -> str:
    """'Barad, K.' → 'Barad' ;  'Alkemeyer, T., Buschmann, N.' → 'Alkemeyer'.

    Nimmt das erste Token vor dem ersten Komma. Filtert Initialen und
    Blocklist-Tokens raus.
    """
    if not before_year:
        return ""
    # Erstes Komma oder " & " teilt — alles davor sollte der Nachname sein.
    head = re.split(r",|\s&\s", before_year, maxsplit=1)[0].strip()
    if not head:
        return ""
    # Wenn das Token wie eine Initiale aussieht, ist die Reihenfolge invers
    # ("K. Barad" statt "Barad, K."): dann letztes Token nehmen.
    tokens = head.split()
    if not tokens:
        return ""
    # Pre-Initial-Form: "Karen Barad" → "Barad" ; "K. Barad" → "Barad"
    while tokens and _INITIAL_RE.match(tokens[0]):
        tokens = tokens[1:]
    if not tokens:
        return ""
    candidate = tokens[-1] if len(tokens) > 1 else tokens[0]
    candidate = candidate.strip(".,;:()[]").strip()
    if not candidate:
        return ""
    if candidate.lower() in _AUTHOR_BLOCKLIST:
        return ""
    if len(candidate) < 2:
        return ""
    return candidate


# Venue-Marker — Boundary zwischen Titel und Quellenangabe.
# Wird in _extract_title benutzt; reicht idR aus, um Verlag/Journal/Pages
# vom Titel zu trennen. Übrig bleibender Resttext ist für OA-Search
# tolerierbar (BM25 + Year + Author-Filter rettet die Spezifität).
_VENUE_MARKER_RE = re.compile(
    r"\s+In:?\s+(?:[A-ZÄÖÜ]|\()"          # "In D. Drascek", "In: Sammelband"
    r"|\(Eds?\.\)"
    r"|\(Hg(?:\.|in)\)"
    r"|https?://"
    r"|\bpp\.\s"
    r"|\(pp\."
    r"|,\s*\d{1,4}\s*\(\d"                # ", 3(1)" volume pattern
    r"|\.\s+[A-ZÄÖÜ][a-zäöü\-]+:\s+[A-ZÄÖÜ]"  # ". Bielefeld: transcript"
    r"|\b(?:Verlag|Press|University[ \t]Press)\b"
)


def _extract_title(after_year: str) -> str:
    """Titel aus dem Post-Jahr-Teil ziehen.

    Heuristik:
      - Schneide am ersten Venue-Marker ab (Verlag, Press, Journal-Vol,
        "In:", URL, City-Publisher). Damit bleibt der GANZE Titel inkl.
        Untertitel erhalten — auch "Wissen. Können. Weitergeben" oder
        "Title: Subtitle" — solange keine Venue-Marker dazwischen sind.
      - Ohne Marker: erste 250 Zeichen, damit OA-Search nicht überläuft.
    """
    if not after_year:
        return ""
    m = _VENUE_MARKER_RE.search(after_year)
    if m:
        title = after_year[:m.start()]
    else:
        title = after_year[:250]
    return _clean_title_candidate(title)


# -- Cache --------------------------------------------------------------------


def _parsed_signature(parsed: ParsedRef) -> str:
    return (
        f"{normalize_text(parsed.first_author_lastname)}|"
        f"{parsed.year if parsed.year is not None else ''}|"
        f"{normalize_text(parsed.title)[:80]}"
    )


def _cache_path(signature: str, cache_dir: Path) -> Path:
    h = hashlib.sha1(signature.encode("utf-8")).hexdigest()
    return cache_dir / f"{h}.json"


def _load_cached(signature: str, cache_dir: Path) -> TextResolvedRef | None:
    p = _cache_path(signature, cache_dir)
    if not p.exists():
        return None
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not d:
        return TextResolvedRef(
            oa_id=None, matched_title=None, matched_year=None,
            matched_doi=None, score=0.0, cache_hit=True,
        )
    return TextResolvedRef(
        oa_id=d.get("oa_id"),
        matched_title=d.get("title"),
        matched_year=d.get("year"),
        matched_doi=d.get("doi"),
        score=float(d.get("score", 0.0)),
        cache_hit=True,
    )


def _save_cache(signature: str, info: dict, cache_dir: Path) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    _cache_path(signature, cache_dir).write_text(
        json.dumps(info, ensure_ascii=False), encoding="utf-8"
    )


# -- Matching -----------------------------------------------------------------


def _title_ratio(parsed_title: str, candidate_title: str) -> float:
    """Asymmetrische Token-Containment-Metrik.

    Wir nehmen die ASYMMETRISCHE Frage: "Wie viel des KANDIDATEN-Titels
    findet sich im geparsten Titel?" — weil der geparste Titel oft
    überschüssiges Venue-/Übersetzer-/Verlagsrauschen mitnimmt, der
    Kandidat aber sauber ist.

    Beispiel:
      candidate = "Promoting Cultural Rights for Inhabitants of Segregated Neighbourhoods..."
      parsed    = "Promoting cultural rights ... Cape Town, Salvador de Bahia, and Toulouse.
                   From cultural insurrection to Epistemic Action (K. Throssell, Übers.).
                   Biens Symboliques/Symbolic Goods. Revue de Sciences ..."
    SequenceMatcher würde wegen der unterschiedlichen Länge ratio≈0.6 liefern.
    Token-Containment: alle Cand-Tokens sind in Parsed → 1.0.

    Stopwörter werden NICHT ausgeschlossen, weil der Recall sonst leidet
    (kurze Titel haben wenig Tokens; "the cat" matched dann "cat" mit 1.0).
    Stattdessen verlangen wir Mindest-Tokenzahl im Kandidaten.
    """
    a = set(normalize_text(parsed_title).split())
    b = set(normalize_text(candidate_title).split())
    if not a or not b:
        return 0.0
    if len(b) < 2:                  # zu kurze Kandidaten-Titel → unverlässlich
        return 0.0
    return len(a & b) / len(b)


def _author_matches(parsed_author: str, candidate_authorships: list[dict]) -> bool:
    """First-Author-Surname muss in der OA-Autorenliste vorkommen.

    Robust gegen Reihenfolge-Variation und Affix-Sortierung: wir prüfen
    Substring auf normalisierten Display-Namen.
    """
    if not parsed_author:
        return False
    needle = normalize_text(parsed_author)
    if not needle or len(needle) < 2:
        return False
    for a in candidate_authorships or []:
        display = (a.get("author") or {}).get("display_name") or ""
        if needle in normalize_text(display):
            return True
    return False


def _best_match(parsed: ParsedRef, candidates: list[dict]) -> TextResolvedRef:
    """Pick best match by title-ratio, with author + year sanity checks."""
    best_score = 0.0
    best: dict | None = None
    for c in candidates:
        title = c.get("title") or ""
        year = c.get("publication_year")
        if year is not None and parsed.year is not None:
            if abs(int(year) - parsed.year) > YEAR_TOLERANCE:
                continue
        if not _author_matches(parsed.first_author_lastname, c.get("authorships") or []):
            continue
        ratio = _title_ratio(parsed.title, title)
        if ratio > best_score:
            best_score = ratio
            best = c
    if best is None or best_score < MIN_TITLE_RATIO:
        return TextResolvedRef(
            oa_id=None, matched_title=None, matched_year=None,
            matched_doi=None, score=best_score,
        )
    doi_raw = (best.get("doi") or "").replace("https://doi.org/", "") or None
    return TextResolvedRef(
        oa_id=best.get("id"),
        matched_title=best.get("title"),
        matched_year=best.get("publication_year"),
        matched_doi=doi_raw,
        score=best_score,
    )


# -- API ---------------------------------------------------------------------


MAX_QUERY_WORDS = 5                 # OpenAlex BM25 toleriert lange Queries
                                    # schlecht — Stress-getestet gegen "Kosmologie
                                    # des Toilettengangs": 8 Tokens lieferten
                                    # 0 Treffer, 3 Tokens den korrekten Treffer.
                                    # 5 Tokens = Sweet-Spot Spezifität/Recall.
MAX_QUERY_CHARS = 70

# Stopwörter (DE+EN) — entfernen wir aus der Query, weil OA's BM25 sie
# nicht ranken kann und sie nur Slots blockieren. Liste konservativ klein.
_QUERY_STOPWORDS = {
    "der", "die", "das", "des", "dem", "den",
    "ein", "eine", "einer", "einen", "einem",
    "und", "oder", "in", "im", "ins", "zu", "zum", "zur",
    "von", "vom", "mit", "auf", "aus", "fur", "für",
    "the", "a", "an", "of", "and", "or",
    "in", "on", "at", "to", "for", "by", "with",
}

# Smart-Quotes / typographische Punkts → ASCII-Form für die Search-Query
_QUERY_SUBSTITUTIONS = str.maketrans({
    "‘": "'", "’": "'", "“": '"', "”": '"',
    "–": "-", "—": "-", "…": " ",  # ellipsis → space
    "ﬁ": "fi", "ﬂ": "fl", "ﬀ": "ff",            # PDF-Ligaturen
})


def _build_search_query(title: str) -> str:
    """Such-Query für OA: Diakritika ERHALTEN (OA's BM25 ist umlaut-sensitiv),
    Smart-Quotes und PDF-Ligaturen normalisieren, Stopwörter rausnehmen,
    auf erste 8 Tokens / 90 Zeichen kappen.
    """
    if not title:
        return ""
    s = title.translate(_QUERY_SUBSTITUTIONS)
    # nicht-alfanumerische Zeichen → Leerzeichen (außer ASCII-Buchstaben +
    # Umlaute/diakritische Buchstaben).
    s = re.sub(r"[^\w\säöüÄÖÜß]+", " ", s, flags=re.UNICODE)
    tokens = [t for t in s.split() if t.lower() not in _QUERY_STOPWORDS]
    tokens = tokens[:MAX_QUERY_WORDS]
    return " ".join(tokens)[:MAX_QUERY_CHARS].strip()


def _build_search_params(parsed: ParsedRef) -> dict:
    """OpenAlex-Search-Query: kurzgehaltener Titel + Year-Range-Filter."""
    q = _build_search_query(parsed.title)
    params: dict[str, str] = {
        "search": q,
        "per-page": "5",
        "select": "id,doi,title,publication_year,authorships",
        "mailto": POLITE_MAILTO,
    }
    if parsed.year is not None:
        y0 = parsed.year - YEAR_TOLERANCE
        y1 = parsed.year + YEAR_TOLERANCE
        # OpenAlex-Filter-Syntax: range via from/to
        params["filter"] = (
            f"from_publication_date:{y0}-01-01,"
            f"to_publication_date:{y1}-12-31"
        )
    return params


def _search_openalex(client: httpx.Client, parsed: ParsedRef) -> list[dict]:
    params = _build_search_params(parsed)
    try:
        r = client.get(
            "https://api.openalex.org/works", params=params, timeout=30.0
        )
    except httpx.HTTPError as e:
        print(f"  [warn] OpenAlex network error: {e}")
        return []
    if r.status_code != 200:
        print(f"  [warn] OpenAlex {r.status_code}: {r.text[:160]}")
        return []
    return r.json().get("results", []) or []


# -- Public API ---------------------------------------------------------------


def resolve_text_refs(
    ref_texts: Iterable[tuple[str, str]],
    cache_dir: Path = DEFAULT_TEXT_CACHE_DIR,
    verbose: bool = False,
    max_calls: int | None = None,
) -> dict[str, TextResolvedRef]:
    """Resolve free-text refs against OpenAlex search.

    Args:
      ref_texts: iterable of `(ref_id, raw_text)` tuples.
      cache_dir: file-cache directory (one JSON per signature).
      verbose: print progress every 50 calls.
      max_calls: optional cap on live API calls (cache-hits zählen nicht).
        Für Smoke-Tests und Cost-Floors.

    Returns:
      dict ref_id → TextResolvedRef. Refs, die nicht parsebar sind, fehlen im
      Output (Caller behandelt sie als "weiterhin text_unresolved").
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    out: dict[str, TextResolvedRef] = {}
    parsed_pairs: list[tuple[str, ParsedRef]] = []
    skipped_unparseable = 0

    for ref_id, text in ref_texts:
        parsed = parse_ref_text(text)
        if parsed is None:
            skipped_unparseable += 1
            continue
        parsed_pairs.append((ref_id, parsed))

    if verbose:
        print(
            f"[text-resolve] parsed={len(parsed_pairs)}, "
            f"unparseable={skipped_unparseable}"
        )
    if not parsed_pairs:
        return out

    # Per-Signatur-Dedup: gleiche Refs aus verschiedenen Pubs → ein Lookup.
    signature_to_ids: dict[str, list[str]] = {}
    signature_to_parsed: dict[str, ParsedRef] = {}
    for ref_id, parsed in parsed_pairs:
        sig = _parsed_signature(parsed)
        signature_to_ids.setdefault(sig, []).append(ref_id)
        signature_to_parsed[sig] = parsed

    if verbose:
        print(
            f"[text-resolve] unique signatures: {len(signature_to_ids)} "
            f"(refs total {len(parsed_pairs)})"
        )

    client: httpx.Client | None = None
    calls_made = 0
    cache_hits = 0
    cache_misses_resolved = 0
    cache_misses_unresolved = 0
    last_log = 0

    try:
        for sig, parsed in signature_to_parsed.items():
            ref_ids = signature_to_ids[sig]
            cached = _load_cached(sig, cache_dir)
            if cached is not None:
                cache_hits += 1
                for rid in ref_ids:
                    out[rid] = cached
                continue
            if max_calls is not None and calls_made >= max_calls:
                continue
            # Live-Call nötig — Lazy-Init des Clients (sparen wenn pur Cache).
            if client is None:
                client = httpx.Client(headers={"User-Agent": USER_AGENT})
            candidates = _search_openalex(client, parsed)
            calls_made += 1
            resolved = _best_match(parsed, candidates)
            if resolved.oa_id:
                cache_misses_resolved += 1
                _save_cache(sig, {
                    "oa_id": resolved.oa_id,
                    "title": resolved.matched_title,
                    "year": resolved.matched_year,
                    "doi": resolved.matched_doi,
                    "score": round(resolved.score, 3),
                }, cache_dir)
            else:
                cache_misses_unresolved += 1
                _save_cache(sig, {}, cache_dir)
            for rid in ref_ids:
                out[rid] = resolved
            if verbose and calls_made - last_log >= 50:
                print(
                    f"  [text-resolve] {calls_made} calls, "
                    f"{cache_misses_resolved} resolved, "
                    f"{cache_misses_unresolved} unresolved"
                )
                last_log = calls_made
            time.sleep(THROTTLE_SECONDS)
    finally:
        if client is not None:
            client.close()

    if verbose:
        print(
            f"[text-resolve] done: calls={calls_made} "
            f"(resolved={cache_misses_resolved}, "
            f"unresolved={cache_misses_unresolved}), "
            f"cache_hits={cache_hits}, total_refs_with_result={len(out)}"
        )
    return out
