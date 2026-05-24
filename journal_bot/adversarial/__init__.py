"""Adversariale Set-Features für die Cascade-Triage (MOJO 2.0 §2.2).

Hintergrund: own_coupling (§2.1) detektiert, was Benjamin *schon* zitiert.
Das ist ein Veto-Up-Signal: hohe Übereinstimmung mit dem eigenen Werk
bedeutet "anschlussfähig zur bisherigen Forschung". Was es NICHT detektiert,
sind Blind Spots — Diskurse, die Benjamin (noch) nicht aufgegriffen hat,
die aber in benachbarten Diskursfeldern (Macgilchrist, Jarke, Chun) gerade
relevant sind.

Adversariales Set: `trigger_refs \\ benjamin_refs` — Refs, die die drei
Trigger-Autoren zitieren, die in Benjamins eigenen Refs aber FEHLEN.
Wenn ein Artikel viele dieser nicht-redundanten Trigger-Refs zitiert,
ist er ein Kandidat für eine produktive Erweiterung des Lektüre-Stands —
genau das, was Iter 11 als "Wrong-LES" identifizierte (Sachen, die der
Algorithmus als IGN klassifiziert hat, die Benjamin aber als LES markierte).

Trigger-Autoren: Macgilchrist, Jarke, Chun (Wendy Hui Kyong) — siehe
`docs/context/project_trigger_autoren.md`.

Architektur:
- `trigger_refs.py`: AdversarialIndex (Set-Differenz, persistent als JSON).
- `signals.signal_adversarial_blindspot`: liest den Index, berechnet
  IDF-gewichteten Score, ähnlich `signal_own_coupling`.
- Cascade-Regel: in der `_infer_*`-Funktionen, abhängig von Daten-Analyse
  entweder Veto-Up oder Empfehlungs-Indikator.
"""
