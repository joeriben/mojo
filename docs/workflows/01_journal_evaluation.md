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
- `journals.json` existiert (Journal-Registry)
- OpenRouter API-Key unter `~/.config/mojo/openrouter_key`

## Schritte

### 1. Watchlist prüfen
```bash
# Watchlist-Datei — ungetrackte Journals haben kein ✓
cat docs/journal_watchlist_full.md
```
Entscheidungspunkt: Sind neue Kandidaten eingetragen? Wenn nein → Ende.

### 2. Diskursraum-Kontext aufbauen (optional, empfohlen)
```bash
mojo diskurs list
mojo diskurs profile <key>       # für einen spezifischen Raum
mojo diskurs crosscut             # Querschnitt-Konzepte (kein LLM)
```

### 3. Scout-Lauf
```bash
mojo scout                        # Volllauf über alle Kandidaten
mojo scout --limit 5              # Begrenzung zum Testen
```
- Kosten: ~$0.03/Journal (3× Haiku) + ~$1–2 Opus-Synthese
- Output: `~/Documents/Obsidian Vault/research/mojo/trends/scout_<datum>.md`
- Prüfe: "Bereits getrackt"-Sektion muss alle ✓-Journals enthalten

### 4. Scout-Ergebnis auswerten
Der Output hat 5 Sektionen — die Summe muss = Gesamtzahl Watchlist-Einträge sein:
- **Aufnehmen** → Schritt 5
- **Beobachten** → Watchlist belassen
- **Nicht aufnehmen** → von Watchlist streichen oder begründet behalten
- **Übersprungen** → ISSN-Probleme prüfen, ggf. manuell nachtragen
- **Bereits getrackt** → Kontrolle, dass nichts fehlt

Entscheidungspunkte:
- Stimmen die vorgeschlagenen Diskursräume? → ggf. `mojo diskurs add`
- Gibt es Übersprungene wegen ISSN-Problemen? → manuelle Recherche

### 5. Journals aufnehmen + Tier zuordnen
Für jedes "aufnehmen"-Journal:
```bash
mojo journal add <SHORT> \
  --name "Voller Name" \
  --issn "XXXX-XXXX" \
  --clusters cluster1 cluster2
```
Dann in `journals.json` das `tier`-Feld setzen:
- **A**: Kern-Journals mit hoher Trefferwahrscheinlichkeit (Agent mit read_publication)
- **B**: Relevantes Umfeld (Agent ohne Tools, Einschätzung aus Summaries)
- **C**: Fernes Umfeld, hohes Volumen (nur Screening, kein Agent)

Orientierung: Diskursraum-Multi-Membership (≥2 Räume → eher A), Datenqualität (Abstract-Abdeckung), Scout-Begründung.

Dann Watchlist-Eintrag mit ✓ markieren (manuell in `docs/journal_watchlist_full.md`).

### 6. Initiales Fetch
```bash
mojo fetch
```
Prüfe im Output, dass die neuen Journals Artikel liefern.

## Bekannte Einschränkungen
- Journals ohne OpenAlex-Indexierung werden übersprungen (zkmb.de, e-flux → Scraper nötig)
- ISSN-Resolution scheitert bei einigen kleinen Zeitschriften
- Watchlist-✓ muss manuell gesetzt werden (TODO: automatisieren)

## Kosten
- Volllauf (~50 Journals): ~$3
- Begrenzter Lauf (5 Journals): ~$0.50
