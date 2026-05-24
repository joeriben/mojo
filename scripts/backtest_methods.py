"""Algorithmische Triage-Verfahren für den Backtest.

WICHTIG — Methodische Disziplin:
Alle Verfahren dürfen AUSSCHLIESSLICH non-LLM-Daten verwenden. Erlaubt:
  - articles.{title, abstract, openalex_abstract, authors_json, doi, year, journal_short}
  - articles.{crossref_refs, openalex_refs, openalex_topics, openalex_concepts}
  - articles.citation_hits_json  (eigener Citation-Tracker, kein LLM)
  - corpus.json.{authored_all, publications}  (Zotero-Export + Original-Texte)
  - projects.json  (vom User formuliert)

Verboten (würde die Aussage "Algorithmus statt LLM" kontaminieren):
  - summaries.json  (Opus-generierte Summaries)
  - articles.agent_verdict / agent_entry_json  (Agent-Output)
  - articles.selection_mode / discourse_indicator / signal_group / suggested_subgroup
    (vom Screening-LLM gesetzte Triage-Metadaten)

Der Backtest-Runner (backtest_run.py) füttert diese Verfahren mit
features_gold.parquet und vergleicht Predictions gegen user_verdict (Goldstandard).
agent_verdict wird NUR als Vergleichs-Baseline am Schluss herangezogen.

Jede Methode implementiert .score(df) → pd.Series[float] (kontinuierlich, höher = relevanter)
und .predict(df) → pd.Series[str] (kategorial: ignorieren | scannen | lesenswert).
"""
from __future__ import annotations

import json
import math
from abc import ABC, abstractmethod
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "backtest_data"

VERDICT_CLASSES = ["ignorieren", "scannen", "lesenswert"]


def thresholds_to_predict(score: pd.Series,
                          thr_scannen: float,
                          thr_lesenswert: float) -> pd.Series:
    """Mappe Score auf 3-Klassen-Verdict per zwei Schwellen."""
    out = pd.Series(["ignorieren"] * len(score), index=score.index)
    out[score >= thr_scannen] = "scannen"
    out[score >= thr_lesenswert] = "lesenswert"
    return out


class Method(ABC):
    name: str = "base"

    @abstractmethod
    def score(self, df: pd.DataFrame) -> pd.Series:
        ...

    def predict(self, df: pd.DataFrame, **kw) -> pd.Series:
        s = self.score(df)
        return thresholds_to_predict(s,
                                     kw.get("thr_scannen", 0.5),
                                     kw.get("thr_lesenswert", 1.5))


# ─────────────────────────────── M1: Citation-Hit-Only ──────────────────────

class M1_CitationHit(Method):
    """≥1 citation_hit → lesenswert; sonst ignorieren.
    Score = Anzahl Citation-Hits (clipped at 5)."""
    name = "M1_CitationHit"

    def score(self, df: pd.DataFrame) -> pd.Series:
        return df["f_citation_hit_count"].clip(0, 5).astype(float)

    def predict(self, df, thr_scannen=0.5, thr_lesenswert=1.0) -> pd.Series:
        return thresholds_to_predict(self.score(df), thr_scannen, thr_lesenswert)


# ─────────────────────────────── M2: Trigger-Author-Only ────────────────────

class M2_TriggerAuthor(Method):
    """Trigger-Autor unter den Authors → lesenswert."""
    name = "M2_TriggerAuthor"

    def score(self, df: pd.DataFrame) -> pd.Series:
        return df["f_trigger_author_match"].astype(float)

    def predict(self, df, thr_scannen=0.5, thr_lesenswert=0.5) -> pd.Series:
        s = self.score(df)
        # binär: 0 → ignorieren, 1 → lesenswert
        out = pd.Series(["ignorieren"] * len(s), index=s.index)
        out[s >= 0.5] = "lesenswert"
        return out


# ─────────────────────────────── M3: Citation OR Trigger ────────────────────

class M3_CitationOrTrigger(Method):
    """M1 ∨ M2: Disjunktion. ≥1 Citation-Hit ODER Trigger-Autor → lesenswert.
    Score = max(citation_hit_count, 5*trigger_match)."""
    name = "M3_CitationOrTrigger"

    def score(self, df: pd.DataFrame) -> pd.Series:
        cit = df["f_citation_hit_count"].clip(0, 5).astype(float)
        trg = (df["f_trigger_author_match"] * 5).astype(float)
        return pd.concat([cit, trg], axis=1).max(axis=1)

    def predict(self, df, thr_scannen=0.5, thr_lesenswert=1.0) -> pd.Series:
        return thresholds_to_predict(self.score(df), thr_scannen, thr_lesenswert)


