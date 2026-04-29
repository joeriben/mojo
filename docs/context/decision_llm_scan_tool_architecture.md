---
name: LLM-Scan: Modell- und Tool-Architektur
description: Aktueller Entscheidungsstand zu DS3.2, DeepSeek V4 Flash/Pro und Tool-Calling im MOJO-Scan
type: decision
---

# LLM-Scan: Modell- und Tool-Architektur

Stand: 2026-04-29

## Entscheidung

Der produktive MOJO-Scan bleibt vorerst auf dem funktionierenden Stand:

- Batch-Screening: `deepseek/deepseek-v3.2`
- Agent-Analyse (`assess_then_verify`): im normalen `mojo digest`-Batch ebenfalls `deepseek/deepseek-v3.2`
- Tool-Architektur bleibt bestehen: `submit_digest_entry` fuer strukturierte Ausgabe, `read_publication` fuer gezielte lokale Volltextverifikation.

DeepSeek V4 Flash und DeepSeek V4 Pro werden nicht als Default uebernommen. MOJO gilt damit vorerst als funktional ausentwickelt; spaetere Arbeit soll nur gezielt validieren, nicht unkontrolliert umbauen.

## Begruendung

Der wichtigste laufende Kostenhebel beim Scannen ist die Agent-Analyse der durchgelassenen Artikel, nicht die einmalige Vorbereitung der User-Daten und nicht das lokale Lesen selbst. Kosten entstehen durch grosse Prompts, Modellpreis, Iterationen und ggf. Volltextauszuege, die nach `read_publication` wieder in den LLM-Kontext eingehen.

Tool-Calling ist dabei nicht bloss technischer Zierrat:

- `read_publication` trennt Vermutung und verifizierte Bezugnahme. Das Modell muss erst `pub_id`, `search_term` und Hypothese nennen; erst danach bekommt es konkrete Textauszuege.
- Die Tool-Logs machen pruefbar, welche Publikation mit welchem Suchterm gelesen wurde.
- `submit_digest_entry` stabilisiert die DB-/UI-Struktur.
- Der Tool-Pfad kann Ergebnisqualitaet erhoehen, weil er den Agenten in explizite Schritte zwingt und Halluzinationen bei `bezuege` reduziert.

Deshalb duerfen Tools nicht einfach aus Kostengruenden entfernt werden. Wenn Tool-Calling ersetzt werden soll, muss vorher geprueft werden, ob JSON-Schema + deterministische Reads dieselbe Qualitaet liefern.

## Bisherige Tests / Befunde

Kontrollierter Modellvergleich auf dem Agent-Pfad:

- DS3.2 funktioniert als aktuelle Baseline mit `submit_digest_entry` und ggf. `read_publication`.
- V4 Flash laeuft technisch, zeigte aber im Test ein Qualitaets-/Loop-Problem: Beim AI-Black-Box-Fall wurden mehrere Publikationen gelesen, am Ende aber keine verifizierten `bezuege` geliefert; der Lauf fiel auf das Assessment zurueck.
- V4 Pro war im aktuellen Tool-Pfad nicht belastbar: Provider-/Routing-Probleme, u.a. `503` bei Together. V4 Pro hat mehrere Endpunkte, aber nur ein Teil unterstuetzt `tools`; dadurch ist der Test durch Provider-Routing und Kostenpfade kontaminiert.

Erster No-Tools-Gegencheck mit DS3.2:

- Ohne Tool-API und ohne explizites JSON-Schema im Prompt kamen 2 von 3 Testfaellen strukturell unbrauchbar zurueck.
- Das beweist nicht final, dass Tool-Calling notwendig ist, zeigt aber, dass die Tool-Struktur vermutlich ein Qualitaetsfaktor ist.

## Spaetere Pruefung

Wenn diese Frage wieder aufgenommen wird, dann nicht durch blindes Modellwechseln, sondern als A/B-Test:

1. Aktueller Tool-Pfad als Baseline.
2. No-Tools-Pfad mit explizitem JSON-Schema bzw. `response_format`.
3. No-Tools-Pfad mit deterministischen Code-Reads zwischen Assessment und Verification.
4. Vergleich auf mindestens 20 bekannten Artikeln / User-Overrides, nicht nur Einzelbeispielen.
5. Metriken: Verdict-Treue, sinnvolle `candidate_reads`, bestaetigte `bezuege`, Fehlklassifikationen, Kosten, Provider, Cache-Verhalten, Iterationen.

Keine Modell- oder Tool-Architekturaenderung ohne vorherige Absprache und dokumentierten Test.
