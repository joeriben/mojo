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
from journal_bot.settings import (
    CORPUS_JSON, MODEL_AGENT, MODEL_SUMMARIZE, SUMMARIES_JSON,
    RESEARCHER_AREAS, RESEARCHER_INSTITUTION, RESEARCHER_NAME,
    RESEARCHER_TRIAGE_TOPICS,
)


# ------------------------------------------------------------------ Prompt --


SYSTEM_INTRO = f"""Du arbeitest als wissenschaftliche Mitarbeiterin von {RESEARCHER_NAME}
({RESEARCHER_INSTITUTION}).
Arbeitsgebiete: {RESEARCHER_AREAS}.

Deine Aufgabe: Du bekommst einen neu erschienenen Beitrag aus einer Zeitschrift gezeigt
und sollst einen Digest-Eintrag schreiben, der {RESEARCHER_NAME} hilft zu entscheiden,
ob der Beitrag gelesen werden soll, und warum bzw. warum nicht — und zwar NICHT generisch
("relevant, weil Bildung"), sondern spezifisch in Bezug auf die eigenen publizierten
Argumentationen.

Unten folgt der Publikationsstand ab 2018, aufbereitet als faktische Kurzprofile.
Diese Kurzprofile sind ein Index, KEINE Interpretation — sie sagen Dir, WORUM es in den
Texten geht, nicht, was VERTRETEN wird. Wenn Du eine konkrete Position zitieren willst,
musst Du den Volltext mit `read_publication(pub_id)` tatsächlich lesen.
Zitiere NIE aus den Kurzprofilen.
"""


SYSTEM_OUTRO = f"""

=== ZWEI ARTEN VON RELEVANZ ===
Es geht nicht nur um Texte, die an das eigene Werk direkt anschließen ("inhaltliche
Relevanz"), sondern auch um Beobachtungen zweiter Ordnung im **Beobachtungsfeld**
("awareness"):
- Jemand versucht eine theorieschwere Fragestellung mit computationalen/AI-Methoden.
- Jemand importiert ein Konzept aus dem eigenen Feld in einen entfernten Kontext (oder umgekehrt).
- Ein empirisches Projekt macht einen methodischen Move, der im Feld neu oder ungewöhnlich ist.
- Ein Text aus einer angrenzenden Disziplin berührt Fragen, die für die eigene Forschung
  phänomenal interessant sind, ohne dass der Text deswegen gelesen werden müsste.

Solche Befunde gehören ins Feld `bemerkenswert`, NICHT ins Feld `bezuege`. Sie rechtfertigen
in der Regel "scannen" oder "lesenswert", aber kein "ignorieren".

"ignorieren" ist für Texte reserviert, an denen **weder** ein inhaltlicher Anschluss **noch**
eine bemerkenswerte methodisch-phänomenale Beobachtung zu machen ist.

=== VORGEHEN ===
1. Lies den neuen Beitrag sorgfältig (Titel, Abstract, Referenzen).
2. **Sofort-Entscheidung**: Wenn nach Schritt 1 klar ist, dass der Beitrag weder
   inhaltliche Anschlüsse noch bemerkenswerte Beobachtungen bietet — rufe SOFORT
   `submit_digest_entry` mit verdict="ignorieren" auf. Minimaler Output:
   kernthese 1 Satz, leere bezuege, leere bemerkenswert. KEIN `read_publication`.
   Das spart Zeit und Kosten. Typische Fälle: reine Psychometrie, klinische Studien,
   angewandte Didaktik ohne theoretischen Anschluss, Berufsethik ohne Bildungsbezug.
3. Wenn potenziell relevant, prüfe beides:
   (a) Gibt es inhaltliche Anschlüsse an die publizierten Arbeiten? — dafür 2–4
       Kandidaten aus der Publikationsliste wählen, Überschneidungen bei named_thinkers
       sind ein starker Hebel. Lade die Kandidaten mit `read_publication(pub_id)` und
       lies sie (ggf. mit `search_term` auf eine Stelle).
   (b) Gibt es eine Beobachtung zweiter Ordnung? Stell Dir die Frage: "Würde
       {RESEARCHER_NAME} das wissen wollen, selbst wenn der Text nicht gelesen wird?"
       — methodisch, phänomenal, feldkonstitutiv, als Indikator für eine Entwicklung.
4. Entscheide Verdict und fülle `bezuege` **und/oder** `bemerkenswert` entsprechend.

=== REGELN ===
- Zitiere das Werk unter `bezuege` NUR, wenn Du den Volltext gelesen hast. Keine
  Hallu-Zitationen, keine Rückgriffe auf die Summaries für die Begründung.
- Wenn die gefundenen inhaltlichen Bezüge dünn sind, sag das klar ("nur schwaches topisches
  Echo zu X, kein echter Anschluss"). Ehrliche dünne Verbindungen werden gegenüber
  aufgeblasenen starken bevorzugt.
- `bemerkenswert` ist der richtige Ort für "interessant zu wissen, dass jemand X mit Y
  versucht". Hier brauchst Du die Volltexte nicht gelesen zu haben — es reicht, den neuen
  Beitrag und den Kontext zu verstehen.
- Sprache: Deutsch, akademisch, präzise, ohne Buzzwords und Floskeln. Keine Wertungen wie
  "wichtig", "innovativ", "spannend" ohne Begründung.
- Nimm Dir Zeit für 2–5 read_publication-Calls, wenn sie nötig sind. Kein Speed-Run.

=== PUBLIKATIONSSTAND (2018+) ==="""


