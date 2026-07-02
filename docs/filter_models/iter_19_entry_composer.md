# Iter 19 — substitutiver Eintrags-Komponist + Ehrlichkeits-Messung

## Anforderung
Festlegung feedback_llm_bezuege_konfabulation: Eintrag **substitutiv** komponieren (Abstract verbatim +
Signale + geerdete Bezüge), LLM aus der Erzähler-Rolle. Messen, nicht behaupten: Verteilung der
Eintrags-Typen — (a) **konkret** (≥1 verifizierbarer Bezug), (b) **nur-Score** (hohe rich-Sim, kein
spezifischer Bezug), (c) **Leerstelle** (bewusstes Schweigen). Bezüge = own (Iter 17) ⊕ bez-direkt (Iter 18).

## Messung (`iter_19_entry_composer.py`, kein LLM)
| Gruppe | konkret | nur-Score | Leerstelle |
|---|---|---|---|
| alle keeper (188) | 37 % | 38 % | 26 % |
| LES (79) | 47 % | 33 % | 20 % |
| blind keeper (25) | 4 % | 68 % | 28 % |

**Komponierter Eintrag (verbatim, verifizierbar):**
> ■ `[EduTheory]` „Predictive Curricula and the Foreclosure of Pedagogical Futures" (lesenswert)
> Abstract: „…the reorganization of schooling arou…" · rich-Sim-Perzentil 73 %
> ↔ teilt Referenz mit deiner Publikation **„Digitalität im erziehungstheoretischen Blick" (2025)**
> ↔ zitiert Umfeld-Autor **Ben Williamson** („Big Data in Education"), **Juliane Jarke** („Dashboard stories")

## Harte Kritik
- **Die Substitution ist erreicht (P16, das 2.0-Kernziel):** statt der auditierten **55.9 % ungrounded**
  LLM-Behauptungen macht der Komponist **null** ungrounded Behauptungen. Jeder „konkret"-Bezug ist eine
  verifizierbare geteilte Referenz / ein direktes Umfeld-Zitat (Williamson, Jarke — Jarke ist sogar
  Trigger-Autor). Wo nichts geerdet ist: Score-Hinweis oder **Leerstelle** — Schweigen statt Slop.
- **Die Verteilung ist die ehrliche Selbstauskunft des Systems (P15):** für 37 % der keeper trägt der
  Eintrag einen konkreten Bezug, für 47 % der LES. Das ist *kein* Vollständigkeits-Versprechen — es ist
  die exakte Reichweite der Erdung, offen ausgewiesen. Der Eintrag lügt nie über mehr, als er weiß.
- **Die 26 % Leerstelle sind der ehrliche Rest — und der einzig legitime LLM-Ort (P13):** keeper ohne
  Bezug *und* ohne hohen Score sind aus Benjamins Werk nicht erdbar. Genau hier — und nur hier — ist die
  dokumentierte **Volltext-Eskalation** gerechtfertigt: nicht als konfabulierte Erzählung, sondern als
  tatsächliche Lektüre mit Anker-Zitaten. Der Komponist markiert diese Stellen, statt sie zu überspielen.
- **Schwächen offen benannt (P3, P15):** (1) „nur-Score" stützt sich auf rich-Sim, die blind nur AUC
  0.63 hat — „rankt hoch in deiner Werk-Ähnlichkeit" ist ein *weicher* Hinweis, kein Bezug; als solcher
  ausgewiesen. (2) Die Score-Schwelle (33. Perzentil der keeper-Sim) ist eine Design-Wahl, nicht
  naturgegeben — sie steuert nur die Score/Leer-Grenze, nicht die konkret-Quote. (3) blind 4 % konkret
  heißt: auf dem realen Strom ist der Eintrag fast immer Score+Abstract, selten Bezug — ehrlich, aber
  mager.

## → nächste Iteration
Iter 20 (Phase-C-Abschluss): **Negativ-Kontrolle gegen Konfabulation** — den Komponisten gegen die
historischen MOJO-1-LLM-Kommentare (articles.db `llm_calls`) stellen: wie viele der dort *behaupteten*
Werk-Bezüge deckt der geerdete Komponist (corroborated) vs. wie viele waren ungrounded? Das schließt den
Audit-Kreis (12.7 % corroborated) und belegt, dass Substitution die Konfabulation nicht nur ersetzt,
sondern messbar korrigiert.
