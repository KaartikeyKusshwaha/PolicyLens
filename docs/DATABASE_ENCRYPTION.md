# Database encryption implementation and current limits

`DATABASE_ENCRYPTION=sqlcipher4` explicitly selects SQLCipher 4 for identity and
all tenant databases. The default remains `none` for existing installations.
Selecting encryption never rewrites an existing plaintext database or falls back
to plaintext if opening an encrypted database fails. The actual Oracle pilot was
migrated offline into a new encrypted installation on 23 October 2026; a separate
off-machine recovery drill passed. Originals were preserved. See
`DEPLOYED_CHECKPOINT_20261023.md` for exact rollout evidence and limits.
For another plaintext installation, complete migration and recovery acceptance
before selecting SQLCipher; changing the setting alone does not migrate data.

## Key and file protection

The pinned `sqlcipher3==0.6.4` dependency supplies the native database driver.
The connection checks its SQLCipher major version, applies a raw 256-bit key,
reads the actual schema to prove successful decryption and checks cipher status.
Database keys are HMAC-SHA256 derived from the original 32-byte installation key
with the distinct purpose `policylens:database-encryption:v1`. MFA secrets and
audit signing retain their existing, separate derivations.

Public installations must pre-provision `SECURITY_KEY_PATH` separately. A new local
installation can generate its key; existing databases never cause a missing key
to be replaced. Keep a protected recovery copy of the original key outside
database snapshots. Changing or losing the key prevents opening the databases;
there is no recovery bypass or implemented rotation procedure. POSIX key files
must have mode 0600. On Windows, restrict the key and data directory ACLs to the
operator/service account; chmod does not establish a Windows ACL.

SQLCipher encrypts database pages, including policy text, FTS indexes, account
records, jobs and audit records. Connections use memory for temporary SQL data
and enable SQLCipher memory security. Database and journal encryption does not
protect a compromised running process, captured application memory, API traffic,
decrypted exports, logs or other files outside the databases. The raw master key
is not stored inside the database. A copied key together with copied databases
removes this protection.

## Offline migration into a separate installation

Stop the application first. Keep the source's original `DATABASE_PATH`,
`DATABASE_ENCRYPTION=none` and explicit `SECURITY_KEY_PATH` configured while running
`python manage.py migrate-encryption --output NEW_ENCRYPTED_SNAPSHOT_DIRECTORY`.
If the installation has never created a master key, provision a private raw
32-byte key first using `manage.py security-key --output PRIVATE_KEY_PATH` and
configure its absolute path. Do not replace any existing key. Migration validates
existing MFA ciphertext against the supplied key and refuses a mismatch.

Migration holds the installation lock and uses SQLCipher's `sqlcipher_export`
to copy identity and every registered tenant, including FTS indexes. It requires
a new output directory, verifies the encrypted snapshot, and leaves plaintext
source databases intact. A failed attempt may leave an incomplete output directory;
it must never be treated as a usable snapshot without successful verification.

Next, select `DATABASE_ENCRYPTION=sqlcipher4`, retain the same absolute
`SECURITY_KEY_PATH`, and run `manage.py verify NEW_ENCRYPTED_SNAPSHOT_DIRECTORY`,
then `manage.py restore NEW_ENCRYPTED_SNAPSHOT_DIRECTORY --destination NEW_DATA_DIRECTORY --deletion-guard CURRENT_EXTERNAL_GUARD --deletion-guard-sha256 CURRENT_INDEPENDENTLY_RETAINED_SHA256`.
Export the guard with `manage.py deletion-guard --output NEW_EXTERNAL_GUARD_FILE`
while the original plaintext source is stopped and still selected. Its
purpose-separated authentication remains valid with the same installation key
after selecting SQLCipher. Retain the current guard and digest independently;
see `DELETION_RESTORE_GUARD.md` for recovery requirements and remaining limits.
Only after successful verification, restore and operator acceptance should the
stopped service's `DATABASE_PATH` point into that new data directory. Restore
rebases tenant paths and revokes credentials as described below. Keep the original
installation available for rollback; migration does not delete plaintext originals,
old backups or other copies. Their eventual removal belongs to the retention and
deletion procedure, which remains unfinished.

## Snapshots and recovery

For retained logical data after deletion, `manage.py compact-encrypted --output
NEW_SNAPSHOT` rebuilds all databases into new encrypted files and verifies table
inventories, row counts/content hashes, integrity and zero free-list pages. It
preserves originals and does not prove physical erasure. Follow
`ENCRYPTED_COMPACTION.md` and the same current-guard/new-directory restore process.

Workspace backup downloads remain encrypted when the workspace is encrypted.
Whole-installation `manage.py backup`, `verify` and `restore` use the configured
database driver. Encrypted snapshots record the scheme and SHA-256 fingerprint
of the derived database key; the fingerprint is not key material. Verification
requires matching configuration and the original installation key, file hashes,
sizes, SQLite integrity, SQLCipher page authentication and tenant mappings.
Legacy plaintext manifests remain supported in plaintext mode.

Restore requires a new destination, preserves source snapshots, rebases tenant
paths, revokes sessions, reset links and agent keys, removes pending MFA setup
and recovery codes, and interrupts jobs that had been running. Enabled MFA seeds
still require the original installation key. Point `SECURITY_KEY_PATH` explicitly
at that key when starting a restored installation; do not use a new destination's
default key path. Keep encryption mode consistent for every process and operator
command.

The server exporter verifies encrypted snapshots with the same settings. For
SQLCipher snapshots, supply `--database-key-file PRIVATE_RECOVERY_COPY` to
`deploy/pull_backup.py`, or `-DatabaseKey PRIVATE_RECOVERY_COPY` to the Windows
task installer. This is a separately protected copy of the original raw 32-byte
installation key, not the Fernet key passed with `--key-file`/`-EncryptionKey`.
Keep both outside the backup destination. Supplying the database key selects
encrypted mode and rejects plaintext downgrades. Without it, legacy plaintext
SQLite snapshots are verified entirely in memory; encrypted snapshots are refused.

SQLCipher's native binding cannot deserialize a database in memory. The receiver
stages only the original ciphertext bytes in a temporary directory, opens them
read-only with the recovery key, enables in-memory SQL temporary storage, and
verifies SQLite integrity, SQLCipher page authentication and tenant mappings.
Temporary files are closed and removed before successful verification returns.
No decrypted database is written to disk. Restrict the receiver's Windows TEMP
directory ACLs to the operator/service account; POSIX temporary directories use
0700 and files use 0600. This is not protection against a compromised running host.

The complete transfer archive is Fernet-encrypted and re-verified after decrypting
in memory before publication. Receipts identify the database scheme/fingerprint
and preserve the last success when a later attempt fails. Automated recovery
drills decrypt the saved archive, re-verify it, restore encrypted databases into
a separate installation and check both tenants, customer records and FTS.
Actual off-machine transfer scheduling, deployed storage verification, key
provisioning and operator migration/recovery acceptance remain unverified.
Application encryption must stay disabled on the current pilot until those
steps are completed and reviewed.