# ─────────────────────────────── M4: Topic/Concept-Jaccard ─────────────────

class M4_TopicConceptJaccard(Method):
    """Jaccard-Similarity zwischen Artikel-Topics/Concepts und Korpus-Profil.
    Korpus-Profil = Topics/Concepts aller Trigger-Autor-Artikel + aller Artikel mit
    citation_hits>0 (Diskurs-Nachbarschaft Benjamins, unabhängig vom user_verdict)."""
    name = "M4_TopicConceptJaccard"

    def __init__(self, corpus_topics: set[str], corpus_concepts: set[str]):
        self.corpus_topics = corpus_topics
        self.corpus_concepts = corpus_concepts

    @staticmethod
    def _jaccard(s1: set[str], s2: set[str]) -> float:
        if not s1 or not s2:
            return 0.0
        return len(s1 & s2) / len(s1 | s2)

    def score(self, df: pd.DataFrame) -> pd.Series:
        scores = []
        for topics_str, concepts_str in zip(df["topics"], df["concepts"]):
            t = set(topics_str.split("|")) if topics_str else set()
            c = set(concepts_str.split("|")) if concepts_str else set()
            jt = self._jaccard(t, self.corpus_topics)
            jc = self._jaccard(c, self.corpus_concepts)
            scores.append(max(jt, jc))
        return pd.Series(scores, index=df.index)

    def predict(self, df, thr_scannen=0.2, thr_lesenswert=0.4) -> pd.Series:
        return thresholds_to_predict(self.score(df), thr_scannen, thr_lesenswert)


# ─────────────────────────────── M5: Reference-Overlap Trigger-Nbhd ────────

class M5_RefOverlapTrigger(Method):
    """Crossref-Ref-Overlap mit aggregierter Trigger-Nachbarschaft.
    Score = log1p(f_ref_overlap_trigger) — log dämpft Long-Tail."""
    name = "M5_RefOverlapTrigger"

    def score(self, df: pd.DataFrame) -> pd.Series:
        return np.log1p(df["f_ref_overlap_trigger"].astype(float))

    def predict(self, df, thr_scannen=1.0, thr_lesenswert=2.0) -> pd.Series:
        return thresholds_to_predict(self.score(df), thr_scannen, thr_lesenswert)


# ─────────────────────────────── M6: TF-IDF Abstract Similarity ────────────

class M6_TfidfSimilarity(Method):
    """TF-IDF auf Abstract gegen Korpus-Text (corpus.json/publications + projects.json).
    Score = max cosine similarity zu allen Korpus-Dokumenten. Non-LLM."""
    name = "M6_TfidfSimilarity"

    def __init__(self, corpus_texts: list[str], language: str = "german"):
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        # multilingual: keine Stopwords (mix DE/EN)
        self.vec = TfidfVectorizer(ngram_range=(1, 2), min_df=1, max_df=0.95,
                                   sublinear_tf=True, lowercase=True)
        self.corpus_matrix = self.vec.fit_transform(corpus_texts)
        self._cos = cosine_similarity

    def score(self, df: pd.DataFrame) -> pd.Series:
        texts = (df["title"].fillna("") + " " + df["abstract"].fillna("")).tolist()
        x = self.vec.transform(texts)
        sim = self._cos(x, self.corpus_matrix)  # (n_articles, n_corpus_docs)
        return pd.Series(sim.max(axis=1), index=df.index)

    def predict(self, df, thr_scannen=0.1, thr_lesenswert=0.25) -> pd.Series:
        return thresholds_to_predict(self.score(df), thr_scannen, thr_lesenswert)


# ─────────────────────────────── M7: Sentence-Embedding Cosine ────────────

