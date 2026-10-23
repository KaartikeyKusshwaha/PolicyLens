# Trust baseline: implementation and deployment

This document describes new source on the governance branch, not protections
already deployed to Oracle. Browser acceptance is deferred until implementation
is complete, as requested. Governed agent access, SQLCipher storage and offline
migration/backup/restore are implemented in source. Retention workflows and
deployment acceptance remain outstanding; see `IMPLEMENTATION.md`.

## Account MFA

Account settings supports manual authenticator setup, confirmation, recovery-code
replacement and disablement. Sign-in and invitation acceptance have an optional
second-factor field that becomes mandatory for accounts with MFA enabled.
Codes follow [RFC 6238](https://datatracker.ietf.org/doc/html/rfc6238).
Lifecycle/recovery boundaries follow the [OWASP MFA guidance](https://cheatsheetseries.owasp.org/cheatsheets/Multifactor_Authentication_Cheat_Sheet.html).

- Seeds are encrypted with AES-256-GCM, bound to the account ID.
- Recovery codes contain 80 random bits and are stored only as account-bound hashes.
- TOTP and recovery consumption are serialized in an immediate database transaction.
- Six-digit TOTP codes accept one adjacent 30-second step for clock skew. Replayed
  counters are rejected even if two requests arrive concurrently.
- Enrollment requires password reauthentication and expires after ten minutes.
- Activation, disabling and recovery-code replacement revoke existing sessions.
- Password reset preserves the factor. Existing-account invitations and password
  changes also enforce the factor.
- Restoring snapshots removes pending enrollment and invalidates all backed-up
  recovery codes. The authenticator remains enabled; used codes cannot reappear.
- Users with no factor and no recovery codes need an independently verified operator
  recovery process. The software has no unauthenticated MFA-reset bypass.

Provision the production key before enabling enrollment:

```sh
sudo install -d -m 750 -o root -g policylens /etc/policylens
sudo /opt/policylens/.venv/bin/python /opt/policylens/manage.py security-key --output /etc/policylens/security.key
sudo chown policylens:policylens /etc/policylens/security.key
sudo chmod 600 /etc/policylens/security.key
```

Set `SECURITY_KEY_PATH=/etc/policylens/security.key` in the private service
environment and restart after deploying the reviewed source. Key generation is
exclusive and refuses to overwrite an existing file. Public enrollment refuses
to auto-generate keys. Store a protected recovery copy separately from database
snapshots; loss of this key prevents decrypting enrolled seeds. Local development
can create `backend/data/.security-key` automatically. Windows operators must
restrict the key's ACL to the service/current user and SYSTEM.

MFA encryption alone does not encrypt the SQLite file. Explicit
`DATABASE_ENCRYPTION=sqlcipher4` enables purpose-separated whole-file encryption;
the current pilot has not been migrated. See `DATABASE_ENCRYPTION.md` for the
non-destructive migration, key recovery procedure and remaining deployment gates.

## Automatic off-machine backups

The server's existing daily snapshot service remains the snapshot writer. The
new exporter reads only the newest dated snapshot and verifies its manifest and
databases before transfer. A corrupt newest snapshot fails; it never selects an
older one silently.

The puller requires the existing private SSH identity and previously verified
known-hosts file. It does not accept an unknown host or interactive authentication.
It downloads through SSH, bounds archive sizes, rejects unsafe paths and extra
members, verifies checksums and database integrity, then encrypts with
Fernet before writing to disk. It decrypts and verifies its own result before
publishing the encrypted archive. No database plaintext is extracted locally.
Keep the Fernet decryption key outside the backup destination.

Plaintext SQLite archives are verified entirely in memory. SQLCipher archives
require `--database-key-file` with a protected recovery copy of the original
raw installation key. Only ciphertext is temporarily staged for the native
SQLCipher driver; decrypted pages and temporary SQL data stay in memory. Both
keys stay outside the backup directory. Configuring the installation key selects
encrypted mode and rejects plaintext snapshots. The Windows installer accepts
the same key path as `-DatabaseKey` and includes it in both its initial verified
transfer and scheduled command. See `DATABASE_ENCRYPTION.md` for key/storage limits.

SQLite WAL snapshots need a documented header adjustment solely in the private
in-memory verification copy; original archive bytes and checksums are preserved.
See [SQLite deserialize documentation](https://www.sqlite.org/c3ref/deserialize.html).

Example manual transfer on Windows (paths are operator-specific):

```powershell
& .\.venv\Scripts\python.exe deploy\pull_backup.py `
  --host ubuntu@YOUR_VERIFIED_HOST `
  --identity C:\private\id_ed25519 `
  --known-hosts C:\private\known_hosts `
  --key-file C:\private\backup-encryption.key `
  --destination C:\private-backups\PolicyLens
```

The key file is a Fernet key, compatible with the earlier encrypted off-machine
copies. It is different from the raw 32-byte MFA installation key.

After deploying `deploy/export_backup.py`, `deploy/install_backup_pull.ps1`
can register a daily 09:00 local-time Windows task. The installer first requires a
successful manual transfer. It uses the current user's interactive logon and
limited privileges, catches up missed runs while signed in, and prevents overlap.
It is an automatic computer-to-computer copy while this Windows user is signed
in, not an always-on remote storage service. If the computer remains signed out
or off, backups cannot transfer; use a separately configured always-on runner
before promising that availability. The server's backup schedule is 08:00–08:05 IST.

`last-attempt.json` records every completed invocation and a failed attempt exits
nonzero. `last-success.json` remains the last verified successful transfer.
Check both: a historical success does not erase a newer failure. Encrypted
archives are retained; this puller does not delete previous backups automatically.
Server snapshots exclude environment/API secrets and the MFA key. Retention and
deletion of all copies must be included in the upcoming retention policy.

## Not yet verified on production

SSH reachability, the expired OCI session refresh, current daily timer results,
live transfer and task registration, MFA enrollment, authenticated production
workflows and mobile acceptance. Source tests do not establish those conditions.
