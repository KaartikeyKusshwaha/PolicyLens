# Deletion state during recovery

Every `manage.py restore` and `recovery.restore_snapshot` call now requires an
external deletion guard and its independently retained **current** SHA-256.
This applies even to snapshots made before any deletion: their own contents
cannot reveal later deletions. There is no unguarded legacy restore option.

With the authoritative source installation stopped and the original configuration
selected, export a new guard outside the database directory:

```sh
python manage.py deletion-guard --output /private/recovery/deletion-guard-UNIQUE.json
```

The command prints the file SHA-256, receipt count and workspace count. Keep the
file privately off the database host, and preserve the latest digest independently.
Never choose a guard merely because it was bundled with an old backup. An old
authentic guard with its old matching digest cannot prove current deletion state.
If the current guard or original installation key is unavailable, do not restore
service by substituting an older guard or generating a replacement key.

```sh
python manage.py restore /private/backups/SNAPSHOT --destination /private/drills/NEW_DATA --deletion-guard /private/recovery/deletion-guard-UNIQUE.json --deletion-guard-sha256 CURRENT_INDEPENDENTLY_RETAINED_SHA256
```

The guard uses HMAC-SHA256 with a purpose-separated derivation of the installation
key. It is not a public-key signature or third-party erasure certificate. Its
complete workspace roster and completed-deletion receipts bind receipt IDs,
receipt hashes and operational record identities. Names, case text, database
contents and API credentials are not included; record identifiers are still
private information. A first empty guard can provision the local signing key;
an installation with deletion receipts must retain its existing key.

Before creating a destination, restore authenticates/pins the guard, checks its
workspace coverage and matches all receipts already present in the snapshot.
Every recorded deletion target must be absent. Customer absence alone is not
enough: orphan notes, transactions, runs, steps, alerts or reviews also refuse
restoration. Jobs' steps are checked by their owning job ID. Shared policy/control
and governance records cannot be suppression targets. The guard refuses an old
snapshot; it does not automatically redact, delete or mutate that snapshot.

Restore also rechecks copied database checksums against the captured manifest
and checks suppression against the copied bytes before rebasing identity paths.
A changed input/copy fails without returning success. A failure during copying
can leave an incomplete destination; never start that directory. Existing source
snapshots and installations are not overwritten or cleaned up automatically.

Guards are bounded at 8 MB, 2,000 receipts and 10,000 target references. Export
requires the same stopped-installation lock as backup and refuses to overwrite
an existing output. Oversized/malformed/unauthenticated guards, missing workspaces,
unsupported target tables/kinds and altered/omitted receipts fail closed.
The normal encrypted/plaintext integrity and credential-revocation checks remain.

Snapshot verification also matches each manifest workspace path to the absolute
tenant path captured in the identity database. Files must map one-to-one, remain
distinct from `identity.db`, and share the captured source installation root.
Both Windows and Unix source paths are understood without resolving those source
paths on the recovery machine. Swapped tenant mappings, duplicate files, unknown
extra databases and mixed roots are refused by local verification, restore,
off-machine export and the independent receiving verifier. File checksums alone
would not detect a manifest that mapped unchanged files to the wrong tenants.

## Remaining deletion work

The stopped-installation executor now revalidates approved inventory and publishes
pending suppression before atomic row removal. Startup refuses pending or mismatched
external history; reconciliation requires proof of commit or full rollback. See
`DELETION_EXECUTION.md`. Tests exercise real logical execution only in isolated
synthetic installations. Automatic off-machine publication, copy reconciliation,
physical storage handling and deployed crash/recovery acceptance remain pending.
Keep the current guard digest outside rollback scope; same-host state alone does
not establish off-machine resilience or independent erasure proof.

Neither the guard nor logical row deletion proves physical erasure of SQLite
pages/WAL, immutable audit text, exports, checkpoints or downstream copies.
Operators who change the code/configuration, use raw SQLite copying, deliberately
select stale trust material or compromise the installation key can bypass these
application checks. Independent security review and deployed recovery drills
remain required before real customer data.
