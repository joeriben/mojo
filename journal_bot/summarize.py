"""Faktische Summarisierung via Haiku 4.5 — liest corpus.json, schreibt summaries.json.

**Keine** Interpretation, keine Bewertung, keine theoretische Verortung.
Nur: Was behandelt der Text, welche Begriffe, welche Denker, welche Methoden.

Inkrementell: Bereits summarisierte pub_ids werden übersprungen (resumable).
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

from journal_bot.llm_client import build_client
from journal_bot.llm_log import record_llm_call
from journal_bot.settings import CORPUS_JSON, MODEL_SUMMARIZE, SUMMARIES_JSON


# Haiku 4.5 hat 200k Context. Wir schneiden bei ~140k Tokens hart ab,
# um Platz für Prompt + Output zu lassen. Zeichenschätzung: 4 chars ≈ 1 token.
MAX_INPUT_CHARS = 560_000


SYSTEM = """Du bekommst den Volltext einer akademischen Publikation (deutsch oder englisch).
Deine Aufgabe ist **rein faktisch**. Du sollst den Inhalt erfassen, nicht interpretieren.

Verboten:
- Wertungen ("innovativ", "wichtig", "bahnbrechend", "wegweisend")
- Theoretische Einordnungen ("dies schließt an die Tradition X an", "steht in der Linie von Y")
- Zusammenfassungen "der Kernthesen" als würden sie feststehen
- Spekulationen über die Position der Autor*innen

Erlaubt und gewünscht:
- Was der Text nach eigener Aussage behandelt ("Der Text diskutiert …", "Im Zentrum steht …")
- Welche Beispiele, Fälle, Daten, empirischen Materialien vorkommen
- Welche Begriffe der Text prominent verwendet (als bloße Nennung, nicht als Charakterisierung)
- Welche Autor*innen / Theoretiker*innen im Text mit einiger Häufigkeit auftauchen (nicht jede Einzelzitation)
- Welche Methoden der Text nach eigener Aussage verwendet

Rufe das Tool `record_summary` mit Deinen Ergebnissen auf.
"""


SUMMARY_TOOL = {
    "type": "function",
    "function": {
        "name": "record_summary",
        "description": "Speichert die faktische Zusammenfassung einer Publikation.",
        "parameters": {
            "type": "object",
            "properties": {
                "summary_de": {
                    "type": "string",
                    "description": (
                        "100–150 Wörter deutsch, dritte Person ('Der Text …'), "
                        "rein deskriptiv. Keine Wertungen."
                    ),
                },
                "key_terms": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "5–15 prominent im Text verwendete Begriffe.",
                },
                "named_thinkers": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "0–15 Theoretiker*innen / Autor*innen, die im Text "
                        "mit einer gewissen Häufigkeit vorkommen (nicht jede Einzelzitation)."
                    ),
                },
                "methods": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "0–10 im Text genannte Methoden / Verfahren.",
                },
                "cases_examples": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "0–10 konkrete Fälle / Studien / Beispiele / Gegenstände.",
                },
            },
            "required": ["summary_de", "key_terms", "named_thinkers", "methods", "cases_examples"],
        },
    },
}


USER_TEMPLATE = """PUBLIKATION
Titel:    {title}
Autoren:  {authors}
Jahr:     {year}
Venue:    {venue}

