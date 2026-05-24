# Feedback: LLM-Calls sind nur sinnvoll bei (a) validierter disziplinärer Zuordnung und (b) Volltext-Analyse

**Datum**: 2026-05-24, Ende Iter 10.

**Originalformulierung Benjamin** (verbatim):

> "Die ganzen LLM-Auswertungen sind NUR dann hilfreich wenn sie a) Text valide
> meinen Forschungsfeldern zuordnen, und v.a. b) wenn sie VOLLTEXTE analysieren.
> Nacherzählen von Abstracts ist verbranntes Geld."

**Zwei harte Kriterien für jeden LLM-Call**:
- **(a) Disziplinäre Zuordnung valide**: nicht thematische Oberflächen-Überlappung,
  sondern echte Anschlussfähigkeit an Benjamins 5 Verortungen. Mit Stellen-Verweis
  begründbar. Fallback: "unzuordenbar" als ehrliche Klassifikation.
- **(b) Volltext-Basis**: Abstract-Triage ist "verbranntes Geld". Volltext-Sektionen
  (Methods, Discussion, Self-Verortung in Intro/Conclusio) entscheiden über
  Disziplin-Zugehörigkeit, nicht Title/Abstract.

**Empirische Bestätigung in Iter 10**: 2nd-Trigger-Coupling-Netz über OpenAlex
(374 Trigger-Works, 9 836 Refs, 620 ≥2-coupled IDs) liefert weiteres
bibliometrisches Signal (LES/IGN-Ratios 5–22×), aber Modell-Plateau bleibt
unverändert bei 0.600–0.607 F1. Wrong-LES (0.77) sind im 2nd-Degree-Netz nicht
von Wrong-IGN (0.67) trennbar. Bibliometrie ist erschöpft.

**Konsequenz für MOJO 2.0** (korrigiert 2026-05-24 nach Benjamin-Reframe —
siehe `feedback_mojo2_reframe_algorithmic.md`):
- **Vorfilter primär algorithmisch**: Cascade_TunedBase (0.600 F1) +
  produktive Refs-basierte Veto-Regeln (own_coupling, adversarial set-features)
  triagieren ≥90 % der Items ohne LLM-Call.
- **Volltext-Eskalation für Restmenge (≤10 %)**: nur Items, die nach allen
  algorithmischen Regeln unklar bleiben, gehen in Volltext-LLM mit
  Anker-Zitaten. Output: `disciplinary_placement` + `anschluss[]`.
- **Kein „Default-Volltext-LLM"**: die ursprüngliche Rechnung
  „$0.20 × 30 Articles/Woche" entsprach implizit ~10 % Default-Rate, die mit
  wachsendem Refs-Index weiter sinken soll.

**Komplementär (optional, NICHT architektonisch erforderlich)**: Coding-LLM
kann als Developer-Tool Heuristik-Vorschläge generieren — das ist KEIN
Auto-Deployment-Pfad, sondern Reviewer-Material für die Entwickler:in.

**Detaillierter Plan**: `../mojo_2_volltext_sketch.md` (in der korrigierten
Fassung vom 2026-05-24).

**Konkretes Anti-Pattern, das vermieden werden muss**:
- Opus/Gemini bekommt Abstract, schreibt 200-Wörter-Paraphrase → Benjamin
  liest Paraphrase statt Volltext → Information geht verloren statt sich
  anzureichern. Genau das ist "verbranntes Geld".
- **Zusätzliches Anti-Pattern**: Volltext-LLM als Default-Triage für >10 %
  der Items aufsetzen, ohne erst die algorithmische Refs-Pipeline auszuschöpfen.
