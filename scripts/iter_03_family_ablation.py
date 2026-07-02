"""Iter 03 — Feature-Familien-Ablation unter StratifiedKFold-CV.

Welche Familie (own / trigger / content) trägt den 3-Klassen-macro-F1, und wie viel
bringt die Kombination? Sauberes out-of-fold (P5). Modell konstant (balanced LogReg),
damit nur die Feature-Menge variiert.
"""
import sys; sys.path.insert(0, "scripts")
import fm_eval as E
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression

df = E.load()

def mk():
    return make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                         LogisticRegression(max_iter=3000, class_weight="balanced"))

families = {
    "own (5)": E.OWN_WORK,
    "trigger (8)": E.TRIGGER,
    "content (3)": E.CONTENT,
    "own+content (8)": E.OWN_WORK + E.CONTENT,
    "own+trigger (13)": E.OWN_WORK + E.TRIGGER,
    "ALL numeric+content": E.NUMERIC_FEATURES + E.SCORE_FEATURES,
}
print(f"{'Feature-Familie':<24}{'f1_3cls':>8}{'f1_keep':>9}{'LES-Rec':>8}{'keepPrec':>9}")
print("-" * 58)
for name, feats in families.items():
    X = df[feats].astype(float)
    oof = E.cv_oof(mk, X, df["y3"])
    m = E.metrics(df["y3"], oof)
    print(f"{name:<24}{m['f1_3cls']:>8.3f}{m['f1_keep']:>9.3f}{m['les_recall']:>8.3f}{m['keep_prec']:>9.3f}")
print("\nReferenz: Algo-Bar 0.603 · LLM-Decke 0.679 (3cls)")
