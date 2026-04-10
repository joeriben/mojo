"""Trend-Analyse über articles.db.

Liest alle Artikel im Zeitfenster, baut eine kompakte Input-Struktur
(Titel + Autoren + Abstract + OpenAlex-Concepts/Topics + agent_verdict falls vorhanden),
schickt sie an Opus mit einem strukturierten Trend-Analyse-Auftrag,
schreibt Dossier nach Obsidian.

Kein Halluzinations-Risiko im Stil von Bezügen-zur-eigenen-Arbeit: Der Agent
sieht NUR die gefetchten Artikel, nicht Benjamins Werk. Zweck ist die
Beobachtung des Feldes, nicht die Verortung des einzelnen Beitrags.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from journal_bot.llm_client import build_client
from journal_bot.settings import (
    DIGEST_DIR,
    DISCOURSE_SPACES,
    MODEL_AGENT,
    journals_in_cluster,
)
from journal_bot.store import Store, StoredArticle


SYSTEM_PROMPT = """Du bist wissenschaftliche Mitarbeiterin mit Fachkenntnis in der
deutschsprachigen Erziehungswissenschaft, insbesondere in kultureller Bildung,
ästhetischer Bildung, Postdigitalität, Medienpädagogik und KI-bezogenen
Bildungsdiskursen.

Du bekommst eine Liste neu erschienener Zeitschriftenbeiträge aus einem definierten
**Diskursraum** ({cluster_name}) — eine bewusst kuratierte Auswahl von Journals, die
miteinander in inhaltlichem Zusammenhang stehen ({cluster_description}). Deine
Aufgabe ist explizit NICHT, fachfremde Diskurse aufeinander zu projizieren, sondern
die Bewegungen INNERHALB dieses einen Feldes zu kartieren.

Dein Auftrag: **Identifiziere die tatsächlichen thematischen Bewegungen im Feld.**
Keine abstrakten Cluster-Übungen, sondern: "Was hat das Feld umgetrieben?
Welche Diskurse konsolidieren sich? Welche gehen zurück? Welche neuen Gegenstände
tauchen auf?"

Regeln:
- **Konkret bleiben**: Jede Trend-Beobachtung muss mit 2–5 konkreten Beiträgen belegt
  werden. Nenne Titel und Jahr bzw. die Artikel-IDs.
