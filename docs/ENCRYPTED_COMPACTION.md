# Rebuild encrypted storage after logical deletion

Logical row deletion can leave free pages in a SQLite database. The stopped
operator can now rebuild all retained identity/workspace data into **new encrypted
snapshot files** using SQLCipher's export mechanism:

```sh
python manage.py compact-encrypted --output /private/NEW-compacted-snapshot
```

The command requires the explicit `sqlcipher4` configuration, original installation
key, stopped-installation lock and a new output directory. It never rewrites,
deletes, vacuums or truncates the original databases. It copies the live retained
schema/rows into separately keyed attached databases, verifies SQLCipher page and
SQLite integrity, compares the complete table inventories, row counts and sorted
logical-row hashes, and requires zero free-list pages in each rebuilt output.
The manifest records source/target page counts and source/target free-page counts.
All identity and registered workspace databases remain represented.

The full snapshot keeps retained policies, controls, audit/governance, deletion
requests/receipts and FTS contents. The command does not selectively redact these
records. Its output reports `physical_erasure_proven: false` and describes the
scope. A failure leaves no successful manifest; an incomplete output directory
must never be treated as a verified snapshot. Original files remain intact.

Verify the result with `manage.py verify`, then use the normal new-directory
restore procedure with the independently retained **current** deletion guard and
digest. Preserve the matching complete external deletion-state directory. Restore
still refuses deleted targets, checks receipt hashes, revokes credentials and
rebases paths. FTS retrieval and multi-tenant recovery are exercised in tests.
Only switch `DATABASE_PATH` after an operator verifies the restored installation.
Old row-location-based pending deletion previews may become stale after a rebuild;
obtain a new preview/review instead of bypassing inventory hashes.

## Limits

Zero free pages in a newly rebuilt encrypted file is not proof that deleted bytes
were erased from media. Original databases/WAL, old encryption keys, snapshots,
exports, external checkpoints, provider context and storage-controller copies
remain. Encryption does not destroy those copies. Immutable audit/governance can
retain identifying text by design. Secure media disposal and complete copy
reconciliation require their own documented operator controls and evidence.
This command performs no filesystem cleanup or remote deletion.

Rebuild verification scans and sorts all logical rows, including FTS shadow data;
it needs disk and time for a full installation copy. It has not been measured or
run on the Oracle pilot. Test the operation, original key recovery, free-space
requirements and guarded restore on actual deployment hardware before relying on
it. Synthetic tests cover encrypted multi-tenant data with deliberately freed
pages, complete logical preservation, FTS, original-byte preservation, recovery,
online/plaintext/overwrite refusal, injected integrity failure and CLI wording.
