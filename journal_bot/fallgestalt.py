"""H7 — Relationale Positionierung: Fallgestalt-Erzeugung (Port aus SARAH).

Ein co-präsenter Werk-Positionierungs-Pass über EIN Dokument: destilliert die
diskursive Positionierung eines Werks in einen getypten Graphen — Quellen
(operativ, mit Haltung: affirms/extends/contrasts/reserves/rejects), In-vivo-
Begriffe, Selbstposition, eigene Trajektorie. Nicht-wertend, kein Verdikt,
KEINE Korpus-/Cross-Dokument-Relation (das ist MOJOs Relate/M1-M4 — dieses
Modul liest EIN Dokument).

Port aus SARAH (src/lib/server/ai/h7/{profile-read,topology,export,types}.ts,
Stand 2026-07-08). Geteilter Vertrag = die Fallgestalt-JSON (V/E/meta), NICHT
ein Endpoint (copy-not-communicate, Setzung 2026-07-06) — dieses Modul
emittiert dieselbe Schema-Form eigenständig, ohne Laufzeit-Kopplung an SARAH.

Ein echter Unterschied zu SARAH: die O1-Quellen-Topologie (Zitationsdichte pro
Autor, die den Prompt als Checkliste führt) kommt hier NICHT aus einer
geparsten Bibliographie + Fußnoten-Auflösung (SARAHs Stratum A) — own_refs.db
liefert für einen Teil der Publikationen (so auch das Verifikations-Dokument
JK26) nur DOI-Referenzen ohne Autor-Rohtext in pub_refs.ref_text, eine
Bibliographie-basierte Kandidatenliste ist also nicht durchgängig verfügbar.
Ersetzt durch einen Zitations-Regex über den Volltext (Autor-Jahr-Muster).
dens dominiert wie in SARAH (`classify_operativity` entscheidet NUR über
dens) — mult wird für die Klassifikation gar nicht gebraucht.

Kalibriert gegen SARAHs bekannte dens-Werte für dasselbe Testdokument (JK26,
aus der geparsten Bibliographie): Jörissen=7, Barad=6, Brown=5, Klepacki=4,
Haraway=3. Die Operativitäts-Schwelle (dens>=3) ist identisch zu SARAHs
topology.ts OPERATIVITY.densMin — v1, am Material revidierbar.
"""

from __future__ import annotations

import os
import re
import time
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from journal_bot.multi_provider import ROUTES, build_client, extract_stats, make_messages

# ── Modell-Route ──────────────────────────────────────────────────────────
# Empirisch verglichen (SARAH, 2026-07-08, JK26): MiMo bleibt bei
# vergleichbaren Kosten der Tier-Default gegenüber Gemini-3-Flash-Preview /
# DeepSeek-v4-Pro / Qwen3.7-Plus — alle drei konvergieren auf ~40% von MiMos
# Quellen-Coverage (5-6 statt 15 externe Quellen mit erkennbarer Haltung).
# Analog SARAHs ai-settings.json: explizit hier als Modul-Default benannt,
# überschreibbar per Parameter — keine versteckte Code-Backdoor, weil sichtbar
# und per Aufruf änderbar (siehe feedback_models_only_from_settings_no_code_default).
DEFAULT_ROUTE_KEY = "mimo"

# ── Prompt (VERBATIM aus SARAH src/lib/server/ai/h7/profile-read.ts SYS_PROFILE) ──