- **Keine Buzzwords** ("spannende Entwicklung", "vielfältiges Feld", "innovativer
  Diskurs"). Statt dessen: Welche begrifflichen Verschiebungen? Welche Kontroversen?
  Welche Autor*innen prägen welche Positionen?
- **Konvergenz, Differenzierung, Ausreißer**: unterscheide zwischen Beiträgen, die
  auf gemeinsame Konzepte hinarbeiten, Beiträgen, die denselben Gegenstand aus
  divergierenden Perspektiven angreifen, und echten Ausreißern (thematisch oder
  methodisch nicht eingebettet).
- **Methodische Beobachtungen**: wenn auffällt, dass ein methodischer Move sich
  häuft (z.B. computerlinguistische Verfahren, Literacy-Frameworks, Multi-Author-
  Kollaborationen), benenne das.
- **Länge**: das gesamte Dossier soll ungefähr 800–1500 Wörter umfassen, klare
  Abschnitte, keine Prosa-Wüste.

Struktur der Ausgabe (Markdown):

# Trendbeobachtung: {cluster_name} ({window})

## Überblick
_2–4 Sätze: Umfang des Fensters, grobe Verteilung über Journals und Jahre, was
beim ersten Durchgang besonders auffällt._

## Konsolidierende Diskurse
_Cluster, die mit mehreren Beiträgen vertreten sind und in eine erkennbare
gemeinsame Richtung arbeiten. Pro Cluster: Name/Charakterisierung, 3–5 belegende
Beiträge als Bulletpoint (Kurztitel + Jahr + ID), 2–4 Sätze was den Cluster
auszeichnet._

## Differenzierungen und offene Spannungen
_Gegenstände, zu denen mehrere Beiträge erscheinen, die aber divergieren.
Beispielhaft belegt._

## Methodische Beobachtungen
_Auffälligkeiten in der Methodenwahl, Formatwahl (z.B. kollaborative
Mehrautor-Texte), Datenarten._

## Ausreißer und Einzelgänger
_Beiträge, die thematisch oder methodisch nicht ins Feld eingebettet sind,
aber interessant genug, um erwähnt zu werden._

## Absenzen (optional)
_Wenn auffällt, dass ein zentrales Thema des Fachs fehlt oder unterbelichtet ist,
kurz benennen — ohne zu spekulieren._
"""


def _format_article_for_llm(sa: StoredArticle, index: int) -> str:
    lines = [f"--- [{index}] id={sa.id[:12]} ---"]
    lines.append(f"Journal: {sa.journal_short} ({sa.journal_full})")
    lines.append(f"Jahr:    {sa.year or '?'}")
    lines.append(f"Titel:   {sa.title}")
    if sa.authors:
        authors = ", ".join(sa.authors[:5])
        if len(sa.authors) > 5:
            authors += f", +{len(sa.authors) - 5} weitere"
        lines.append(f"Autoren: {authors}")
    abstract = sa.openalex_abstract or sa.abstract or ""
    if abstract:
        lines.append(f"Abstract: {abstract[:1200]}")
    if sa.openalex_concepts:
        names = ", ".join(c.get("name", "") for c in sa.openalex_concepts[:6] if c.get("name"))
        if names:
            lines.append(f"OpenAlex-Concepts: {names}")
    if sa.openalex_topics:
        names = ", ".join(t.get("name", "") for t in sa.openalex_topics[:3] if t.get("name"))
        if names:
            lines.append(f"OpenAlex-Topics: {names}")
    if sa.agent_verdict:
        lines.append(f"Mein Verdict (früher): {sa.agent_verdict}")
    return "\n".join(lines)


def run(
    cluster: str,
    window_years: int = 3,
    journals: list[str] | None = None,
    verbose: bool = True,
    out_dir: Path = DIGEST_DIR,
) -> dict:
    """Trend-Analyse für einen Diskursraum.

    cluster: Schlüssel aus DISCOURSE_SPACES (z.B. 'digitale_kultur').
    journals: optionaler Override — explizite Journal-Short-Liste statt Cluster.
    """
    store = Store()

    # Cluster auflösen, wenn keine explizite Journal-Liste übergeben wurde
    if journals is None:
        if cluster not in DISCOURSE_SPACES:
            raise ValueError(
                f"Unbekannter Cluster {cluster!r}. "
                f"Verfügbar: {list(DISCOURSE_SPACES.keys())}"
            )
        cluster_meta = DISCOURSE_SPACES[cluster]
        journals = [j.short for j in journals_in_cluster(cluster)]
        if not journals:
            raise ValueError(f"Cluster {cluster!r} enthält keine aktiven Journals.")
    else:
        cluster_meta = {
            "name": f"Custom: {', '.join(journals)}",
            "description": "Explizit ausgewählte Journal-Menge ohne Diskursraum-Zuordnung.",
        }

    this_year = datetime.now().year
    start_year = this_year - window_years + 1
    articles = store.find_in_window(
        start_year=start_year,
        journals=journals,
    )
    articles = [
        a for a in articles
        if a.title and (a.openalex_abstract or a.abstract)
    ]

    if verbose:
        print(f"[trends] Cluster:     {cluster_meta['name']}")
        print(f"[trends] Fenster:     {start_year}–{this_year}")
        print(f"[trends] Journals:    {', '.join(journals)}")
        print(f"[trends] Artikel mit Abstract: {len(articles)}")

    if len(articles) < 5:
        print(f"[trends] Zu wenige Artikel ({len(articles)}) für sinnvolle Trend-Analyse.")
        print(f"[trends] Mindestens 5 nötig. Tipp: öfter fetchen oder Fenster erweitern.")
        return {"status": "too_few", "count": len(articles)}

    journal_list = ", ".join(sorted(set(a.journal_short for a in articles)))
    window_label = f"{start_year}–{this_year}"

    parts = [
        f"DISKURSRAUM:   {cluster_meta['name']}",
        f"BESCHREIBUNG:  {cluster_meta['description']}",
        f"ZEITFENSTER:   {window_label}",
        f"JOURNALS:      {journal_list}",
        f"ARTIKELANZAHL: {len(articles)}",
        "",
        "=== ARTIKEL ===",
    ]
    for i, sa in enumerate(articles, 1):
        parts.append("")
        parts.append(_format_article_for_llm(sa, i))

    user_content = "\n".join(parts)
    if verbose:
        print(f"[trends] User-Content: ~{len(user_content)//4} Tokens")

    # LLM-Call (kein Tool-Use, direkt Markdown als Antwort)
    client = build_client()
    resp = client.chat.completions.create(
        model=MODEL_AGENT,
        max_tokens=5000,
        messages=[
            {
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": SYSTEM_PROMPT.format(
                            cluster_name=cluster_meta["name"],
                            cluster_description=cluster_meta["description"],
                            window=window_label,
                        ),
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
            },
            {"role": "user", "content": user_content},
        ],
    )

    md = resp.choices[0].message.content or ""
    usage = resp.usage
    usage_dump = usage.model_dump() if hasattr(usage, "model_dump") else {}
    cost = usage_dump.get("cost") or 0.0
    pd = usage_dump.get("prompt_tokens_details") or {}

    if verbose:
        print(f"[trends] Tokens: {usage.prompt_tokens} in / {usage.completion_tokens} out")
        print(f"[trends] Kosten: ${cost:.3f}")

    # Footer anhängen
    footer = (
        f"\n\n---\n_Cluster: {cluster_meta['name']} · Fenster: {window_label} · "
        f"{len(articles)} Artikel aus {journal_list} · "
        f"{usage.prompt_tokens:,} in / {usage.completion_tokens:,} out · ${cost:.3f}_\n"
    )
    full_md = md + footer

    # Schreiben
    trends_dir = out_dir / "trends"
    trends_dir.mkdir(parents=True, exist_ok=True)
    cluster_slug = cluster.replace(" ", "_")
    filename = f"trends_{date.today().isoformat()}_{cluster_slug}_{window_label}.md"
    out_path = trends_dir / filename
    out_path.write_text(full_md, encoding="utf-8")
    if verbose:
        print(f"[trends] Geschrieben: {out_path}")

    return {
        "status": "ok",
        "path": str(out_path),
        "count": len(articles),
        "cost_usd": cost,
    }
