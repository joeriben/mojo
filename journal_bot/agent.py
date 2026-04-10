"""Agent-Loop mit Tool-Use über OpenRouter (Claude Opus 4.6).

Der Agent:
  - bekommt im System-Prompt alle 53 Haiku-Summaries als Benjamins Werkstand
  - bekommt im User-Turn den neuen Beitrag + Enrichment (OpenAlex abstract, refs)
  - darf via read_publication() konkrete Stellen aus Benjamins Volltexten lesen
  - schließt mit submit_digest_entry() ab, liefert strukturierten Digest-Eintrag
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from journal_bot.citation_tracker import find_citations, format_for_agent
from journal_bot.enrichment import enrich
from journal_bot.llm_client import build_client
from journal_bot.settings import CORPUS_JSON, MODEL_AGENT, SUMMARIES_JSON


# ------------------------------------------------------------------ Prompt --


SYSTEM_INTRO = """Du arbeitest als wissenschaftliche Mitarbeiterin von Benjamin Jörissen
(FAU Erlangen-Nürnberg, Lehrstuhl für Pädagogik mit Schwerpunkt kulturelle Bildung).
Seine Arbeitsgebiete: ästhetische und kulturelle Bildung, Postdigitalität, generative KI
in Bildungskontexten, Cultural Resilience, digital-kulturelles Erbe, New Materialisms.

