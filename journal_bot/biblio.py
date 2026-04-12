"""Bibliometrische Trend-Analyse auf Basis der Crossref-Referenzlisten.

Methode:
  1. Alle Referenzlisten eines Diskursraums/Zeitfensters sammeln
  2. Normalisierung: Erst-Autor-Nachname + Titel-Kernwörter → composite key
  3. Häufigkeitsranking (wie oft wird diese Referenz zitiert?)
  4. Top 10-15% nehmen
  5. Jahresverteilung: in welchen Jahren (der ZITIERENDEN Artikel) wird zitiert?
  6. Trend-Statement: steigend / Peak / fallend

Kein LLM. Rein Python. Null Kosten.
"""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from journal_bot.settings import DISCOURSE_SPACES, journals_in_cluster
from journal_bot.store import Store, StoredArticle


@dataclass
class CitedWork:
    """Ein normalisierter Eintrag aus einer Referenzliste."""
    key: str           # Normalisierter composite key
    raw_samples: list[str]  # Originalzeilen (für Anzeige)
    first_author: str
    title_fragment: str     # 4-Wort-Normalisierung (für Matching)
    year: str               # Erscheinungsjahr der zitierten Arbeit
    doi: str
    count: int              # Wie oft insgesamt zitiert (Roh-Zählung)
    unique_citers: int      # Anzahl VERSCHIEDENER zitierender Erst-Autor*innen
    citing_authors: list[str]   # zitierenden Autor*innen (normalisiert, unique)
    citing_years: dict[int, int]  # {Jahr_des_zitierenden_Artikels: Anzahl}
    title_full: str = ""    # Voller extrahierter Titel (für Anzeige)


# ---------------------------------------------------------------- Normalisierung


_STOP = {
    "the", "a", "an", "of", "in", "on", "for", "and", "to", "from", "with",
    "by", "at", "as", "is", "are", "was", "were", "be", "been", "has", "have",
    "or", "not", "but", "its", "it", "this", "that", "these", "those",
    "der", "die", "das", "und", "von", "zur", "zum", "des", "den", "dem",
    "ein", "eine", "einer", "einem", "einen", "mit", "auf", "aus", "für",
    "über", "unter", "nach", "bei", "als", "durch",
}


def _normalize_author(raw: str) -> str:
    """Extrahiert den Nachnamen des Erst-Autors, lowercase."""
    raw = raw.strip()
    if not raw:
        return ""
    # "Smith, J." → "smith"
    # "J Smith" → "smith"
    # "Smith" → "smith"
    parts = re.split(r"[,;]", raw)
    name = parts[0].strip()
    # Wenn mehrere Wörter: letztes Wort ist vermutlich der Nachname,
    # es sei denn es ist ein Initial ("J.") → dann erstes Wort
    words = name.split()
    if not words:
        return ""
    # Initialen entfernen
    non_initials = [w for w in words if len(w) > 2 or not w.endswith(".")]
    if non_initials:
        return non_initials[-1].lower().strip(".")
    return words[0].lower().strip(".")


def _normalize_title(raw: str) -> str:
    """Extrahiert die ersten 4 signifikanten Wörter aus dem Titel, lowercase."""
    words = re.findall(r"\w{3,}", raw.lower())
    sig = [w for w in words if w not in _STOP][:4]
    return " ".join(sig)


