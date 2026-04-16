---
name: Kostenkontrolle bei API-Tests
description: NIEMALS Batch-API-Tests im Hintergrund starten ohne vorherige Verifikation der Einzelkosten
type: feedback
---

IMMER erst 2-3 Einzelcalls testen und Kosten verifizieren, bevor ein Batch gestartet wird. Niemals einen teuren API-Lauf blind im Hintergrund starten.

**Why:** Ein 100-Artikel-Test der $1 hätte kosten sollen hat $43 gekostet, weil der Prompt-Cache nicht gegriffen hat. Der Fehler wurde erst nach Abschluss bemerkt.

**How to apply:** Bei jedem API-Test: (1) Erst 2 Artikel manuell laufen lassen, (2) Kosten pro Artikel prüfen und hochrechnen, (3) Ergebnis dem User zeigen, (4) erst nach Bestätigung den Batch starten. Gilt besonders für Opus-Calls mit großem System-Prompt.