Deine Aufgabe: Du bekommst einen neu erschienenen Beitrag aus einer Zeitschrift gezeigt
und sollst einen Digest-Eintrag schreiben, der Benjamin hilft zu entscheiden, ob er den
Beitrag lesen soll, und warum bzw. warum nicht — und zwar NICHT generisch ("relevant, weil
Bildung"), sondern spezifisch in Bezug auf seine eigenen publizierten Argumentationen.

Unten folgt Benjamins Publikationsstand ab 2018, aufbereitet als faktische Kurzprofile.
Diese Kurzprofile sind ein Index, KEINE Interpretation — sie sagen Dir, WORUM es in seinen
Texten geht, nicht, was er VERTRITT. Wenn Du eine konkrete Position von Benjamin zitieren
willst, musst Du den Volltext einer seiner Publikationen mit `read_publication(pub_id)`
tatsächlich lesen. Zitiere ihn NIE aus den Kurzprofilen.
"""


SYSTEM_OUTRO = """

=== ZWEI ARTEN VON RELEVANZ ===
Benjamin interessiert sich nicht nur für Texte, die an sein eigenes Werk direkt anschließen
("inhaltliche Relevanz"), sondern auch für Beobachtungen zweiter Ordnung in seinem
**Beobachtungsfeld** ("awareness"):
- Jemand versucht eine theorieschwere Fragestellung mit computationalen/AI-Methoden.
- Jemand importiert ein Konzept aus Benjamins Feld in einen entfernten Kontext (oder umgekehrt).
- Ein empirisches Projekt macht einen methodischen Move, der im Feld neu oder ungewöhnlich ist.
- Ein Text aus einer angrenzenden Disziplin berührt Fragen, die für Benjamins Forschung
  phänomenal interessant sind, ohne dass er den Text deswegen lesen müsste.

Solche Befunde gehören ins Feld `bemerkenswert`, NICHT ins Feld `bezuege`. Sie rechtfertigen
in der Regel "scannen" oder "lesenswert", aber kein "ignorieren".

"ignorieren" ist für Texte reserviert, an denen **weder** ein inhaltlicher Anschluss **noch**
eine bemerkenswerte methodisch-phänomenale Beobachtung zu machen ist.

=== VORGEHEN ===
1. Lies den neuen Beitrag sorgfältig (Titel, Abstract, Referenzen).
2. Prüfe beides:
   (a) Gibt es inhaltliche Anschlüsse an Benjamins publizierte Arbeiten? — dafür 2–4
       Kandidaten aus der Publikationsliste wählen, Überschneidungen bei named_thinkers
       sind ein starker Hebel. Lade die Kandidaten mit `read_publication(pub_id)` und
       lies sie (ggf. mit `search_term` auf eine Stelle).
   (b) Gibt es eine Beobachtung zweiter Ordnung? Stell Dir die Frage: "Würde Benjamin das
       wissen wollen, selbst wenn er den Text nicht liest?" — methodisch, phänomenal,
       feldkonstitutiv, als Indikator für eine Entwicklung.
3. Entscheide Verdict und fülle `bezuege` **und/oder** `bemerkenswert` entsprechend.

=== REGELN ===
- Zitiere Benjamins Werk unter `bezuege` NUR, wenn Du den Volltext gelesen hast. Keine
  Hallu-Zitationen, keine Rückgriffe auf die Summaries für die Begründung.
- Wenn die gefundenen inhaltlichen Bezüge dünn sind, sag das klar ("nur schwaches topisches
  Echo zu X, kein echter Anschluss"). Benjamin bevorzugt ehrliche dünne Verbindungen
  gegenüber aufgeblasenen starken.
- `bemerkenswert` ist der richtige Ort für "interessant zu wissen, dass jemand X mit Y
  versucht". Hier brauchst Du die Volltexte nicht gelesen zu haben — es reicht, den neuen
  Beitrag und den Kontext zu verstehen.
- Sprache: Deutsch, akademisch, präzise, ohne Buzzwords und Floskeln. Keine Wertungen wie
  "wichtig", "innovativ", "spannend" ohne Begründung.
- Nimm Dir Zeit für 2–5 read_publication-Calls, wenn sie nötig sind. Kein Speed-Run.

=== BENJAMINS PUBLIKATIONSSTAND (2018+) ==="""


def build_system_prompt(summaries: dict[str, dict]) -> str:
    lines = [SYSTEM_INTRO, SYSTEM_OUTRO, ""]
    # Sortiert nach Jahr absteigend — aktuelles zuerst
    sorted_pubs = sorted(
        summaries.items(),
        key=lambda kv: (kv[1].get("year") or 0),
        reverse=True,
    )
    for pub_id, s in sorted_pubs:
        year = s.get("year") or "?"
        title = s.get("title", "").strip()
        authors = ", ".join((s.get("authors") or [])[:3])
        lines.append(f"\n--- pub_id: {pub_id} ({year}) ---")
        lines.append(f"{title}")
        if authors:
            lines.append(f"[{authors}]")
        if s.get("summary_de"):
            lines.append(s["summary_de"])
        if s.get("key_terms"):
            lines.append("Begriffe: " + "; ".join(s["key_terms"][:12]))
        if s.get("named_thinkers"):
            lines.append("Denker*innen: " + "; ".join(s["named_thinkers"][:12]))
        if s.get("methods"):
            lines.append("Methoden: " + "; ".join(s["methods"][:6]))
    return "\n".join(lines)


# ------------------------------------------------------------------- Tools --


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "read_publication",
            "description": (
                "Lädt einen Ausschnitt aus einer von Benjamins Publikationen. "
                "Nutze das, um konkrete Stellen und Argumentationen zu lesen, "
                "bevor Du sie zitierst. Ein search_term schneidet um die erste "
                "Fundstelle; ohne search_term bekommst Du den Anfang (~4k Wörter)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pub_id": {
                        "type": "string",
                        "description": "Die pub_id aus der Publikationsliste im System-Prompt.",
                    },
                    "search_term": {
                        "type": "string",
                        "description": (
                            "Optional. Begriff, Name oder kurze Phrase. Der Bot "
                            "gibt den Textausschnitt um die erste Fundstelle zurück. "
                            "Wenn der Begriff nicht vorkommt, bekommst Du den Anfang."
                        ),
                    },
                },
                "required": ["pub_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "submit_digest_entry",
            "description": (
                "Schließt den Lauf ab. Rufe das auf, wenn Du genug gelesen hast, "
                "um einen strukturierten Digest-Eintrag zu liefern."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "kernthese": {
                        "type": "string",
                        "description": (
                            "2–3 Sätze, referierend: Was behandelt der neue Beitrag, "
                            "was ist seine zentrale Aussage. Kein Urteil."
                        ),
                    },
                    "bezuege": {
                        "type": "array",
                        "description": (
                            "Konkrete Bezüge zu Publikationen, die Du GELESEN hast. "
                            "Leer, wenn Du keine substantiellen Bezüge findest."
                        ),
                        "items": {
                            "type": "object",
                            "properties": {
                                "pub_id": {"type": "string"},
                                "pub_kurz": {
                                    "type": "string",
                                    "description": "Kurzform: Autor + Jahr + Kurztitel",
                                },
                                "bezug": {
                                    "type": "string",
                                    "description": (
                                        "2–4 Sätze: Wie verhält sich der neue Beitrag "
                                        "zu dieser Publikation? Basiert auf dem Text, "
                                        "den Du mit read_publication gelesen hast."
                                    ),
                                },
                                "relation": {
                                    "type": "string",
                                    "enum": [
                                        "erweitert",
                                        "widerspricht",
                                        "parallelisiert",
                                        "importiert",
                                        "tangential",
                                    ],
                                },
                            },
                            "required": ["pub_id", "pub_kurz", "bezug", "relation"],
                        },
                    },
                    "theoretisch_methodisch": {
                        "type": "string",
                        "description": (
                            "1–3 Sätze: methodische und theoretische Einschätzung "
                            "des neuen Beitrags. Referierend, keine Wertung."
                        ),
                    },
                    "bemerkenswert": {
                        "type": "array",
                        "description": (
                            "Beobachtungen zweiter Ordnung, die Benjamin wissen möchte, "
                            "auch wenn der Text selbst nicht lesenswert ist. Jede Beobachtung "
                            "1–2 Sätze, knapp, konkret. Leer, wenn nichts Bemerkenswertes "
                            "auffällt."
                        ),
                        "items": {"type": "string"},
                    },
                    "verdict": {
                        "type": "string",
                        "enum": [
                            "pflichtlektuere",
                            "lesenswert",
                            "scannen",
                            "ignorieren",
                        ],
                    },
                    "verdict_begruendung": {
                        "type": "string",
                        "description": "1–2 Sätze: warum dieses Verdict.",
                    },
                },
                "required": [
                    "kernthese",
                    "bezuege",
                    "theoretisch_methodisch",
                    "bemerkenswert",
                    "verdict",
                    "verdict_begruendung",
                ],
            },
        },
    },
]


# ------------------------------------------------------------------ Runner --


def _load_corpus_index(corpus_path: Path) -> dict[str, dict]:
    data = json.loads(corpus_path.read_text(encoding="utf-8"))
    return {p["pub_id"]: p for p in data["publications"]}


def _load_authored_all(corpus_path: Path) -> list[dict]:
    data = json.loads(corpus_path.read_text(encoding="utf-8"))
    return data.get("authored_all", [])


def handle_read_publication(
    corpus_index: dict[str, dict],
    pub_id: str,
    search_term: str = "",
) -> str:
    if pub_id not in corpus_index:
        return f"[FEHLER] pub_id {pub_id!r} nicht im Corpus gefunden."
    pub = corpus_index[pub_id]
    fulltext = pub.get("fulltext", "")
    if not fulltext:
        return f"[FEHLER] Kein Volltext für {pub_id} ({pub.get('title', '')[:80]})."

    title = pub.get("title", "")
    year = pub.get("year", "")
    header = f"[Publikation {pub_id} — {title} ({year})]\n\n"

    if search_term:
        lower_text = fulltext.lower()
        lower_term = search_term.lower()
        idx = lower_text.find(lower_term)
        if idx >= 0:
            start = max(0, idx - 1800)
            end = min(len(fulltext), idx + 4200)
            snippet = fulltext[start:end]
            prefix = "… " if start > 0 else ""
            suffix = " …" if end < len(fulltext) else ""
            return (
                f"{header}[Ausschnitt um '{search_term}' — "
                f"Zeichen {start}–{end} von {len(fulltext)}]\n\n"
                f"{prefix}{snippet}{suffix}"
            )
        # Term nicht gefunden: wir sagen das ehrlich
        header += f"[Hinweis: '{search_term}' nicht im Text gefunden, gebe Anfang zurück]\n\n"

    # Default: Anfang
    return header + fulltext[:16000] + (" …" if len(fulltext) > 16000 else "")


def run_agent(
    new_article: dict,
    corpus_path: Path = CORPUS_JSON,
    summaries_path: Path = SUMMARIES_JSON,
    model: str = MODEL_AGENT,
    max_iterations: int = 8,
    verbose: bool = True,
) -> dict:
    """new_article: dict mit title, authors, abstract, doi, url, journal."""
    corpus_index = _load_corpus_index(corpus_path)
    authored_all = _load_authored_all(corpus_path)
    summaries_data = json.loads(summaries_path.read_text(encoding="utf-8"))
    summaries = summaries_data["summaries"]

    system_prompt = build_system_prompt(summaries)
    if verbose:
        print(f"[agent] System-Prompt: ~{len(system_prompt)//4} Tokens "
              f"({len(summaries)} Publikationen im Index)")

    doi = (new_article.get("doi") or "").strip()
    enrichment_data = enrich(doi) if doi else {}

    # Citation-Tracker: Jörissen-Zitate in den Refs finden
    citation_hits = find_citations(
        enrichment_data.get("references_crossref") or [],
        authored_all,
    )
    if verbose:
        if citation_hits:
            high = sum(1 for h in citation_hits if h.confidence == "high")
            print(f"[agent] Zitationstreffer: {len(citation_hits)} "
                  f"(davon {high} mit hoher Confidence)")
        else:
            print(f"[agent] Keine Jörissen-Zitate in den Refs")

    citations_block = format_for_agent(citation_hits)
    user_content = _format_new_article(new_article, enrichment_data) + citations_block
    if verbose:
        print(f"[agent] User-Content: ~{len(user_content)//4} Tokens")

    client = build_client()

    # System-Prompt als cache-fähigen Content-Block (Anthropic ephemeral cache
    # über OpenRouter). 5-Minuten-TTL reicht für Multi-Iter-Läufe und Batches.
    messages: list[dict[str, Any]] = [
        {
            "role": "system",
            "content": [
                {
                    "type": "text",
                    "text": system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
        },
        {"role": "user", "content": user_content},
    ]

    final_entry: dict | None = None
    tool_call_log: list[dict] = []
    total_in = 0
    total_out = 0
    total_cached_read = 0
    total_cache_write = 0
    total_cost_usd = 0.0

    for it in range(1, max_iterations + 1):
        if verbose:
            print(f"\n[agent] --- Iteration {it} ---")

        resp = client.chat.completions.create(
            model=model,
            max_tokens=4000,
            messages=messages,
            tools=TOOLS,
        )
        usage = getattr(resp, "usage", None)
        if usage:
            total_in += usage.prompt_tokens or 0
            total_out += usage.completion_tokens or 0
            # OpenRouter-spezifische Extras im usage-Dump
            usage_dump = usage.model_dump() if hasattr(usage, "model_dump") else {}
            pd = usage_dump.get("prompt_tokens_details") or {}
            total_cached_read += pd.get("cached_tokens") or 0
            total_cache_write += pd.get("cache_write_tokens") or 0
            total_cost_usd += usage_dump.get("cost") or 0.0
            if verbose and (pd.get("cached_tokens") or pd.get("cache_write_tokens")):
                print(
                    f"[agent] cache: read={pd.get('cached_tokens', 0)}, "
                    f"write={pd.get('cache_write_tokens', 0)}"
                )

        msg = resp.choices[0].message
        finish = resp.choices[0].finish_reason
        if verbose:
            if msg.content:
                print(f"[agent] Claude: {msg.content[:500]}")
            print(f"[agent] finish={finish}")

        tool_calls = getattr(msg, "tool_calls", None) or []

        if not tool_calls:
            if verbose:
                print("[agent] Keine Tool-Calls — Lauf endet.")
            break

        # Assistant-Nachricht mit Tool-Calls ins Transcript
        messages.append(
            {
                "role": "assistant",
                "content": msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in tool_calls
                ],
            }
        )

        # Tool-Calls abarbeiten
        for tc in tool_calls:
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments)
            except Exception as e:
                result = f"[FEHLER beim Args-Parse] {e}"
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
                continue

            if verbose:
                args_preview = json.dumps(args, ensure_ascii=False)[:200]
                print(f"[agent] → {name}({args_preview})")

            if name == "read_publication":
                result = handle_read_publication(
                    corpus_index,
                    pub_id=args.get("pub_id", ""),
                    search_term=args.get("search_term", ""),
                )
                tool_call_log.append(
                    {"tool": name, "pub_id": args.get("pub_id"),
                     "search_term": args.get("search_term", ""), "chars": len(result)}
                )
                messages.append(
                    {"role": "tool", "tool_call_id": tc.id, "content": result}
                )
            elif name == "submit_digest_entry":
                final_entry = args
                tool_call_log.append({"tool": name})
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": "Digest-Eintrag empfangen. Lauf beendet.",
                    }
                )
            else:
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": f"[FEHLER] Unbekanntes Tool: {name}",
                    }
                )

        if final_entry is not None:
            break

    # OpenRouter liefert tatsächliche Kosten, wir nehmen die statt Schätzung.
    # Fallback auf manuelle Schätzung, wenn cost-Feld fehlt.
    actual_or_estimated = total_cost_usd if total_cost_usd > 0 else (
        (total_in / 1_000_000) * 15.0 + (total_out / 1_000_000) * 75.0
    )

    return {
        "entry": final_entry,
        "iterations": it,
        "tool_calls": tool_call_log,
        "new_article": new_article,
        "enrichment": enrichment_data,
        "citation_hits": [h.__dict__ for h in citation_hits],
        "tokens_in": total_in,
        "tokens_out": total_out,
        "tokens_cached_read": total_cached_read,
        "tokens_cache_write": total_cache_write,
        "est_cost_usd": actual_or_estimated,
    }


def _format_new_article(article: dict, enrichment: dict) -> str:
    parts = ["=== NEUER BEITRAG ===\n"]
    parts.append(f"Journal:   {article.get('journal', '')}")
    parts.append(f"Titel:     {article.get('title', '')}")
    parts.append(f"Autor*innen: {', '.join(article.get('authors') or []) or '(unbekannt)'}")
    parts.append(f"DOI:       {article.get('doi', '') or '(kein DOI)'}")
    parts.append(f"URL:       {article.get('url', '')}")
    parts.append("")
    parts.append("Abstract (aus Feed):")
    parts.append(article.get("abstract", "") or "(leer)")

    oa = (enrichment or {}).get("openalex") or {}
    if oa.get("abstract"):
        parts.append("\nAbstract (aus OpenAlex, meist vollständiger):")
        parts.append(oa["abstract"][:4000])
    if oa.get("topics"):
        parts.append("\nOpenAlex-Topics: " + "; ".join(t["name"] for t in oa["topics"][:5]))
    if oa.get("concepts"):
        parts.append("OpenAlex-Concepts: " + "; ".join(c["name"] for c in oa["concepts"][:10]))

    refs = (enrichment or {}).get("references_crossref") or []
    if refs:
        parts.append(f"\nLiteraturverzeichnis ({len(refs)} Einträge, erste 40):")
        for r in refs[:40]:
            authors = ", ".join(r.get("authors") or [])
            year = r.get("year", "")
            title = r.get("title", "") or r.get("raw", "")
            parts.append(f"  · {year} {authors} — {title[:160]}")

    return "\n".join(parts)


# ------------------------------------------------------------- Rendering ---


VERDICT_LABEL = {
    "pflichtlektuere": "PFLICHTLEKTÜRE",
    "lesenswert":      "LESENSWERT",
    "scannen":         "SCANNEN",
    "ignorieren":      "IGNORIEREN",
}

RELATION_LABEL = {
    "erweitert":       "erweitert",
    "widerspricht":    "widerspricht",
    "parallelisiert":  "parallel",
    "importiert":      "import",
    "tangential":      "tangential",
}


def render_markdown(result: dict) -> str:
    article = result["new_article"]
    entry = result.get("entry")
    lines: list[str] = []

    title = article.get("title") or "(ohne Titel)"
    lines.append(f"## {title}")
    meta_bits: list[str] = []
    if article.get("authors"):
        meta_bits.append(", ".join(article["authors"]))
    if article.get("journal"):
        meta_bits.append(article["journal"])
    if article.get("doi"):
        meta_bits.append(f"doi:{article['doi']}")
    if meta_bits:
        lines.append("_" + " · ".join(meta_bits) + "_")
    if article.get("url"):
        lines.append(f"{article['url']}")
    lines.append("")

    if not entry:
        lines.append(
            f"(Agent hat nach {result['iterations']} Iterationen keinen "
            f"submit_digest_entry erreicht.)"
        )
        return "\n".join(lines)

    label = VERDICT_LABEL.get(entry.get("verdict", ""), entry.get("verdict", "?"))
    lines.append(f"**Verdict:** {label} — {entry.get('verdict_begruendung', '')}")
    lines.append("")

    # Zitationstreffer (wenn vorhanden) direkt nach dem Verdict sichtbar machen
    citation_hits = result.get("citation_hits") or []
    high = [h for h in citation_hits if h.get("confidence") == "high"]
    med = [h for h in citation_hits if h.get("confidence") == "medium"]
    low = [h for h in citation_hits if h.get("confidence") == "low"]
    if high or med or low:
        lines.append("### Zitiert Dich")
        if high:
            for h in high:
                authors = ", ".join(h.get("pub_authors", [])[:2]) or "?"
                lines.append(
                    f"- **{authors}** ({h.get('pub_year')}): "
                    f"{h.get('pub_title', '')[:100]} · `{h.get('pub_id')}`"
                )
        if med:
            for h in med:
                authors = ", ".join(h.get("pub_authors", [])[:2]) or "?"
                lines.append(
                    f"- _(wahrscheinlich)_ **{authors}** ({h.get('pub_year')}): "
                    f"{h.get('pub_title', '')[:100]} · `{h.get('pub_id')}`"
                )
        if low:
            lines.append(
                f"- _(unspezifische Jörissen-Erwähnung in {len(low)} Ref(s) "
                f"ohne Jahr/Titel-Match)_"
            )
        lines.append("")

    lines.append("### Kernthese")
    lines.append(entry.get("kernthese", ""))
    lines.append("")

    bezuege = entry.get("bezuege") or []
    lines.append("### Bezüge zu Deinem Werk")
    if not bezuege:
        lines.append("_Keine substantiellen Bezüge gefunden._")
    else:
        for b in bezuege:
            rel = RELATION_LABEL.get(b.get("relation", ""), b.get("relation", ""))
            lines.append(f"\n**{b.get('pub_kurz', '?')}** (`{b.get('pub_id', '?')}`, {rel})")
            lines.append(b.get("bezug", ""))
    lines.append("")

    bemerkenswert = entry.get("bemerkenswert") or []
    if bemerkenswert:
        lines.append("### Bemerkenswert")
        for note in bemerkenswert:
            lines.append(f"- {note}")
        lines.append("")

    lines.append("### Methodisch / theoretisch")
    lines.append(entry.get("theoretisch_methodisch", ""))
    lines.append("")

    # Footer: Meta
    lines.append("---")
    reads = sum(1 for t in result["tool_calls"] if t["tool"] == "read_publication")
    cache_read = result.get("tokens_cached_read", 0) or 0
    cache_write = result.get("tokens_cache_write", 0) or 0
    cache_bit = ""
    if cache_read or cache_write:
        cache_bit = f" · cache: {cache_read:,} read / {cache_write:,} write"
    foot = (
        f"_{result['iterations']} Agent-Iterationen · "
        f"{reads} Volltext-Reads · "
        f"{result['tokens_in']:,} in / {result['tokens_out']:,} out"
        f"{cache_bit} · "
        f"${result['est_cost_usd']:.3f}_"
    )
    lines.append(foot)
    return "\n".join(lines)