def build_system_prompt(summaries: dict[str, dict], outro: str | None = None) -> str:
    lines = [SYSTEM_INTRO, outro or SYSTEM_OUTRO, ""]
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
                "Lädt einen Ausschnitt aus einer Publikation des Forschers. "
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
                            "Beobachtungen zweiter Ordnung, die der/die Forscher*in wissen möchte, "
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
                    "candidate_reads": {
                        "type": "array",
                        "description": (
                            "NUR in der Assessment-Phase: Publikationen, deren "
                            "Volltext gelesen werden müsste, um bezuege zu "
                            "verifizieren. Leer lassen wenn keine Verifikation "
                            "nötig oder wenn Volltext bereits gelesen wurde."
                        ),
                        "items": {
                            "type": "object",
                            "properties": {
                                "pub_id": {
                                    "type": "string",
                                    "description": "pub_id aus der Publikationsliste.",
                                },
                                "search_term": {
                                    "type": "string",
                                    "description": (
                                        "Konkreter Begriff/Phrase, nach dem im "
                                        "Volltext gesucht werden soll."
                                    ),
                                },
                                "hypothesis": {
                                    "type": "string",
                                    "description": (
                                        "1 Satz: Welchen Bezug vermutest Du?"
                                    ),
                                },
                            },
                            "required": ["pub_id", "search_term", "hypothesis"],
                        },
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


# ----------------------------------------------------------------- Triage --

_triage_topics = "\n".join(f"- {t}" for t in RESEARCHER_TRIAGE_TOPICS)
TRIAGE_PROMPT = f"""Du bist ein Vorfilter für einen Forschungs-Digest.

{RESEARCHER_NAME} ({RESEARCHER_INSTITUTION}) arbeitet zu:
{_triage_topics}

Du bekommst Titel, Abstract und Journal eines neuen Beitrags.
Entscheide: Könnte dieser Beitrag relevant sein?

Antworte NUR mit einem JSON-Objekt:
{{"triage": "relevant", "grund": "..."}} — wenn es inhaltliche oder methodische Berührungspunkte geben KÖNNTE (auch entfernte)
{{"triage": "ignorieren", "grund": "..."}} — wenn der Beitrag offensichtlich thematisch keine Berührung hat

Im Zweifel: "relevant". Lieber einen irrelevanten Artikel durchlassen als einen relevanten verpassen."""


def triage_article(
    article: dict,
    model: str = MODEL_SUMMARIZE,
    verbose: bool = True,
) -> dict:
    """Haiku-Vorfilter: entscheidet ob ein Artikel den Opus-Agenten braucht.

    Returns dict with keys: triage ("relevant"|"ignorieren"), grund, cost_usd.
    """
    client = build_client()
    user_msg = (
        f"Journal: {article.get('journal', '')}\n"
        f"Titel: {article.get('title', '')}\n"
        f"Abstract: {(article.get('abstract') or '(kein Abstract)')[:2000]}"
    )
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": TRIAGE_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        max_tokens=200,
        temperature=0.0,
    )
    raw = resp.choices[0].message.content.strip()
    cost = 0.0
    if resp.usage:
        # Haiku pricing: ~$0.80/M input, $4/M output via OpenRouter
        cost = (resp.usage.prompt_tokens / 1_000_000) * 0.80 + (
            resp.usage.completion_tokens / 1_000_000
        ) * 4.0

    # Parse JSON from response
    result = None
    # Try 1: direct parse
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        pass
    # Try 2: extract between first { and last }
    if result is None:
        first = raw.find("{")
        last = raw.rfind("}")
        if first >= 0 and last > first:
            try:
                result = json.loads(raw[first:last + 1])
            except json.JSONDecodeError:
                pass
    if result is None or not isinstance(result, dict):
        result = {"triage": "relevant", "grund": f"(Triage-Parse-Fehler: {raw[:100]})"}

    result["cost_usd"] = cost
    if verbose:
        print(f"[triage] {result['triage']} — {result.get('grund', '')[:80]}  (${cost:.4f})")
    return result


