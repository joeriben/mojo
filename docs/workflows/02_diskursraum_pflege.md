# Workflow: Diskursraum-Pflege

## Zweck
Diskursräume aktuell halten: Profile prüfen, Querschnitte erkennen, neue Räume vorschlagen, Journals umzuordnen.

## Trigger
- Nach Journal-Aufnahme (Workflow 01) — neue Journals brauchen Cluster-Zuordnung
- Periodisch (z.B. quartalsweise) — Diskurse verschieben sich
- Bei inhaltlicher Unzufriedenheit mit Trend-Analysen

## Voraussetzungen
- `diskursraeume.json` existiert
- `articles.db` hat aktuelle Daten (nach `mojo fetch`)
- Für `suggest`: OpenRouter API-Key

## Schritte

### 1. Übersicht
```bash
mojo diskurs list
```
Zeigt alle Räume mit Journal-Anzahl und Artikel-Anzahl. Prüfe:
- Sind Räume zu dünn besetzt (<3 Journals)?
- Sind Räume zu breit (>10 Journals)?

### 2. Profile einzelner Räume
```bash
mojo diskurs profile <key>
```
Liefert (kein LLM, keine Kosten):
- Zeitliche Verteilung (Histogramm)
- Top OpenAlex-Konzepte und -Topics
- Key-Term-Overlap mit Benjamins Publikationen
- Cross-Cluster-Overlap (geteilte Journals)
- Agent-Verdict-Verteilung

Entscheidungspunkt: Passt das Konzept-Profil zur Beschreibung des Raums?

### 3. Querschnitte identifizieren
```bash
mojo diskurs crosscut
```
Konzepte die in ≥3 Räumen stark vertreten sind. Hinweis auf:
- Fehlende Räume (starkes Querschnitt-Konzept ohne eigenen Raum)
- Redundante Räume (zu viel Overlap)

### 4. LLM-Vorschläge (optional)
```bash
mojo diskurs suggest
```
- Kosten: ~$0.01 (Haiku)
- Schlägt bis zu 3 neue Räume + 3 Umbenennungen/Zusammenlegungen vor
- Basiert auf Cluster-Profilen + Querschnitt-Konzepten + Benjamins Key Terms

### 5. Änderungen durchführen
```bash
# Neuen Raum anlegen
mojo diskurs add <key> --name "Name" --desc "Beschreibung"

# Raum umbenennen (kaskadiert zu allen Journals)
mojo diskurs rename <alt> <neu>

# Raum entfernen
mojo diskurs remove <key>

# Journal einem Raum zuordnen
mojo diskurs assign <journal_short> <cluster1> <cluster2>

# Journal aus Raum entfernen
mojo diskurs unassign <journal_short> <cluster>
```

### 6. Verifizieren
```bash
mojo diskurs list                          # Neue Zuordnungen prüfen
mojo diskurs profile <neuer_key>           # Profil des neuen Raums
```

## Entscheidungsregeln
- Ein Journal kann zu mehreren Räumen gehören (Multi-Membership ist gewollt)
- Beheimatungen ≠ Diskursräume (Beheimatungen sind in den Scout-Linsen, Diskursräume sind Journal-Cluster)
- Neue Räume nur bei ≥3 zuordenbaren Journals
- Räume mit <2 Journals prüfen: zusammenlegen oder Journals suchen (→ Workflow 01)

## Kosten
- Profile + Crosscut: $0 (kein LLM)
- Suggest: ~$0.01
