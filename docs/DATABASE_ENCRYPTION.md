# Database encryption implementation and current limits

`DATABASE_ENCRYPTION=sqlcipher4` explicitly selects SQLCipher 4 for identity and
all tenant databases. The default remains `none` for existing installations.
Selecting encryption never rewrites an existing plaintext database or falls back
to plaintext if opening an encrypted database fails. Do not enable it on the
existing Oracle installation: encrypted off-machine backup verification and an
operator migration drill there are still required. No deployed encryption claim
is made here.

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
then `manage.py restore NEW_ENCRYPTED_SNAPSHOT_DIRECTORY --destination NEW_DATA_DIRECTORY`.
Only after successful verification, restore and operator acceptance should the
stopped service's `DATABASE_PATH` point into that new data directory. Restore
rebases tenant paths and revokes credentials as described below. Keep the original
installation available for rollback; migration does not delete plaintext originals,
old backups or other copies. Their eventual removal belongs to the retention and
deletion procedure, which remains unfinished.

## Snapshots and recovery

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

The server exporter verifies encrypted snapshots with the same settings. The
off-machine receiver currently supports plaintext SQLite archives, which it
verifies in memory and then encrypts with a separate Fernet key. It rejects
SQLCipher files; it does not silently skip database verification. Extending this
receiver, recovery drills through it, deployed storage verification and operator acceptance remain
unfinished. Application encryption must stay disabled on the current pilot until
those paths are completed and reviewed.
