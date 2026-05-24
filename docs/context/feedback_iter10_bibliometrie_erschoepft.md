# Iter 10 Befund: Bibliometrische Features sind erschöpft

**Datum**: 2026-05-24.

**Iter 10 = das fehlte in Iter 1–9**: Benjamin hatte explizit angeregt:
> "Phase 1 ist sogar noch entwickelbar: Wen zitieren die Trigger-Autoren vor allem,
> welche Journals, welcher Werke?"

Diese Anregung wurde in Iter 1–9 übersehen. Iter 10 holt sie nach: pro Trigger-Autor
(Macgilchrist, Jarke, Chun) wurde via OpenAlex die komplette Werk-Bibliographie inkl.
referenced_works gezogen (374 Works, 9 836 Refs), Diskursraum-spezifisch
bibliographisch gekoppelt (Coupling-Score = Anzahl Trigger-Autoren, die einen Ref
zitieren), und als 6 neue Features in den 461-Gold-Backtest gefüttert.

**Befunde**:

1. **Coupling funktioniert als Diagnostik-Werkzeug**: 620 ≥2-coupled Ref-IDs über
   alle Diskursräume; digitale_kultur das einzige mit 13 Triple-Coupling-Refs.
2. **Per-class Signal ist real**: ref_overlap-Features 5–22× LES/IGN-Ratio.
3. **Modell-Plateau bleibt unverändert**: M9_Cascade_TunedBase landet auf 0.600
   (vs Iter-9-Baseline 0.607) — die neuen Features sind **redundant** mit den
   bestehenden f_ref_overlap_trigger und f_ref_overlap_authored.
4. **Wrong-LES bleiben strukturell unerreichbar via Bibliometrie**: wrong-LES (0.77)
   ≈ wrong-IGN (0.67) im 2nd-Degree-Netz — die diskriminative Information liegt
   nicht in Refs/Authors/Journals/Concepts.

**Heuristik-Bug (Kutscher-Fall) als Nebenertrag**:
- Erste Iter-10-Version listete in sparsen Diskursräumen (resilienz, AKB, deutsche,
  bildungstheorie) Coupling-1-Autoren als "Top-Authors-for-Features". Beispiel:
  Nadia Kutscher als idx 24/20 in deutsche/bildungstheorie, obwohl nur 1× von
  Macgilchrist zitiert.
- Fix: `top_authors/journals_for_features` Filter auf `max_trigger_count >= 2`
  in `scripts/iter10_build_trigger_network.py`. Im LogReg-Modell hat der Fix
  0 Predictions verändert (L2-Regularisierung dämpfte Noise selbständig), aber
  für jede LIVE-Pipeline ohne Regularisierung ist der Filter zwingend.

**Methodische Lehre**: 
- Jede neue Heuristik auf OpenAlex-Metadaten (Refs, Authors, Journals, Concepts,
  Topics) korreliert mit den existierenden Bibliometrie-Features.
- Plateau-Diagnose seit Iter 3 (5+ Iterationen) ist endgültig: Bibliometrie ist
  erschöpft, Information muss aus Volltext kommen.

**Konsequenz** (korrigiert 2026-05-24, siehe
`feedback_mojo2_reframe_algorithmic.md`): MOJO 2.0 setzt **primär auf eine
produktive, multi-source, additiv-inkrementelle Refs-Pipeline**
(`journal_bot/own_refs.py`), aus der weitere algorithmische
Veto-Up/Veto-Down-Regeln auf die Cascade andocken (analog
`f_own_coupling_union ≥ 1` aus Iter 11). Volltext-LLM bleibt **gezielte
Eskalation** für ≤10 % Restmenge, nicht Default-Layer. Quellen:
`feedback_volltext_pflicht.md` (korrigiert), `../mojo_2_volltext_sketch.md`
(korrigiert in §2.3, §4, §5, §6, §7, TL;DR).
