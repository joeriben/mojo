---
name: Open-Source-Plan mit Agent-gesteuerten Workflows
description: MOJO wird Open Source; ein Claude-Agent innerhalb der Plattform soll über die gebauten Tools die Workflows autonom steuern können — braucht dokumentierte Workflow-Scripts
type: project
---

MOJO soll als Open-Source-Plattform veröffentlicht werden.

**Why:** Der aktuelle Entwickler (Claude Code in interaktiver Session) wird nicht dauerhaft verfügbar sein. Stattdessen soll ein Claude-Agent *innerhalb* der Plattform die agentic Tools (Scout, Diskursraum-Management, Fetch, Digest, Trends, Biblio) autonom steuern können.

**How to apply:**
- Workflows müssen als ausführbare Scripts/Runbooks dokumentiert werden, nicht nur als DEVLOG-Prosa
- Jeder Workflow braucht: Trigger-Bedingung, Schrittfolge, Entscheidungspunkte, erwartete Outputs
- Zielgruppe der Dokumentation: ein Claude-Agent mit Tool-Zugriff, nicht ein menschlicher Entwickler
- Beispiel-Workflows: "Neues Journal evaluieren", "Diskursraum pflegen", "Wöchentlicher Digest-Lauf"
