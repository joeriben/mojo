# Workflow: Override-Kalibrierung

## Zweck
User-Overrides in `articles.db` systematisch auswerten und daraus reproduzierbare Änderungen an Prompt, Signal-Heuristik oder `projects.json` ableiten.

## Trigger
- Nach 20+ neuen User-Overrides
- Wenn ein Journal auffällig oft hoch- oder heruntergestuft wird
- Nach größeren Änderungen an `projects.json`, `journal_bot/signals.py` oder Prompt-Kalibrierung

## Kosten
- Keine LLM-Kosten
- Nur lokale Analyse gegen `articles.db`

## Schritte

### 1. Override-Lage auswerten
```bash
python3 scripts/analyze_overrides.py --suggest-rules
```

Optional für Weiterverarbeitung:
```bash
python3 scripts/analyze_overrides.py --suggest-rules --json > override_report.json
```

Das Script liefert:
- Übergänge (`scannen -> ignorieren`, `ignorieren -> lesenswert`, ...)
- auffällige Journale
- Signalgruppen pro Upgrade/Downgrade
- Memo-Keywords
- Regelhinweise:
  - positive Cues
  - negative Cues
  - Journal-Kandidaten
  - Projekt-Cluster mit False Positives

### 2. Regeltyp entscheiden

Es gibt drei zulässige Zielorte:

1. `journal_bot/signals.py`
   Für deterministische Regeln:
   - Positiv-/Negativ-Cues
   - Kontext-Gates
   - Blockdomänen
   - projektbezogene Match-Heuristiken

2. `projects.json`
   Für projektbezogene Suchverschiebungen:
   - neue `relevance_shifts`
   - schärfere Projektbeschreibungen
   - fehlende Brückenterme

3. `journal_bot/agent.py`
   Für Prompt-/Verdict-Kalibrierung:
   - Relevanzverständnis
   - Bewertungslogik
   - Instructions für Assessment/Verification

Regel:
- Wenn etwas ohne LLM aus Metadaten erkennbar ist, zuerst `signals.py`.
- Wenn das Problem projektspezifisch ist, zuerst `projects.json`.
- Prompt nur ändern, wenn das Problem nicht sauber deterministisch lösbar ist.

### 3. Nur kleine Änderungen einführen

Keine große Sammelrefaktorierung. Pro Kalibrierungsrunde nur wenige, begründbare Regeln.

Typische sichere Änderungen:
- Block-Cue wie `healthcare`, `interview`, `project management`
- neue positive Cue-Familie wie `Auschwitz`, `Shoah`, `Anthropocene`
- schärfere projektbezogene Kontext-Gates
- konkrete `relevance_shifts` in `projects.json`

### 4. Lokal validieren

Nach jeder Änderung:
```bash
python3 -m py_compile journal_bot/signals.py scripts/analyze_overrides.py scripts/backfill_attention_metadata.py
python3 scripts/analyze_overrides.py --suggest-rules
```

Zu prüfen:
- sinken die False Positives?
- bleiben die wichtigen Upgrades erhalten?
- verschiebt sich das Muster in die richtige Richtung?

Keine optimistischen Projektionen aus Einzelfällen.

### 5. Bestand synchronisieren

Wenn die Änderung plausibel ist:
```bash
python3 scripts/backfill_attention_metadata.py
```

Dadurch werden `selection_mode`, `discourse_indicator`, `signal_group`,
`suggested_subgroup` und `project_hits` im Bestand neu geschrieben.

### 6. Ergebnis erneut prüfen

Direkt danach:
```bash
python3 scripts/analyze_overrides.py --suggest-rules
```

Ziel ist nicht Perfektion, sondern eine nachvollziehbare Verbesserung mit geringerem Rauschen.

## Outputs

- geänderter Heuristik-/Prompt-/Projektcode
- aktualisierte Attention-Metadaten in `articles.db`
- neuer Override-Analysebericht

## Nicht tun

- Keine Batch-LLM-Tests zur Heuristikvalidierung ohne separate Kostenprüfung
- Keine großen gleichzeitigen Änderungen an Prompt und Heuristik, wenn die Ursache noch unklar ist
- Keine Übernahme von Memo-Keywords als Regeln ohne Prüfung an Beispieltiteln
- Keine Rückschlüsse aus nur einem Journal auf das Gesamtsystem
