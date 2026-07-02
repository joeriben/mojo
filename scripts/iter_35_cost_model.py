"""Iter 35 — Modell M-E Kosten-Bilanz (echte Call-Kosten aus articles.db).

Gemessen: assess(Gemini-3.5-Flash) $0.034/Call, assess(Opus) $0.086, screen(DeepSeek) $0.011.
rich-Ranker = offline (sentence-transformers, $0 marginal); Opus-Summaries = einmalige Senke (~53 Calls).
Kosten pro 100 blinden Artikeln: „assess-alle" vs M-E (Pfad-A-only) vs M-E+Kaskade. CLAUDE.md-Abbruch
bei >$0.15/Artikel. Anteile aus dem Gold-Strom (Pfad B = 43%, Pfad A = 57%).
"""
import sys; sys.path.insert(0, "scripts")
import sqlite3
import numpy as np, pandas as pd
import fm_eval as E

# echte Kosten/Call
con=sqlite3.connect("articles.db")
def call_cost(endpoint, model):
    r=con.execute("SELECT avg(cost_usd) FROM llm_calls WHERE endpoint=? AND model=? AND cost_usd IS NOT NULL",
                  (endpoint,model)).fetchone()
    return r[0] or 0
C_ASSESS=call_cost("assess","google/gemini-3.5-flash")
C_OPUS=call_cost("assess","anthropic/claude-opus-4.6")
C_SCREEN=call_cost("batch_screen","deepseek/deepseek-v3.2")
con.close()
print(f"Echte Call-Kosten: Gemini-assess ${C_ASSESS:.4f} · Opus-assess ${C_OPUS:.4f} · DeepSeek-screen ${C_SCREEN:.4f}")

# Strom-Anteile (Iter 34): Pfad A (abstract-reich) 57%, Pfad B (abstract-arm) 43%
pA, pB = 0.57, 0.43
N=100
print(f"\nKosten pro {N} blinden Artikeln (Pfad A {pA:.0%}, Pfad B {pB:.0%}):")
def line(name, n_assess, c=C_ASSESS, note=""):
    cost=n_assess*c
    flag=" ⚠️ >$0.15/Art!" if c>0.15 else ""
    print(f"  {name:<34}{n_assess:>6.0f} assess-Calls  ${cost:>6.2f}  (${cost/N:.4f}/Art){flag} {note}")

line("MOJO-1 ~ assess ALLE (Gemini)", N)
line("MOJO-1 screen→assess (~40% Überleben)", 0.40*N, note=f"+ {N}×screen ${N*C_SCREEN:.2f}")
line("M-E Pfad-A-only (Gemini)", pA*N, note="0 LES verloren (Iter 34)")
line("M-E Pfad-A Kaskade Top-30% (Gemini)", 0.30*pA*N, note="−LES (Iter 33)")
print(f"\nEinmal-Senke (sunk): Opus-Summaries 53× @ ~${C_OPUS:.3f} = ${53*C_OPUS:.2f} (amortisiert über alle Läufe)")
print(f"rich-Ranker pro Lauf: $0.00 (offline sentence-transformers)")
print(f"\nAbbruch-Schwelle CLAUDE.md: $0.15/Artikel — alle Varianten (Gemini ${C_ASSESS:.3f}) liegen weit darunter.")
print(f"Einzelkosten-Verifikation: erst 2-3 Einzelcalls messen, dann Batch (kein Pauschal-Lauf blind).")
