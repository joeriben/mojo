# SARAH-Brief für MOJO — „Relationale Positionierung"

**Zweck.** Der Brief, mit dem ein Dokument (ein eskalierter Kandidat *oder* ein Eigenwerk)
durch SARAH gefahren wird, um den **Fallgestalt-Export** zu erzeugen, den MOJO für `Relate`
konsumiert (Stratum A via H3-Bibliografie, Stratum B via Argument-Graph + Grounding + Validity).
Kein Code-Kontakt — der Brief wird im **BriefEditor** angelegt; MOJO liest später nur den Export.

**Verifikationsgrad.** Brief-Schema gegen `migrations/029` geprüft; Flags gegen `migrations/032/040/047`;
der `persona`/`criteria`-Prompt gegen `src/lib/server/ai/brief-auswertung/index.ts` gelesen (Default-Persona
ist „erfahrener Gutachter", die Kriterien-Auswertung ist von Bauart *evaluativ*). **Inferiert, nicht gelesen:**
dass der per-¶ Argument-Graph-Pass (`hermeneutic/argument-assessment.ts`) kriterien-*un*abhängig ist und allein
über das Flag `argumentation_graph` läuft — plausibel aus Architektur + „referential_grounding = Pure Textanalyse,
Pflichtfeld" (Mig 040), aber nicht im Prompt nachgeprüft. Der Brief funktioniert unabhängig davon: die Flags treiben
die Strukturpässe, `persona`/`criteria` formen die Werk-Ebene.

---

## Felder (für BriefEditor)

- **Name:** `MOJO – Relational Positioning`
- **work_type:** `article`  *(empfohlen; Pipeline-Effekt von `work_type` nicht durchverfolgt — `corpus_analysis` als Alternative, falls Mehr-Dokument-Aggregation gewünscht)*
- **Flags:**
  - `argumentation_graph = true`  → Stratum B: `argument_nodes`/`argument_edges`
  - `validity_check = true`       → `validity_assessment` (carries/inference_form/fallacy) — Stützsignal für σ
  - `h3_enabled = true`           → Stratum A: `bibliography_entries` + Inline-Auflösung (GRUNDLAGENTHEORIE)
  - `include_formulierend = false` → kein zusätzlicher formulierender Memo nötig

## persona (füllt den `[PERSONA]`-Block — überschreibt den Default-Gutachter)

*Prompts auf Englisch (neutraleres Modellverhalten, weniger Register-Drift); die Output-Sprache
steuert SARAHs deutscher Wrapper-Prompt — der Export bleibt i.d.R. Deutsch / Dokumentsprache.*

```
You are a relational discourse cartographer, not an evaluative reviewer. Your task is not to
judge the quality of the work but to reconstruct its position in the discourse: what it
operatively builds on, what it sets itself apart from, and what it claims as its own
contribution. Strictly distinguish sources that bear an argument (operative, anchored to a
concrete passage) from sources that are merely named (namedropping or abstract reference). For
each bearing source, determine the text's stance toward it — affirmative (builds on it),
extending (carries it further), contrastive (sets itself apart from it), or rejecting
(contradicts it) — and name the foils against which the text positions itself. Be charitable:
reconstruct the strongest reading before marking any gap. Your analysis feeds a downstream
system that matches this positioning against an existing corpus of works; what matters is the
precision of the relations, not an overall verdict.
```

## criteria (Markdown; jede `## `-Gruppe wird ein eigener Auswertungs-Pass)

```
## Operative vs. named sources
Which sources does the work draw on operatively — invoked repeatedly or densely, anchored to
concrete passages — and which are only named (a single mention, abstract, namedropping)? List
the bearing sources individually and give each its referential grounding
(concrete / abstract / namedropping).

## Stance toward the bearing sources
What stance does the work take toward each bearing source: affirmative, extending, contrastive,
or rejecting? Which sources or positions serve as foils that the work explicitly sets itself
apart from?

## Self-positioning and key terms
What is the work's central claim of its own? Which self-coined or key terms does it introduce,
and how does it position its contribution relative to the field?

## Trajectory and self-reference
Which self-citations and continuity markers (e.g. "in previous work", the authors' own earlier
publications) does the work carry, and what does it connect itself back to? Treat these as
trajectory, not as operative external sources.
```

---

## Warum so (Mapping auf MOJO-Operanden)

| criteria-Gruppe | MOJO-Operand | füttert |
|---|---|---|
| Operative vs. named sources | O1 + `referential_grounding` | Quellen-Topologie, operativ↔genannt (Cross-Val gegen Density) |
| Stance toward the bearing sources | **O4 Vorzeichen (σ)** | `RESOLVE_SIGN`, M2/M3 |
| Self-positioning and key terms | O3 Ziel + O2 In-vivo | Komplementarität, In-vivo-Signatur |
| Trajectory and self-reference | O6 | cites-you / Trajektorie, sauber von O1 getrennt |

Die Umkehrung gegenüber SARAHs Default ist der Kern: weg vom **Qualitäts-Urteil** (Gutachter),
hin zur **Positionierungs-Karte** (Kartograf). Was MOJO strukturell konsumiert (Argument-Graph +
Grounding + Bibliografie), liefern ohnehin die Flags; `persona`/`criteria` sorgen dafür, dass die
Werk-Ebene Positionierung *referiert* statt zu *benoten* — und damit σ und Eigenpositionierung
explizit macht, die der bibliometrische Stratum-A-Teil nur als Leerstelle adressieren kann.

**Import-Disziplin (gilt MOJO-seitig):** Stratum B kommt mit seinem Tri-State-Audit-Status als
Konfidenz herein, nie als Wahrheit (vgl. `mojo2_proto_indikator.md` §10).
