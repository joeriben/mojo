# 10 Strategien — Referenzmaterial optimieren (korrekt ausgerichtet)

> Stand 2026-05-31, bereinigter 156er-Korpus. **„Referenzmaterial" = das Material, das BENJAMIN
> repräsentiert** — seine **Volltexte**, seine **Projekte**, sein **Profil** — *nicht* die bibliografischen
> Zitate in fremden Artikeln. Der Quellen-Abgleich (`own_coupling`) ist **erledigt** und hier raus.
> Parsing-Sackgassen (Refs-Strings, creatorType, Denker-Disambiguierung) sind **nicht** das Thema.
> Maßstab bleibt: macht es **(A)** das Relevanz-Urteil richtiger (an Benjamins Arbeit, nicht an Labels) und
> **(B)** die Aussage über die Verbindung wahrhaftiger (belegt statt erfunden)?

---

## Dimension I — Verarbeitung von Volltexten: erfasst MOJO, *was deine Texte sagen*?

### S1 — Volltext-Repräsentation nach *Substanz*, nicht nach Titel/Abstract
**Problem:** 90/156 Werke haben Volltext, werden aber für Ähnlichkeit oft nur über Titel/Abstract
repräsentiert. Genau daraus entsteht das Erfinden (B): MOJO „weiß" nicht, was im Text *steht*.
**v1:** jeden Volltext als *einen* Vektor einbetten.
**Adversariale Kritik:** ein 57 000-Zeichen-Text als ein Vektor ist ein Brei-Mittelwert — die *einzelnen
Argumente* verschwinden, und es gibt keine *auffindbare Stelle* für (B).
**v2:** **Abschnitts-/Passagen-Repräsentation** — ein eingehender Artikel kann eine *konkrete* These von dir
treffen; diese Passage ist dann der Beleg für (B). Volltext-Verständnis = Substanz auf Passagen-Ebene.

### S2 — Stimmen-Trennung: dein Text vs. von dir nur herausgegebene Bände (ohne Parsing-Sackgasse)
**Problem:** der 4,17-Mio-Zeichen-Ausreißer (Jahrbuch Medienpädagogik) ist ein **Herausgeberband** —
fremde Autorenschaft, die als „Benjamins Stimme" jede Profil-Mittelung verzerrt.
**v1:** je Werk Autor-vs-Herausgeber über Zotero-Rollen exakt klassifizieren.
**Adversariale Kritik:** das ist die **creatorType-Parsing-Sackgasse**, vor der du gewarnt hast — fragil,
und es löst nur einen Randfall.
**v2:** **kein Klassifizier-Parsing.** Längen-/Typ-Heuristik: extrem lange `book`/Sammelband-Ausreißer im
Profil **herunterwichten** statt hart trennen — robust, billig, erledigt den Verzerrungs-Effekt.

### S3 — Volltext-Hygiene als Verständnis-Voraussetzung
**Problem:** Kopfzeilen, Seitenzahlen, OCR-Reste im extrahierten Text verrauschen jede Substanz-Ähnlichkeit.
**v1:** aggressiv Header/Footer per Regex strippen.
**Adversariale Kritik:** zu aggressiv löscht echten Text; je PDF anders.
**v2:** konservative, gemessene Reinigung (nur belegte Artefakt-Muster), Wirkung an Substanz-Ähnlichkeit
*messen*, nicht an einer Reinigungs-Quote. Hygiene dient S1, ist nicht Selbstzweck.

---

## Dimension II — Verständnis der Projekte: weiß MOJO, *worum* es geht und *wohin* es zielt?

### S4 — Projekte als lebende Richtungen über `relevance_shifts`, nicht über Antrags-Prosa
**Problem:** `projects.json` hat Beschreibungen *und* kuratierte `relevance_shifts` (6–7/Projekt).
**v1:** Projekt-Beschreibung einbetten.
**Adversariale Kritik:** **gemessen** — Beschreibung als Keep-Signal liegt bei **AUC 0.410 (schlechter als
Zufall)**: Förder-Prosa ≠ Relevanz. Die `relevance_shifts` sind das dichte, kuratierte Material.
**v2:** jedes Projekt durch seine **relevance_shifts** repräsentieren (was eine Verschiebung ausmacht) —
das ist Benjamins eigene Formulierung dessen, was relevant wird.

### S5 — Frontier-Verständnis: gegen *wohin du gehst*, nicht nur *wo du warst*
**Problem:** das rückblickende Œuvre ist ÄKB-lastig → das System begräbt deine *aufkommende* Front
(digitale_kultur/Resilienz, Iter 37/47).
**v2:** ein **vorausschauender Anker** aus den `relevance_shifts` *ergänzt* die Œuvre-Repräsentation, damit
ein Artikel auf deiner Frontier erkannt wird, auch wenn er zum *vergangenen* Schwerpunkt nicht passt.
**Adversariale Kritik & Offenheit:** Overlap ≠ Relevanz (Iter 45) — in Phase 2 gegen `user_verdict` messen,
nicht behaupten.

