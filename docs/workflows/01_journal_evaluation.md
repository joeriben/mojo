# Workflow: Journal-Evaluation und Aufnahme

## Zweck
Evaluiert Kandidaten-Journals aus der Watchlist und entscheidet, welche ins aktive Tracking aufgenommen werden.

## Trigger
- Initial-Setup des Systems
- Neue Journals in `docs/journal_watchlist_full.md` eingetragen
- Periodisch (z.B. halbjährlich) zur Watchlist-Pflege

## Voraussetzungen
- `summaries.json` existiert (Haiku-Summaries der eigenen Publikationen)
- `diskursraeume.json` existiert (Diskursraum-Definitionen)
- OpenRouter API-Key unter `~/.config/mojo/openrouter_key`

## Schritte

### 1. Watchlist prüfen
```bash
# Watchlist-Datei anzeigen — ungetrackte Journals haben kein ✓
cat docs/journal_watchlist_full.md
```
Entscheidungspunkt: Sind neue Kandidaten eingetragen? Wenn nein → Ende.

### 2. Diskursraum-Kontext aufbauen (optional, empfohlen)
```bash
# Welche Diskursräume existieren, wie sind sie besetzt?
mojo diskurs list

# Für einen spezifischen Raum: Profil mit OpenAlex-Konzepten
mojo diskurs profile <key>

# Querschnitt-Konzepte über alle Räume (kein LLM)
mojo diskurs crosscut
```
Output: Verständnis der aktuellen Diskursraum-Landschaft.

### 3. Scout-Lauf
```bash
# Volllauf über alle ungetrackten Kandidaten
mojo scout

# Optional: Begrenzung auf N Journals (zum Testen)
mojo scout --limit 5
```
- Kosten: ~$0.03/Journal (3× Haiku) + ~$1-2 Opus-Synthese (einmalig)
- Dauer: ~2-10 Min. je nach Anzahl
- Output: `~/Documents/Obsidian Vault/research/mojo/trends/scout_<datum>.md`

### 4. Scout-Ergebnis auswerten
Der Scout-Output hat drei Kategorien:
- **Aufnehmen**: Journals mit starker Empfehlung → Schritt 5
- **Beobachten**: Auf Watchlist belassen, gelegentlich prüfen
- **Nicht aufnehmen**: Von Watchlist streichen (oder begründet behalten)

Entscheidungspunkte:
- Stimmen die vorgeschlagenen Diskursräume? (→ ggf. `mojo diskurs add` für neue Räume)
- Gibt es Übersprungene wegen ISSN-Problemen? (→ manuelle ISSN-Recherche, ggf. Scraper nötig)

### 5. Journals aufnehmen
Für jedes "aufnehmen"-Journal:

```bash
# TODO: `mojo journal add` implementieren (siehe Workflow 02)
# Vorerst manuell in settings.py:
# 1. JournalConfig hinzufügen (Name, Short, ISSN, Typ=openalex, Cluster)
# 2. Watchlist-Eintrag mit ✓ markieren
# 3. Diskursraum-Zuordnung: mojo diskurs assign <short> <cluster1> <cluster2>
```

### 6. Initiales Fetch
```bash
# Artikel der neuen Journals in die DB laden
mojo fetch
```

## Bekannte Einschränkungen
- Journals ohne OpenAlex-Indexierung werden übersprungen (zkmb.de, e-flux → Scraper nötig)
- ISSN-Resolution scheitert bei einigen kleinen Zeitschriften
- Opus-Synthese braucht ausreichend `max_tokens` (aktuell 16000)
- Duplicate-Einträge in der Watchlist werden dedupliziert

## Kosten
- Volllauf (50 Journals): ~$3-4
- Begrenzter Lauf (5 Journals): ~$0.50