SYS_PROFILE = """Du liest einen wissenschaftlichen Text, der dir GANZ und KO-PRÄSENT vorliegt. Lege das DISKURSIVE PROFIL des Werks frei: wo es sich im Diskurs verortet — zu welchen Quellen es sich wie verhält, welche Begriffe es als eigene Münze führt, was es selbst will, und auf welche eigenen Vorarbeiten es aufbaut.

Dies ist KEINE Bewertung. Du beurteilst NICHT, ob das Werk gut ist oder ob seine Setzungen berechtigt sind — das ist eine andere Frage. Du legst deskriptiv frei, WO der Text steht, für ein Retrieval-System, das dieses Werk zu anderen in Beziehung setzt.

KO-PRÄSENZ: der ganze Text liegt vor; nutze Vor- und Rückgriff, um die Haltung einer Stelle im Licht des ganzen Werks zu bestimmen.
BELEG-PFLICHT: jede Zeile an einem wörtlich zitierten Zug festmachen.
SELBSTBEZUG GETRENNT HALTEN: Verweise des Werks auf EIGENE frühere Arbeiten (gleiche Autorschaft — »in vorangegangenen Arbeiten«, »wir haben andernorts«, »unsere frühere Studie«) gehören unter TRAJEKTORIE, NICHT unter QUELLEN. Sie sind keine Haltung zu einer externen Quelle, sondern die eigene Linie.

Gib GENAU diese vier Blöcke aus, jeden mit seiner Kopfzeile in eckigen Klammern. Hat ein Block keinen Eintrag: nur »—«.

[SELBSTPOSITION]
ZIEL: <was das Werk leisten/zeigen will, wo es sich verortet — 1–2 Sätze> | BELEG: «<wörtliches Zitat>»

[QUELLEN]
Je operativ verarbeiteter externer Quelle GENAU EINE Zeile:
QUELLE: <Autor/Werk> | RELATION: <affirms|extends|contrasts|reserves|rejects> | ADRESSE: <was das Werk mit ihr tut / in welcher Denkgemeinschaft das steht> | BELEG: «<wörtliches Zitat>»
Relations-Vokabular: affirms = schließt zustimmend an · extends = baut aus / führt weiter · contrasts = stellt kontrastierend gegenüber · reserves = übernimmt mit Vorbehalt · rejects = weist zurück.
NUR Quellen, zu denen der Text eine erkennbare Haltung einnimmt; bloß einmal beiläufig Genannte ohne Verarbeitung NICHT.

[BEGRIFFE]
Je in-vivo-Begriff, den das Werk als eigene Münze führt, GENAU EINE Zeile:
BEGRIFF: <Terminus> | HERKUNFT: <Quelle, von der er geprägt ist, oder »Werk selbst«> | BELEG: «<wörtliches Zitat>»

[TRAJEKTORIE]
Je Bezug auf eine EIGENE frühere Arbeit GENAU EINE Zeile:
SELBSTBEZUG: <auf welche eigene Vorarbeit / welches eigene Programm> | BELEG: «<wörtliches Zitat>»"""

USER_MSG = "Erzeuge jetzt das diskursive Profil dieses Werks in den vier Blöcken."

# ── O1: Quellen-Topologie (Regex-Zitationsdichte statt SARAHs Bibliographie-Pass) ──

DENS_MIN = 3  # identisch zu SARAHs OPERATIVITY.densMin (topology.ts)

# Autor-Jahr-Zitationsmuster: "Name (Jahr", "(Name Jahr", "(Name, Jahr",
# "Name/Name2 Jahr", "Name & Name2 (Jahr" — deckt die im Material beobachteten
# Zitationsstile ab (Klammer-Zitat, Fließtext-Zitat, deutscher Autorenverbund).
_CITE_RE = re.compile(
    r"(?<![\w])([A-ZÄÖÜ][a-zäöüß]+)(?:\s*[/&]\s*([A-ZÄÖÜ][a-zäöüß]+))?"
    r"(?:,?\s*(?:et al\.?)?)?\s*[\(,]?\s*(?:19|20)\d{2}\)?"
)

# Wörter, die zufällig vor einer Jahreszahl stehen können, aber keine
# Autorennamen sind (Satzanfänge, Struktur-/Zeitangaben) — Regex-Rauschen filtern.
_STOP_SURNAMES = {
    "Following", "Since", "Until", "Before", "After", "During", "Around", "Vol",
    "Chapter", "Section", "Table", "Figure", "Part", "Page", "Pp", "The", "In",
    "See", "Cf", "Cultural", "International", "Journal", "This", "That", "From",
    "According", "Between", "Within", "Beyond", "Towards", "Toward",
}


def build_source_topology(fulltext: str) -> dict[str, dict[str, Any]]:
    """Zitationsdichte pro Autor-Nachname aus dem Volltext (Regex-Heuristik,
    ersetzt SARAHs bibliography_entries+Fußnoten-Pass — siehe Modul-Docstring)."""
    counts: dict[str, int] = {}
    for m in _CITE_RE.finditer(fulltext):
        for name in (m.group(1), m.group(2)):
            if not name or name in _STOP_SURNAMES:
                continue
            counts[name] = counts.get(name, 0) + 1
    return {
        author: {"dens": dens, "op": "operative" if dens >= DENS_MIN else "named"}
        for author, dens in counts.items()
    }


