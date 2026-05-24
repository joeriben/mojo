"""Iter 10 / Phase 1b+1c: Diskursraum-Klassifikation + 2nd-Trigger-Network.

Schritte:
1. Lade Trigger-Bibliografien (3 JSONs aus Phase 1a).
2. Klassifiziere jedes Trigger-Work nach Diskursraum (Journal-Cluster bzw. Topic-Heuristik).
3. Pro Diskursraum × Trigger-Autor: aggregiere referenced_works (Multiplicity zählt).
4. Pro Diskursraum: Coupling-Score auf Ref-ID-Ebene = Anzahl Trigger-Autoren mit count≥1.
5. Top-N Coupling-Refs via OpenAlex /works/{id} auflösen (cached).
6. Aus aufgelösten Refs: zitierte Autoren + Journals aggregieren.
7. Output:
   - backtest_data/trigger_network/per_discourse/{discourse}.json (vollständige Daten)
   - backtest_data/trigger_network/sichtungs_report.md (Phase 2 Sichtungsvorlage)
   - backtest_data/trigger_network/network_summary.json (Aggregate für Phase 3)

KEINE LLM-Calls. Reine OpenAlex + Pattern-Matching.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import httpx


POLITE_MAILTO = "mojo@localhost"
USER_AGENT = f"mojo/0.1 iter10-network (mailto:{POLITE_MAILTO})"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BIB_DIR = PROJECT_ROOT / "backtest_data" / "trigger_bibliographies"
OUT_DIR = PROJECT_ROOT / "backtest_data" / "trigger_network"
PER_DISC_DIR = OUT_DIR / "per_discourse"
CACHE_DIR = PROJECT_ROOT / ".enrichment_cache" / "iter10_refs"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
PER_DISC_DIR.mkdir(parents=True, exist_ok=True)


# Aus diskursraeume.json. Wir laden zur Laufzeit, dies hier als Default-Liste.
DISCOURSE_SPACES = [
    "deutsche", "erziehungswiss", "digitale_kultur", "medienpaed",
    "bildungstheorie", "aesthetische_kulturelle_bildung", "resilienz",
]

# Heuristisches Mapping Topic/Journal-Keywords → Diskursraum.
# Diese Patterns sind bewusst breit; ein Work kann in mehreren Diskursräumen liegen.
DISCOURSE_PATTERNS = {
    "digitale_kultur": {
        "topic_kw": [
            "digital", "software", "platform", "social media", "computing",
            "cybernetics", "internet", "media studies", "human-technology",
            "communication", "big data", "online", "technoscience", "code",
            "ai", "artificial intelligence", "algorithm", "data analysis",
            "data archiving", "human-computer", "innovation in technology",
        ],
        "journal_kw": [
            "media", "digital", "computing", "communication", "software",
            "platform", "data society", "code", "mit press",
        ],
    },
    "medienpaed": {
        "topic_kw": [
            "media literacy", "media education", "online learning",
            "educational technology", "literacy and media", "literacy, media",
        ],
        "journal_kw": [
            "medienpäd", "medienbildung", "merz", "medienpadagogik",
            "learning media", "edutech",
        ],
    },
    "erziehungswiss": {
        "topic_kw": [
            "education", "sociology and education", "educator training",
            "educational assessment", "educational research", "pedagogical",
            "teacher", "school", "discourse analysis in language",
            "education methods", "literacy, media, and education",
        ],
        "journal_kw": [
            "education", "erziehung", "pedagog", "teach", "schule",
            "british journal of educ", "european education",
        ],
    },
    "bildungstheorie": {
        "topic_kw": [
            "philosophy of education", "educational theory", "bildung",
            "ethics in education", "critical pedagogy", "educational philosophy",
            "history of education",
        ],
        "journal_kw": [
            "philosophy of education", "educational theory", "bildung",
            "pädagogische",
        ],
    },
    "aesthetische_kulturelle_bildung": {
        "topic_kw": [
            "arts education", "aesthetic", "cultural education",
            "visual culture", "music education", "creativity",
            "creative practice", "art and design",
        ],
        "journal_kw": [
            "arts", "aesthetic", "kunst", "visual", "music", "creativity",
            "art education", "studies in art",
        ],
    },
    "resilienz": {
        "topic_kw": [
            "resilience", "sustainability", "environment", "climate",
            "ecological", "anthropocene", "earth", "sustainable",
        ],
        "journal_kw": [
            "resilience", "sustainability", "environment", "ecological",
            "nachhaltigkeit",
        ],
    },
    "deutsche": {
        "topic_kw": [],  # Diskursraum primär per Journal-Hinweis
        "journal_kw": [
            "zeitschrift", "verlag", "diskurs", "transcript",
            "klinkhardt", "beltz", "deutsch", "vs verlag", "springer vs",
            "waxmann", "barbara budrich", "kohlhammer", "fink", "wbv",
        ],
    },
}


def http_get_json(url: str, cache_key: str, timeout: float = 30) -> dict | None:
    """GET JSON mit File-Cache."""
    safe = hashlib.sha256(cache_key.encode()).hexdigest()[:24]
    cache_file = CACHE_DIR / f"{safe}.json"
    if cache_file.exists():
        try:
            return json.loads(cache_file.read_text(encoding="utf-8"))
        except Exception:
            cache_file.unlink(missing_ok=True)
    try:
        resp = httpx.get(
            url,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            timeout=timeout,
            follow_redirects=True,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        cache_file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return data
    except Exception:
        return None


def classify_work_discourses(
    work: dict, journal_clusters_map: dict[str, list[str]]
) -> list[str]:
    """Bestimme die Diskursräume eines Trigger-Works."""
    discourses = set()
    journal_name = (work.get("journal") or "").strip()
    primary_topic = (work.get("primary_topic") or "").lower()
    concepts_text = " ".join(c.get("name", "") for c in (work.get("concepts") or [])).lower()
    journal_lower = journal_name.lower()

    # 1. Journal-Cluster (case-insensitive Match auf full names im diskursraeume.json
    #    funktioniert nicht direkt, weil dort Shortcodes wie "ZfE" stehen).
    #    Wir nehmen das hier als Bonus — primär läuft die Klassifikation per Pattern.

    # 2. Pattern-Matching
    for disc, pats in DISCOURSE_PATTERNS.items():
        for kw in pats.get("topic_kw", []):
            if kw in primary_topic or kw in concepts_text:
                discourses.add(disc)
                break
        if disc not in discourses:
            for kw in pats.get("journal_kw", []):
                if kw in journal_lower:
                    discourses.add(disc)
                    break

    # 3. "deutsche" zusätzlich, wenn deutscher Journal/Verlag erkannt
    #    (kann mit jedem anderen kombinieren)
    return sorted(discourses)


def slim_resolved_work(w: dict) -> dict:
    """Reduziere ein OpenAlex-Work auf die Felder für Network-Aggregation."""
    primary_loc = w.get("primary_location") or {}
    source = primary_loc.get("source") or {}
    primary_topic = w.get("primary_topic") or {}
    return {
        "id": (w.get("id", "") or "").rsplit("/", 1)[-1],
        "doi": w.get("doi", "") or "",
        "title": w.get("title", "") or "",
        "year": w.get("publication_year"),
        "journal": source.get("display_name", "") or "",
        "primary_topic": primary_topic.get("display_name", "") or "",
        "authors": [
            au.get("author", {}).get("display_name", "") or ""
            for au in (w.get("authorships") or [])
        ],
        "cited_by_count": w.get("cited_by_count", 0),
    }


def resolve_work(work_id: str) -> dict | None:
    """Hole OpenAlex-Work per ID. Gibt slim-version zurück."""
    if not work_id:
        return None
    wid = work_id.rsplit("/", 1)[-1]
    url = (
        f"https://api.openalex.org/works/{wid}"
        f"?select=id,doi,title,publication_year,primary_location,primary_topic,"
        f"authorships,cited_by_count"
        f"&mailto={POLITE_MAILTO}"
    )
    data = http_get_json(url, cache_key=f"resolve_work:{wid}")
    if not data:
        return None
    return slim_resolved_work(data)


def main():
    print(f"Bib dir: {BIB_DIR}")
    print(f"Out dir: {OUT_DIR}\n")

    # Lade Diskursraum-Definitionen
    diskursraeume = json.loads((PROJECT_ROOT / "diskursraeume.json").read_text())
    discourse_spaces = list(diskursraeume.get("discourse_spaces", {}).keys())
    journal_clusters_map = diskursraeume.get("journal_clusters", {})

    # Lade Bibliografien
    trigger_data = {}
    for f in sorted(BIB_DIR.glob("*.json")):
        if f.name.startswith("_"):
            continue
        d = json.loads(f.read_text())
        slug = d["trigger_author"]["slug"]
        trigger_data[slug] = d
        print(f"  Loaded {slug}: {len(d['works'])} Works")

    if not trigger_data:
        print("Keine Bibliografien gefunden, Abbruch.")
        return 1

    print(f"\nDiskursräume: {discourse_spaces}\n")

    # === Schritt 1+2: Klassifikation pro Work, Sammlung pro Diskursraum
    # Struktur: per_discourse[disc][trigger_slug] = list of refs (with multiplicity)
    per_discourse: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    # Diagnostik: wie viele Works pro Diskursraum & Trigger
    work_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    # Sammle alle Works, die in KEINEM Diskursraum landen (zur QC)
    unclassified_per_trigger: dict[str, list[dict]] = defaultdict(list)

    for slug, d in trigger_data.items():
        for w in d["works"]:
            disc_list = classify_work_discourses(w, journal_clusters_map)
            if not disc_list:
                unclassified_per_trigger[slug].append({
                    "title": w["title"], "journal": w["journal"],
                    "primary_topic": w["primary_topic"],
                })
                continue
            refs = w.get("referenced_works") or []
            for disc in disc_list:
                work_counts[disc][slug] += 1
                per_discourse[disc][slug].extend(refs)

    # Diagnostik-Print
    print("=== Klassifikations-Übersicht (Works pro Diskursraum × Trigger-Autor) ===")
    print(f"{'Diskursraum':<32}" + "".join(f"{s:>14}" for s in trigger_data))
    for disc in discourse_spaces:
        counts = [work_counts.get(disc, {}).get(s, 0) for s in trigger_data]
        print(f"{disc:<32}" + "".join(f"{c:>14}" for c in counts))

    print("\n=== Unklassifizierte Works (Top 5 pro Trigger) ===")
    for slug, lst in unclassified_per_trigger.items():
        print(f"  {slug}: {len(lst)} Works ohne Diskursraum")
        for u in lst[:5]:
            print(f"    - {u['title'][:80]}  | {u['journal'][:40]}  | {u['primary_topic']}")

    # === Schritt 3+4: Coupling-Score pro Diskursraum
    # network_summary[disc] = {"refs": {ref_id: {"trigger_count": ..., "total_freq": ..., "per_trigger": {slug: freq}}}}
    network_summary: dict[str, dict] = {}
    for disc in discourse_spaces:
        ref_data: dict[str, dict] = {}
        triggers = per_discourse.get(disc, {})
        for slug, refs in triggers.items():
            cnt = Counter(refs)
            for ref_id, freq in cnt.items():
                if ref_id not in ref_data:
                    ref_data[ref_id] = {
                        "trigger_count": 0,
                        "total_freq": 0,
                        "per_trigger": {},
                    }
                ref_data[ref_id]["trigger_count"] += 1
                ref_data[ref_id]["total_freq"] += freq
                ref_data[ref_id]["per_trigger"][slug] = freq
        network_summary[disc] = {
            "n_unique_refs": len(ref_data),
            "n_coupled_refs": sum(1 for v in ref_data.values() if v["trigger_count"] >= 2),
            "n_triple_coupled": sum(1 for v in ref_data.values() if v["trigger_count"] >= 3),
            "ref_data": ref_data,
        }

    print("\n=== Coupling-Statistik pro Diskursraum ===")
    print(f"{'Diskursraum':<32}{'unique refs':>14}{'≥2 coupled':>14}{'≥3 coupled':>14}")
    for disc in discourse_spaces:
        s = network_summary[disc]
        print(f"{disc:<32}{s['n_unique_refs']:>14}{s['n_coupled_refs']:>14}{s['n_triple_coupled']:>14}")

    # === Schritt 5: Top-N Coupling-Refs auflösen
    # Pro Diskursraum: Top-50 nach (trigger_count, total_freq) auflösen
    TOP_N = 50
    print(f"\n=== Top-{TOP_N} Coupling-Refs pro Diskursraum auflösen via OpenAlex ===")
    for disc in discourse_spaces:
        ref_data = network_summary[disc]["ref_data"]
        if not ref_data:
            continue
        ranked = sorted(
            ref_data.items(),
            key=lambda kv: (kv[1]["trigger_count"], kv[1]["total_freq"]),
            reverse=True,
        )[:TOP_N]
        resolved = []
        for ref_id, info in ranked:
            rw = resolve_work(ref_id)
            if rw:
                rw["coupling"] = info
                resolved.append(rw)
            time.sleep(0.05)
        network_summary[disc]["top_resolved"] = resolved
        print(f"  {disc}: {len(resolved)}/{len(ranked)} Refs aufgelöst")

    # === Schritt 6: Zitierte Autoren + Journals aggregieren pro Diskursraum
    # Wichtig: max_trigger_count auch für Journals tracken, damit wir später
    # nach Coupling filtern können (sonst landen Single-Coupling-"Filler"-Journals
    # in den Features = Rauschen; vgl. Kutscher-Befund in deutsche/bildungstheorie).
    for disc in discourse_spaces:
        resolved = network_summary[disc].get("top_resolved", [])
        author_freq: Counter = Counter()
        author_coupling: dict[str, int] = defaultdict(int)
        journal_freq: Counter = Counter()
        journal_coupling: dict[str, int] = defaultdict(int)
        for rw in resolved:
            tc = rw["coupling"]["trigger_count"]
            for au in rw["authors"]:
                if au:
                    author_freq[au] += 1
                    author_coupling[au] = max(author_coupling[au], tc)
            if rw["journal"]:
                journal_freq[rw["journal"]] += 1
                journal_coupling[rw["journal"]] = max(
                    journal_coupling[rw["journal"]], tc
                )
        # Coupling-Rank: erst nach max_trigger_count, dann nach Frequenz
        author_ranked = sorted(
            author_freq.items(),
            key=lambda kv: (author_coupling[kv[0]], kv[1]),
            reverse=True,
        )
        journal_ranked = sorted(
            journal_freq.items(),
            key=lambda kv: (journal_coupling[kv[0]], kv[1]),
            reverse=True,
        )
        network_summary[disc]["top_cited_authors"] = [
            {"name": n, "freq": f, "max_trigger_count": author_coupling[n]}
            for n, f in author_ranked[:30]
        ]
        network_summary[disc]["top_cited_journals"] = [
            {"name": j, "freq": f, "max_trigger_count": journal_coupling[j]}
            for j, f in journal_ranked[:20]
        ]

    # === Schritt 7: Output
    # 7a: Per-Discourse JSONs
    for disc in discourse_spaces:
        out_file = PER_DISC_DIR / f"{disc}.json"
        # Speichere komprimiert (ref_data ist groß)
        out_data = {
            "discourse": disc,
            "n_unique_refs": network_summary[disc]["n_unique_refs"],
            "n_coupled_refs": network_summary[disc]["n_coupled_refs"],
            "n_triple_coupled": network_summary[disc]["n_triple_coupled"],
            "n_works_per_trigger": work_counts.get(disc, {}),
            "top_resolved": network_summary[disc].get("top_resolved", []),
            "top_cited_authors": network_summary[disc].get("top_cited_authors", []),
            "top_cited_journals": network_summary[disc].get("top_cited_journals", []),
        }
        out_file.write_text(json.dumps(out_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n  Wrote per-discourse JSONs to {PER_DISC_DIR}/")

    # 7b: Sichtungs-Report Markdown
    report_lines = ["# Iter 10 / Phase 2: Sichtungs-Report 2nd-Trigger-Network\n"]
    report_lines.append(f"**Quelle**: OpenAlex-Bibliografien von Macgilchrist (165 Works), "
                       f"Jarke (110 Works), Chun (99 Works) = 374 Works mit insgesamt "
                       f"9836 Referenzen.\n")
    report_lines.append("**Methode**: Pro Trigger-Autor Works klassifiziert nach Diskursraum "
                       "(Topic/Journal-Patterns). Pro Diskursraum aggregierte referenced_works "
                       "mit Coupling-Score = Anzahl Trigger-Autoren, die ein Ref zitieren. "
                       "Top-50 Coupling-Refs aufgelöst via OpenAlex, daraus zitierte Autoren "
                       "und Journals abgeleitet.\n")
    report_lines.append("**Sichtungs-Aufgabe für Benjamin**: Welche der gefundenen 2nd-degree-"
                       "Autoren/Werke/Journals sind\n- *erwartbar* (= solide Heuristik-Basis),\n"
                       "- *überraschend* (= interessanter Erweiterungs-Kandidat),\n"
                       "- *Rauschen* (= ausschließen)?\n")
    report_lines.append("---\n")

    for disc in discourse_spaces:
        s = network_summary[disc]
        if s["n_unique_refs"] == 0:
            continue
        disc_name = diskursraeume["discourse_spaces"].get(disc, {}).get("name", disc)
        report_lines.append(f"\n## {disc_name} (`{disc}`)\n")
        wc = work_counts.get(disc, {})
        report_lines.append(
            f"**Trigger-Works**: Macgilchrist {wc.get('macgilchrist',0)}, "
            f"Jarke {wc.get('jarke',0)}, Chun {wc.get('wendy_chun',0)} | "
            f"Unique Refs: {s['n_unique_refs']} | "
            f"≥2-coupled: {s['n_coupled_refs']} | ≥3-coupled: {s['n_triple_coupled']}\n"
        )

        # Top zitierte Werke (Top-25)
        report_lines.append("\n### Top-zitierte Werke (nach Coupling)")
        report_lines.append("\n| # | Coup | Freq | Autor(en) | Titel | Jahr | Journal |")
        report_lines.append("|---:|---:|---:|---|---|---:|---|")
        for i, rw in enumerate(s.get("top_resolved", [])[:25]):
            authors_str = ", ".join(rw["authors"][:3])
            if len(rw["authors"]) > 3:
                authors_str += f" +{len(rw['authors'])-3}"
            title = rw["title"][:80].replace("|", " ")
            journal = rw["journal"][:40].replace("|", " ")
            report_lines.append(
                f"| {i+1} | {rw['coupling']['trigger_count']} | "
                f"{rw['coupling']['total_freq']} | {authors_str} | {title} | "
                f"{rw['year'] or '?'} | {journal} |"
            )

        # Top zitierte Autoren (Top-25)
        report_lines.append("\n### Top-zitierte Autoren\n")
        report_lines.append("| # | Coup | Freq | Autor |")
        report_lines.append("|---:|---:|---:|---|")
        for i, a in enumerate(s.get("top_cited_authors", [])[:25]):
            report_lines.append(
                f"| {i+1} | {a['max_trigger_count']} | {a['freq']} | {a['name']} |"
            )

        # Top zitierte Journals (Top-15)
        report_lines.append("\n### Top-zitierte Journals\n")
        report_lines.append("| # | Freq | Journal |")
        report_lines.append("|---:|---:|---|")
        for i, j in enumerate(s.get("top_cited_journals", [])[:15]):
            report_lines.append(f"| {i+1} | {j['freq']} | {j['name']} |")

    report_file = OUT_DIR / "sichtungs_report.md"
    report_file.write_text("\n".join(report_lines), encoding="utf-8")
    print(f"  Wrote sichtungs report: {report_file}")

    # 7c: Network-Summary (kompakt, für Phase 3 Feature-Engineering)
    compact_summary = {}
    for disc in discourse_spaces:
        s = network_summary[disc]
        compact_summary[disc] = {
            "n_works_per_trigger": work_counts.get(disc, {}),
            "n_unique_refs": s["n_unique_refs"],
            "n_coupled_refs": s["n_coupled_refs"],
            # Coupling-IDs als Feature-Source für Phase 3
            "coupled_ref_ids": sorted(
                [r for r, v in s["ref_data"].items() if v["trigger_count"] >= 2]
            ),
            # Nur Coupling≥2: ein Autor/Journal, der nur in einer einzigen
            # Trigger-Bib auftaucht, ist kein Netzwerk-Signal sondern Eigenart
            # des einzelnen Trigger-Autors. Sparse Diskursräume (resilienz,
            # aesthetische_kulturelle_bildung, deutsche, bildungstheorie) liefern
            # damit ggf. leere Listen — das ist gewollt.
            "top_authors_for_features": [
                a["name"] for a in s.get("top_cited_authors", [])
                if a.get("max_trigger_count", 0) >= 2
            ],
            "top_journals_for_features": [
                j["name"] for j in s.get("top_cited_journals", [])
                if j.get("max_trigger_count", 0) >= 2
            ],
        }
    summary_file = OUT_DIR / "network_summary.json"
    summary_file.write_text(json.dumps(compact_summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  Wrote network summary: {summary_file}")

    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