# ---------------------------------------------------------- Batch Screening --

MODEL_SCREEN = "deepseek/deepseek-v3.2"

SCREENING_SUFFIX = f"""

=== SCREENING-MODUS ===
Du bekommst jetzt eine LISTE von Artikeln (Titel, Journal, Abstract-Auszug).
Für jeden Artikel: Entscheide, ob er potenziell relevant sein KÖNNTE
und daher eine vollständige Analyse verdient.

Antworte mit GENAU einer Zeile pro Artikel im Format:
[ID] weitergeben|ignorieren — Grund in ≤15 Worten

"weitergeben" wenn:
- Inhaltliche Berührungspunkte mit den Themen/Positionen erkennbar
- Methodisch/phänomenal bemerkenswert für das Beobachtungsfeld
- Zitiert {RESEARCHER_NAME} oder zitiert Werke aus der Bibliothek

"ignorieren" wenn:
- Offensichtlich kein Bezug zur Forschung
- Rein empirisch/angewandt ohne theoretischen Anschluss an die Themen
- Thematisch in einem Feld ohne Berührung (z.B. reine Psychometrie, Pflegedidaktik)

Im Zweifel: weitergeben. Lieber einen irrelevanten durchlassen als einen relevanten verpassen.
Keine Erklärung, keine Einleitung, nur die Zeilen."""