def build_profile_prefix(fulltext: str, topology: dict[str, dict[str, Any]]) -> str:
    """Port von SARAHs buildProfilePrefix: SYS + Checkliste (operative Quellen,
    dens-sortiert) + ganzer Text."""
    operative = sorted(
        ((a, t["dens"]) for a, t in topology.items() if t["op"] == "operative"),
        key=lambda x: -x[1],
    )
    checklist = (
        "\n".join(f"- {a} ({d}×)" for a, d in operative)
        if operative
        else "(keine via Zitationsdichte vorklassifiziert — allein aus dem Text bestimmen)"
    )
    return (
        f"{SYS_PROFILE}\n\n"
        f"[OPERATIVE QUELLEN — Kandidaten aus der Zitationsanalyse]\n"
        f"Diese Quellen werden im Text gehäuft zitiert. Positioniere das Werk zu jeder, "
        f"soweit eine Haltung erkennbar ist; ergänze weitere, die du im Text findest; "
        f"prüfe, ob darunter Selbstbezüge sind (→ TRAJEKTORIE statt QUELLEN).\n"
        f"{checklist}\n\n"
        f"[GANZER TEXT — KO-PRÄSENT]\n{fulltext}"
    )


# ── Degenerate-Generation-Check (Port aus SARAH client.ts isDegenerateGeneration) ──

_REPEAT_CHAR_RE = re.compile(r"(.)\1{40,}", re.UNICODE)
_REPEAT_TOKEN_RE = re.compile(r"(\S{1,40})(?:\s+\1){7,}", re.UNICODE)


def is_degenerate_generation(text: str) -> bool:
    if not text:
        return False
    if _REPEAT_CHAR_RE.search(text):
        return True
    if _REPEAT_TOKEN_RE.search(text):
        return True
    return False


# ── Parser: Modell-Output → Knoten/Kanten (Port aus SARAH parseProfile) ──

POSITION_KEY = "position:self"
RELATION_KINDS = {"affirms", "extends", "contrasts", "reserves", "rejects"}


def _sigma_for_relation(rel: str) -> str | None:
    """σ aus der Relation ableiten (affirms/extends → +, contrasts/reserves/rejects → −)."""
    if rel in ("affirms", "extends"):
        return "+"
    if rel in ("contrasts", "reserves", "rejects"):
        return "-"
    return None


def _parse_fields(line: str) -> dict[str, str]:
    """Eine `KEY: val | KEY: val`-Zeile in eine Feld-Map zerlegen (lenient)."""
    out: dict[str, str] = {}
    for part in line.split("|"):
        idx = part.find(":")
        if idx < 0:
            continue
        key = part[:idx].strip().upper()
        val = part[idx + 1 :].strip().strip("«»").strip()
        if key:
            out[key] = val
    return out


_TOKEN_SPLIT_RE = re.compile(r"[^a-zäöüßéèàóíú]+")


def _tokenize(s: str) -> set[str]:
    return {t for t in _TOKEN_SPLIT_RE.split(s.lower()) if len(t) > 2}


@dataclass
class ParsedProfile:
    nodes: list[dict[str, Any]] = field(default_factory=list)
    edges: list[dict[str, Any]] = field(default_factory=list)
    unparsed: list[str] = field(default_factory=list)


