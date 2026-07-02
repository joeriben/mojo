# Phase-1 Neuausrichtung — wofür das Referenzmaterial überhaupt gut sein muss

> Stand 2026-05-31, am **bereinigten 156er-Korpus**. Diese Datei korrigiert den Maßstab, an dem die
> 10 Strategien (`strat_01..10`) zu messen sind. Vorher fehlte genau dieser Maßstab — deshalb lief ich in
> Diskursraum-Etiketten, Kontaminations-Aufräumen und eine erschöpfte Quellen-Abgleich-Optimierung.

## Der Maßstab (in Klartext)

Das Referenzmaterial ist **nur** in dem Maß gut, in dem es MOJO erlaubt, **zwei** Dinge zu tun — beide
verankert an Benjamins **tatsächlicher Arbeit**, nicht an Journal-/Diskursraum-Etiketten:

- **(A) Urteil:** „Knüpft dieser neue Artikel an das an, woran Benjamin *wirklich* arbeitet?" — beurteilt
  am **Inhalt** seiner Texte, der **Richtung** seiner Projekte, seinem **Begriffsrepertoire**. Nicht an
  einem Themen-Label.
- **(B) Aussage:** etwas **Wahres und Konkretes** über die Verbindung sagen — eine **real geteilte Quelle**,
  eine **auffindbare Textstelle** — statt eine plausibel klingende Verbindung zu **erfinden**. Das Erfinden
  („ungrounded", 55,9 % der Werk-Bezug-Behauptungen, Memory `feedback_llm_bezuege_konfabulation`) ist der
  **eigentliche Grund für 2.0**.

**Prüffrage für jede Material-Verbesserung:** Macht sie (A) richtiger und (B) wahrhaftiger?
Quellen-Abgleich-Quoten und Triage-Genauigkeit sind **Werkzeug, nicht Ziel** — und als Ziel das
dokumentierte Plateau (0.60 F1, 5× bestätigt).

## Die 10 Strategien, an diesem Maßstab neu sortiert

Die drei Achsen aus dem Auftrag — **Volltexte / Projekte / Profil** — bleiben, aber jede Strategie wird
danach beurteilt, ob sie (A)/(B) dient.

### Tragend: Benjamins Werk als *das, was es wirklich sagt* (Volltext + Profil)
- **01 Volltext-Lücke (66/156):** Das **Fundament gegen Erfindung.** Solange Werk nur über Titel/Abstract
  repräsentiert ist, *muss* MOJO bei (B) raten. *Adversarial:* es ist v.a. ein Aufbereitungs-, kein
  Beschaffungsproblem (→ 03); pre-2018-Fundament (48/66) zuerst, weil dort die Begriffe sitzen.
- **03 Volltext säubern + Rollen trennen:** „Was Benjamin *geschrieben* hat" vs. „Bände, die er nur
  *herausgegeben* hat" (4,17-Mio-Zeichen-Sammelband). Sonst übertönt fremde Autorenschaft seine Stimme in
  jeder Ähnlichkeit. Dient (A) direkt. *Adversarial:* ohne diese Trennung ist 08 (Profil) verzerrt.
- **08 Profil-Form:** den **Zuschnitt** des Œuvres je Einzelwerk darstellen (nicht ein gemittelter Haufen,
  nicht ein Cluster-Label). Dient (A): Ähnlichkeit gegen *einzelne* Werke statt gegen einen Schwerpunkt.
- **05 Begriffe (faktisch, R6) + 09 Denker-Lexikon (disambiguiert):** die **Vokabel-/Bezugs-Brücke** für
  (A) — und für (B) entscheidend, dass „knüpft an deinen Barad-Bezug an" den **richtigen** Barad meint
  (keine Nachnamen-Verschmelzung).

### Vorausschauend: wohin die Arbeit *geht* (Projekte)
- **06/07 Projekte:** gemessen **schlechter als Zufall** als Relevanz-*Score* (0.410). Richtige Rolle:
  sie sind **kein Keep/Drop-Filter**, sondern (a) der **vorausschauende** Anker für (A) — wohin sich
  Relevanz verschiebt (`relevance_shifts`, kuratiert) — und (b) echte **Sprache** für (B).

### Werkzeug, kein Ziel (heruntergestuft)
- **02 Quellen-Abgleich (12 %→~18 %):** war als „größter Hebel" **überbewertet** — gemessen +6 Pp,
  Plateau. Neuausrichtung: Auflösung zählt **nur dort**, wo sie einen **Kommentar wahr macht** (ein
  *einziger* korrekt geteilter Verweis für (B) ist mehr wert als +6 % im Schnitt), nicht als Punktzahl.
- **04 Summaries:** sind ein **komprimierter Stellvertreter** — und ein LLM-Summary kann die Erfindung,
  die wir loswerden wollen, **wieder einschleppen**. Also: Volltext bevorzugen, Summary nur wo kein
  Volltext; Geld erst nach Gratis-Messung (ersetzt Volltext-Einbettung den Summary?).

### Hygiene, zuletzt
- **10 Index:** ein Zugang über alle Achsen — erst *nachdem* das Material steht, sonst indexiert man Lücken.

## Der eigentliche Redirect (Selbstkritik der bisherigen Linie)
Der „größte Hebel" ist **nicht** der Quellen-Abgleich (02) und auch keine Triage-Punktzahl. Er ist:
**Benjamins Werk als realer Text (01/03)** → speist eine **substitutive** Kommentar-Komposition
(Abstract verbatim + echte Signale + **real** geteilte Verweise + **auffindbare** Textstellen), wie in
`feedback_llm_bezuege_konfabulation` festgelegt. Alles Bibliometrische ist dem **untergeordnet**.

## Nächste Schritte (Phasen 2 & 3, unter diesem Maßstab)
- **Phase 2:** Die algorithmischen Strategien **neu testen** — aber die Messlatte ist nicht mehr Triage-F1,
  sondern: hebt besseres Material (A) und macht es (B) wahrhaftiger? Validierung gegen `user_verdict` +
  grounded-Bezug-Quote, nicht gegen Diskursraum-Zugehörigkeit.
- **Phase 3:** Begründete Algo-LLM-Kombination: Algo erdet (was ist real geteilt/auffindbar?), LLM
  formuliert **nur** über belegtem Material — nie als freier Erzähler.
