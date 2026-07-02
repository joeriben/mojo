# MOJO 2.0 — Proto-Indikator: Stand (gerechnet)

**Stand 2026-05-31.** Dieses Dokument hält den ko-entwickelten „Proto-Indikator"
fest: ein algorithmisches **Indikatorfeld** (kein binärer Klassifikator), das
*getypte, vorzeichen-behaftete Relationen* zwischen einem Kandidatentext und
Benjamins Eigenwerken bestimmt. Die Architektur ist aus der Gegenstandslogik
abgeleitet, nicht aus Triage-F1.

**Epistemische Marker (verbindlich, siehe Memory `feedback_kein_anschein_objektiver_gueltigkeit`):**
- **[gerechnet]** = mit Code reproduzierbar, Daten liegen vor.
- **[gelesen]** = LLM-Lektüre → Hypothese, kleines n, NICHT Proxy-gegen-Ziel.
- **[asseriert]** = Plausibilität aus Modellwissen, ungeprüft.

Reproduktion aller [gerechnet]-Befunde: `python3 scripts/proto_topology_probe.py`
(Operanden: K = Jörissen/Klepacki/Klepacki „Nachhaltigkeit und kulturelle
Resilienz"; Kandidaten Bettinger 2022, MacGilchrist 2021; Korpus `own_refs.db`).

---

## 1. Module (vorerst festgepinnt, revidierbar)

**Operand-Extraktion pro Text:**
- **O1 Operative Quellen** = Dichte × Multiplizität × struktureller Rolle (kanonisiert).
- **O2 In-vivo-Signatur** = selbstgeprägte Begriffe (zitations-unsichtbar → semantisch).
- **O3 Ziel** · **O4 Vorzeichen** (wofür/wogegen) · **O5 disziplinäre Verortung**
  (≠ thematische Überlappung) · **O6 Trajektorie / Eigen-Korpus-Bezug**.

**Relationale Module (Kandidat ↔ K), vorzeichen-gegatet:**
- **M1 Komplementarität**: Ziel geteilt ∧ operative Quellen disjunkt.
- **M2 Affiliation**: Quellen geteilt ∧ Vorzeichen gleich.
- **M3 Spannung**: Quelle/Interlokutor geteilt ∧ Vorzeichen entgegengesetzt.
- **M4 Blind-Spot/Frontier**: Quellen ⊂ (Trigger \ Eigen) ∧ disziplinär nah.

**Meta-Verdrahtung:** billige Trigger auf vorhandenen Feldern (kein zweiter
Klassifikator) · Tri-State statt binär · Schwellen an den Enden kalibriert ·
**mehrere Module dürfen gleichzeitig feuern — die Signatur *ist* der Relationstyp** ·
Gating multiplikativ-bedingt (verstärken/dämpfen), nicht additiv.

---

## 2. [gerechnet] O1 — Multiplizität vs. Density (die Kern-Wette, getestet)

Werk-Multiplizität (Bib, billig, auch für Kandidaten verfügbar) **gegen**
Body-Citation-Density (Volltext, Name+Jahr aufgelöst):

| Quelle (in K) | Werk-Mult | Density | Befund |
|---|---|---|---|
| Barad | 3 | 7 | operativ — beide Signale einig |
| Brown | **1** | **4** | operativ — **nur Density** fängt es (Einzelwerk; trägt „kult. Resilienz nach K. Brown", Resourcefulness, Resistance) |
| Latour | **3** | 2 | Multiplizität **über**bewertet (Bib-aufgebläht) |
| Haraway | 1 | **0** (Konzept *Sympoiesis* ×2) | konzept-operativ, zitations-unsichtbar → O2 |
| „anders" | — | Wort 7× / Citation 0 | Methoden-Beweis: Substring ≠ Citation |

→ **Multiplizität allein ist weder hinreichend (Brown) noch sicher (Latour);
Density löst beide; konzept-getragene Operativität (Sympoiesis) entgeht beiden
Zähl-Metriken** → genau der O2-Rest für die semantische Schicht.

---

## 3. [gerechnet] Relationale Topologie (Set-Ops auf echten Bibs)

**K ↔ Bettinger 2022** (|K|=42, |Bett|=42 Erstautoren)
- geteilt & operativ: **Barad** (K-Density 7 / Bett ×2) — Affiliations-Kern.
- cites-you: **Jörissen ×2 + Marotzki**.
- disjunkt & operativ (mult≥2): Taylor ×3, Braidotti ×2, Reckwitz ×2, Wimmer ×2,
  Kokemohr ×2 — sein eigener Apparat.
- **Signatur = {Affiliation(Barad) ∧ cites-you ∧ Komplementarität}.**
  Die Spannung (M3, sein „…und ihre Tücken") steht **nicht** in den Zahlen → semantischer Rest.

**K ↔ MacGilchrist 2021** (|Mac|=35)
- geteilt: Haraway (Bib K×1/Mac×2, konzeptuell *Sympoiesis*) + Jörissen (cites-you, Mycel).
- disjunkt & operativ: **Tsing ×3** (Friction/Mushroom/Feral Atlas) — die *einzige*
  dichte disjunkte Quelle. Critical-Data-Cluster (Couldry/Zuboff/Williamson/Jarke/Chun)
  präsent, aber je ×1 (nicht operativ-dicht). Jandrić ×2 = korrekt als Nicht-Trigger-Rauschen.
- **Signatur = {Komplementarität ∧ Frontier(Tsing)}.**

---

## 4. [gerechnet] M4 Frontier — korpusweit (gegen `own_refs.pub_refs`, 6244 Refs / 156 Werke)

| Quelle | Korpus-Refs | in Werken | Verdikt |
|---|---|---|---|
| Tsing (MacGilchrist ×3) | **0** | 0 | **blinder Fleck** |
| Braidotti (Bettinger ×2) | **0** | 0 | **blinder Fleck** |
| Barad | 12 | 7 | Heimat-Terrain |
| Haraway | 7 | 6 | Heimat-Terrain |
| Schatzki | 4 | 3 | Heimat-Terrain |
| Koller | 13 | 11 | Heimat-Terrain |

Tsing ist in Benjamins *gesamtem* zitierten Korpus nie vorgekommen — obwohl
*Mushroom at the End of the World* fast K's Thema ist. Die Missed Reference,
korpus-bestätigt. (Hinweis: kurze Nachnamen wie „Chun" sind per Substring-LIKE
kontaminiert — `chun` trifft dt. „…chung" → unbrauchbar, nicht als Befund geführt.)

---

## 5. Was das Rechnen am Lesen korrigiert hat

- **Haraway:** [gelesen] „operativ in K" → [gerechnet] 0 formale Events,
  konzept-operativ via *Sympoiesis*; geteilt mit MacGilchrist nur bib-tief.
- **Schatzki:** [gelesen] „Bettingers *disjunkter* Apparat" → [gerechnet] **geteilt**.
- **Latour:** [gelesen] „operativ in K" → [gerechnet] bib-aufgebläht (3 Werke / 2 Events).
- **Neu aufgetaucht:** Braidotti-blinder-Fleck; Koller als geteilte Brücke; Taylor als Bettingers operative Spitze.

---

## 6. Offene Vektoren (von Benjamin markiert, 2026-05-31)

### 6a. M4 → Vorschlagswesen („must know")
M4 Frontier ist nicht nur ein Relevanz-Signal, sondern eine **Quelle für aktives
Vorschlagswesen**: „diese Quelle solltest Du kennen/zitieren". Stärkerer Sprechakt
als „relevant" — ein *must-know*-Schwellwert über dem Indikatorfeld. Realisiert den
Missed-References-Detektor (Memory `project_missed_references_detector`) rein aus
qualifizierter Quellen-Topologie. Tsing für K ist der gerechnete Beleg.
Schwelle: disjunkt-operativ (mult_cand≥2) ∧ korpusweit absent (0 own-refs) ∧ disziplinär nah.

**[gerechnet] Funktionalitäts-Beweis (`scripts/proto_topology_probe.py`):** Regel mechanisch
über die *volle* disjunkt-operative Menge (10 Quellen, 2 Kandidaten) → schlägt **genau 2** vor:
**Tsing** (MacGilchrist, Korpus 0) und **Braidotti** (Bettinger, Korpus 0); filtert die 8 anderen
korrekt — inkl. der schweren Fälle: Jandrić (von Benjamin als Rausch-Autor markiert) fällt raus
*ohne* Sonderregel, weil schon einmal zitiert (Korpus=1); Ko-Autor Marotzki (120); Heimat-Terrain
Taylor/Reckwitz/Wimmer. Die Schwelle bei **0** („nie berührt") macht die Arbeit. **O5-Gate** (Feld-Nähe
= Anteil Kandidaten-Autoren im Korpus): MacGilchrist 33 %, Bettinger 68 % — beide in-field (Ablehn-
Richtung mangels fachfremdem Kandidaten ungetestet). Ehrlich: n=10, **Demonstration, keine
Präzisions-Statistik**. Braucht NICHTS von SARAH — reines Stratum A + `own_refs.db`.

### 6b. Vorzeichen elegant/effizient ermitteln — DIE Herausforderung
Vorzeichen ist der teure semantische Rest. Eleganz = **nicht überall lesen, sondern
an den lasttragenden Positionen, und nur die reflexive Restmenge eskalieren.**
Vorgeschlagene (noch [asseriert]) Mechanik:
1. **Paratext-Stance** (Titel/Abstract/Überschriften/Konklusions-Rahmung): Lexikon
   Vorbehalt/Kritik (Tücken, Grenzen, Aporie, jedoch) vs. Konstruktion (Entwurf,
   Perspektive, produktiv). Fängt das *angekündigte/globale* Vorzeichen.
2. **Citation-Window-Polarität** je geteilter Quelle (±N Token): Distanzierung
   (in Abgrenzung zu, im Unterschied zu, kritisiert) vs. Affiliation (im Anschluss an,
   folgt, mit, produktiv aufgreifen). Fängt das *lokale* Vorzeichen-zur-Quelle.
3. **Divergenz-Router** (= H4-`contradicts` transponiert):
   - Paratext+ ∧ Windows+ → **Affiliation** (billig entschieden)
   - Paratext− ∧ Windows− → **Kritik/Tension** (billig entschieden)
   - Paratext− ∧ Windows+ (Quelle affirmativ genutzt, Programm reserviert) →
     **reflexive Spannung** (der Bettinger-Fall) → eskaliere *eng* (gezielte Frage),
     nicht Blind-Read.
Eleganz: die konkordante Mehrheit wird per Lexikon über wenige hundert Token (Paratext
+ Windows) entschieden; nur die divergente Minderheit kostet semantische/​SARAH-Budget.
Prämisse (zu prüfen): die reflexive Spannung *ist* der Spalt lokal-affirmativ ×
global-reserviert — aus einem Einzelsignal nicht gewinnbar.

**[gerechnet] Prämisse-Probe (2026-05-31):** Die Struktur ist vorhanden und
lokalisierbar. *Bettinger:* Vorbehalt im **Untertitel** („…und ihre Tücken", Z. 3)
+ in der Konklusion („jedoch nicht unproblematisch" Z. 628; „Ambivalenz … bezweifelt"
Z. 658), während die **Barad-Fenster affirmative Nutzung** sind („legt Karen Barad
mit ihrem Ansatz", „so Barad", „Barad kritisiert" = Barad als zustimmend referiertes
Subjekt) → Divergenz Paratext− × Window+ = reflexive Spannung. *MacGilchrist:* Tsing
affirmativ genutzt („arts of noticing"), **kein** Titel-Vorbehalt; die 6 Body-Marker
(however/limits) sind generisches Rauschen → **Diskriminator ist paratext-/konklusions-
gewichtet, nicht Body-Lexikon-Zählung.** Offen [semantisch/asseriert]: die
Fenster-→-Vorzeichen-Klassifikation selbst und die Routing-Regel.

---

## 7. Ehrliche Grenze (noch NICHT gerechnet)
- **Vorzeichen / O4** (§6b) — semantischer Rest, Mechanik erst [asseriert].
- **O2 In-vivo-Extraktion** systematisch (Sympoiesis, „-Werden") — bisher Hand-Grep.
- **Set-Ops** auf First-Author-Korn (Ko-Autor nur per Substring-Augmentation).
- **disziplinäre Nähe (O5)** als Gate noch qualitativ, nicht berechnet.

---

## 8. Fallgestalt als Datenformat (Vektor, Benjamin 2026-05-31)

Beobachtung: Die Pipeline produziert pro Artikel keine Relevanz-Zahl, sondern eine
charakteristische **Konfiguration** — eine *algorithmische Fallgestalt* (im Sinn der
Fallrekonstruktion: die positionale Struktur, die diesen Text *diesen* Fall sein lässt).
Sie verdient ein eigenes, persistiertes Datenformat — die konkrete Form des Anti-Tüte-Prinzips.

**Drei Festlegungen, damit es Gestalt bleibt und nicht zur Feld-Tüte wird:**
1. **Konfigurational, nicht Zeilenvektor.** Fallgestalt = *getypter Graph pro Artikel*:
   Knoten (Quellen, In-vivo-Begriffe, Positions-/Vorzeichen-Marker) + Kanten (*trägt* Move,
   *prägt-aus* Begriff, *reserviert* Programm, *verdichtet* Cluster). Eine flache Feldzeile re-tüte-t.
2. **Vergleichsfrei / wiederverwendbarer Operand.** Rein per-Text (O1–O6); die relationalen
   Module M1–M4 werden *zwischen* zwei Fallgestalten on-demand gerechnet, nicht eingebacken.
   → ein Kandidat wird *einmal* aufbereitet, dann gegen die ganze Eigenwerk-Hülle verglichen.
3. **Provenienz pro Element.** Jeder Knoten/jede Kante trägt [gerechnet]/[gelesen]/[semantisch]/
   [SARAH-importiert]. Auditierbar, kein Black-Box-Embedding. Zugleich der **Kontrakt zwischen
   algorithmischer und semantischer Schicht**: SARAH-Output (Ziel/Vorzeichen/operative Rolle)
   *populiert* die semantischen Kanten, ohne Code-Integration.

**Verhältnis zur Datenebene:** Evolution von `own_refs` (publications + pub_refs) — die
Fallgestalt fügt Density/Rolle, In-vivo-Signatur, Verdichtungsprofil, Vorzeichen-Positionen hinzu.
Einfachste Form: ein JSON pro Artikel (Knoten/Kanten/Provenienz), kein Graph-DB-Overkill.

**Vereinheitlichung der offenen Vektoren:** §6a Must-Know ist eine *Query über* gespeicherte
Fallgestalten (disjunkt-operativ ∧ korpus-absent); §6b Vorzeichen-Router *annotiert* die
O4-Kanten. Die Fallgestalt ist das Substrat, die anderen zwei sind Lese-/Schreib-Operationen darauf.

**[teils gerechnet] Worked Example — K's Fallgestalt (nur belegte Elemente; Lücken markiert):**
- operative Quellen: Barad {density 7, mult 3} ·trägt· §2/agentielle-Schnitte; Brown {density 4,
  mult 1} ·trägt· Resilienz-Triade (Rooting/Resourcing/Resistance) — [gerechnet]
- in-vivo: „-Werden"-Familie, „kulturelle Resilienz", „colerisches Werden" [Extraktion gerechnet /
  operativ-Status gelesen]; *Sympoiesis* ·prägt-aus· Haraway-Konzept (Quelle citation-sparse, density 0)
- Vorzeichen-Positionen: gegen individualistisch-funktionale Resilienz (Folie Anders et al. 2022)
  — [semantisch, NICHT gerechnet]
- O6 Trajektorie: Jörissen/Klepacki 2021 → Jörissen 2022 → Klepacki/Jörissen 2023 [gerechnet; Dublette kanonisiert]
- O5 disziplinär: ÄKB / Resilienz / Bildungstheorie [qualitativ]

---

## 9. Formalisierung: `BuildFallgestalt(A)` und `Relate(FG_c, FG_K)`

Notation: `R*` kanonisierte Referenzen · `Ω` own_refs (Benjamins zitiertes Korpus) ·
`W_own` Benjamins eigene Werke · `op()` Operativität · `σ` Vorzeichen · `⊥` unbestimmt.
Provenienz-Tag je Zuweisung: **[c]** gerechnet · **[r]** gelesen · **[s]** semantisch/eskaliert.
Das Vorzeichen existiert noch nicht real → es ist als Funktion `RESOLVE_SIGN` mit
explizitem Leerzustand formalisiert, nicht ausgelassen.

```
DATENOBJEKT
  Fallgestalt FG = (V, E, prov, meta)
    V    typed nodes : Source | Term | Position
    E    typed edges : bears | coins | reserves | affirms | condenses | cites_back | trajectory
    prov : V∪E → {c, r, s, sarah}                       # Provenienz/epistemischer Status pro Element
    meta : {id, title, authors, year, venue, doi, disc}

ALGORITHM BuildFallgestalt(A = ⟨T?, R, P, meta⟩):        # T Volltext (optional), P Paratext
  1  R* ← canon(R)                                        # dedup über (norm_surname, year)          [c]
  2  for a ∈ first_authors(R*):                           # O1 — qualifizieren, nicht bündeln
        mult(a) ← |works_of(a, R*)|                       #   Bib-billig, immer verfügbar             [c]
        dens(a) ← (T≠⊥) ? |cite_events(a,T)| : ⊥          #   Volltext: Name+Jahr aufgelöst           [c]
        role(a) ← role_hint(a, T)                         #   Überschrift/Enum-Proxy                  [r]
        op(a)   ← qualify(mult, dens, role)               #   NICHT additiv: dens dominiert mult
        V ← V ∪ Source(a, {mult, dens, role, op})         #   (Brown↑ trotz mult=1, Latour↓ trotz 3); Form zu kalibrieren
  3  if T≠⊥:                                              # Verdichtungsprofil (Gestalt-Kern)
        clusters ← segment(⋃_a positions(a,T))                                                       [c]
        for c ∈ clusters:
           type(c) ← {1 Autor dicht→building-on ; 2–3 Autoren→positioning ; Komb.→transfer}         [r]
           E ← E ∪ condenses(c über seine Sources)
  4  cand_terms ← { t : TF↑(t,T) ∧ refDF↓(t) ∧ ¬adj_cite(t) ∧ morph(t) }   # O2 In-vivo             [c]
     for t ∈ cand_terms:
        V ← V ∪ Term(t)
        if concept_source(t)=s: E ← E ∪ coins(t→s)        # z.B. Sympoiesis→Haraway                 [r/s]
  5  meta.disc ← disc_vector(venue, concepts(A), venue_dist(R*))           # O5                       [c]
  6  cites_back ← { s ∈ R* : s ∈ authors(Ω) }             # O6 — Anker-Kanten, einmalig gegen Ω      [c]
     E ← E ∪ { cites_back(A→s) }
     if A ∈ W_own: E ← E ∪ trajectory(self_chain(R* ∩ W_own))                                        [c]
  7  # ---- O4 VORZEICHEN: formaler Slot, Klassifikation deferred ----
     para ← locate(stance_lexicon, P)                     # Marker+Position; Titel/Konklusion ≫ Body  [c]
     for s ∈ operative_core(V): win(s) ← cue_lexicon(window(±N, positions(s), T))                    [c]
     for g ∈ programs ∪ operative_core(V):
        (rel, σ, route) ← RESOLVE_SIGN(para, win, g)
        E ← E ∪ Position(rel, g, {σ})
        prov(edge) ← (route = ESCALATE) ? s : c
  8  return FG = (V, E, prov, meta)

FUNCTION RESOLVE_SIGN(para, win, g):                      # der Platzhalter — σ noch nicht real
     p ← paratext_stance(para, g) ∈ {+,−,∅}               # [c] lokalisiert / [r] Polarität
     w ← window_polarity(win, g)  ∈ {+,−,∅}               # [c] lokalisiert
     if p=+ ∧ w=+ : return (affirms,  +, HEUR)            # Affiliation, billig entschieden
     if p=− ∧ w=− : return (reserves, −, HEUR)            # Kritik/Tension, billig entschieden
     if p=− ∧ w=+ : return (reserves, ⊥, ESCALATE)        # reflexive Spannung (Bettinger)
     if p=+ ∧ w=− : return (affirms,  ⊥, ESCALATE)        # Transfer
     else         : return (reserves, ⊥, ESCALATE)
     # ESCALATE → SARAH/H4 liefert σ ∈ {wofür, wogegen} + operative Rolle; bis dahin σ=⊥
     # AKTUELLER ZUSTAND: SARAH nicht angeschlossen ⇒ für alle g route=ESCALATE, σ=⊥.
     #   Slot, Kanten, Provenienz existieren; nur σ ist leer — eine adressierte Lücke, kein Loch.

ALGORITHM Relate(FG_c, FG_K):                             # Kandidat ↔ Eigenwerk K; NICHT gespeichert
     S_c ← op_sources(FG_c) ; S_K ← op_sources(FG_K)      # operativitäts-gewichtet
     shared ← S_c ∩ S_K ;  disj_c ← S_c \ S_K
     M1 Komplementarität  ← (Ziel≈geteilt) ∧ (shared≈∅ ∧ |disj_c| groß)                              [c]
     M4 Frontier/MustKnow ← { s ∈ disj_c : s ∉ authors(Ω) ∧ disc_c≈disc_K ∧ op(s)↑ }                 [c]
     M2 Affiliation       ← { s ∈ shared : σ_c(s) ≈ σ_K(s) }                              [gated by σ]
     M3 Spannung          ← { s ∈ shared : σ_c(s) ≠ σ_K(s) }                              [gated by σ]
     signature ← { Module die feuern }   # mehrere gleichzeitig = der Relationstyp; Tri-State, kein Skalar
     return signature
     # KONSEQUENZ des leeren σ-Slots: M1, M4 voll rechenbar JETZT; M2, M3 emittieren 'pending-sign'
     #   statt +/−. Die relationale Schicht ist partiell live — genau an der Vorzeichen-Naht.
```

**Lesart der Formalisierung:** `BuildFallgestalt` ist vergleichsfrei und produziert das
persistierbare Objekt; `Relate` rechnet on-demand zwischen zwei Fallgestalten. Das fehlende
Vorzeichen ist kein blockierendes Loch: `RESOLVE_SIGN` ist definiert, ihre Eingänge (`p`,`w`)
sind **[c] berechenbar**, nur die Auflösung `σ` steht auf `⊥`. Folge: **M1/M4 (inkl. Must-Know)
laufen heute; M2/M3 warten formal sauber an der Naht** — die Stelle, an die später die
semantische/SARAH-Schicht andockt.

---

## 10. SARAH-Kontrakt — schema-geprüft (Benjamin 2026-05-31)

Ersetzt die vorige [asseriert]-Fassung: gegen SARAHs reales Schema geprüft
(`migrations/032_argumentation_graph_experiment`, `040_argument_validity_and_grounding`,
`048_bibliography_entries`). Das übergebene Beispiel ist SARAHs **H4-Analyse von K selbst**
→ dieselbe Fallgestalt, beide Strata sichtbar.

**[Schema-geprüft] Stratum B — Argument-Graph (= „Aussage als Einheit", real):**
- `argument_nodes` = die **Aussage**: `claim`, `premises` (typisiert `stated|carried|background`),
  `anchor_phrase` + char-Span (die „Stelle"), `position_in_paragraph`. Diagnostik im Schema-Kommentar:
  „wenn die meisten premises als *background* zurückkommen, hat das LLM Theory-Mining statt
  Argument-Extraktion betrieben" — das **ist** operativ-vs-genannt auf Prämissen-Ebene.
- `argument_edges`: `kind ∈ {supports, refines, contradicts, presupposes}`,
  `scope ∈ {inter_argument, prior_paragraph}`. **`contradicts` ist real** (im K-Beispiel nur
  nicht instanziiert, weil kohärenter Eigentext).
- `referential_grounding ∈ {none, namedropping, abstract, concrete}` — **exakt die
  operativ↔genannt-Achse**, 4-stufig, Pflichtfeld, „Pure Textanalyse, niedriges Halluzinationsrisiko".
- `validity_assessment` {`carries`, `inference_form ∈ deductive|inductive|abductive`, `fallacy`} —
  Charity-First (positiv-rekonstruktiv vor Fallacy-Suche).
- Anmerkung: der Argument-Graph ist in SARAH selbst ein **experimenteller, opt-in, entfernbarer**
  Seitenzweig (Brief-Flag `argumentation_graph`), nicht ihre Kern-Ontologie.

**[Schema-geprüft] SARAH spannt AUCH Stratum A — was ich unterschätzt hatte:**
- `bibliography_entries` (Mig. 048, **deterministisch, KEIN LLM**): `first_author_lastname` + `year`
  am Werk-Ende; Inline-Citations werden dagegen aufgelöst (H3 „GRUNDLAGENTHEORIE"), mit
  orphan-citations + primär/sekundär-Befund. **Das ist mein `R*` + die Density-Auflösung — Stratum A,
  in SARAH bereits gebaut.** D.h. `BuildFallgestalt` ist für *in SARAH geladene Dokumente* großteils
  schon da: H3 (bibliometrisch [c]) + H1/H4 (argumentativ [sarah]).

**Die Naht, konkret:** mein `bears: Source→Aussage` ist in SARAH realisiert als
`argument_node.premises[type=background|…]` + `referential_grounding`. Mein bibliometrisch
**gerechnetes** operativ↔genannt (Density) und SARAHs **gelesenes** `referential_grounding`
sind dieselbe Achse in zwei Auflösungen → direkt gegeneinander validierbar. Erste Überlagerung
am K-Beispiel: die Selbstzitate (Jörissen/Klepacki 2021; Jörissen 2022; Klepacki/Jörissen 2023)
erscheinen in §3 als „Werkbezug ohne Stelle / Werk genannt, ohne Stelle" = **genannt** — deckt sich
mit dem Stratum-A-Befund O6-Trajektorie (nicht O1-operativ).

**[Schluss, nicht Schema] Arbeitsteilung:**
- **SARAH = per-Dokument-Extraktor beider Strata** (Eigenwerke + tief gelesene Dokumente).
- **MOJO = relationale Schicht**: `Relate`, M1/M4, Korpus-Frontier gegen `own_refs.db`, Must-Know,
  Slider. Cross-Dokument + Korpus-Abgleich sind *nicht* SARAHs Job (sie arbeitet per case/document).
- **Eskalation = SARAH-Ingestion:** `RESOLVE_SIGN`-ESCALATE heißt praktisch „lade diesen Kandidaten
  als SARAH-Case und fahre H1/H4". Billig überall (MOJO Stratum A aus flacher Refliste), semantisch
  nur dort, wo σ entscheidet. Komposition rein über Daten — kein Code-Import.

**Ehrlichkeit — Stratum B ist kein Orakel:** Das K-Beispiel zeigt SARAHs eigene Fehlbarkeit offen:
§1-Audit korrigiert ein `assessment_failure`, wo die AA selbst normative Begriffe in den claim
eingeschleppt hatte; §3 degeneriert in LLM-Wortsalat und wird als „unaufgelöst/abstract" geflaggt.
Folge für den Import: Stratum B kommt **mit** seinem Tri-State-Status (aufgelöst/teils/unaufgelöst)
+ Audit-Trigger als Konfidenz herein — nie als gerechnete Wahrheit gewaschen.