def parse_profile(raw: str, topology: dict[str, dict[str, Any]]) -> ParsedProfile:
    """Parst die vier Blöcke ([SELBSTPOSITION]/[QUELLEN]/[BEGRIFFE]/[TRAJEKTORIE])
    in Knoten/Kanten. Lenient: unverständliche Zeilen landen in `unparsed`.
    Quellen-Knoten werden mit dem Regex-dens aus der Topologie angereichert, wo
    der Name matcht (Token-Quercheck, analog SARAHs topoTok-Match — das Modell
    labelt reicher als der bare Nachname, z.B. »Brown (2015)« vs. »Brown«)."""
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    unparsed: list[str] = []
    seen_keys: set[str] = set()

    topo_tok = [(author, author.lower()) for author in topology]

    def match_topo(label: str) -> tuple[str, dict[str, Any]] | None:
        toks = _tokenize(label)
        for author, tok in topo_tok:
            if tok in toks:
                return author, topology[author]
        return None

    def match_existing_source(herkunft: str) -> dict[str, Any] | None:
        toks = _tokenize(herkunft)
        for n in nodes:
            if n["nodeType"] == "source" and _tokenize(n["label"]) & toks:
                return n
        return None

    def add_node(n: dict[str, Any]) -> None:
        if n["localKey"] in seen_keys:
            return
        seen_keys.add(n["localKey"])
        nodes.append(n)

    block: str | None = None
    own_counter = 0
    has_position = False

    for raw_line in raw.split("\n"):
        # Markdown-Echo tolerieren: Emphasis-Sternchen (»**[QUELLEN]**«, »**QUELLE:**«)
        # und führende Listenzeichen (»- QUELLE: …«) sind Modell-Marotten, keine
        # Inhalte — vor dem Parsen strippen statt die Zeile still zu verlieren.
        line = raw_line.strip().replace("**", "")
        line = re.sub(r"^[-•*]\s+", "", line)
        if not line or line == "—":
            continue

        header = re.match(r"^\[([A-ZÄÖÜ]+)\]$", line)
        if header:
            h = header.group(1)
            block = {
                "SELBSTPOSITION": "pos",
                "QUELLEN": "src",
                "BEGRIFFE": "term",
                "TRAJEKTORIE": "traj",
            }.get(h)
            continue
        # Zeilen ohne KEY:-Form (Präambeln, Vokabular-Echo) nicht still verlieren,
        # sondern als unparsed ausweisen (Befund, kein Fehler).
        if not re.match(r"^[A-ZÄÖÜ]+\s*:", line):
            unparsed.append(line)
            continue

        f = _parse_fields(line)

        if block == "pos" and f.get("ZIEL"):
            add_node(
                {
                    "localKey": POSITION_KEY,
                    "nodeType": "position",
                    "label": f["ZIEL"],
                    "provenance": "s",
                    "properties": {"goal": f["ZIEL"], "beleg": f.get("BELEG")},
                }
            )
            has_position = True

        elif block == "src" and f.get("QUELLE"):
            # RELATION lenient: Zusätze (»affirms (mit Vorbehalt)«) kosten nicht die
            # ganze Quelle — das in Textreihenfolge erste bekannte Relations-Wort
            # zählt; ohne erkennbares Vokabular bleibt die Zeile unparsed (sichtbar).
            rel_raw = (f.get("RELATION") or "").lower()
            rel: str | None = None
            rel_pos: int | None = None
            for k in RELATION_KINDS:
                m = re.search(rf"\b{k}\b", rel_raw)
                if m and (rel_pos is None or m.start() < rel_pos):
                    rel_pos = m.start()
                    rel = k
            if rel is None:
                unparsed.append(line)
                continue
            key = f"source:{f['QUELLE']}"
            topo_hit = match_topo(f["QUELLE"])
            props: dict[str, Any] = {"address": f.get("ADRESSE"), "beleg": f.get("BELEG")}
            if topo_hit:
                _, t = topo_hit
                props.update({"dens": t["dens"], "op": t["op"]})
            add_node(
                {
                    "localKey": key,
                    "nodeType": "source",
                    "label": f["QUELLE"],
                    "provenance": "s",
                    "properties": props,
                }
            )
            edges.append(
                {
                    "edgeKind": rel,
                    "fromKey": POSITION_KEY,
                    "toKey": key,
                    "sigma": _sigma_for_relation(rel),
                    "properties": {"address": f.get("ADRESSE"), "beleg": f.get("BELEG")},
                    "provenance": "s",
                }
            )

        elif block == "term" and f.get("BEGRIFF"):
            key = f"term:{f['BEGRIFF']}"
            add_node(
                {
                    "localKey": key,
                    "nodeType": "term",
                    "label": f["BEGRIFF"],
                    "provenance": "s",
                    "properties": {"coinedBy": f.get("HERKUNFT"), "beleg": f.get("BELEG")},
                }
            )
            # coins: O2 = in-vivo-Begriffe, die das Werk als eigene Münze führt →
            # Default ist Prägung DURCH DAS WERK. Nur wenn HERKUNFT sauber eine
            # bereits positionierte Quelle benennt, prägt diese. Niemals einen
            # Quellen-Knoten aus Freitext-HERKUNFT fabrizieren.
            herkunft = (f.get("HERKUNFT") or "").strip()
            work_coined = not herkunft or bool(
                re.search(
                    r"werk selbst|selbst|eigen|anschluss|anlehnung|angelehnt|umakzentuiert|umformuliert",
                    herkunft,
                    re.IGNORECASE,
                )
            )
            from_key = POSITION_KEY
            if not work_coined:
                existing = match_existing_source(herkunft)
                if existing:
                    from_key = existing["localKey"]
                # sonst: Werk-Prägung (kein fabrizierter Knoten); coinedBy bleibt im Extrakt.
            edges.append(
                {
                    "edgeKind": "coins",
                    "fromKey": from_key,
                    "toKey": key,
                    "properties": {"beleg": f.get("BELEG")},
                    "provenance": "s",
                }
            )

        elif block == "traj" and f.get("SELBSTBEZUG"):
            key = f"own:{own_counter}"
            own_counter += 1
            add_node(
                {
                    "localKey": key,
                    "nodeType": "source",
                    "label": f["SELBSTBEZUG"],
                    "provenance": "s",
                    "properties": {"ownWork": True, "beleg": f.get("BELEG")},
                }
            )
            edges.append(
                {
                    "edgeKind": "trajectory",
                    "fromKey": POSITION_KEY,
                    "toKey": key,
                    "properties": {"beleg": f.get("BELEG")},
                    "provenance": "s",
                }
            )
        else:
            unparsed.append(line)

    # Kanten ohne Position-Knoten wären verwaist — synthetischen Position-Knoten
    # ergänzen, falls der Pass keinen ZIEL-Block lieferte (Fehlendes = Befund).
    if not has_position and any(e["fromKey"] == POSITION_KEY for e in edges):
        add_node(
            {
                "localKey": POSITION_KEY,
                "nodeType": "position",
                "label": "(Selbstposition nicht explizit)",
                "provenance": "s",
                "properties": {"goal": None},
            }
        )

    return ParsedProfile(nodes=nodes, edges=edges, unparsed=unparsed)


