# Schedule complete signed checkpoint-history copies

This source integration adds checkpoint history to the daily server/receiver
pipeline. No Oracle script, SSH permission, receiver schedule or Windows task was
installed or changed during implementation. Current server access remains blocked.

When `CHECKPOINT_DIRECTORY` is configured, `deploy/backup.sh` stages complete
signed history while the installation is still stopped, after its database
snapshot and optional deletion-history stage. It uses
`deploy/checkpoint_backup.py stage`. Failure retains the nonzero exit status and
restarts the service through the existing exit trap. Without checkpoint
configuration, the optional stage is skipped. Snapshot/history cleanup is not
performed automatically.

The private fixed staging root is `/var/backups/policylens-checkpoint-history`.
Bundles are flushed and atomically published with timestamp/hash names. Bounds
are 2,000 staged files/256 MiB total, with complete signed-bundle limits described
in `CHECKPOINT_BACKUP.md`. Unknown/pending files or exhausted capacity refuse
publication; no history is silently pruned. Unix permissions must be 0700.

The fixed verified-SSH exporter is:

```sh
/opt/policylens/.venv/bin/python /opt/policylens/deploy/checkpoint_backup.py latest
```

It reads only the newest staged bytes after service restart, checks filename
SHA-256 and source signing identity, and verifies all signatures, predecessor
links and source age. It does not capture a fresh online audit snapshot or fall
back to older history after newest-file corruption. Daily staging is a point in
time; later audit activity is not included until the next successful stage.

## Receiver and scheduled task

Add an optional checkpoint destination **and independently trusted fingerprint**
to `deploy/pull_backup.py`:

```sh
python deploy/pull_backup.py --host ubuntu@YOUR_VERIFIED_HOST --identity PRIVATE_SSH_KEY --known-hosts VERIFIED_KNOWN_HOSTS --key-file OFFSITE_FERNET_KEY --database-key-file ORIGINAL_INSTALLATION_RECOVERY_KEY --destination DATABASE_ARCHIVE_DIRECTORY --deletion-state-destination DELETION_HISTORY_DIRECTORY --checkpoint-destination CHECKPOINT_HISTORY_DIRECTORY --checkpoint-fingerprint INDEPENDENTLY_TRUSTED_SIGNING_FINGERPRINT
```

Deletion history remains optional, as does checkpoint history; configuring either
makes that copy required for combined success. Checkpoint destination/fingerprint
must be supplied together. Invalid/incomplete trust configuration fails before
remote collection. Its receiver needs no installation/signing key, but the example
includes a separate original recovery key for encrypted DB/deletion verification.
Do not learn the trusted fingerprint solely from the bundle you are verifying.

SSH stays noninteractive with strict host-key checking and fixed script/argument
selection. Each configured artifact must verify before `last-success.json`
updates. Checkpoint failure records a failed latest attempt, returns exit 1 and
preserves the previous success receipt, even if earlier ciphertext copies were
saved. A successful combined receipt includes checkpoint archive/digest/fingerprint,
anchor count and workspace heads. The existing watchdog observes latest-attempt
failure; receipt success alone does not prove continued history freshness.

The receiver cross-checks selected artifacts before combined success. Every signed
checkpoint head must exactly anchor its snapshot workspace's full audit chain;
history/snapshot workspace rosters must match. For deletion history, snapshot
receipts must match external hashes, committed targets must be absent, and
uncommitted entries require matching cancelled requests/proved-abort links.
Pre-deletion databases with newer history, or older checkpoint prefixes with
newer database events, fail the attempt. Individually verified ciphertext may
already be saved on cross-check failure; it is not a verified recovery set and
no new success receipt is produced. This is selected-copy consistency evidence,
not proof of current source state, physical erasure or deployed recovery.
Historical deletion guards may predate newly added workspaces; their older rosters
must be subsets of the snapshot roster, while current checkpoint history must
cover it exactly. A historical guard naming an omitted tenant still fails.

The Windows installer accepts `-CheckpointDestination` and
`-CheckpointFingerprint`, together with existing DB/deletion options. Validation
and argument quoting apply, and the first complete transfer must pass before
registration. It runs only while the Windows user is signed in. Updating source
does not update existing installed scripts/tasks or prove a schedule ran.

Use separate private receiver directories for DB, deletion and checkpoint archives.
Keep encryption keys outside them and retain current bundle digests/fingerprint
independently of rollback. See `CHECKPOINT_BACKUP.md` for monotonic receiver
retention, encrypted recovery and the incomplete-recovery startup block. Actual
transfer/custody, scheduling, checkpoint age between stages, deployed restore and
independent review remain required. No external notification or cloud mutation
was performed.
