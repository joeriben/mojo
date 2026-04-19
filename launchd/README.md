`launchd/` enthaelt nur versionierbare Vorlagen und Hinweise.

Nicht versionieren:
- lokal erzeugte `*.plist`
- Laufzeit-Logs wie `stdout.log`, `stderr.log`, `web_stdout.log`, `web_stderr.log`

Versioniert werden nur Templates:
- `mojo.plist.template`
- `mojo-web.plist.template`

Vor der Nutzung die Platzhalter ersetzen:
- `__LABEL__`
- `__PROJECT_ROOT__`
- `__PYTHON__`
- bei der Web-UI optional `__PORT__`

Die Wochenvorlage ruft [scripts/run_weekly_digest.sh](/Users/joerissen/ai/mojo/scripts/run_weekly_digest.sh) auf.
Die Wochenvorlage ruft `../scripts/run_weekly_digest.sh` auf.
