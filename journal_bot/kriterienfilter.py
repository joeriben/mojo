"""Semantischer Vorfilter — verwirft aussichtslose Artikel VOR dem LLM-Screening.

Kalibriert an den Urteilen des Nutzers (`scripts/kriterienfilter_build.py`),
gemessen ausserhalb der Anpassung: übertragen auf ungesehene Zeitschrift
AUC 0.779 — deutlich über Zeitschriften-Basisrate (0.675) und OpenAlex-Themen
(0.695). Substrat ist ein lokales MiniLM-Embedding von Titel + Abstract; es
braucht KEIN DOI und erreicht damit die Kernzeitschriften, an denen die
OpenAlex-Anreicherung leer bleibt.

Das Modul entscheidet nichts allein. Es verwirft nur die untere Zone — kanal-
abhängig so kalibriert, dass je Kanal höchstens 5 % der »lesenswert« verloren
gehen (im Screening-Kanal, dem Betriebsfall neuer Wochenartikel, 0 % auf der
Stichprobe bei 20 % Auto-Verwerfen). Alles darüber geht unverändert ins LLM-
Screening. Ausfall ist folgenlos: fehlen die Parameter, ist jeder Artikel
`unsicher`, und der Lauf verhält sich wie bisher.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PARAMS_JSON = PROJECT_ROOT / "kriterienfilter_params.json"
PUB_NPY = PROJECT_ROOT / "kriterienfilter_pub.npy"

_STATE: "_Filter | None" = None
_GELADEN = False


def platt_params(dec: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """Platt-Skalierung: eine Sigmoid auf die Basis-Entscheidungswerte legen.

    Macht die Behalten-Wahrscheinlichkeit skalenstabil, damit eine Schwelle
    dasselbe bedeutet, egal wie confident das Vollmodell ist. Gibt (a, b) für
    P = sigmoid(a·dec + b) zurück.
    """
    from sklearn.linear_model import LogisticRegression

    lr = LogisticRegression(C=1e6, max_iter=5000).fit(dec.reshape(-1, 1), y)
    return float(lr.coef_[0][0]), float(lr.intercept_[0])


@dataclass
class Zone:
    zone: str          # "verwerfen" | "unsicher"
    score: float       # kalibrierte Behalten-Wahrscheinlichkeit
    schwelle: float    # angewandte Kanal-Schwelle


class _Filter:
    def __init__(self, params: dict, pub: np.ndarray) -> None:
        self.mean = np.array(params["standardize"]["mean"], dtype="float32")
        self.std = np.array(params["standardize"]["std"], dtype="float32")
        self.coef = np.array(params["coef"], dtype="float32")
        self.intercept = float(params["intercept"])
        # Platt-Kalibrierung (a, b): OHNE sie driftet die Schwelle zwischen
        # OOF- und Vollmodell-Skala (belegt: 0.34 → 51 % Fund-Verlust, mit
        # Kalibrierung 18 %). Fehlt sie in alten Parametern, ist a=1, b=0.
        self.platt_a = float(params.get("platt_a", 1.0))
        self.platt_b = float(params.get("platt_b", 0.0))
        # EINE globale Schwelle — die kanalweisen übertrugen nicht (siehe
        # kriterienfilter_build.py). Ältere Parameter ohne "schwelle" werden
        # konservativ als »nichts verwerfen« gelesen.
        self.schwelle = float(params.get("schwelle", -1.0))
        self.pub = pub

    def _features(self, emb: np.ndarray) -> np.ndarray:
        sim = emb @ self.pub.T
        top = np.sort(sim, axis=1)[:, ::-1]
        naehe = np.stack([top[:, 0], top[:, :5].mean(axis=1)], axis=1)
        return np.hstack([emb, naehe])

    def score(self, emb: np.ndarray) -> np.ndarray:
        X = self._features(emb)
        Xs = (X - self.mean) / self.std
        dec = Xs @ self.coef + self.intercept          # Basis-Entscheidungswert
        return 1.0 / (1.0 + np.exp(-(self.platt_a * dec + self.platt_b)))  # kalibriert



def _load() -> "_Filter | None":
    global _STATE, _GELADEN
    if _GELADEN:
        return _STATE
    _GELADEN = True
    if not (PARAMS_JSON.exists() and PUB_NPY.exists()):
        _STATE = None
        return None
    try:
        params = json.loads(PARAMS_JSON.read_text(encoding="utf-8"))
        _STATE = _Filter(params, np.load(PUB_NPY))
    except Exception:
        _STATE = None
    return _STATE


def verfuegbar() -> bool:
    return _load() is not None


def bewerte(articles: list[dict], kanal: str = "screening") -> dict[str, Zone]:
    """Artikel bewerten; id -> Zone. Leeres dict, wenn der Filter nicht geladen ist.

    articles: dicts mit id, title, abstract (oder openalex_abstract).
    Der Aufrufer verwirft die »verwerfen«-Zone ohne LLM und schickt den Rest
    weiter — recall-sicher durch die globale ≤5 %-Kalibrierung. `kanal` wird
    aktuell nicht mehr zur Schwellenwahl gebraucht (globale Schwelle), bleibt
    aber im Signaturkopf für die Aufrufer erhalten.
    """
    f = _load()
    if f is None or not articles:
        return {}
    from journal_bot import textembed

    texte = [f"{a.get('title') or ''}. "
             f"{a.get('abstract') or a.get('openalex_abstract') or ''}".strip()
             for a in articles]
    emb = textembed.encode(texte)
    scores = f.score(emb)
    aus: dict[str, Zone] = {}
    for a, s in zip(articles, scores):
        zone = "verwerfen" if (f.schwelle >= 0 and s < f.schwelle) else "unsicher"
        aus[a["id"]] = Zone(zone=zone, score=float(s), schwelle=f.schwelle)
    return aus