class M7_EmbeddingSimilarity(Method):
    """Embedding-Cosine zu Korpus-Embeddings.
    Default-Modell: BAAI/bge-m3 (1024-dim, multilingual, sehr stark für DE/EN
    Forschungstexte). Fallback: paraphrase-multilingual-MiniLM-L12-v2.

    Score = max cosine similarity. Erweiterte Features (max, mean, top-5-mean,
    Anzahl >0.6, separat zu authored vs. nicht-authored) werden via
    compute_embedding_features() für M8 bereitgestellt.
    """
    name = "M7_EmbeddingSimilarity"

    def __init__(self, corpus_texts: list[str],
                 model_name: str = "BAAI/bge-m3",
                 authored_idx: list[int] | None = None,
                 n_clusters: int = 0,
                 cluster_seed: int = 42):
        from sentence_transformers import SentenceTransformer
        self.model = SentenceTransformer(model_name)
        self.model_name = model_name
        self.corpus_emb = self.model.encode(corpus_texts, normalize_embeddings=True,
                                            show_progress_bar=False, batch_size=4)
        # authored_idx markiert welche der corpus_texts authored_all sind (vs. projects)
        self.authored_idx = (np.array(authored_idx, dtype=int)
                             if authored_idx is not None else None)
        self._article_emb_cache: tuple[tuple[str, ...], np.ndarray] | None = None
        # ── Verortungs-Cluster (Iteration 6) ────────────────────────────────
        # Hypothese: Benjamins 5 Verortungen sind als Cluster im BGE-M3-Raum
        # der authored_all latent vorhanden. K-Means(k=5) auf den authored-
        # Embeddings; Centroids werden L2-renormiert, sodass die Cosines wieder
        # stabil im [-1,1]-Korridor liegen.
        self.cluster_centroids: np.ndarray | None = None
        self.cluster_sizes: np.ndarray | None = None
        self.n_clusters = n_clusters
        if (n_clusters > 0
                and self.authored_idx is not None
                and len(self.authored_idx) >= n_clusters):
            from sklearn.cluster import KMeans
            authored_emb = self.corpus_emb[self.authored_idx]
            km = KMeans(n_clusters=n_clusters, random_state=cluster_seed,
                        n_init=10)
            km.fit(authored_emb)
            centroids = km.cluster_centers_
            # L2-renormieren (Mittel von Einheitsvektoren ist nicht unitär)
            norms = np.linalg.norm(centroids, axis=1, keepdims=True)
            norms[norms == 0] = 1.0
            self.cluster_centroids = centroids / norms
            # Cluster-Sizes für Reporting (sortiert)
            self.cluster_sizes = np.bincount(km.labels_, minlength=n_clusters)

    def _encode_articles(self, df: pd.DataFrame) -> np.ndarray:
        texts = (df["title"].fillna("") + " " + df["abstract"].fillna("")).tolist()
        key = tuple(texts)
        if self._article_emb_cache and self._article_emb_cache[0] == key:
            return self._article_emb_cache[1]
        emb = self.model.encode(texts, normalize_embeddings=True,
                                show_progress_bar=False, batch_size=4)
        self._article_emb_cache = (key, emb)
        return emb

    def score(self, df: pd.DataFrame) -> pd.Series:
        emb = self._encode_articles(df)
        sim = emb @ self.corpus_emb.T
        return pd.Series(sim.max(axis=1), index=df.index)

    def get_article_embeddings(self, df: pd.DataFrame) -> np.ndarray | None:
        """Liefert die L2-normierten Embeddings der Artikel (für kNN-Features).
        Wenn das Modell bereits freigegeben wurde, nutzt nur den Cache.
        Gibt None zurück, wenn weder Modell noch passender Cache verfügbar."""
        texts = (df["title"].fillna("") + " " + df["abstract"].fillna("")).tolist()
        key = tuple(texts)
        if self._article_emb_cache and self._article_emb_cache[0] == key:
            return self._article_emb_cache[1]
        if self.model is None:
            return None
        return self._encode_articles(df)

    def compute_embedding_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Reichere Embedding-basierte Features für M8."""
        emb = self._encode_articles(df)
        sim = emb @ self.corpus_emb.T  # (n_articles, n_corpus)
        n_corpus = sim.shape[1]
        k = min(5, n_corpus)
        sorted_sim = np.sort(sim, axis=1)[:, ::-1]
        feats = pd.DataFrame(index=df.index)
        feats["f_emb_max"] = sim.max(axis=1)
        feats["f_emb_mean"] = sim.mean(axis=1)
        feats[f"f_emb_top{k}_mean"] = sorted_sim[:, :k].mean(axis=1)
        feats["f_emb_n_high"] = (sim >= 0.60).sum(axis=1)
        feats["f_emb_n_vhigh"] = (sim >= 0.70).sum(axis=1)
        if self.authored_idx is not None and len(self.authored_idx) > 0:
            mask_auth = np.zeros(n_corpus, dtype=bool)
            mask_auth[self.authored_idx] = True
            sim_auth = sim[:, mask_auth]
            if sim_auth.shape[1] > 0:
                feats["f_emb_auth_max"] = sim_auth.max(axis=1)
                feats["f_emb_auth_mean"] = sim_auth.mean(axis=1)
                k2 = min(5, sim_auth.shape[1])
                feats[f"f_emb_auth_top{k2}_mean"] = np.sort(sim_auth, axis=1)[:, -k2:].mean(axis=1)
        # ── Verortungs-Cluster-Cosines (Iteration 6) ────────────────────────
        if self.cluster_centroids is not None:
            sim_clu = emb @ self.cluster_centroids.T   # (n_articles, k)
            for i in range(sim_clu.shape[1]):
                feats[f"f_emb_clu_{i}_cos"] = sim_clu[:, i]
            # Spread (max - second-max): wie scharf ist die Verortungs-Affinität?
            sorted_clu = np.sort(sim_clu, axis=1)[:, ::-1]
            feats["f_emb_clu_max"] = sorted_clu[:, 0]
            if sim_clu.shape[1] >= 2:
                feats["f_emb_clu_spread"] = sorted_clu[:, 0] - sorted_clu[:, 1]
            feats["f_emb_clu_argmax"] = np.argmax(sim_clu, axis=1).astype(float)
            feats["f_emb_clu_n_high"] = (sim_clu >= 0.55).sum(axis=1).astype(float)
        return feats

    def predict(self, df, thr_scannen=0.5, thr_lesenswert=0.65) -> pd.Series:
        return thresholds_to_predict(self.score(df), thr_scannen, thr_lesenswert)


# ─────────────────────────────── M8: Combined ML ───────────────────────────

class M8_CombinedML(Method):
    """Logistic Regression / Gradient Boosting auf allen numerischen Features
    + Score von M6/M7. Wird in backtest_run.py mit Cross-Val trainiert."""
    name = "M8_CombinedML"

    def __init__(self, clf, feature_cols: list[str]):
        self.clf = clf
        self.feature_cols = feature_cols

    def fit(self, df: pd.DataFrame, y: pd.Series):
        self.clf.fit(df[self.feature_cols].values, y.values)

    def score(self, df: pd.DataFrame) -> pd.Series:
        """Score = Wahrscheinlichkeit für ≥lesenswert."""
        classes = list(self.clf.classes_)
        proba = self.clf.predict_proba(df[self.feature_cols].values)
        if "lesenswert" in classes:
            return pd.Series(proba[:, classes.index("lesenswert")], index=df.index)
        return pd.Series(np.zeros(len(df)), index=df.index)

    def predict(self, df, **_) -> pd.Series:
        return pd.Series(self.clf.predict(df[self.feature_cols].values), index=df.index)


# ─────────────────────────────── M9: Cascade ───────────────────────────────

class M9_Cascade(Method):
    """ML-Default mit Veto-Overlays:

    Basis-Layer: M8-Prediction (out-of-fold) als Ausgangspunkt.

    Veto-Up (87.5% Lesenswert-Precision empirisch):
      f_citation_hit_count ≥ cit_thr  OR  f_trigger_author_match == 1
      → forced "lesenswert"

    Optional Coauthor-Boost (Schwelle für Coauthor-Hits):
      f_coauthor_hits ≥ coauthor_thr → mindestens "scannen"

    Optional Veto-Down (NUR wenn ML noch zwischen ign/scn schwankt):
      Wenn ML-Prediction != "lesenswert" UND alle Soft-Signale unter q-Quantil
      → "ignorieren" (cleanup für Müll).
    """
    name = "M9_Cascade"

    def __init__(self,
                 score_lookup: dict[str, pd.Series],
                 m8_pred: pd.Series,
                 m8_proba_les: pd.Series,
                 cit_thr: int = 1,
                 use_trigger: bool = True,
                 coauthor_thr: int | None = 2,
                 veto_down_quantile: float | None = 0.10):
        self.score_lookup = score_lookup
        self.m8_pred = m8_pred
        self.m8_proba_les = m8_proba_les
        self.cit_thr = cit_thr
        self.use_trigger = use_trigger
        self.coauthor_thr = coauthor_thr
        self.veto_down_quantile = veto_down_quantile

    def score(self, df: pd.DataFrame) -> pd.Series:
        return self.m8_proba_les

    def predict(self, df: pd.DataFrame, **_) -> pd.Series:
        # Start mit M8-Prediction
        out = self.m8_pred.copy()

        # Stage Veto-Down: ML sagt nicht "lesenswert" UND alle Soft-Scores
        # sind im untersten Quantil → "ignorieren"
        if self.veto_down_quantile is not None and self.score_lookup:
            veto_down = pd.Series(True, index=df.index)
            for nm, s in self.score_lookup.items():
                q = float(np.nanquantile(s.values, self.veto_down_quantile))
                veto_down &= (s <= q)
            # Nur überschreiben wenn ML nicht "lesenswert" gesagt hat
            mask = veto_down & (out != "lesenswert")
            out[mask] = "ignorieren"

        # Stage Coauthor-Boost: erzwinge mindestens scannen
        if self.coauthor_thr is not None:
            ca_hit = df["f_coauthor_hits"] >= self.coauthor_thr
            mask = ca_hit & (out == "ignorieren")
            out[mask] = "scannen"

        # Stage Veto-Up: explizite Signale → lesenswert (Highest precision)
        cit_hit = df["f_citation_hit_count"] >= self.cit_thr
        veto_up = cit_hit.copy()
        if self.use_trigger:
            veto_up = veto_up | (df["f_trigger_author_match"] == 1)
        out[veto_up] = "lesenswert"

        return out


# ─────────────────────────────── M10: Concept-Score-Vector Cosine ────────


class M10_ConceptVector:
    """Sparse Concept-Score-Vector Cosine zu einem Korpus-Concept-Profil.

    Hypothese: OpenAlex liefert pro Artikel benannte Topics/Concepts mit Scores
    (0..1). Wenn wir das Korpus-Profil als gewichteten Vektor (mean score über
    alle Korpus-Artikel mit Trigger-Match oder citation_hit) bauen, ist die
    Cosine-Similarity zu diesem Vektor ein direktes Signal für "wie nah am
    Diskurs", semantisch unabhängig vom Embedding (deckt Lücken, wo der Abstract
    unscharf ist, aber die OpenAlex-Klassifikation klar).

    Inputs:
      concept_score_lookup: dict[article_id, dict[concept_name, score]]
      corpus_profile: dict[concept_name, weight]  (z.B. mean score über Nbhd)
    """
    name = "M10_ConceptVector"

    def __init__(self, concept_score_lookup: dict[str, dict[str, float]],
                 corpus_profile: dict[str, float]):
        self.concept_score_lookup = concept_score_lookup
        # L2-Norm des Korpus-Profils vorberechnen
        keys = sorted(corpus_profile.keys())
        self.keys = keys
        self.profile_vec = np.array([corpus_profile[k] for k in keys], dtype=float)
        norm = np.linalg.norm(self.profile_vec)
        self.profile_norm = float(norm) if norm > 0 else 1.0
        self.profile_dict = corpus_profile

    def score(self, df: pd.DataFrame) -> pd.Series:
        scores: list[float] = []
        for aid in df["id"]:
            v = self.concept_score_lookup.get(str(aid)) or {}
            if not v:
                scores.append(0.0)
                continue
            # Dot-Product über die Schnittmenge der Keys
            dot = 0.0
            for k, sc in v.items():
                w = self.profile_dict.get(k)
                if w:
                    dot += float(sc) * float(w)
            # Norm des Artikel-Vectors
            article_norm = float(np.sqrt(sum(float(s) * float(s) for s in v.values()))) or 1.0
            scores.append(dot / (article_norm * self.profile_norm))
        return pd.Series(scores, index=df.index)

    def compute_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Multi-Stat-Features: cosine, top-1-concept-weight, n_overlap_concepts."""
        feats = pd.DataFrame(index=df.index)
        cos_vals = []
        max_w_vals = []
        n_overlap_vals = []
        sum_w_vals = []
        for aid in df["id"]:
            v = self.concept_score_lookup.get(str(aid)) or {}
            if not v:
                cos_vals.append(0.0); max_w_vals.append(0.0)
                n_overlap_vals.append(0); sum_w_vals.append(0.0)
                continue
            dot = 0.0; n_ov = 0; mx = 0.0; sm = 0.0
            for k, sc in v.items():
                w = self.profile_dict.get(k)
                if w:
                    prod = float(sc) * float(w)
                    dot += prod
                    n_ov += 1
                    sm += prod
                    if prod > mx:
                        mx = prod
            article_norm = float(np.sqrt(sum(float(s) * float(s) for s in v.values()))) or 1.0
            cos_vals.append(dot / (article_norm * self.profile_norm))
            max_w_vals.append(mx)
            n_overlap_vals.append(n_ov)
            sum_w_vals.append(sm)
        feats["f_concept_cosine"] = cos_vals
        feats["f_concept_max_weight"] = max_w_vals
        feats["f_concept_overlap_n"] = n_overlap_vals
        feats["f_concept_sum_weight"] = sum_w_vals
        return feats

    def predict(self, df: pd.DataFrame, thr_scannen: float = 0.10,
                thr_lesenswert: float = 0.30) -> pd.Series:
        return thresholds_to_predict(self.score(df), thr_scannen, thr_lesenswert)


