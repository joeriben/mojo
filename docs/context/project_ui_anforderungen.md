---
name: UI-Anforderungen MOJO
description: Drei Kernfunktionen der MOJO-Oberfläche — strukturierte Ablage, Zotero-1-Click, dialogischer Research-Agent
type: project
---

MOJO braucht ein eigenes Interface (nicht Obsidian). Drei Kernfunktionen:

1. **Strukturierte Ablage**: Neue relevante Titel nach Diskursraum, neue Trends, neue Zitationen von Benjamins Titeln — organisiert, nicht als Markdown-Halde.

2. **1-Click-Aufnahme in Zotero**: Pro Titel (nicht Batch), legt in mojo-Unterordner an. Überträgt Metadaten + Opus-Kommentare als Zotero-Notiz. Nutzt lokale Zotero-API (pyzotero, bereits im Projekt).

3. **Dialogischer Research-Agent**: Rohtext/Stub hochladen, Frage dazu stellen → Retrieval einschlägiger Literatur aus dem Store. Ist bereits in transact-qda gebaut, kann adaptiert werden.

**Why:** Obsidian ist überkomplex mit schlechter UX für diesen Workflow. MOJO soll ein praktisches Forschungsinstrument sein.

**How to apply:** Vor einem großen Digest-Run muss mindestens Funktion 1+2 stehen. Funktion 3 kann nachgelagert kommen. transact-qda als Referenzimplementierung für den dialogischen Agent prüfen.
