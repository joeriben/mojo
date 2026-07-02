"""Iter 04 — Baummodell (HistGradientBoosting) unter CV.

Iter 03-Kritik: LogReg ist linear, verpasst Interaktionen; own+content schlug ALL.
Test: fängt ein Baummodell Interaktionen, und hält own+content > ALL auch hier?
HistGBM (sklearn-eigen, NaN-nativ, keine Extra-Dependency).
"""
import sys; sys.path.insert(0, "scripts")
import numpy as np
import fm_eval as E
from sklearn.ensemble import HistGradientBoostingClassifier

df = E.load()
# Klassengewichte: LES/SCAN seltener → leichtes Upweight (kostensensitiv, nicht 'balanced'-brutal)
import pandas as pd
cw = {"ignorieren": 1.0, "scannen": 1.6, "lesenswert": 2.2}
sw = df["y3"].map(cw).values

def mk():
    return HistGradientBoostingClassifier(max_depth=3, learning_rate=0.06,
                                           max_iter=300, l2_regularization=1.0,
                                           min_samples_leaf=20, random_state=42)

class W:  # Wrapper, der sample_weight aus dem Trainingsindex zieht
    def __init__(s): s.m = mk()
    def fit(s, X, y):
        idx = y.index if hasattr(y, "index") else range(len(y))
        s.m.fit(X, y, sample_weight=np.array([cw[v] for v in (y.values if hasattr(y,'values') else y)]))
        return s
    def predict(s, X): return s.m.predict(X)

print(f"{'Feature-Menge':<24}{'f1_3cls':>8}{'f1_keep':>9}{'LES-Rec':>8}{'keepPrec':>9}")
print("-" * 58)
for name, feats in [("own+content (8)", E.OWN_WORK + E.CONTENT),
                    ("ALL numeric+content", E.NUMERIC_FEATURES + E.SCORE_FEATURES)]:
    X = df[feats].astype(float)
    oof = E.cv_oof(lambda: W(), X, df["y3"])
    m = E.metrics(df["y3"], oof)
    print(f"{name:<24}{m['f1_3cls']:>8.3f}{m['f1_keep']:>9.3f}{m['les_recall']:>8.3f}{m['keep_prec']:>9.3f}")
print("\nReferenz: LogReg own+content 0.514 · Algo-Bar 0.603 · LLM-Decke 0.679")