def batch_screen(
    articles: list[dict],
    summaries_path: Path = SUMMARIES_JSON,
    model: str = MODEL_SCREEN,
    batch_size: int = 25,
    verbose: bool = True,
) -> dict[str, dict]:
    """Batch screening: cheap model with cached system prompt, one verdict per article.

    articles: list of dicts with keys: id, title, journal, abstract (or openalex_abstract).
    Returns: dict of article_id -> {"verdict": "weitergeben"|"ignorieren", "grund": str}.
    """
    summaries_data = json.loads(summaries_path.read_text(encoding="utf-8"))
    system_prompt = build_system_prompt(summaries_data["summaries"]) + SCREENING_SUFFIX

    client = build_client()
    all_results: dict[str, dict] = {}
    total_cost = 0.0

    for i in range(0, len(articles), batch_size):
        batch = articles[i:i + batch_size]
        batch_num = i // batch_size + 1

        # Format batch
        lines = []
        for a in batch:
            abstract = (a.get("openalex_abstract") or a.get("abstract") or "")[:500]
            lines.append(
                f"[{a['id'][:8]}] {a.get('journal', '')} | {a.get('title', '')}\n"
                f"  Abstract: {abstract}\n"
            )
        user_msg = "\n".join(lines)

        if verbose:
            print(f"[screen] Batch {batch_num}: {len(batch)} Artikel, "
                  f"~{len(user_msg) // 4} User-Tokens")

        resp = client.chat.completions.create(
            model=model,
            messages=[
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
                {"role": "user", "content": user_msg},
            ],
            max_tokens=2000,
            temperature=0.0,
        )

        raw = resp.choices[0].message.content or ""
        usage = getattr(resp, "usage", None)
        cost = 0.0
        if usage:
            usage_dump = usage.model_dump() if hasattr(usage, "model_dump") else {}
            cost = usage_dump.get("cost") or 0.0
        total_cost += cost

        # Parse response
        valid_ids = {a["id"]: a["id"][:8] for a in batch}
        short_to_full = {v: k for k, v in valid_ids.items()}

        for line in raw.strip().split("\n"):
            line = line.strip()
            if not line or not line.startswith("["):
                continue
            bracket_end = line.find("]")
            if bracket_end < 0:
                continue
            short_id = line[1:bracket_end].strip()
            rest = line[bracket_end + 1:].strip()

            verdict = "weitergeben"  # default: pass through
            if rest.startswith("ignorieren") or rest.startswith("ignor"):
                verdict = "ignorieren"

            full_id = short_to_full.get(short_id)
            if full_id:
                grund = rest.split("—", 1)[1].strip() if "—" in rest else rest[:80]
                all_results[full_id] = {"verdict": verdict, "grund": grund}

        parsed = sum(1 for a in batch if a["id"] in all_results)
        if verbose:
            print(f"[screen] → {parsed}/{len(batch)} geparst, ${cost:.4f}")

    # Articles not in results default to "weitergeben"
    for a in articles:
        if a["id"] not in all_results:
            all_results[a["id"]] = {
                "verdict": "weitergeben",
                "grund": "(nicht im Screening-Output, default: weitergeben)",
            }

    if verbose:
        passed = sum(1 for r in all_results.values() if r["verdict"] == "weitergeben")
        filtered = sum(1 for r in all_results.values() if r["verdict"] == "ignorieren")
        print(f"[screen] Gesamt: {passed} weitergeben, {filtered} ignorieren, "
              f"${total_cost:.4f}")

    return all_results


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


TOOLS_SUBMIT_ONLY = [t for t in TOOLS if t["function"]["name"] == "submit_digest_entry"]


# ------------------------------------------------- Assessment-Phase Prompt --


ASSESSMENT_OUTRO = f"""

=== ZWEI ARTEN VON RELEVANZ ===
Es geht nicht nur um Texte, die an das eigene Werk direkt anschließen ("inhaltliche
Relevanz"), sondern auch um Beobachtungen zweiter Ordnung im **Beobachtungsfeld**
("awareness"):
- Jemand versucht eine theorieschwere Fragestellung mit computationalen/AI-Methoden.
- Jemand importiert ein Konzept aus dem eigenen Feld in einen entfernten Kontext (oder umgekehrt).
- Ein empirisches Projekt macht einen methodischen Move, der im Feld neu oder ungewöhnlich ist.
- Ein Text aus einer angrenzenden Disziplin berührt Fragen, die für die eigene Forschung
  phänomenal interessant sind, ohne dass der Text deswegen gelesen werden müsste.

Solche Befunde gehören ins Feld `bemerkenswert`, NICHT ins Feld `bezuege`. Sie rechtfertigen
in der Regel "scannen" oder "lesenswert", aber kein "ignorieren".

"ignorieren" ist für Texte reserviert, an denen **weder** ein inhaltlicher Anschluss **noch**
eine bemerkenswerte methodisch-phänomenale Beobachtung zu machen ist.

=== VORGEHEN (ASSESSMENT-PHASE) ===
Du hast KEINEN Zugriff auf Volltexte. Du arbeitest nur mit dem Publikationsindex oben.

1. Lies den neuen Beitrag sorgfältig (Titel, Abstract, Referenzen).
2. **Sofort-Entscheidung**: Wenn nach Schritt 1 klar ist, dass der Beitrag weder
   inhaltliche Anschlüsse noch bemerkenswerte Beobachtungen bietet — rufe SOFORT
   `submit_digest_entry` mit verdict="ignorieren" auf. Leere bezuege, leere
   candidate_reads, leere bemerkenswert. Typische Fälle: reine Psychometrie,
   klinische Studien, angewandte Didaktik ohne theoretischen Anschluss.
3. Wenn potenziell relevant, prüfe beides:
   (a) **Kandidaten-Bezüge**: Gibt es im Index Publikationen, deren Kurzprofil einen
       SPEZIFISCHEN Anschluss nahelegt? Überschneidungen bei named_thinkers, methods
       oder key_terms sind starke Hebel. Für jede: Trage sie in `candidate_reads` ein
       mit pub_id, einem konkreten search_term, und einer 1-Satz-Hypothese.
       → `bezuege` bleibt LEER. Bezüge erfordern Volltext-Lektüre.
   (b) **Bemerkenswert**: Gibt es eine Beobachtung zweiter Ordnung? "Würde
       {RESEARCHER_NAME} das wissen wollen, selbst wenn der Text nicht gelesen wird?"
       → bemerkenswert ausfüllen.
4. Entscheide ein vorläufiges verdict. Wenn candidate_reads nicht leer ist, folgt
   eine Verifikationsphase mit Volltext-Zugriff.

=== REGELN ===
- Schreibe KEINE bezuege. Das Feld bleibt leer. Bezüge erfordern Volltext-Lektüre.
- candidate_reads nur für Publikationen, bei denen der Index einen SPEZIFISCHEN
  Anschluss nahelegt — nicht "mal schauen". Jede Kandidatur braucht eine Hypothese.
- Maximal 3 candidate_reads. Mehr ist fast nie nötig.
- bemerkenswert darf und soll gefüllt werden, wenn zutreffend.
- Sprache: Deutsch, akademisch, präzise, ohne Buzzwords und Floskeln.

=== PUBLIKATIONSSTAND (2018+) ==="""