### S6 — Projekt↔Werk-Verständnis über `connected_publications`
**Problem:** Projekte und deine Werke stehen unverbunden nebeneinander.
**v2:** die kuratierten `connected_publications` als Verständnis-Brücke nutzen — MOJO weiß dann, *welche
deiner Texte welche Projektrichtung realisieren*; für (B): „knüpft an deine MetaKuBi-Arbeit zu X an" wird
belegbar statt erfunden. **Kritik:** nur 3–6 Verknüpfungen/Projekt → schmal, ergänzend, kein Hauptsignal.

---

## Dimension III — Verständnis des Profils: bildet MOJO ab, *wer du fachlich bist*?

### S7 — Profil als Topologie (Spannweite), nicht als Mittelwert
**Problem:** ein globaler Œuvre-Mittelwert löscht deine *Spannweite* (5 Verortungen) aus.
**v1:** Werke hart clustern (k=5 = Verortungen).
**Adversariale Kritik:** **gemessen** — Silhouette 0.06: das Œuvre ist eine *kontinuierliche Wolke*, harte
Cluster sind aufgezwungen und seed-instabil; ÄKB-Dominanz ist zudem ein Sampling-Artefakt.
**v2:** **Per-Werk-Repräsentation + weiche Zugehörigkeit** über die 5 Verortungen (aus `discourse_json`,
jetzt 100 % vorhanden, kuratiert) — Spannweite verstehen statt Cluster erzwingen.

### S8 — Die 5 Verortungen als Profil-Rückgrat (gegen den Diskursraum-Zirkel)
**Problem:** der Ur-Fehler war, Relevanz an *Journal-Diskursräumen* zu erden (zirkulär).
**v2:** Benjamins **5 disziplinäre Verortungen** (CLAUDE.md) sind die *autoritativen* Profil-Achsen.
Werke *und* eingehende Artikel auf diese Achsen abbilden; (A) = berührt es deine Verortungen, an der
Substanz beurteilt — nicht an einem Journal-Etikett. **Kritik:** Verortungen sind grob; ergänzen, nicht
ersetzen die Per-Werk-Topologie (S7).

### S9 — Begriffsrepertoire als Verständnisbrücke (faktisch, R6, ohne Disambiguierungs-Sackgasse)
**Problem:** deine wiederkehrenden Begriffe/Bezugsdenker signalisieren „spricht deine Sprache".
**v1:** kuratiertes, OpenAlex-disambiguiertes Denker-Lexikon.
**Adversariale Kritik:** die **Disambiguierung ist eine Parsing-Sackgasse** (Gibson-Kollisionen etc.) — viel
Aufwand, fragil.
**v2:** **faktische** Begriffs-/Namens-Häufigkeit aus deinen Texten als *weiches* Überlappungssignal
(R6: keine Deutung). Kein perfektes Lexikon — ein robustes Vokabel-Signal für (A) und ein benennbarer
geteilter Begriff für (B).

---

## Integration

### S10 — Ein kohärentes „Benjamin-Verständnis", aus dem (A) und (B) schöpfen
**Problem:** Volltext-Substanz (S1), Projekt-Richtung (S4–6), Profil-Topologie (S7–9) liegen verstreut.
**v1:** einen großen neuen Verständnis-Store bauen.
**Adversariale Kritik:** Over-Engineering — verfrühte Abstraktion über noch dünnem Material.
**v2:** **ein Lese-Interface** über die bestehenden Quellen (additiv, versioniert), das genau zwei Fragen
beantwortet: *(A) Wie nah ist Artikel X an Benjamins Arbeit?* und *(B) An welchem konkreten Werk/Passage/
Projekt/Begriff lässt sich das belegen?* — zuletzt, wenn S1–S9 stehen.

---

## Was hier bewusst NICHT steht (und warum)
- **Quellen-Abgleich / `own_coupling` / Refs-Auflösung:** erledigt — kein Phase-1-Ziel mehr.
- **creatorType-/Refs-/Denker-Parsing als Strategie:** Sackgassen; wo eine Rolle/ein Begriff gebraucht
  wird, über robuste Heuristik, nicht über fragiles Parsen.

## Phase 2 (danach)
Algorithmische Strategien gegen `user_verdict` (oeuvre-geerdet) neu testen — Messlatte: (A)-Trennschärfe
und (B)-Belegbarkeit, **nicht** Triage-F1 oder Diskursraum-Zugehörigkeit.
