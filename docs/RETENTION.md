# Retention and legal-hold implementation

This is an incomplete implementation of the master plan's retention/deletion
workflow. Policy approval and legal-hold governance are available in Settings
at `/settings/retention`. No data is deleted or scheduled for deletion by these
endpoints. Customer-linked inventory preview is implemented; deletion request
approval/execution, physical storage handling and backup/export reconciliation
remain to be implemented.

## Policy governance

Administrators draft tenant-local retention policies. Every period is an explicit
integer from 1 to 36,500 days; the application supplies no statutory or recommended
duration. The author records a rationale and an external-copy/backup procedure.
Separate fields cover customer data, resolved cases, terminal agent runs, backups
and minimum audit retention. The current foundation stores these policy choices;
the customer preview now calculates candidate eligibility. No schedule or deletion
executor enforces those periods yet.

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
holds and holds on linked cases discovered by the deletion planner. Current
record-edit APIs do not acquire deletion capability from this foundation. The
eventual executor must recheck holds, policy and inventory hashes inside its
write transaction.

## Customer inventory preview

`GET /api/retention/deletion-preview?customer_id=...` is available to administrators,
reviewers and auditors. A CSRF-protected POST variant is available to administrators
and reviewers. Both are read-only and return one consistent SQLite read snapshot.
The settings UI clears an old result when its customer changes or a refresh fails.

Ownership uses explicit customer/case/agent/decision IDs. Candidates include the
customer, linked cases/notes/tasks/screening/imported objects, transactions, alerts,
agent runs/steps and explicitly customer-linked assessments/reviews. Shared import
receipts, webhook replay records, backtests and free-text mentions are scanned for
known IDs, external references and the recorded customer name. They are flagged
for review rather than treated as authority to delete unrelated/shared rows.
Legacy assessments without explicit ownership remain unresolved references when
they mention known identifiers. Alias-free or unlinked text cannot be proved
absent by this scan; it is not a complete erasure discovery guarantee.

The preview pins row identities/content hashes, current approved policy,
applicable active/pending-release holds, retained governance references and the
latest candidate eligibility timestamp in a deterministic inventory hash. Changing
those values changes the hash. The generation time and informational audit event
count are excluded from that hash; audit history is retained regardless. A recent
transaction receipt, updated note or imported object can extend eligibility even
when the customer was created long ago. Resolved cases require resolution dates;
open cases/tasks, resumable agent runs and conflicting ownership are blockers.

Every inspected table has a 5,000-row bound, with 16 MB total serialized input and
a bounded estimate for reference-search work. Unknown/missing tables, invalid
objects/timestamps or exceeded bounds fail without a partial preview. Public
source feeds, identity/account databases, checkpoint files, free pages/WAL and
external copies are explicitly outside this row inventory. The immutable audit
chain remains retained and may contain supplied customer names/text. Every plan
currently has an external-copy reconciliation blocker and no execution action.

## Boundaries still requiring implementation

- Build independently reviewed deletion requests from the inventory, handle shared
  and ambiguous references, reconcile saved exports and revalidate the exact
  eligible record set during execution. Concurrent changes must invalidate approval.
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
