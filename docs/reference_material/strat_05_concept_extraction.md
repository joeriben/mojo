# Strategie 05 — Denker/Begriffe faktisch extrahieren (Vokabularbrücke, Iter 47)

## Ist-Zustand (gemessen, `/tmp/s5.py`)
- **400 unique named_thinkers** über 53 Summaries; 554 key_terms.
- **Die Iter-47-Namen SIND vorhanden:** Barad (6×), Whitehead, Haraway (7×), Foucault (10×). Der Hard-Case
  „Gesture-ing in drawing via Whitehead and Barad" wäre über **Denker-Overlap** fangbar gewesen.
- **Aber drei Defekte:**
  1. **Namensform-Fragmentierung:** „Karen Barad" vs „Barad, Karen"; „Haraway, Donna J." vs „Donna
     Haraway" vs „Haraway, Donna"; „Whitehead, Alfred North" vs „Alfred North Whitehead". Derselbe Denker
     zählt mehrfach → Matching gebrochen, Frequenz fragmentiert.
  2. **Long-Tail:** 278/400 (70 %) nur 1× genannt → Rausch-Risiko (Iter 20/21: Nachnamen-Kollision).
  3. **Nur Summaries (53):** das pre-2018-Fundament fehlt — Deleuze taucht **gar nicht** auf (vermutlich
     in unzusammengefassten Frühwerken).

## Strategie v1
Aus Volltexten alle genannten Denker/Begriffe extrahieren und als Profil-Achse nutzen.

## Adversariale Kritik (v1)
- **Verstößt potenziell gegen R6/CLAUDE.md:** „named_thinkers" droht in „theoretische Verortung"
  (Interpretation) zu kippen. „Beeinflusst von Deleuze" ist Deutung; „nennt Deleuze auf S. 7" ist Faktum.
  Nur Letzteres ist zulässig.
- **Ohne Normalisierung nutzlos:** die Fragmentierung (Defekt 1) macht jede Frequenz/jedes Matching falsch.
- **Long-Tail = Rauschen:** 70 % Ein-Mal-Nennungen als Signal zu nehmen reproduziert den Iter-20/21-Fehler
  (Coverage-Inflation durch Nachnamen-Kollision).

## Strategie v2 (faktisch, normalisiert, gewichtet, als Overlap-Signal)
1. **Rein faktische Extraktion (R6):** explizit genannte Personennamen/zitierte Werke (Named-Entity +
   Zitations-Anker), **keine** „Verortung"/„beeinflusst von". Quelle: Volltexte + vorhandene
   named_thinkers, kein Deutungs-Prompt.
2. **Kanonische Normalisierung:** alle Formen → „Nachname, Vorname" (Dedup über OpenAlex-Autor-Disambig.
   wo möglich). „Karen Barad" = „Barad, Karen" = ein Knoten mit Frequenz 7+.
3. **Frequenz-/Recency-Gewicht:** Long-Tail (1×) nicht verwerfen, aber **niedrig gewichten**; das Profil
   ist die *gewichtete* Denker-Verteilung, kein Set.
4. **Als Signal, nicht nur Material:** ein **Denker-Overlap-Score** (Artikel-genannte-Denker ∩ Benjamins
   gewichtetes Denker-Profil) — die direkte Iter-47-Brücke. Wird in Phase 2 gegen `user_verdict` getestet
   (Achtung Iter 45: Overlap kann Heuhaufen sein → Precision messen, nicht annehmen).
5. **pre-2018-Abdeckung** kommt über Strat 01/04 (Volltexte/Summaries der Frühwerke) — dann erscheinen
   Deleuze & Co.

## Erwarteter Effekt & Messbarkeit (R2)
Ein normalisiertes, gewichtetes Denker/Begriffs-Profil + ein Overlap-Signal, das genau die
theoretisch-verwandten Hard-Cases (Iter 47) adressiert. **Aber Iter 45 mahnt:** Ref-/Overlap-Signale waren
bisher kein Relevanz-Hebel. Daher in Phase 2 streng auf Precision testen — und ehrlich akzeptieren, falls
es wieder nur Erdungs-Text statt Relevanz-Signal liefert.

## → Benjamin-Aufgabe?
Nein — extrahierbar aus vorhandenem Material.

## → nächste
Strat 06: die ungenutzte Projekt-Achse als Erdungssignal aktivieren (`projects.json` ist reich, aber
nirgends im Signal).
