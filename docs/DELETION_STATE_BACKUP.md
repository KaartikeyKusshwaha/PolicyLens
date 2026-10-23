# Encrypted off-machine deletion history

`deploy/deletion_state_backup.py` exports the complete external deletion state,
authenticates it with a purpose-separated installation-key HMAC, and verifies and
encrypts it at a receiver. Installation keys are never included. This complements
database backup: a database snapshot alone cannot replace current external
suppression history. The tool has **not** been scheduled or deployed on Oracle.

## Export and receive

Stop the authoritative Python service, select its original configuration and
run on the server:

```sh
python deploy/deletion_state_backup.py export > /private/staging/deletion-state-UNIQUE.json
```

Protect staging as private data: it contains record identities and authenticated
guards, though no database narratives, account credentials or key bytes. Export
holds the installation and external-state locks, verifies live receipts/targets
against all state, and refuses pending or inconsistent operations. It includes
committed **and aborted** history. Do not alter, rename or omit artifacts.

Transfer the bytes through the existing independently verified SSH connection to
the off-machine receiver. Keep host-key verification enabled. No arbitrary remote
command, SSH configuration change, transfer, deletion or notification is performed
by this tool. On the receiver, with separately provisioned recovery keys:

```sh
python deploy/deletion_state_backup.py receive --installation-key /private/keys/original-installation.key --encryption-key /private/keys/offsite-fernet.key --destination /private/deletion-history < /private/staging/deletion-state-UNIQUE.json
```

The installation key authenticates the source; the separate Fernet key encrypts
the received bundle. Keep both outside the destination. The command returns the
bundle SHA-256, encrypted filename, artifact count and source creation time. Retain
the **current** bundle digest independently of database and archive rollback.
It is distinct from a `manage.py deletion-guard` file digest used for DB restore.
No output certifies physical erasure or proves that a local directory is off-machine.

Before publishing, receive verifies the outer HMAC and every embedded guard's
HMAC/schema, safe UUID filenames, bounds and source age (30 hours; more than five
minutes into the future is refused). It decrypts and authenticates every retained
history bundle. New state cannot predate the newest retained source time, omit a
previous artifact or change its bytes. A repeated identical bundle is idempotent.
It writes new ciphertext exclusively, flushes, then atomically publishes it; a
partial `.pending` artifact blocks subsequent receipt until operator investigation.
Nothing cleans up or replaces retained history automatically.

## Recover a separate state directory

Choose the archive using the independently retained **current** bundle digest:

```sh
python deploy/deletion_state_backup.py recover --archive /private/deletion-history/deletion-state-DIGEST.fernet --installation-key /private/keys/original-installation.key --encryption-key /private/keys/offsite-fernet.key --destination /private/NEW-deletion-state --bundle-sha256 CURRENT_INDEPENDENTLY_RETAINED_BUNDLE_SHA256
```

Recovery requires a new nonredirected directory. It decrypts, pins the exact
bundle, verifies all embedded guards and reconstructs their original bytes/names.
Creation age may be old for disaster recovery; current selection comes from the
independently trusted digest. It leaves `restoration.pending` until every file is
flushed. Interrupted reconstruction remains ineligible for service startup and
is never silently resumed or overwritten. Source archives remain untouched.

Point `DELETION_STATE_DIRECTORY` at the recovered directory only alongside the
matching database recovery. Normal startup still checks live receipt identities,
cancelled aborted-request links and absent deleted targets. Use a separately
retained current `manage.py deletion-guard` and its digest for database restore;
the complete-state bundle is not a replacement for that guard input.

Limits: 96 MiB complete plaintext bundle, 8 MB per embedded guard, 2,000 state
artifacts; receiver history at most 2,000 encrypted bundles/512 MiB. Bounds fail
without partial inventory. Host/key compromise, deliberate stale trust material,
source and receiver rolling back together, unknown external copies, physical media
erasure and notification delivery remain outside these guarantees. Actual verified
SSH transfer, scheduling after deletion, independent digest retention and deployed
recovery drills remain pending. A successful isolated synthetic test cannot prove
those operational gates.