# ── Verbatim-BELEG-Gate (Port aus SARAH profile-parse.ts) ──────────────────
#
# Wörtlichkeit der Belege nicht nur im Prompt fordern, sondern mechanisch gegen
# den Volltext prüfen. Normalisierung beidseitig identisch (Quote-/Strich-
# Glyphen, Whitespace); Ellipsen teilen den Beleg in unabhängig prüfbare
# Stücke. Fails werden markiert (belegVerified: False) und gezählt — nicht
# verworfen (Abweichung sichtbar machen, kein stilles Droppen).


def normalize_for_beleg_match(s: str) -> str:
    """Vereinheitlicht Anführungs-/Strich-Glyphen + Whitespace für den
    Verbatim-Vergleich (NFKC, klein, Soft Hyphen raus, Glyphen-Varianten
    vereinheitlicht)."""
    s = unicodedata.normalize("NFKC", s).lower()
    s = s.replace("\xad", "")  # Soft Hyphen (Silbentrennung aus PDF/DOCX-Extrakten)
    s = re.sub("[\"'„“”«»‹›’‘`´]", "", s)
    s = re.sub(r"[–—‒−]", "-", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


# Unterhalb dieser normalisierten Länge ist ein Zitat-Stück kein belastbarer Check.
BELEG_MIN_CHECKABLE = 12


def _beleg_pieces(beleg: str) -> list[str]:
    """Prüfstücke eines Belegs: an Ellipsen UND an Quote-Glyphen gesplittet,
    normalisiert, nur prüfbar lange Stücke behalten. Der Quote-Split fängt
    Mehrfach-Zitate in einem BELEG-Feld (»«Zitat1» sowie «Zitat2»« — real
    beobachtet, MiMo/JK26): jedes Stück muss einzeln im Text stehen; die
    Verkettung müsste es nicht. Apostrophe bleiben ungesplittet
    (Binnen-'quotes' gehören zum Zitat). Spiegel von SARAH profile-parse.ts."""
    raw_pieces = re.split(r"\[\s*(?:…|\.{3})\s*\]|…|\.{3}|[«»„“”\"]", beleg)
    pieces = [normalize_for_beleg_match(p) for p in raw_pieces]
    return [p for p in pieces if len(p) >= BELEG_MIN_CHECKABLE]


@dataclass
class BelegGateResult:
    """Ergebnis des Verbatim-Gates. `checked` = Anzahl distinkter Belege mit
    mindestens einem prüfbaren Stück."""

    checked: int = 0
    failed: int = 0
    failures: list[dict[str, str]] = field(default_factory=list)


def verify_belege(parsed: ParsedProfile, full_text: str) -> BelegGateResult:
    """Prüft alle »beleg«-Properties (Knoten UND Kanten) verbatim gegen den
    Volltext. Nicht verifizierbare Belege werden in place mit
    belegVerified=False markiert (verifizierte bleiben unmarkiert — minimale
    Extrakt-Berührung) und einmal pro distinktem Beleg-Text in `failures`
    ausgewiesen."""
    haystack = normalize_for_beleg_match(full_text)
    verdict_by_beleg: dict[str, bool] = {}
    failures: list[dict[str, str]] = []

    def check(obj: dict[str, Any], where: str) -> None:
        beleg = (obj.get("properties") or {}).get("beleg")
        if not isinstance(beleg, str):
            return
        pieces = _beleg_pieces(beleg)
        if not pieces:
            return  # zu kurz für einen belastbaren Check
        ok = verdict_by_beleg.get(beleg)
        if ok is None:
            ok = all(p in haystack for p in pieces)
            verdict_by_beleg[beleg] = ok
            if not ok:
                failures.append({"where": where, "beleg": beleg})
        if not ok:
            obj.setdefault("properties", {})["belegVerified"] = False

    for n in parsed.nodes:
        check(n, f"{n['nodeType']}:{n['label']}")
    for e in parsed.edges:
        check(e, f"{e['edgeKind']}→{e['toKey']}")

    return BelegGateResult(checked=len(verdict_by_beleg), failed=len(failures), failures=failures)


# ── Export: 4-wertige Haltung → MoJos 2-wertiges Set (Port aus SARAH export.ts) ──

_STRUCTURAL_KINDS = {"bears", "coins", "condenses", "cites_back", "trajectory"}


def map_edge_kind_to_mojo(kind: str) -> str:
    """Setzung 8.1 des SARAH-Designs: interne 4-wertige Haltung → MoJos
    2-wertiges Set. Das Vorzeichen σ trägt die Feinheit, die das Kanten-Label
    kollabiert: affirms/extends → affirms; reserves/contrasts/rejects →
    reserves; strukturelle Kanten unverändert. internalKind bleibt als
    Audit-Spur im Export erhalten."""
    if kind in ("affirms", "extends"):
        return "affirms"
    if kind in ("reserves", "contrasts", "rejects"):
        return "reserves"
    if kind in _STRUCTURAL_KINDS:
        return kind
    raise ValueError(f"Unbekannte Kantenart: {kind}")


def assemble_fallgestalt(
    meta: dict[str, Any], nodes: list[dict[str, Any]], edges: list[dict[str, Any]]
) -> dict[str, Any]:
    """Baut die MoJo-Fallgestalt (V/E/meta) aus geparsten Knoten/Kanten. Anders
    als SARAHs assembleFallgestalt (das auf DB-Rows mit echten Primärschlüsseln
    arbeitet) läuft dieser Port direkt auf den geparsten Knoten: `id` =
    `localKey` (stabil und eindeutig innerhalb eines Laufs, kein DB-Primär-
    schlüssel nötig — MOJO persistiert die Fallgestalt nicht in einer eigenen
    Graph-Tabelle, sondern konsumiert das JSON direkt).

    Kanten führen `props` mit, weil das Verbatim-BELEG-Gate (verify_belege)
    auch Kanten prüft und dort `belegVerified=False` setzt. Ohne dieses Feld
    fielen die Kanten-Fails aus dem Export heraus und jede Auswertung der
    Beleg-Verlässlichkeit hätte systematisch zu niedrig gezählt."""
    v = [
        {
            "id": n["localKey"],
            "type": n["nodeType"],
            "label": n["label"],
            "props": n.get("properties") or {},
            "prov": n["provenance"],
        }
        for n in nodes
    ]
    e = [
        {
            "id": f"edge-{i}",
            "kind": map_edge_kind_to_mojo(ed["edgeKind"]),
            "from": ed["fromKey"],
            "to": ed["toKey"],
            "sigma": ed.get("sigma"),
            "anchors": ed.get("anchorElementIds") or [],
            "props": ed.get("properties") or {},
            "prov": ed["provenance"],
            "internalKind": ed["edgeKind"],
        }
        for i, ed in enumerate(edges)
    ]
    return {"meta": meta, "V": v, "E": e}


# ── Öffentliche API: ein Werk-Pass ───────────────────────────────────────

_BACKOFFS_S = (0, 5, 15, 45)  # wie multi_provider/test_sarah_v2 429-Retry


def run_document_profile_h7(
    fulltext: str,
    *,
    route_key: str = DEFAULT_ROUTE_KEY,
    max_tokens: int = 16000,
) -> dict[str, Any]:
    """Führt EINEN co-präsenten Werk-Positionierungs-Pass aus (Port aus SARAHs
    runDocumentProfileH7). Bis zu 4 Content-Versuche (Temperatur steigt bei
    Leer-/Degenerat-Output, wie SARAH); pro Versuch 429-Backoff-Retry. Nach
    jedem nicht-degenerierten Kandidaten läuft das Verbatim-BELEG-Gate gegen
    GENAU den Text, der ans Modell ging — scheitern die Belege breit (>50%
    bei belastbarer Basis ≥3 geprüfter Belege) UND sind noch Versuche übrig,
    wird der Kandidat verworfen und mit höherer Temperatur neu gelesen (Port
    aus SARAH profile-read.ts, Konfabulations-Bremse). Einzelne Fails bleiben
    Befund (Marker), kein Abbruch."""
    route = ROUTES[route_key]
    topology = build_source_topology(fulltext)
    prefix = build_profile_prefix(fulltext, topology)
    client = build_client(route.provider)
    messages = make_messages(prefix, USER_MSG, route)

    content = ""
    parsed = ParsedProfile()
    gate = BelegGateResult()
    tokens_in = 0
    tokens_out = 0
    for attempt in range(4):
        temperature = 0.0 if attempt == 0 else min(0.6, 0.25 * attempt)
        resp = None
        for wait in _BACKOFFS_S:
            if wait:
                time.sleep(wait)
            try:
                resp = client.chat.completions.create(
                    model=route.model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                break
            except Exception as e:  # noqa: BLE001 — Provider-Fehler, nicht klassifizierbar vorab
                status = getattr(e, "status_code", None) or getattr(e, "status", None)
                msg = str(e)
                if status == 429 or " 429 " in msg or "rate-limited" in msg.lower():
                    continue
                raise
        if resp is None:
            continue
        stats = extract_stats(resp.usage, route)
        tokens_in += stats.tokens_in
        tokens_out += stats.tokens_out
        cand = (resp.choices[0].message.content or "").strip()
        if os.environ.get("H7_DEBUG_ATTEMPTS"):
            print(
                f"  [attempt {attempt}] finish={resp.choices[0].finish_reason} "
                f"len={len(cand)} tok_in={stats.tokens_in} tok_out={stats.tokens_out} "
                f"degenerate={is_degenerate_generation(cand)}"
            )
        if not cand or is_degenerate_generation(cand):
            continue
        p = parse_profile(cand, topology)
        g = verify_belege(p, fulltext)
        # Verbatim-Gate als Konfabulations-Bremse: scheitern die Belege breit
        # UND sind noch Versuche übrig, wird der Versuch verworfen und mit
        # der nächsten Temperatur neu gelesen (Port aus SARAH profile-read.ts).
        if g.checked >= 3 and g.failed / g.checked > 0.5 and attempt < 3:
            continue
        content = cand
        parsed = p
        gate = g
        break

    return {
        "raw": content,
        "nodes": parsed.nodes,
        "edges": parsed.edges,
        "unparsed": parsed.unparsed,
        "belegFailures": gate.failures,
        "topology": topology,
        "tokens": {"input": tokens_in, "output": tokens_out},
        "model": {"provider": route.provider, "model": route.model},
    }
