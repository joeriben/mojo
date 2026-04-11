# Workflow: Trend-Analyse

## Zweck
Diskurs-Trends identifizieren: Was wird in einem Diskursraum gerade verhandelt? Was fehlt? Welche Referenzen steigen/fallen?

## Trigger
- Nach ausreichend Agent-Verdicts (≥30 Artikel im Diskursraum)
- Periodisch (z.B. quartalsweise pro Raum)
- Vor Publikationsplanung oder Projektanträgen

## Voraussetzungen
- `articles.db` mit aktuellen, agent-verarbeiteten Artikeln
- `diskursraeume.json` konfiguriert
- Für LLM-Trends: OpenRouter API-Key

## Schritte

### 1. Diskursraum wählen
```bash
mojo diskurs list
```
Wähle einen Raum mit ausreichend Artikeln (≥30 empfohlen).

### 2. Bibliometrische Analyse (kein LLM)
```bash
mojo biblio --cluster <key>
```
- Kosten: $0
- Aggregiert Crossref-Referenzlisten aller Artikel im Cluster
- Sortierung nach `unique_citing_authors` (robuster als Roh-Zitationszahl)
- Trend-Labels nur bei ≥3 Zitationsjahren UND ≥5 Gesamtzitationen
- Output: Top-Referenzen mit Trend-Indikatoren (↑ steigend, → stabil, ↓ fallend)

Prüfe:
- Welche Autor:innen/Werke dominieren den Diskurs?
- Gibt es Aufsteiger (neue Referenzen mit schnell wachsender Zitation)?
- Gibt es Absenzen (erwartbare Referenzen die fehlen)?

### 3. LLM-Trendanalyse
```bash
mojo trends --cluster <key>
```
- Kosten: ~$0.20 pro Raum (Opus)
- Analysiert alle Artikel im Zeitfenster
- Output: Konsolidierende Diskurse, Spannungen, methodische Beobachtungen, Absenzen
- Ergebnis wird in der Konsole ausgegeben (perspektivisch: Web-UI)

### 4. Diskursraum-Profil als Kontext
```bash
mojo diskurs profile <key>
```
Vergleiche LLM-Trends mit dem datengetriebenen Profil:
- Stimmen die Top-Konzepte mit den identifizierten Trends überein?
- Gibt es Absenzen die sich auch im Konzept-Profil zeigen?

### 5. Ergebnisse interpretieren
Schlüsselfragen für die Interpretation:
- **Konsolidierende Diskurse**: Was wird zum Konsens? Wo schließt Benjamin an?
- **Spannungen**: Wo gibt es produktive Widersprüche? (Das sind oft die interessantesten Forschungslücken)
- **Absenzen**: Was wird NICHT verhandelt, obwohl es relevant wäre? (z.B. "Ästhetische Bildung ist im Diskursraum Digitale Kultur absent")
- **Bibliometrische Aufsteiger**: Welche neuen Referenzen sollte Benjamin kennen?

## Kombination der Räume
Für ein Gesamtbild über alle Räume:
```bash
# Alle Räume nacheinander
for key in $(mojo diskurs list | grep '→' | awk '{print $1}'); do
  mojo trends --cluster "$key"
  mojo biblio --cluster "$key"
done
```
Dann Querschnitt-Analyse:
```bash
mojo diskurs crosscut
```

## Kosten
- Biblio: $0
- Trends pro Raum: ~$0.20
- Alle 7 Räume: ~$1.50