def _extract_title_from_raw(raw: str) -> str:
    """Robuste Titel-Extraktion aus Roh-Zitationsstrings aller gängigen Formate.

    Strategie: Alles was NICHT Titel ist, entfernen, dann signifikante Wörter nehmen.
    """
    text = raw
    # 1. Autor-Teil entfernen (alles vor dem Erscheinungsjahr)
    m = re.search(r"\(?((?:19|20)\d{2})[a-z]?\)?", text)
    if m:
        text = text[m.end():]
    # 2. DOI / URL entfernen
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"doi:\S+", "", text, flags=re.IGNORECASE)
    # 3. Volume/Issue/Pages-Muster entfernen
    text = re.sub(r",?\s*\d+\s*\(\d+\)", "", text)   # 50(10)
    text = re.sub(r",?\s*\d+\s*[-–]\s*\d+", "", text) # 893-899 / S. 12-34
    text = re.sub(r",?\s*pp?\.\s*\d+", "", text)       # p. 123
    text = re.sub(r",?\s*[Vv]ol\.?\s*\d+", "", text)   # Vol. 3
    # 4. Verlagsnamen und typische Venue-Marker entfernen
    text = re.sub(
        r"(?:Springer|Routledge|Sage|Wiley|Cambridge|Oxford|Palgrave|"
        r"Taylor\s*&?\s*Francis|University\s+Press|Verlag|Press)\b",
        "", text, flags=re.IGNORECASE,
    )
    # 5. ISBN entfernen
    text = re.sub(r"ISBN[\s:-]*[\d-]+", "", text, flags=re.IGNORECASE)
    # 6. Interpunktion bereinigen
    text = re.sub(r"[.,:;()\[\]{}\"']+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _is_valid_doi(doi: str) -> bool:
    """Prüft ob ein DOI plausibel vollständig ist (nicht nur Journal-Prefix)."""
    if not doi:
        return False
    # Nach dem Registrant-Prefix (10.XXXX/) muss ein Suffix mit mindestens
    # einem Punkt oder Bindestrich oder >8 Zeichen kommen
    m = re.match(r"10\.\d{4,}/(.+)", doi)
    if not m:
        return False
    suffix = m.group(1)
    return len(suffix) > 8 or "." in suffix or "-" in suffix


def _make_ref_key(author: str, title: str) -> str:
    a = _normalize_author(author)
    t = _normalize_title(title)
    return f"{a}|{t}" if a or t else ""


# ---------------------------------------------------------------- Aggregation


def _parse_refs(article: StoredArticle) -> list[dict]:
    """Holt die Crossref-Referenzen aus dem Store-Eintrag."""
    refs = article.crossref_refs
    if isinstance(refs, str):
        try:
            refs = json.loads(refs)
        except Exception:
            return []
    return refs if isinstance(refs, list) else []


def _extract_ref_identity(ref: dict) -> tuple[str, str, str, str, str]:
    """Gibt (composite_key, first_author, title_fragment, year, title_full) zurück."""
    authors = ref.get("authors") or []
    first_author = authors[0] if authors else ""
    title = ref.get("title") or ""
    raw = ref.get("raw") or ""

    # Fallback Autor: aus raw extrahieren
    if not first_author and raw:
        m = re.match(r"([^(]+?)[\s,]*\(?\d{4}", raw)
        if m:
            first_author = m.group(1).strip().rstrip(",")

    # Fallback Titel: robuste Extraktion aus Raw-String
    if not title and raw:
        title = _extract_title_from_raw(raw)

    year = ref.get("year") or ""
    if not year and raw:
        m = re.search(r"\b(19|20)\d{2}\b", raw)
        if m:
            year = m.group(0)

    # Clean up full title for display
    title_full = re.sub(r"\s+", " ", title).strip().rstrip(".,;")

    key = _make_ref_key(first_author, title)
    return key, _normalize_author(first_author), _normalize_title(title), str(year), title_full


def analyze(
    cluster: str,
    window_years: int = 3,
    top_pct: float = 0.10,
    min_count: int = 2,
) -> list[CitedWork]:
    """Bibliometrische Analyse: meistzitierte Werke in einem Diskursraum.

    Returns: Liste von CitedWork, sortiert nach count desc.
    """
    store = Store()

    if cluster not in DISCOURSE_SPACES:
        raise ValueError(f"Unbekannter Cluster: {cluster}")

    journals = [j.short for j in journals_in_cluster(cluster)]
    this_year = datetime.now().year
    start_year = this_year - window_years + 1

    articles = store.find_in_window(
        start_year=start_year,
        journals=journals,
    )

    # Aggregation: ref_key → {count, citing_years, citing_authors, raw_samples, ...}
    ref_counts: Counter[str] = Counter()
    ref_years: dict[str, Counter[int]] = defaultdict(Counter)
    ref_citers: dict[str, set[str]] = defaultdict(set)  # unique citing authors
    ref_meta: dict[str, dict] = {}
    ref_samples: dict[str, list[str]] = defaultdict(list)

    for art in articles:
        citing_year = art.year or 0
        # Erst-Autor*in des ZITIERENDEN Artikels (normalisiert)
        citing_author = _normalize_author(art.authors[0]) if art.authors else ""
        refs = _parse_refs(art)
        for ref in refs:
            key, first_author, title_frag, ref_year, title_full = _extract_ref_identity(ref)
            if not key or len(key) < 5:
                continue

            ref_counts[key] += 1
            if citing_year:
                ref_years[key][citing_year] += 1
            if citing_author:
                ref_citers[key].add(citing_author)

            if key not in ref_meta:
                ref_meta[key] = {
                    "first_author": first_author,
                    "title_fragment": title_frag,
                    "title_full": title_full,
                    "year": ref_year,
                    "doi": ref.get("doi", ""),
                }
            raw = ref.get("raw") or ref.get("title") or ""
            if raw and len(ref_samples[key]) < 3:
                ref_samples[key].append(raw[:200])

    if not ref_counts:
        return []

    # Erst min_count-Filter (entfernt Rauschen), DANN Top-N% auf dem Rest
    n_articles = len(articles)
    effective_min = max(min_count, 3)  # nie unter 3

    above_min = [(k, c) for k, c in ref_counts.most_common() if c >= effective_min]
    n_top = max(1, int(len(above_min) * top_pct))
    top_refs = above_min[:n_top]

    # Sortierung nach unique_citers (robust), nicht nach Rohzahl
    top_refs.sort(key=lambda kc: len(ref_citers.get(kc[0], set())), reverse=True)

    result: list[CitedWork] = []
    for key, count in top_refs:
        meta = ref_meta.get(key, {})
        citers = sorted(ref_citers.get(key, set()))
        result.append(CitedWork(
            key=key,
            raw_samples=ref_samples.get(key, []),
            first_author=meta.get("first_author", ""),
            title_fragment=meta.get("title_fragment", ""),
            title_full=meta.get("title_full", ""),
            year=meta.get("year", ""),
            doi=meta.get("doi", ""),
            count=count,
            unique_citers=len(citers),
            citing_authors=citers,
            citing_years=dict(ref_years.get(key, {})),
        ))

    return result


# ---------------------------------------------------------------- Rendering


MIN_YEARS_FOR_TREND = 3   # Mindestens 3 verschiedene Zitationsjahre für Trend-Statement
MIN_COUNT_FOR_TREND = 5   # Mindestens 5 Gesamtzitationen für Trend-Statement


def _trend_label(citing_years: dict[int, int], total_count: int = 0) -> str:
    """Trend-Statement auf Basis der Jahresverteilung.

    Gibt '' zurück wenn die Datenlage für eine Aussage nicht reicht.
    Zwei Datenpunkte sind kein Trend, sondern ein Vergleich.
    """
    if not citing_years:
        return ""
    years = sorted(citing_years.keys())

    # Statistische Mindestanforderung: genug Jahre UND genug Gesamtzitationen
    if len(years) < MIN_YEARS_FOR_TREND or total_count < MIN_COUNT_FOR_TREND:
        if len(years) == 1:
            return f"nur {years[0]}"
        return ""  # keine Aussage bei zu wenig Daten

    # Peak-Jahr
    peak_year = max(citing_years, key=citing_years.get)  # type: ignore
    total = sum(citing_years.values())
    peak_share = citing_years[peak_year] / total if total else 0

    if peak_year == years[-1]:
        return "steigend"
    if peak_year == years[0]:
        return "fallend"
    if peak_share > 0.5:
        return f"Peak {peak_year}"
    return "stabil"


def render_markdown(
    cluster: str,
    results: list[CitedWork],
    window_years: int = 3,
) -> str:
    meta = DISCOURSE_SPACES.get(cluster, {})
    this_year = datetime.now().year
    start_year = this_year - window_years + 1
    window_label = f"{start_year}–{this_year}"

    lines: list[str] = []
    lines.append(f"# Bibliometrische Analyse: {meta.get('name', cluster)}")
    lines.append(f"_Fenster: {window_label} · Top-{len(results)} meistzitierte Werke_")
    lines.append("")

    if not results:
        lines.append("_Keine Referenzdaten mit ausreichender Häufigkeit vorhanden._")
        return "\n".join(lines)

    # Tabelle: Sortierung nach unique_citers (robuster als Rohzahl)
    lines.append("| # | Aut. | Zit. | Trend | Erst-Autor | Titel | Jahr | Zitiert in Jahren |")
    lines.append("|---|------|------|-------|------------|-------|------|-------------------|")
    for i, r in enumerate(results, 1):
        trend = _trend_label(r.citing_years, total_count=r.count)
        years_str = ", ".join(
            f"{y}({n})" for y, n in sorted(r.citing_years.items())
        )
        title_display = r.title_full or r.title_fragment
        lines.append(
            f"| {i} | {r.unique_citers} | {r.count} | {trend} | {r.first_author} | "
            f"{title_display} | {r.year} | {years_str} |"
        )

    lines.append("")
    lines.append("_Aut. = verschiedene zitierende Erst-Autor\\*innen; "
                 "Zit. = Gesamtzitationen (kann bei Vielpublizierenden höher sein)_")
    lines.append("")
    lines.append("## Referenz-Samples (Rohzeilen)")
    lines.append("")
    for i, r in enumerate(results[:20], 1):
        if r.raw_samples:
            citers_str = ", ".join(r.citing_authors[:8])
            if len(r.citing_authors) > 8:
                citers_str += f", +{len(r.citing_authors) - 8}"
            lines.append(
                f"**{i}. {r.first_author}** ({r.year}), "
                f"{r.unique_citers} Aut. / {r.count}× zitiert"
            )
            lines.append(f"Zitiert von: {citers_str}")
            for s in r.raw_samples[:2]:
                lines.append(f"> {s}")
            lines.append("")

    lines.append("---")
    lines.append(
        f"_Cluster: {meta.get('name', cluster)} · "
        f"Fenster: {window_label} · "
        f"Top {len(results)} Referenzen · Keine LLM-Kosten_"
    )
    return "\n".join(lines)


# ---------------------------------------------------------------- CLI-Entry


def run(
    cluster: str,
    window_years: int = 3,
    top_pct: float = 0.10,
    min_count: int = 2,
    verbose: bool = True,
    out_dir: Path | None = None,
) -> dict:
    from journal_bot.settings import DIGEST_DIR
    out_dir = out_dir or DIGEST_DIR

    if verbose:
        print(f"[biblio] Cluster: {cluster}")
        print(f"[biblio] Basis-min: {min_count}, dynamisch angepasst an Corpus-Größe")

    results = analyze(cluster, window_years, top_pct, min_count)

    if verbose:
        print(f"[biblio] Meistzitierte Werke gefunden: {len(results)}")
        if results:
            print(f"[biblio] Höchste Zitationszahl: {results[0].count}")

    md = render_markdown(cluster, results, window_years)

    trends_dir = out_dir / "trends"
    trends_dir.mkdir(parents=True, exist_ok=True)
    filename = f"biblio_{date.today().isoformat()}_{cluster}_{datetime.now().year - window_years + 1}-{datetime.now().year}.md"
    out_path = trends_dir / filename
    out_path.write_text(md, encoding="utf-8")

    if verbose:
        print(f"[biblio] Geschrieben: {out_path}")

    return {
        "status": "ok",
        "path": str(out_path),
        "count": len(results),
        "top_cited": results[0].count if results else 0,
    }
