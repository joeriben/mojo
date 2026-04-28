---
name: OpenAlex Journal Topic Router
description: Journal-Top-Topics als nahezu kostenfreier Routing-Layer fuer Suchprozesse, Journal-Kandidaten und A/B/C-Tier-Intuition
type: project
---

# OpenAlex Journal Topic Router

Stand: 2026-04-28

## Kernidee

OpenAlex liefert fuer Sources/Journals thematische Profile (`topics` bzw. aktuell oft noch `x_concepts`). Diese Daten sind praktisch kostenlos abrufbar und koennen genutzt werden, um Journals nicht nur ueber Titel, ISSN oder kuratierte Watchlists zu finden, sondern ueber ihre tatsaechliche thematische und disziplinaere Lagerung.

Die zentrale Produktidee ist ein Retrieval-Router: Bei einer Suchfrage, einem Artikel oder einem eigenen Textentwurf wird nicht indifferent ueber alle Journals gesucht. MOJO rekonstruiert zuerst das Anfrageprofil und vermutet dann, in welchen Journalwelten relevante Literatur mit hoeherer Wahrscheinlichkeit auftaucht. Diese Journals werden tief analysiert; andere werden nur algorithmisch oder breit-flach durchsucht.

Damit entsteht eine formalisierte "begruendete Intuition" fuer Suchprozesse.

## Warum das wichtig ist

Die bestehende A/B/C-Tier-Strategie ist bisher vor allem journalpolitisch und erfahrungsbasiert: Welche Journals sind erfahrungsgemaess wichtig genug fuer teure Analyse? OpenAlex-Top-Topics geben dafuer eine zweite, datenbasierte Perspektive:

- Thematische Naehe zum Forschungsprofil kann pro Journal grob geschaetzt werden.
- Neue Journal-Kandidaten koennen ueber Topics gefunden werden, nicht nur ueber Journaltitel.
- Missed-References-Suchen koennen zuerst dort tief suchen, wo eine Frage vermutlich diskursiv beheimatet ist.
- C-Tier muss nicht "unwichtig" bedeuten, sondern kann fuer eine konkrete Anfrage trotzdem kurzfristig hochpriorisiert werden.

Wichtig: Der Topic-Fit ersetzt keine fachliche Entscheidung. Er ist ein Routing-Signal, kein endgueltiges Urteil.

## Bereits implementierter Stand

Neues Modul:

- `journal_bot/journal_topics.py`

Funktionen:

- `normalize_source_topics()` normalisiert `topics` und `x_concepts` aus OpenAlex-Source-Objekten.
- `compute_source_profile_fit()` vergleicht Journal-Topics heuristisch mit `RESEARCHER_TRIAGE_TOPICS` und `RESEARCHER_AREAS`.
- `search_topics()` mappt Profilbegriffe auf OpenAlex-Topics.
- `discover_candidate_journals()` sucht ueber `topics.id` passende OpenAlex-Sources und markiert bereits getrackte Journals.
- Responses werden lokal in `.openalex_cache/` gecached.

Web-Routen:

- `/api/openalex/lookup` liefert nun zusaetzlich `top_topics`, `topics_source` und `profile_fit`.
- `/api/openalex/journal-candidates` rendert topicbasierte Journal-Kandidaten.

Web-UI:

- Setup > Journals & Diskursraeume enthaelt eine Karte "Themenbasierte Journal-Kandidaten".
- ISSN-Pruefung zeigt jetzt neben Name/Werkzahl auch Top-Themen und einen heuristischen `~A/~B/~C`-Hinweis.
- Neue Kandidaten koennen ins Journal-Hinzufuegen-Formular uebernommen werden.

Nachtrag Codex 2026-04-28:

- `journal_bot/journal_topics.py` enthaelt jetzt auch einen persistierten JournalProfile-Layer:
  - `build_journal_profile()` baut Profile fuer getrackte Journals aus OpenAlex-Sources.
  - `refresh_journal_profiles()` schreibt `journal_profiles.json` als lokale, generierte Persistenz.
  - `journal_profile_status()` liest Status/Counts fuer UI und CLI.
  - `route_query_to_journal_profiles()` rankt eine Suchfrage deterministisch gegen gespeicherte Profile.
- Profile enthalten `topics_raw`, `topic_clusters`, `paradigmatic_signals`, `disciplinary_home`,
  `methodological_signals`, `fit_to_research_profile`, OpenAlex-Metadaten und Refresh-Zeitpunkt.
- Setup > Journals & Diskursraeume enthaelt zusaetzlich eine Karte "Journal-Profile-Router" mit
  Refresh-Button und Profiluebersicht.
- Neue Routen:
  - `/api/openalex/journal-profiles`
  - `/api/openalex/journal-profiles/refresh`
- Neue CLI:
  - `mojo journal-topics status`
  - `mojo journal-topics refresh`
  - `mojo journal-topics rank "..."`
