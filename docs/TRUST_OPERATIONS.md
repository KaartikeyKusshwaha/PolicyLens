# Trust baseline: implementation and deployment

Governed access, SQLCipher and retention workflows are deployed on Oracle.
Migration, verified off-machine transfer, separate restore and selected populated
synthetic browser checks have passed. Full browser/operator acceptance,
independent security review and real-data gates remain open. Read the dated
`DEPLOYED_CHECKPOINT_20261023.md` and `RELEASE_READINESS.md` before taking operator
actions. `SECURITY_REVIEW_HANDOFF.md` prepares the independent review.

## Account sign-in and installation keys

PolicyLens uses normal email/password sign-in. Account 2FA and its enrollment,
verification and recovery-code interfaces were removed at the owner's request.
Password changes, operator-issued single-use reset links and session revocation
remain. See [account authentication](ACCOUNT_AUTHENTICATION.md) for current behavior
and compatibility with obsolete factor records in historical databases/backups.

The existing Oracle installation already uses its protected original key at
`/etc/policylens-secrets/installation.key`. Keep that configured identity and its
protected recovery copy. Do not generate another key or change its path when
changing account features: the same original installation identity is needed for
encrypted databases, protected integration data and derived audit signing.
No rotation procedure is implemented.

For a **new installation only**, provision a private key before encrypted setup,
using an operator-selected, persistent path. For example:

```sh
sudo install -d -m 750 -o root -g policylens /etc/policylens
sudo /opt/policylens/.venv/bin/python /opt/policylens/manage.py security-key --output /etc/policylens/security.key
sudo chown policylens:policylens /etc/policylens/security.key
sudo chmod 600 /etc/policylens/security.key
```

Set `SECURITY_KEY_PATH=/etc/policylens/security.key` in the private service
environment and restart after deploying the reviewed source. Key generation is
exclusive and refuses to overwrite an existing file. Public deployments refuse
to auto-generate keys. Store a protected recovery copy separately from database
snapshots; loss of this key prevents database decryption. Local development
can create `backend/data/.security-key` automatically. Windows operators must
restrict the key's ACL to the service/current user and SYSTEM.

`DATABASE_ENCRYPTION=sqlcipher4` enables purpose-separated whole-file encryption;
the current Oracle pilot was migrated into new encrypted files, with originals
preserved. See `DATABASE_ENCRYPTION.md` for the migration, key recovery procedure
and remaining deployment gates. Never infer encryption of historical copies from
the current live configuration.

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
copies. It is different from the raw 32-byte installation key.

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
Server snapshots exclude environment/API secrets and the installation key. Retention and
deletion of all copies must be included in the upcoming retention policy.

## Remaining operational acceptance

Verified SSH, server timer logs, live transfer, receiver registration, triggered
execution and selected populated mobile checks are recorded in the dated evidence.
The next unattended daily receiver trigger, Telegram pairing/delivery,
owner-workspace authentication/recovery acceptance and remaining browser scenarios
are still open. Source tests do not establish these observations. Before real
customer data, complete independent review/remediation and a signed agreement.
