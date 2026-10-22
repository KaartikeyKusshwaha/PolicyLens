# Retention and legal-hold implementation

This is an incomplete implementation of the master plan's retention/deletion
workflow. Policy approval and legal-hold governance are available in Settings
at `/settings/retention`. No data is deleted or scheduled for deletion by these
endpoints. Customer/case deletion preview, approval, execution, physical storage
handling and backup/export reconciliation remain to be implemented.

## Policy governance

Administrators draft tenant-local retention policies. Every period is an explicit
integer from 1 to 36,500 days; the application supplies no statutory or recommended
duration. The author records a rationale and an external-copy/backup procedure.
Separate fields cover customer data, resolved cases, terminal agent runs, backups
and minimum audit retention. The current foundation stores these policy choices;
it does not yet calculate eligibility or enforce those periods.

A different administrator or reviewer must approve activation. Drafts pin the
active parent version; if another policy was approved first, the stale draft must
be replaced after review. Approval atomically supersedes the prior active policy.
The configuration hash, author, reviewer, reasons and version history remain
recorded. There is no edit-in-place API for approved policy versions.

## Legal holds

Administrators and reviewers can immediately place workspace, customer or case
holds. Customer/case IDs must resolve in the current tenant. Placement records
the reason and authority reference without copying those sensitive narratives
into the audit chain. Holds never expire automatically. Release has two stages:
a reasoned request, then approval by a different administrator/reviewer. A hold
with a pending release remains effective. Released holds stay in history.

The shared blocking-hold selector covers workspace holds, the selected customer's
holds and holds on linked cases supplied by the deletion planner. That planner
is still outstanding; current record-edit APIs do not acquire deletion capability
from this foundation. The final planner must calculate the complete linkage set
and recheck holds and policy versions inside execution's write transaction.

## Boundaries still requiring implementation

- Inventory customer records, transactions, alerts, cases/notes/tasks, screening,
  assessments/reviews, agent inputs/results/steps, adapter records, webhook replay
  data and saved exports before deletion. Open work and held dependencies must
  prevent execution. An approved preview must pin the exact eligible record set;
  concurrent changes must invalidate it.
- Keep policy/control versions, approval evidence, deletion receipts and the audit
  chain's integrity. Existing immutable audit events can include customer names
  and other supplied text. Deleting operational rows cannot erase retained text
  without redesigning integrity/retention handling. Do not claim complete erasure
  or anonymization.
- Track backups, off-machine archives, operator recovery copies and exported packs.
  Apply holds to their lifecycle, record custodians and reconcile removal separately.
  A database deletion cannot retract downloaded files or downstream model context.
- Define physical deletion/compaction behavior for SQLite WAL, free pages and
  plaintext migration originals, and prove restoration cannot silently resurrect
  deleted records. Encryption does not itself remove those copies.

All policy/hold changes and their audit events share a write transaction.
Role checks, CSRF and tenant isolation apply; agent keys cannot call these human
routes. History reads fail above 2,000 records per kind rather than sampling.
Encrypted full-installation backup/restore preserves active policies and pending
holds. Automated tests cover independence, concurrent approval, stale parents,
rollback and recovery; deployed/operator/browser checks are pending.
