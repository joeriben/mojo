"""Iter 01 — Fundament: keep-all-Floor + Einzelsignal-Schwellen.

Zweck: ehrlicher Boden. Was leisten die rohen werk-geerdeten Einzelsignale je allein
als binäre keep-Regel? Belegt Benjamins These „1 geteilte Ref = primitive Suchfunktion".
KEINE Komplexität — der Floor, gegen den Komplexität sich rechtfertigen muss.
"""
import sys; sys.path.insert(0, "scripts")
import pandas as pd
import fm_eval as E

df = E.load()
yk = df["ykeep"]

def bin_metrics(name, keep_mask):
    pred3 = pd.Series(["scannen" if k else "ignorieren" for k in keep_mask])
    m = E.metrics(df["y3"], pred3)
    print(f"{name:<38} f1_keep={m['f1_keep']:.3f}  keepPrec={m['keep_prec']:.3f}  "
          f"keepRec={m['keep_recall']:.3f}  LES-Rec={m['les_recall']:.3f}")
    return m

print(f"n={len(df)}  keep-Basisrate={yk.mean():.3f}\n")
bin_metrics("keep-all (Floor)", [True]*len(df))
bin_metrics("own_coupling_union >= 1", df["f_own_coupling_union"] >= 1)
bin_metrics("citation_hit_count >= 1", df["f_citation_hit_count"] >= 1)
bin_metrics("trigger_author_match == 1", df["f_trigger_author_match"] == 1)
bin_metrics("ref_overlap_authored >= 1", df["f_ref_overlap_authored"] >= 1)
bin_metrics("UNION der vier Signale", (df["f_own_coupling_union"] >= 1) |
            (df["f_citation_hit_count"] >= 1) | (df["f_trigger_author_match"] == 1) |
            (df["f_ref_overlap_authored"] >= 1))

# Wie viele keep-Artikel besitzen ÜBERHAUPT eines dieser Signale? (Recall-Decke der Bibliometrie)
keepers = df[yk == 1]
any_sig = ((keepers["f_own_coupling_union"] >= 1) | (keepers["f_citation_hit_count"] >= 1) |
           (keepers["f_trigger_author_match"] == 1) | (keepers["f_ref_overlap_authored"] >= 1))
print(f"\nkeep-Artikel mit MIND. EINEM werk-geerdeten Signal: {any_sig.sum()}/{len(keepers)} "
      f"({any_sig.mean():.1%}) → bibliometrische Recall-Decke")