VOLLTEXT (ggf. gekürzt):
{fulltext}
"""


def _load_existing(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("summaries", {})


ARRAY_FIELDS = ("key_terms", "named_thinkers", "methods", "cases_examples")


def _coerce_array_field(value) -> list[str]:
    """Haiku liefert Array-Felder gelegentlich als String mit JSON-Array-Literal.
    Wir bügeln das glatt: String → versuchen zu parsen → sonst als Einzelelement."""
    if isinstance(value, list):
        return [str(x) for x in value]
    if isinstance(value, str):
        s = value.strip()
        if s.startswith("[") and s.endswith("]"):
            try:
                parsed = json.loads(s)
                if isinstance(parsed, list):
                    return [str(x) for x in parsed]
            except Exception:
                pass
        return [s] if s else []
    return []


def _extract_tool_args(resp) -> dict:
    """Holt die tool-call arguments aus der Response. Wirft ValueError wenn nichts da."""
    choice = resp.choices[0]
    msg = choice.message
    tool_calls = getattr(msg, "tool_calls", None) or []
    if not tool_calls:
        raise ValueError(
            f"Keine tool_calls in Response. stop_reason={choice.finish_reason}, "
            f"content={str(msg.content)[:300]}"
        )
    tc = tool_calls[0]
    if tc.function.name != "record_summary":
        raise ValueError(f"Unerwarteter Tool-Name: {tc.function.name}")
    data = json.loads(tc.function.arguments)

    # Defensiv normalisieren
    out = {"summary_de": str(data.get("summary_de", "")).strip()}
    for field_name in ARRAY_FIELDS:
        out[field_name] = _coerce_array_field(data.get(field_name))
    return out


def _save_incremental(path: Path, summaries: dict[str, dict], meta: dict) -> None:
    payload = {
        **meta,
        "count": len(summaries),
        "summaries": summaries,
    }
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def run(
    corpus_path: Path = CORPUS_JSON,
    output_path: Path = SUMMARIES_JSON,
    model: str = MODEL_SUMMARIZE,
    limit: int | None = None,
) -> dict:
    corpus_data = json.loads(corpus_path.read_text(encoding="utf-8"))
    pubs = corpus_data["publications"]
    pubs_with_text = [p for p in pubs if p["fulltext_chars"] > 0]

    print(f"Corpus: {len(pubs)} Publikationen, davon {len(pubs_with_text)} mit Volltext.")
    if limit:
        pubs_with_text = pubs_with_text[:limit]
        print(f"  (Begrenzung auf {limit} für diesen Lauf)")

    existing = _load_existing(output_path)
    print(f"Bereits summarisiert: {len(existing)}  →  offen: "
          f"{len(pubs_with_text) - sum(1 for p in pubs_with_text if p['pub_id'] in existing)}")

    client = build_client()
    meta = {
        "model": model,
        "corpus_file": str(corpus_path),
        "since_year": corpus_data.get("since_year"),
    }

    total_in = 0
    total_out = 0
    errors = 0
    start = time.time()

    for i, pub in enumerate(pubs_with_text, 1):
        pub_id = pub["pub_id"]
        if pub_id in existing and "error" not in existing[pub_id]:
            continue  # sauber summarisiert → skip

        fulltext = pub["fulltext"]
        truncated = False
        if len(fulltext) > MAX_INPUT_CHARS:
            fulltext = fulltext[:MAX_INPUT_CHARS]
            truncated = True

        user_msg = USER_TEMPLATE.format(
            title=pub["title"],
            authors=", ".join(pub["authors"]),
            year=pub.get("year") or "",
            venue=pub.get("venue") or "",
            fulltext=fulltext,
        )

        label = f"[{i:>3}/{len(pubs_with_text)}] {pub.get('year')} {pub['title'][:60]}"
        if truncated:
            label += " ✂"

        try:
            resp = client.chat.completions.create(
                model=model,
                max_tokens=1500,
                messages=[
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": user_msg},
                ],
                tools=[SUMMARY_TOOL],
                tool_choice={"type": "function", "function": {"name": "record_summary"}},
            )
        except Exception as e:
            errors += 1
            print(f"{label}  API-FEHLER: {str(e)[:150]}")
            continue

        try:
            parsed = _extract_tool_args(resp)
        except Exception as e:
            errors += 1
            print(f"{label}  TOOL-PARSE: {str(e)[:150]}")
            existing[pub_id] = {
                "error": f"tool_parse: {e}",
                "title": pub["title"],
                "year": pub.get("year"),
            }
            _save_incremental(output_path, existing, meta)
            continue

        usage = getattr(resp, "usage", None)
        usage_dump: dict = {}
        per_call_cost = 0.0
        if usage:
            total_in += usage.prompt_tokens or 0
            total_out += usage.completion_tokens or 0
            usage_dump = (
                usage.model_dump() if hasattr(usage, "model_dump") else {}
            )
            per_call_cost = float(usage_dump.get("cost") or 0.0)
            if per_call_cost == 0.0:
                # Opus 4.6: ~$15 in / $75 out per M tokens
                per_call_cost = (
                    (usage.prompt_tokens or 0) / 1_000_000 * 15.0
                    + (usage.completion_tokens or 0) / 1_000_000 * 75.0
                )
        record_llm_call(
            endpoint="summarize", model=model,
            usage=usage_dump, cost_usd=per_call_cost, status="ok",
            pub_id=pub_id,
        )

        existing[pub_id] = {
            "title": pub["title"],
            "authors": pub["authors"],
            "year": pub.get("year"),
            "venue": pub.get("venue"),
            "doi": pub.get("doi"),
            "item_type": pub.get("item_type"),
            "truncated": truncated,
            **parsed,
        }
        _save_incremental(output_path, existing, meta)
        print(f"{label}  ✓  "
              f"in={usage.prompt_tokens if usage else '?'} out={usage.completion_tokens if usage else '?'}")

    elapsed = time.time() - start
    # Opus 4.6 Pricing auf OpenRouter: ~$15/M input, ~$75/M output (Stand Anf. 2026)
    est_cost = (total_in / 1_000_000) * 15.0 + (total_out / 1_000_000) * 75.0
    print()
    print("=== Summarize fertig ===")
    print(f"Summarisiert in summaries.json: {len(existing)}")
    print(f"Fehler diesem Lauf:              {errors}")
    print(f"Tokens gesamt: in={total_in:,}  out={total_out:,}")
    print(f"Geschätzte Kosten (Opus 4.6):    ~${est_cost:.2f}")
    print(f"Dauer:                           {elapsed:.0f}s")
    print(f"Geschrieben: {output_path}")

    return {
        "summaries": existing,
        "errors": errors,
        "tokens_in": total_in,
        "tokens_out": total_out,
        "est_cost_usd": est_cost,
    }
