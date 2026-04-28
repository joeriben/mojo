`launchd/` enthaelt nur versionierbare Vorlagen und Hinweise.

Nicht versionieren:
- lokal erzeugte `*.plist`
- Laufzeit-Logs wie `stdout.log`, `stderr.log`, `web_stdout.log`, `web_stderr.log`

Versioniert werden nur Templates:
- `mojo.plist.template`
- `mojo-web.plist.template`
- `mojo-backup.plist.template`

Vor der Nutzung die Platzhalter ersetzen:
- `__LABEL__`
- `__PROJECT_ROOT__`
- `__PYTHON__`
- bei der Wochenvorlage zusätzlich `__DIGEST_NEXT__`, `__SINCE_YEAR__`, `__WEEKDAY__`, `__HOUR__`, `__MINUTE__`
- bei der Web-UI optional `__PORT__`
- beim Backup `__BACKUP_DIR__` (z.B. `~/Documents/MOJO Backups`)
- beim Backup `__BACKUP_KEEP__` (z.B. `10`)

Die Wochenvorlage ruft `../scripts/run_weekly_digest.sh` auf.
Zur Installation der woechentlichen Monitoring-Planung gibt es `../scripts/install_monitor_launchd.sh`.
Die Backup-Vorlage ruft `../scripts/run_scheduled_backup.sh` auf.
Zur Installation der taeglichen Backup-Planung gibt es `../scripts/install_backup_launchd.sh`.