def build_corpus_concept_profile_weighted(
    concept_score_lookup: dict[str, dict[str, float]],
    nbhd_ids: list[str],
) -> dict[str, float]:
    """Mittlerer Concept-Score über die Trigger-/Citation-Nachbarschaft."""
    accum: dict[str, list[float]] = {}
    n_total = 0
    for aid in nbhd_ids:
        v = concept_score_lookup.get(str(aid))
        if not v:
            continue
        n_total += 1
        for k, sc in v.items():
            accum.setdefault(k, []).append(float(sc))
    # Gewicht = mean_score * (n_present / n_total)  → bevorzugt häufige UND starke
    if n_total == 0:
        return {}
    return {k: float(np.mean(scores)) * (len(scores) / n_total)
            for k, scores in accum.items()}


# ─────────────────────────────── Helper: Korpus-Profile bauen ──────────────

def build_corpus_topic_concept_profile(features_df: pd.DataFrame) -> tuple[set[str], set[str]]:
    """Topics/Concepts aller Artikel mit Trigger-Autor ODER ≥1 citation_hit
    — als Approximation an Benjamins Diskurs-Nachbarschaft. Bewusst unabhängig
    von user_verdict (sonst Leakage)."""
    mask = (features_df["f_trigger_author_match"] == 1) | (features_df["f_citation_hit_count"] >= 1)
    nbhd = features_df[mask]
    topics: set[str] = set()
    concepts: set[str] = set()
    for t in nbhd["topics"]:
        if t:
            topics |= set(t.split("|"))
    for c in nbhd["concepts"]:
        if c:
            concepts |= set(c.split("|"))
    return topics, concepts


