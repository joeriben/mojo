"""M-E-Keep-Ranker — operative Verdrahtung der 50er-Filtermodell-Serie.

Implementiert das in `docs/filter_models/iter_50_synthese.md` spezifizierte
Modell M-E für den Wochenlauf (Formel exakt wie iter_46):

    mc = z( z(rich_sim) + 0.5 · z(max(0, pj − G)) )
    final = 1 + mc  falls biblio (own_coupling ≥ 1 ∨ citation ≥ 1), sonst mc

    rich_sim = max. Cosine des Artikels (Titel+Abstract+Concepts+Topics) gegen
               die Opus-Summaries des Eigenwerks (title+summary_de+key_terms+
               named_thinkers), all-MiniLM-L6-v2, L2-normalisiert
    pj       = Empirical-Bayes-Journal-Prior (k=5), G = globale Keep-Rate;
               nur-Lift: der Prior hebt, senkt nie (Serendipitäts-Schutz)
    z        = Min-Max-Skalierung mit EINGEFRORENEN Parametern aus dem
               Gold-Set (scripts/ranker_build_params.py) — kein Within-Wave-
               Scaling, kleine Wellen wären sonst verrauscht

Rollenvertrag (5× bestätigtes Plateau, iter_32/46/50): Der Ranker ist
Vorfilter, Sortierer und Erder — NIE Entscheider. Konkret:
  - Zone "drop" (mc < t_lo, kalibriert: unterhalb des niedrigsten Gold-LES-
    Scores) ist nur eine STIMME; verworfen wird ausschließlich im Konsens mit
    dem LLM-Screening (journal_bot/combine.py, Benjamins Festlegung 2026-05-30).
  - Ein sicher-KEEP-Band existiert nicht (iter_46: leer) — der Ranker
    surfaced nie allein, er sortiert nur die Agent-Reihenfolge (bester zuerst).
  - Kein Urteil ohne Abstract (iter_49: Metadaten-AUC 0.532 = Rauschen) —
    Zone "no_abstract", niemals drop.

Alles lokal und $0 (Embedding via sentence-transformers). Fehlen Parameter-
Datei, summaries.json oder das Modell, degradiert der Lauf transparent auf das
bisherige Verhalten (Ranker aus, Log-Hinweis) — niemals ein harter Abbruch.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from journal_bot.settings import PROJECT_ROOT, SUMMARIES_JSON

if TYPE_CHECKING:  # pragma: no cover
    from journal_bot.store import StoredArticle

RANKER_PARAMS_JSON = PROJECT_ROOT / "ranker_params.json"
EMB_CACHE_DIR = PROJECT_ROOT / ".enrichment_cache" / "ranker"
MODEL_NAME = "all-MiniLM-L6-v2"
PARAMS_VERSION = 1

_MODEL = None  # lazy singleton (Encoder-Load ~2 s, nur bei Bedarf)


def _get_model():
    global _MODEL
    if _MODEL is None:
        from sentence_transformers import SentenceTransformer
        _MODEL = SentenceTransformer(MODEL_NAME)
    return _MODEL


def _encode_normed(texts: list[str]):
    import numpy as np
    m = _get_model()
    v = np.asarray(m.encode(texts, show_progress_bar=False), dtype="float32")
    return v / (np.linalg.norm(v, axis=1, keepdims=True) + 1e-9)


# ── Texte (Provenienz: exakt die Rezeptur der Serie, _build_rich_sim.py) ─────

def rich_pub_texts(summaries: dict) -> list[str]:
    """Eigenwerk-Seite: title + summary_de + key_terms + named_thinkers."""
    out = []
    for e in summaries.values():
        parts = [
            e.get("title", ""),
            e.get("summary_de", ""),
            " ".join(e.get("key_terms", []) or []),
            " ".join(e.get("named_thinkers", []) or []),
        ]
        out.append(" ".join(p for p in parts if p))
    return out


def _names(items: list | None) -> str:
    out = []
    for it in items or []:
        if isinstance(it, dict):
            n = it.get("display_name") or it.get("name") or ""
        else:
            n = str(it)
        if n:
            out.append(n)
    return " ".join(out)


def article_text(sa: "StoredArticle") -> str:
    """Artikel-Seite: Titel + Abstract + Concept-/Topic-Namen (Serie: Spalten
    aus features_gold; hier live aus dem Store rekonstruiert)."""
    abstract = (sa.abstract or "").strip() or (sa.openalex_abstract or "").strip()
    return (
        f"{sa.title or ''}. {abstract}. "
        f"{_names(sa.openalex_concepts)} {_names(sa.openalex_topics)}"
    ).strip()


def summaries_hash(path: Path = SUMMARIES_JSON) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


# ── Empirical-Bayes-Journal-Prior (iter_25, k=5) ─────────────────────────────

def eb_journal_prior(
    journal_keep: list[tuple[str, int]], k: int = 5
) -> tuple[dict[str, float], float]:
    """(journal_short, ykeep)-Paare → (prior je Journal, globale Rate G).

    rate_j = (mean_j·n_j + G·k) / (n_j + k) — dünne Journals zur Globalrate
    geschrumpft (iter_05-Leak-Lektion; iter_25: k=5 optimal).
    """
    if not journal_keep:
        return {}, 0.0
    g = sum(y for _, y in journal_keep) / len(journal_keep)
    agg: dict[str, list[int]] = {}
    for j, y in journal_keep:
        agg.setdefault(j, []).append(y)
    rate = {
        j: (sum(ys) + g * k) / (len(ys) + k)
        for j, ys in agg.items()
    }
    return rate, g


# ── Scoring mit eingefrorenen Parametern ─────────────────────────────────────

def _z(v: float, lo: float, hi: float) -> float:
    """Min-Max mit Clipping auf [0,1] — Werte außerhalb des Gold-Rahmens
    laufen nicht aus der Skala."""
    return min(1.0, max(0.0, (v - lo) / (hi - lo + 1e-9)))


@dataclass
class RankedArticle:
    id: str
    mc: float            # finaler Score (inkl. Biblio-Veto, ∈ [0,2])
    rich_sim: float      # roher max-Cosine
    zone: str            # "drop" | "mid" | "no_abstract"
    biblio: bool


class Ranker:
    def __init__(self, params: dict, pub_emb) -> None:
        self.params = params
        self.pub_emb = pub_emb  # (n_pubs, dim), L2-normiert

    # -- Laden ---------------------------------------------------------------

    @classmethod
    def load(
        cls,
        params_path: Path = RANKER_PARAMS_JSON,
        summaries_path: Path = SUMMARIES_JSON,
        cache_dir: Path = EMB_CACHE_DIR,
    ) -> "Ranker | None":
        """None wenn Parameter/Summaries fehlen — Aufrufer loggt und läuft
        ohne Ranker weiter (transparente Degradation, kein Abbruch)."""
        if not params_path.exists() or not summaries_path.exists():
            return None
        params = json.loads(params_path.read_text(encoding="utf-8"))
        pub_emb = cls._pub_embeddings(summaries_path, cache_dir)
        return cls(params, pub_emb)

    @staticmethod
    def _pub_embeddings(summaries_path: Path, cache_dir: Path):
        """Eigenwerk-Embeddings, gecacht; Rebuild wenn summaries.json sich
        ändert (Hash-Vergleich)."""
        import numpy as np
        cache_dir.mkdir(parents=True, exist_ok=True)
        emb_path = cache_dir / "pub_emb.npy"
        meta_path = cache_dir / "pub_emb_meta.json"
        h = summaries_hash(summaries_path)
        if emb_path.exists() and meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
                if meta.get("hash") == h and meta.get("model") == MODEL_NAME:
                    return np.load(emb_path)
            except (json.JSONDecodeError, OSError, ValueError):
                pass
        summaries = json.loads(summaries_path.read_text(encoding="utf-8"))["summaries"]
        emb = _encode_normed(rich_pub_texts(summaries))
        np.save(emb_path, emb)
        meta_path.write_text(
            json.dumps({"hash": h, "model": MODEL_NAME, "n": int(emb.shape[0]),
                        "built_at": datetime.now(timezone.utc).isoformat()}),
            encoding="utf-8",
        )
        return emb

    # -- Scoring ---------------------------------------------------------------

    def rich_sims(self, sas: list["StoredArticle"]):
        emb = _encode_normed([article_text(sa) for sa in sas])
        return (emb @ self.pub_emb.T).max(axis=1)

    def score(
        self,
        sas: list["StoredArticle"],
        biblio_flags: dict[str, bool],
    ) -> dict[str, RankedArticle]:
        if not sas:
            return {}
        p = self.params
        zp = p["z"]
        prior = p.get("journal_prior", {})
        g = float(p.get("global_keep_rate", 0.0))
        t_lo = float(p["t_lo"])
        rich = self.rich_sims(sas)

        out: dict[str, RankedArticle] = {}
        for i, sa in enumerate(sas):
            r = float(rich[i])
            pj = float(prior.get(sa.journal_short, g))
            lift = max(0.0, pj - g)
            mc_pre = _z(r, zp["rich_min"], zp["rich_max"]) + 0.5 * _z(
                lift, 0.0, zp["lift_max"]
            )
            mc = _z(mc_pre, zp["mc_min"], zp["mc_max"])
            biblio = bool(biblio_flags.get(sa.id, False))
            final = 1.0 + mc if biblio else mc
            has_abstract = bool(
                (sa.abstract or "").strip() or (sa.openalex_abstract or "").strip()
            )
            if not has_abstract:
                zone = "no_abstract"   # iter_49: kein Metadaten-Urteil
            elif final < t_lo:
                zone = "drop"          # nur eine STIMME — Drop nur im Konsens
            else:
                zone = "mid"
            out[sa.id] = RankedArticle(
                id=sa.id, mc=round(final, 4), rich_sim=round(r, 4),
                zone=zone, biblio=biblio,
            )
        return out