def run_agent(
    new_article: dict,
    corpus_path: Path = CORPUS_JSON,
    summaries_path: Path = SUMMARIES_JSON,
    model: str = MODEL_AGENT,
    max_iterations: int = 8,
    verbose: bool = True,
    allow_read: bool = True,
    system_outro: str | None = None,
    extra_user_content: str = "",
) -> dict:
    """new_article: dict mit title, authors, abstract, doi, url, journal.

    allow_read=False disables read_publication tool (assessment from
    summaries only, no fulltext verification).
    system_outro: replaces the default SYSTEM_OUTRO in the system prompt.
    extra_user_content: appended to the user message (e.g. verification context).
    """
    corpus_index = _load_corpus_index(corpus_path)
    authored_all = _load_authored_all(corpus_path)
    summaries_data = json.loads(summaries_path.read_text(encoding="utf-8"))
    summaries = summaries_data["summaries"]

    system_prompt = build_system_prompt(summaries, outro=system_outro)
    if verbose:
        phase = "assessment" if system_outro is ASSESSMENT_OUTRO else "full"
        print(f"[agent] System-Prompt ({phase}): ~{len(system_prompt)//4} Tokens "
              f"({len(summaries)} Publikationen im Index)")

    doi = (new_article.get("doi") or "").strip()

    # Use pre-computed enrichment from store if available, else fetch
    enrichment_data = new_article.get("enrichment") or {}
    if not enrichment_data and doi:
        enrichment_data = enrich(doi)

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
    if extra_user_content:
        user_content += extra_user_content
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
            tools=TOOLS if allow_read else TOOLS_SUBMIT_ONLY,
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
                # Guard against double-encoded JSON (string instead of dict)
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        pass
                final_entry = args if isinstance(args, dict) else None
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


# ------------------------------------------------ Two-Phase: Assess → Verify


