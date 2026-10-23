# Explicit-root copy discovery

The read-only operator command inventories every regular file under explicitly
selected local folders, including older snapshots, exports or migration originals:

```sh
python manage.py copy-inventory --root /private/backups --root /private/exports --output /private/review/NEW-discovery.json
```

The output parent must exist and the output file must be new and outside all
selected roots. Roots must not overlap. Files are hashed as bytes; they are not
opened as databases, archives or customer documents. The private JSON report
records selected absolute roots, relative paths, sizes, modification times,
SHA-256 and hard-link counts. Matching hashes do not prove matching custody or
authorize removal. Hard-linked names remain separate entries flagged for review.
No source file is moved, deleted, rewritten or automatically registered.

The console summary includes file/directory/byte counts, canonical inventory
digest and exact report-byte SHA-256, without printing selected paths. Preserve
the report privately: filenames/paths can themselves identify customers. Use its
reference and exact `report_sha256` as discovery evidence when reviewing a deletion
plan. Explicitly classify and register applicable copies through existing custody
governance; this report does not automatically establish customer ownership,
retention eligibility or completeness of that register.
Offline execution now requires `--discovery-evidence` pointing to the exact approved
artifact. Its file-byte SHA-256 must match the approved `discovery_evidence_sha256`;
use the report's exact-byte digest, not the embedded canonical inventory digest.
Other reviewed evidence formats remain valid; the executor hashes bytes rather
than interpreting their claims. Keep the original approved report available.

Every accessible entry must be inventoried. Symlinks, junctions/reparse points,
redirected parents, nonregular files, unreadable directories and detectable input
changes fail the whole inventory rather than silently skipping entries. Files
are checked through path and open-handle identity before/after hashing; directories
and files are checked again before the complete report is returned. Windows
creation-time semantics differ between path and CRT handles, so Windows checks
identity, size, modification time and link count; Unix additionally checks ctime.
This is not an atomic filesystem snapshot or a defense against hostile mutation
that preserves all observed metadata. Stop writers or use trusted filesystem
snapshots when review needs a stable point-in-time inventory.

Bounds: 1–32 nonoverlapping roots, 10,000 files, 2,000 directories, depth 100,
512 MiB per file, 8 GiB total file bytes and 8 MiB report. Exceeding a bound leaves
no successful partial report. A write/flush failure can leave incomplete output;
without a successful console result/digest it is not verified discovery evidence.
Existing output is never overwritten. CLI failures omit raw exception paths.

The command covers only selected accessible local roots at the observed time.
Unselected volumes, remote storage, downloads, checkpoints, other users' folders,
provider context and media/controller copies remain unknown. It does not certify
system-wide discovery, authenticate custodians, verify physical erasure, infer
legal requirements or execute deletion. Complete historical-copy reconciliation
and operator/deployed acceptance remain separate master-plan requirements.