def load_corpus_texts(return_authored_idx: bool = False) -> list[str] | tuple[list[str], list[int]]:
    """Korpus-Text-Snippets — AUSSCHLIESSLICH non-LLM-Quellen:

      - corpus.json.publications[].abstract  (Original-Abstracts aus Zotero/Publisher)
      - corpus.json.publications[].fulltext  (extrahierte Volltexte)
      - corpus.json.authored_all[].title     (Titel der 160 Publikationen)
      - projects.json                        (vom User geschriebene Projektbeschreibungen)

    NICHT verwendet: summaries.json (Opus-LLM-generiert → würde Methodik kontaminieren).
    Wenn return_authored_idx=True: gibt zusätzlich Indizes der "authored"-Texte zurück
    (publications + authored_all-Titel), so dass M7 diese gegenüber den projects.json-
    Texten gewichten kann.
    """
    texts: list[str] = []
    authored_idx: list[int] = []
    corpus = json.loads((ROOT / "corpus.json").read_text())

    for pub in corpus.get("publications", []):
        if not isinstance(pub, dict):
            continue
        title = pub.get("title") or ""
        abstract = pub.get("abstract") or ""
        fulltext = pub.get("fulltext") or ""
        if fulltext:
            fulltext = fulltext[:5000]
        t = ". ".join(s for s in (title, abstract, fulltext) if s.strip())
        if t.strip():
            authored_idx.append(len(texts))
            texts.append(t.strip())

    seen_titles = set()
    for pub in corpus.get("authored_all", []):
        title = (pub.get("title") or "").strip()
        if title and title not in seen_titles:
            seen_titles.add(title)
            authored_idx.append(len(texts))
            texts.append(title)

    projects = json.loads((ROOT / "projects.json").read_text())
    if isinstance(projects, dict):
        proj_list = projects.get("projects", [])
        if isinstance(proj_list, list):
            for p in proj_list:
                if isinstance(p, dict):
                    chunks: list[str] = []
                    for v in p.values():
                        if isinstance(v, str):
                            chunks.append(v)
                        elif isinstance(v, list):
                            chunks.extend(str(x) for x in v if isinstance(x, (str, int)))
                    text = " ".join(c for c in chunks if c)
                    if text.strip():
                        texts.append(text.strip())
    if return_authored_idx:
        return texts, authored_idx
    return texts
