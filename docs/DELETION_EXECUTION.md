# Offline logical deletion

Logical deletion is an explicit operator command. There is no execution route in
the web app or agent toolkit. It removes only the exact eligible operational rows
from an independently reviewed customer inventory. It does not prove erasure of
immutable audit/governance text, SQLite pages/WAL, exports, backups, checkpoints,
migration originals or downstream model context.

Configure SQLCipher and the original installation key. Set
`DELETION_STATE_DIRECTORY` to a private, durable directory outside the data root,
without symlinks or redirected parents. Keep that complete directory and the
current independently retained guard digest outside database rollback scope.
The directory may be on the same host; that alone is not off-machine resilience.

Use Settings → Retention to approve a documented retention policy, reconcile copy
custody and discovery evidence, then submit a current customer inventory preview.
A different current administrator/reviewer must approve it. The author must still
be an administrator at execution. Approval expires 24 hours after submission.
Retention periods, open cases/tasks, nonterminal jobs, legal holds, shared/text
references and outstanding registered copies block execution. Discovery evidence
and retained-data acknowledgements are mandatory human review evidence, not
independent proof of complete copy discovery. Stop the Python process, then run:

```sh
python manage.py execute-deletion --workspace WORKSPACE_UUID --request APPROVED_REQUEST_UUID --reason "Reviewed the exact inventory and operator recovery requirements." --acknowledge-retained-data
```

The command holds the installation lock and an immediate workspace transaction,
rechecks maker/checker membership, approval, expiry and the complete pinned plan.
Customer/policy/hold/custody changes invalidate the request. It publishes the
complete prospective authenticated suppression state as `REQUEST.pending` and
flushes it before deleting any row. Each row's complete hash and row identity are
rechecked; deletion must affect exactly one row. Dependent reviews/steps are
removed before their decisions/jobs. Rows, executed request, receipt and audit
events commit together. The external file then becomes `REQUEST.guard`.

Output includes the receipt ID, removed-row count, guard path and SHA-256, with
`physical_erasure_proven: false`. Retain the guard and digest independently before
treating recovery readiness as accepted. The web review page and signed sponsor
evidence packs retain receipts. The request's original pinned snapshot and audit
remain, including retained identifying metadata. Re-execution is refused.

## Interrupted execution

Any `.pending` file blocks startup and further execution. Do not delete it,
replace the external directory, or generate an empty guard to bypass it. With an
authenticated intact pending file and the installation stopped:

```sh
python manage.py reconcile-deletion --workspace WORKSPACE_UUID --request REQUEST_UUID --outcome commit --reason "Verified the committed receipt and absence of all operational targets."
```

Commit requires the exact receipt hash/request link and absence of every target.
If the transaction fully rolled back, use `--outcome abort`: it requires the full
original inventory to match and no execution receipt to exist. It cancels that
authorization and retains authenticated `.aborted` history. A retry needs a fresh
preview and independent approval. Reconciliation can resume after interruption
following its database commit; outcomes are audited.

Startup verifies each aborted artifact against the exact cancelled request,
aborted receipt identity and filename. Its prior receipts must still match live
committed receipts. File extensions alone never authorize ignoring signed state:
renaming a committed guard to `.aborted`, changing the request linkage or rolling
its cancelled state back to approved refuses startup.

Malformed/partially written pending data cannot be automatically authenticated
and reconciled. Startup stays refused; preserve it for operator investigation and
recovery from separately trusted state. Filesystem failures never authorize
continuing without suppression. Unix directory fsync follows publication/rename;
Windows uses file fsync and atomic replace, whose final power-loss durability
depends on storage. Test recovery on the actual deployment.
Failure-injection tests cover both a failed fsync with an intact guard (full
rollback followed by proved abort) and a truncated write (rows preserved, startup,
execution, guard export and automatic reconciliation refused).

Startup authenticates all external guards and matches their hashes to the complete
live receipt set. Missing/changed history, unexpected files, pending operations or
resurrected rows refuse startup. An empty replacement directory cannot satisfy a
database with receipts. Keep cumulative committed and aborted artifacts. Bounds:
2,000 artifacts, 64 MB external history, 8 MB per guard, 2,000 receipts and 10,000
target references. Capacity refusal never samples a partial history.

Every restore requires a current guard and independently trusted current SHA-256;
see `DELETION_RESTORE_GUARD.md`. Old snapshots containing targets are refused; new
snapshots preserve receipts and need matching external state at startup. An old
authentic guard cannot establish current state. Key/host compromise or deliberate
code/raw-database bypass remains outside these checks.

The [encrypted complete-history backup tool](DELETION_STATE_BACKUP.md) now supports
stopped-source export, authenticated receiver retention and recovery into a new
directory. Its actual off-machine transfer and scheduling remain pending.
Automatic off-machine guard publication, complete historical-copy discovery,
physical compaction/media erasure and deployed crash/recovery acceptance remain
pending. This command has been exercised only on isolated synthetic data. It is
not permission to erase existing pilot/customer data or a completion claim for
the full deletion/retention master-plan gate.