- `journal_profiles.json` ist absichtlich in `.gitignore`, wird aber im Nutzer-Backup mitgesichert.

Templates:

- `journal_bot/web/templates/setup.html`
- `journal_bot/web/templates/_journal_candidates.html`
- `journal_bot/web/templates/_journal_profiles.html`

## Validierung

Durchgefuehrt:

- `python3 -m py_compile journal_bot/web/app.py journal_bot/journal_topics.py`
- Flask-Testclient fuer `/setup`
- Gemockter Route-Test fuer `/api/openalex/lookup`
- Gemockter Route-Test fuer `/api/openalex/journal-candidates`
- Codex-Nachtrag: `python3 -m py_compile journal_bot/journal_topics.py journal_bot/web/app.py journal_bot/cli.py journal_bot/backup.py`
- Codex-Nachtrag: Flask-Testclient fuer `/api/openalex/journal-profiles`
- Codex-Nachtrag: Gemockter Route-Test fuer `/api/openalex/journal-profiles/refresh`
- Codex-Nachtrag: Gemockter Profilbau und persistierter Refresh mit Temp-Datei

Nicht durchgefuehrt:

- Kein Live-Lasttest gegen OpenAlex.
- Keine qualitative Validierung des Topic-Rankings mit echten Journal-Beispielen.
- Kein echter Refresh ueber alle Journals in `journal_profiles.json` im Projektordner.

## Naechster sinnvoller Schritt

Der erste persistierte Router-Layer existiert. Der naechste Schritt ist qualitative Validierung und bessere Query-UX:

- Einmaliger kontrollierter Live-Refresh ueber alle aktiven Journals.
- Ranking an echten Beispielanfragen pruefen: AI4ArtsEd, Cultural Resilience, Missed References, Bildungstheorie.
- Scoring kalibrieren: thematische Naehe, disziplinaere Naehe und produktive Reibung getrennt ausweisen.
- Kandidaten nicht nur anzeigen, sondern optional als persistierte Candidate-Profile neben getrackten Journals speichern.

Ein spaeterer zweiter Schritt kann optional ein kleines Modell nutzen:

- Aus einem Artikel, Abstract oder Textentwurf Fragestellung, Problemraum, theoretische Lagerung und Begriffsnetz extrahieren.
- Gegen JournalProfile ranken.
- Routing ausgeben: `deep`, `medium`, `shallow`, plus Begruendung.

## Ziel-Workflow

Use-Case: "Forschungsprofil A, Artikel/Text X soll auf fehlende Literatur geprueft werden."

1. Anfrageprofil extrahieren:
   Fragestellung, Gegenstand, Theoriebezug, Methode, Begriffsnetz.
2. Journalprofile ranken:
   Wo ist diese Kombination aus Problemraum und Lagerung wahrscheinlich diskursiv beheimatet?
3. Retrieval budgetieren:
   Top-Journals tief analysieren, mittlere Journals semantisch/algorithmisch durchsuchen, Rest nur flach.
4. Ergebnis begruenden:
   Nicht nur "Treffer gefunden", sondern "diese Journalwelt wurde tiefer durchsucht, weil...".

## Offene technische Entscheidungen

- Persistenz: eigenes `journal_profiles.json`, SQLite-Tabelle oder Erweiterung von `journals.json`.
- Refresh-Strategie: manuell im Setup, woechentlich im Monitoring, oder bei Journal-Aenderungen.
- Anzahl Topics: OpenAlex zeigt in der UI offenbar "Top 200"; API-Feld und Pagination muessen live geprueft werden.
- Scoring: aktuelle Heuristik ist absichtlich grob. Fuer produktive Suche muss zwischen thematischer Naehe, disziplinaerer Naehe und paradigmatischer Reibung unterschieden werden.
- Exploration: Router darf nicht nur bekannte Naehe verstaerken; ein kleiner Anteil sollte bewusst entfernte, aber plausible Journals einschliessen.

## Risiken

- OpenAlex-Topics koennen generisch oder schief sein, besonders bei kleineren Journals.
- Topic-Naehe ist nicht identisch mit Relevanz fuer Benjamin.
- Hohe Passung kann Mainstream-Nahe bedeuten, nicht unbedingt produktive Irritation.
- Die Tier-Hinweise duerfen nicht automatisch die Matrix ueberschreiben.

## How to apply

Bei kuenftiger Arbeit an Missed-References, dialogischem Research-Agent oder A/B/C-Tier-Optimierung diesen Router-Strang zuerst beruecksichtigen. Die naechste Implementierung sollte nicht mit LLM-Retrieval beginnen, sondern mit persistierten Journalprofilen und einem transparenten Ranking, das LLM-Kosten nur fuer die Anfrage-Extraktion oder Tiefenanalyse nutzt.
