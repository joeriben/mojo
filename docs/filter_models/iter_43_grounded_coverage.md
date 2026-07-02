# Iter 43 — Grounded-Bezug-Coverage: wo der substitutive Komponist etwas sagen kann

## Anforderung
Memory feedback_llm_bezuege: das 2.0-Motiv ist der konfabulationsfreie Eintrag. Der substitutive Komponist
kann nur dort einen ECHTEN Werk-Bezug schreiben, wo ein geerdeter Anker existiert. Drei Typen:
(1) own_coupling (Artikel teilt Referenz mit Benjamins Werk), (2) citation (zitiert Benjamin direkt),
(3) bezugsautoren (Artikel-Refs ∩ Werke von Benjamins Bezugsautoren). Welcher Anteil der keeper/LES ist
geerdet, welcher bleibt „Leerstelle"?

## Messung (`iter_43_grounded_coverage.py`)
Bezugsautoren-Universum 6 263 Werke; 83 % der Artikel haben OpenAlex-Refs.

| Menge | n | geerdet | (own / cit / bez) | Leerstelle |
|---|---|---|---|---|
| alle keeper | 188 | **36 %** | 16 / 11 / 30 | 64 % |
| LES (lesenswert) | 79 | 46 % | 28 / 24 / 38 | 54 % |
| **keeper im BLINDEN Strom** | 25 | **4 %** | 0 / 0 / 4 | **96 %** |
| **LES im BLINDEN Strom** | 8 | **0 %** | 0 / 0 / 0 | **100 %** |
| non-keeper (Kontrast) | 273 | 15 % | 2 / 0 / 14 | 85 % |

121 keeper-Leerstellen: 31 ohne *jegliche* Refs (Datenarmut), 90 mit Refs aber ohne Anker-Treffer.

## Harte Kritik
- **Der härteste Befund der Serie für den Produkt-Output (P15, P16):** der zitations-/autoren-basierte
  grounded Bezug ist auf dem **blinden Strom** — dem eigentlichen Produktionsfall — fast leer: **4 %**
  der keeper, **0 %** der LES geerdet. Die 36 %/46 %-Coverage auf der Gesamtmenge stammt fast vollständig
  aus dem **intentional-positiven Backfill** (citation/complementarity-Pool), der per Konstruktion
  biblio-verankert ist. **Die geerdeten Anker konzentrieren sich exakt dort, wo sie am wenigsten gebraucht
  werden (bereits bekannte Items), und fehlen exakt dort, wo Entdeckung zählt (neuer Strom).**
- **Das tötet den Ansatz nicht — es begrenzt ehrlich seinen Geltungsbereich (P11, P16):** grounded Bezüge
  sind, *wo vorhanden*, wertvoll und konfabulationsfrei. Aber sie sind eine **Anreicherung für die
  verankerte Minderheit**, NICHT der universelle Ersatz für LLM-Kommentar, den man erhofft hatte. Für
  ~96 % der blind-relevanten Artikel kann der Komponist faktentreu nur sagen: *„relevant — Begründung
  über Lektüre/Volltext"*. Das ist ehrlicher als ein konfabulierter Bezug (Memory: 55,9 % ungrounded),
  aber es ist auch dünn.
- **Es erklärt, WARUM Volltext-Eskalation die dokumentierte 2.0-Linie ist (P6):** die blind-relevanten
  Artikel HABEN Refs (83 % insgesamt), aber diese schneiden Benjamins Zitations-/Autoren-Netz nicht —
  ihre Relevanz ist **inhaltlich-komplementär, nicht referenziell** (= Iter 39, Iter 11). Der Anker muss
  vom **Inhalt** kommen (rich_sim trägt auf dem Strom, AUC 0.63), nicht vom Zitationsgraph. Das ist die
  Begründung für own_refs + OA-PDF + Volltext-LLM-mit-Anker-Zitaten: nur dort entstehen geerdete
  *inhaltliche* Belegstellen, wo bibliometrische fehlen.
- **bezugsautoren ist der produktivste Anker — aber teils zirkulär (P3):** bez-Treffer (30 % der keeper)
  schlägt own (16 %) und cit (11 %). ABER bezugsautoren.db wurde aus den Erstautoren der Gold-Artikel
  geseedet (author_seed, role=first_author) → auf den intentional-positiven Items inflationiert. Die
  **4 % auf dem blinden Strom** ist die unverzerrte Zahl. Skalierung der bezugsautoren-DB über das Gold
  hinaus (Memory project_bezugsautoren_db: voller Korpus 16 404 Autoren) würde die Strom-Coverage heben —
  um wie viel, ist offen und muss gemessen, nicht projiziert werden (P14).
- **Anker hat Diskriminationswert, aber schwachen (P6):** keeper 36 % vs non-keeper 15 % geerdet (Faktor
  2,4) — der Anker ist also auch ein *Relevanz*-Signal, nicht nur ein Bezug-Lieferant. Aber 15 % False-
  Positive-Erdung (non-keeper mit Anker, v. a. bez 14 %) zeigt: Anker ≠ Relevanz. Erdung ist notwendig
  für den Bezug-*Text*, nicht hinreichend fürs Relevanz-*Urteil*.

## → nächste Iteration
Iter 44: **bezugsautoren-Coupling als Zusatz-Signal im Ranker** — hebt der bez-direct-Treffer (der
produktivste Anker, 30 %) die keep-AUC / LES-Recall über M-C hinaus, oder ist er redundant zu own+cit?
Misst den Relevanz-Beitrag der Autoren-Ebene (Memory: ungrounded 59→30 % halbiert) am Triage-Ziel.
