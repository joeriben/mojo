# Iter 45 — Trigger-Autoren-Regel: Wert-Eskalation vs. statistische Fata Morgana

## Anforderung
Memory project_trigger_autoren: MacGilchrist/Jarke/Chun → Eskalation unabhängig vom Tier (dokumentierte
harte Regel). Verdient sie — anders als bezugsautoren (Iter 44) — ihren Platz? Zwei Operationalisierungen:
(A) direkter Autoren-Match (Artikel *von* einem Trigger-Autor), (B) Trigger-Ref-Overlap (Artikel *zitiert*
ein Trigger-Autor-Werk). Precision/Recall gegen keep+LES, voll + blinder Strom.

## Messung (`iter_45_trigger_rule.py`)
Patterns (profile.json): `macgilchrist, jarke, wendy chun, wendy hui kyong`.

| Regel | Menge | feuert | Precision | Recall |
|---|---|---|---|---|
| **(A) Autoren-Match** | keep (alle) | 2× | **100 %** | 1 % |
| (A) | LES (alle) | 2× | **100 %** | 3 % |
| (A) | keep (blind) | 0× | — | — |
| **(B) Ref-Overlap** | keep (alle) | 137× | 55 % | 40 % |
| (B) | LES (alle) | 137× | 28 % | 49 % |
| **(B)** | **keep (blind)** | 11× | **9 %** | 4 % |
| (B) | LES (blind) | 11× | **0 %** | 0 % |

Basisrate keep: gesamt 41 %, blind 21 %. **(B)-Lift blind: 9 % / 21 % = 0.4× (unter Basis!).**

## Harte Kritik
- **(A) und (B) sind grundverschieden — und nur (A) verdient den Ranker (P6, P16):** der direkte
  Autoren-Match feuert selten (2×), aber mit **100 % Precision** (beide LES). Das ist die *richtige*
  Trigger-Regel: sie sagt nicht „statistisch relevant", sondern „**Benjamin will per eigener Anweisung
  sehen, was diese 3 publizieren**" — eine **Wert-Eskalation**, keine statistische. Perfekte Precision,
  triviale Recall, nie schädlich: als Veto-Up behalten, gerade weil sie selten und nie falsch ist.
- **(B) ist eine Fata Morgana — schlimmer als bezugsautoren (P15, P16):** der Ref-Overlap sieht auf allen
  Quellen brauchbar aus (55 % keep-Precision), ist aber auf dem **blinden Strom ein NEGATIV-Signal**:
  9 % Precision gegen 21 % Basisrate = **0.4× Lift**, 0 % auf LES. Ein Artikel, der einen Trigger-Autor
  *zitiert*, ist blind *unwahrscheinlicher* ein keeper. Grund: MacGilchrist/Jarke/Chun sind im KI&
  Gesellschaft-Korpus **breit zitiert** — der Overlap markiert „engagiert kritischen Daten/KI-Diskurs
  allgemein" = der **Heuhaufen**, nicht die Nadel. Die 55 % auf „alle Quellen" sind reiner Selection-
  Bias (der intentional-positive Pool ist trigger-ref-dicht selektiert).
- **Generalisiert den Iter-44-Befund (P3):** wie bei bezugsautoren gilt — **Referenz-Overlap ≠ Relevanz.**
  Beide (bez-Werke, Trigger-Werke) sind als *Erdungs*-/Anreicherungs-Signale brauchbar, als *Relevanz*-
  Veto schädlich. Das ist jetzt zweifach unabhängig gemessen und damit ein belastbares Architektur-
  Prinzip, kein Einzelbefund: **Was ein Artikel zitiert, taugt zum Bezug-Text, nicht zum Relevanz-Urteil.**
- **Caveat zu (A) (P3, P14):** (A) feuert im Gold-Snapshot 0× auf dem blinden Strom — keiner der 393
  2026er-Artikel stammt von den 3 Autoren. Das ist kein Defekt, sondern die Natur einer seltenen,
  hochwertigen Regel: in Produktion feuert sie, *wann immer* eine der 3 publiziert (und dann mit der hier
  belegten Top-Precision). Ihr Wert ist nicht messbar an der Recall-Zahl, sondern an der Garantie, kein
  Trigger-Autor-Paper zu verpassen — genau Benjamins Anweisung.
- **Konfigurierbarkeit (P11):** die Liste lebt korrekt in profile.json (`trigger_author_patterns`) — die
  OS-Schuld #3/#4 ist gelöst (Task 43). M-E nutzt (A) als konfigurierbares Veto-Up, (B) gar nicht.

## → nächste Iteration
Iter 46: **Confidence-banded Operating Point** — die M-E-Ausgabe in drei Zonen schneiden (sicher-keep /
unsicher→LLM-Lektüre / sicher-drop), dimensioniert an der Kaskade (Iter 33/35) und an der biblio-
ankerlosen Mittelzone (Iter 39). Macht die „weiß ich nicht"-Zone explizit, statt eine Scheinsicherheit
über alle Artikel zu legen.
