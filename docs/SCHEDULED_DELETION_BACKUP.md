# Schedule deletion history alongside database backups

This source integration extends the daily server backup and encrypted receiver.
It has not been installed on Oracle or registered as a new Windows task. Actual
SSH access, authentication, first transfer and recovery acceptance remain required.

When `DELETION_STATE_DIRECTORY` is configured, `deploy/backup.sh` stages complete
authenticated history after the database snapshot while the app is still stopped.
The existing exit trap restarts the service on failure, while the backup service
reports failure. Without the setting, database-only behavior remains.

The source script retains snapshots instead of deleting them after a fixed age.
An age-only cutoff cannot enforce approved retention periods or legal holds.
Monitor disk growth and use explicit reconciled copy-removal procedures. Neither
database snapshots nor history bundles are automatically pruned by this pipeline.

Staging uses fixed `/var/backups/policylens-deletion-state`, private 0700 on Unix.
A new file is flushed and atomically published with timestamp and full SHA-256 in
its name. Unknown files, incomplete publication, redirection and full capacity
refuse new staging. Nothing deletes old history automatically. Bounds are 2,000
staged bundles/512 MiB total; plan preservation before capacity runs out. Staging
is separate from runtime deletion state.

The fixed SSH export command is:

```sh
/opt/policylens/.venv/bin/python /opt/policylens/deploy/deletion_state_backup.py latest
```

It reads staged bytes after the app restarts, verifies the newest file's name hash,
outer/embedded authentication, schema and age, and refuses incomplete/unknown
artifacts. It never falls back to an older copy after a failure. It does not query
live customer databases or initiate online export. A daily stage reflects that
stopped snapshot's point in time: deletion after staging needs a fresh stopped
stage before recovery readiness can be asserted.

The service template permits the conventional `/var/lib/policylens-deletion-state`
path through `ProtectSystem=strict`. Provision private service ownership separately.
A custom location needs a reviewed unit override; do not broaden writes to all
of `/var/lib` or disable filesystem protection.

## Receiver

Add the optional separate history destination and original recovery key:

```sh
python deploy/pull_backup.py --host ubuntu@YOUR_VERIFIED_HOST --identity PRIVATE_SSH_KEY --known-hosts VERIFIED_KNOWN_HOSTS --key-file OFFSITE_FERNET_KEY --database-key-file ORIGINAL_INSTALLATION_RECOVERY_KEY --destination DATABASE_ARCHIVE_DIRECTORY --deletion-state-destination SEPARATE_HISTORY_DIRECTORY
```

SSH stays noninteractive with strict host-key checking and fixed remote commands.
The two receivers verify/decrypt/re-encrypt their content. `last-success.json` is
updated only after **both** succeed. If history verification fails, the latest
attempt reports failure and the command exits 1 even if a DB archive was saved.
Existing success receipts remain. The watchdog detects that failed latest attempt.
Cross-artifact verification also checks snapshot receipts/removed targets against
the supplied history before success. A post-deletion history bundle cannot certify
an older snapshot containing those records. Matching proved-abort metadata is
required for uncommitted history entries. See `SCHEDULED_CHECKPOINT_BACKUP.md`
for the combined database/history consistency boundary.
A successful receipt includes history digest/filename/count; preserve the current
digest independently of database/archive rollback.

`deploy/install_backup_pull.ps1` accepts optional `-DeletionStateDestination` with
`-DatabaseKey`. Initial combined transfer must pass before task registration.
Arguments use the existing validation/quoting mechanism. The task still runs only
while the Windows user is signed in. Repository updates do not update installed
tasks. No task registration or actual remote transfer occurred during this work.

See `DELETION_STATE_BACKUP.md` for encrypted retention and history reconstruction.
DB restore separately needs a current guard/digest. This integration does not prove
off-machine custody, guard freshness between daily stages, complete copy discovery,
media erasure, notifications or deployed recovery. It never executes deletion or
changes firewall/authentication settings.
