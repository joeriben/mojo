"""Few-Shot aus den Daten — die nächsten schon beurteilten Artikel als Beleg.

Der treueste Weg, das Auswahlverhalten des Nutzers ins Screening zu tragen, ist
nicht eine Beschreibung seiner Vorlieben, sondern seine tatsächlichen Urteile:
zu jedem neuen Artikel die semantisch nächsten schon beurteilten Artikel mit dem
echten Verdikt (und, wo vorhanden, dem Memo im Wortlaut des Nutzers).

Held-out gemessen (`scripts/beispiel_wirksamkeit.py`, n=220, 3 Läufe je
Bedingung, Rauschgrenze ±2.3 %): Beispiele allein heben die Übereinstimmung von
74.4 % auf 77.0 % und halbieren die verlorenen Funde (4.7 → 2.0 von 29);
zusammen mit dem Regelblock auf 81.2 % (+6.8 pp, über dem Rauschen), verlorene
Funde 2.3. Regeln und Beispiele verstärken sich: der Block sagt, welche
Dimensionen zählen, die Beispiele zeigen, wie sie in Nachbarurteilen ausfallen.

Kosten: der grosse, gecachte Systemprompt dominiert; die Beispielzeilen im User-
Turn kosten praktisch nichts extra (gemessen ~$0.10 je 220er-Durchlauf).

Substrat ist derselbe lokale MiniLM-Raum wie im Vorfilter — kein DOI nötig,
erreicht damit die Kernzeitschriften ohne OpenAlex-Anreicherung. Fehlt der Index,
ist `bloecke` leer und das Screening verhält sich wie bisher.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INDEX_NPZ = PROJECT_ROOT / "beispiel_index.npz"

# Als Zusatz zum Screening-Systemprompt, nur wenn Beispiele mitlaufen. Englisch
# wie der übrige Prompt; die Verdikte bleiben in der Domänensprache des Nutzers.
HINWEIS = (
    "\n\n=== NEAREST PAST DECISIONS ===\n"
    "For most articles the batch shows a line 'Frühere Urteile des Nutzers zu "
    "ähnlichen Artikeln:' listing this user's OWN past decisions on the "
    "semantically most similar articles, each as \"title\" -> verdict. These are "
    "the strongest available evidence of how THIS user judges this region of the "
    "literature — weight them above generic topical impressions. They are "
    "examples, not rules: a given article may still warrant a different call, and "
    "the neighbours can disagree among themselves. Verdicts: ignorieren = drop, "
    "scannen/lesenswert/pflichtlektuere = keep (increasing interest)."
)

_STATE: "_Index | None" = None
_GELADEN = False


def _norm_titel(t: str | None) -> str:
    return "".join(ch for ch in (t or "").lower() if ch.isalnum())


class _Index:
    def __init__(self, data) -> None:
        self.emb = data["emb"].astype("float32")        # (n, d), normiert
        self.titles = list(data["titles"])
        self.verdicts = list(data["verdicts"])
        self.memos = list(data["memos"])
        self.norm_titles = [_norm_titel(t) for t in self.titles]


def _load() -> "_Index | None":
    global _STATE, _GELADEN
    if _GELADEN:
        return _STATE
    _GELADEN = True
    if not INDEX_NPZ.exists():
        _STATE = None
        return None
    try:
        _STATE = _Index(np.load(INDEX_NPZ, allow_pickle=True))
    except Exception:
        _STATE = None
    return _STATE


def verfuegbar() -> bool:
    return _load() is not None


def _zeile(idx: int, ix: "_Index") -> str:
    titel = (ix.titles[idx] or "")[:75].replace("\n", " ").strip()
    zeile = f'"{titel}" -> {ix.verdicts[idx]}'
    memo = (ix.memos[idx] or "").strip().replace("\n", " ")
    if memo and len(memo) <= 60:
        zeile += f" ({memo})"
    return zeile


def bloecke(articles: list[dict], k: int = 5) -> dict[str, str]:
    """id -> vorformatierte Beispielzeile der k nächsten beurteilten Artikel.

    articles: dicts mit id, title, abstract (oder openalex_abstract).
    Leeres dict, wenn der Index fehlt. Titelgleiche Nachbarn (derselbe, schon
    beurteilte Artikel) fallen raus — sonst zitiert ein Kandidat sich selbst.
    """
    ix = _load()
    if ix is None or not articles:
        return {}
    from journal_bot import textembed

    texte = [f"{a.get('title') or ''}. "
             f"{a.get('abstract') or a.get('openalex_abstract') or ''}".strip()
             for a in articles]
    emb = textembed.encode(texte)
    sim = emb @ ix.emb.T                                  # (m, n) Kosinus
    aus: dict[str, str] = {}
    for a, reihe in zip(articles, sim):
        selbst = _norm_titel(a.get("title"))
        order = np.argsort(reihe)[::-1]
        zeilen = []
        for j in order:
            if ix.norm_titles[int(j)] == selbst:
                continue
            zeilen.append(_zeile(int(j), ix))
            if len(zeilen) >= k:
                break
        if zeilen:
            aus[a["id"]] = ("Frühere Urteile des Nutzers zu ähnlichen Artikeln: "
                            + " | ".join(zeilen))
    return aus