def _format_verification_context(assessment_entry: dict, candidates: list[dict]) -> str:
    """Build the verification context appended to the user message in Phase 2."""
    lines = [
        "\n\n=== VERIFIKATION ===",
        "Du hast eine Voreinschätzung zu diesem Artikel gemacht.",
        "Deine Kandidaten-Bezüge:\n",
    ]
    for c in candidates:
        lines.append(f"- pub_id: {c['pub_id']}")
        lines.append(f"  search_term: {c.get('search_term', '')}")
        lines.append(f"  Hypothese: {c.get('hypothesis', '')}")
    lines.append("")
    lines.append("Deine Aufgabe:")
    lines.append("1. Lies die identifizierten Publikationen mit "
                 "read_publication(pub_id, search_term).")
    lines.append("2. Verifiziere oder falsifiziere jede Hypothese am Volltext.")
    lines.append("3. Schreibe bezuege NUR für bestätigte Verbindungen. Sei ehrlich")
    lines.append("   wenn eine Hypothese sich nicht bestätigt — das ist ein valides Ergebnis.")
    lines.append("4. Übernimm bemerkenswert und theoretisch_methodisch aus der Voreinschätzung,")
    lines.append("   ergänze wenn der Volltext neue Einsichten liefert.")
    lines.append("5. Korrigiere das verdict, wenn der Volltext Deine Einschätzung ändert.")
    lines.append("")
    if assessment_entry.get("kernthese"):
        lines.append(f"Voreinschätzung — Kernthese: {assessment_entry['kernthese']}")
    if assessment_entry.get("bemerkenswert"):
        lines.append("Voreinschätzung — Bemerkenswert: "
                     + "; ".join(assessment_entry["bemerkenswert"]))
    if assessment_entry.get("verdict"):
        lines.append(f"Voreinschätzung — Verdict: {assessment_entry['verdict']}")
        lines.append(f"  Begründung: {assessment_entry.get('verdict_begruendung', '')}")
    return "\n".join(lines)


def assess_then_verify(
    new_article: dict,
    corpus_path: Path = CORPUS_JSON,
    summaries_path: Path = SUMMARIES_JSON,
    model: str = MODEL_AGENT,
    verbose: bool = True,
) -> dict:
    """Two-phase pipeline: assessment from summaries, then targeted verification.

    Phase 1 (Assessment): Agent works from the summary index only.
      - Irrelevant articles → submit immediately, no fulltext reads.
      - Relevant articles → identifies candidate_reads (pub_id + hypothesis).

    Phase 2 (Verification): Only when candidate_reads is non-empty.
      - Agent reads specifically identified publications.
      - Verifies or refutes candidate connections.
      - Produces final digest entry with honest, verified bezuege.
    """
    # --- Phase 1: Assessment ---
    if verbose:
        print("[assess] === Phase 1: Assessment (nur Index) ===")
    assessment = run_agent(
        new_article,
        corpus_path=corpus_path,
        summaries_path=summaries_path,
        model=model,
        max_iterations=1,
        verbose=verbose,
        allow_read=False,
        system_outro=ASSESSMENT_OUTRO,
    )

    entry = assessment.get("entry") or {}
    candidates = entry.get("candidate_reads") or []

    if not candidates:
        if verbose:
            print(f"[assess] Keine candidate_reads → Assessment ist Endergebnis "
                  f"(verdict={entry.get('verdict', '?')})")
        # Clean up: remove candidate_reads from final entry, ensure bezuege present
        entry.pop("candidate_reads", None)
        if "bezuege" not in entry:
            entry["bezuege"] = []
        return assessment

    # --- Phase 2: Verification ---
    if verbose:
        pubs = ", ".join(c["pub_id"] for c in candidates)
        print(f"[assess] {len(candidates)} candidate_reads → Verifikation ({pubs})")
        print("[assess] === Phase 2: Verification (gezielte Volltext-Reads) ===")

    max_iter_verify = min(max(len(candidates) + 2, 3), 6)
    verification = run_agent(
        new_article,
        corpus_path=corpus_path,
        summaries_path=summaries_path,
        model=model,
        max_iterations=max_iter_verify,
        verbose=verbose,
        allow_read=True,
        extra_user_content=_format_verification_context(entry, candidates),
    )

    # Combine costs from both phases
    for key in ("tokens_in", "tokens_out", "tokens_cached_read",
                "tokens_cache_write", "est_cost_usd"):
        verification[key] = verification.get(key, 0) + assessment.get(key, 0)
    verification["iterations"] = (
        assessment.get("iterations", 0) + verification.get("iterations", 0)
    )
    verification["tool_calls"] = (
        assessment.get("tool_calls", []) + verification.get("tool_calls", [])
    )
    # Stash assessment for transparency
    verification["assessment"] = entry

    # Clean up candidate_reads from final entry
    final = verification.get("entry") or {}
    final.pop("candidate_reads", None)

    return verification


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
    citation_hits = [
        h for h in (result.get("citation_hits") or []) if isinstance(h, dict)
    ]
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
