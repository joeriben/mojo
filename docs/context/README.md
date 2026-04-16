# Context — Arbeitskontext für Coding-Assistenten

Dieser Ordner enthält die über mehrere Sessions aufgebaute Arbeitskontextualisierung.
Ursprünglich wurden diese Dateien in Claude Codes persönlicher Memory gespeichert
(`~/.claude/projects/.../memory/`). Für die Portierung zu anderen Coding-Assistenten
(z.B. GPT Codex) liegen sie jetzt im Projekt.

## Inhalt

- `MEMORY.md` — Index mit Kurzbeschreibungen
- `user_*.md` — User-Profil
- `feedback_*.md` — Guidance / Regeln aus vergangenen Interaktionen
- `project_*.md` — Projekt-Kontext (Initiativen, Use-Cases, strategische Entscheidungen)

## Empfohlenes Vorgehen für neue Assistenten

1. `HANDOVER.md` im Projekt-Root zuerst lesen
2. `CLAUDE.md` im Projekt-Root als Projekt-Instruktionen lesen
3. Diese Context-Dateien als Kenntnisstand über den User und die bisherige Arbeit
4. Bei neuen Erkenntnissen / Feedback-Regeln: hier ergänzen, damit die nächste
   Session davon profitiert

Die Dateien sind kurz, auf den Punkt, strukturiert mit Frontmatter und "Why/How to apply"-Logik.
