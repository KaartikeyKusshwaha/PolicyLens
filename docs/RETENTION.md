# Retention and legal-hold implementation

This is an incomplete implementation of the master plan's retention/deletion
workflow. Policy approval and legal-hold governance are available in Settings
at `/settings/retention`. No data is deleted or scheduled for deletion by these
endpoints. Independently approved logical execution is available through the
stopped-installation operator CLI with SQLCipher and external suppression state;
see `DELETION_EXECUTION.md`. Physical storage handling, complete backup/export
reconciliation and deployed recovery acceptance remain incomplete.

## Expiring independent deletion-plan review

An administrator can submit the current customer preview with its exact inventory
SHA-256 and a reason. The server recalculates it in a write transaction and refuses
stale input. It preserves the complete bounded snapshot, author and audit record;
one customer may have only one requested/approved plan at a time. Review expires
24 hours after submission. Expired requests must be cancelled/rejected and replaced.

A different administrator or reviewer can approve the logical plan only when
the current inventory still matches and every operational, retention, hold,
shared-reference and registered-copy blocker is clear. Approval also requires a
copy-discovery report reference/hash and explicit acknowledgements that immutable
audit remains and physical/restore limits are unresolved. This records human review
of discovery evidence; it does not automatically prove discovery completeness or
remove the planner's reconciliation warning. Neither approval nor an acknowledgement
executes deletion. There is no web/agent execution endpoint; the stopped operator
command separately revalidates approval and publishes suppression.

The inspection endpoint compares pinned and current hashes, reports staleness,
expiry and current blockers, and exposes the full review snapshot. Requests and
receipts are retained workflow metadata excluded from the business inventory hash;
otherwise creating/approving a request would invalidate itself. Changes to actual
candidate records, policy, holds or applicable custody still invalidate the plan.
Audit events retain request/content hashes rather than copying customer narrative.
Sponsor packs include retained request history and its pinned snapshot.

Authors or administrators can cancel pending/approved requests; a different reviewer
can reject them. Terminal requests cannot be rewritten through these actions.
Every transition and its audit event share a transaction. Review history is retained,
with at most 2,000 requests and 2 MB per pinned snapshot; capacity refusal never
stores a partial plan. Approval is revalidated again by the offline executor,
including expiry, holds, copy reconciliation and exact rows inside its write lock.
The offline executor also requires the actual discovery evidence file and verifies
its exact bytes against the independently approved SHA-256 before publishing
suppression or deleting rows. The receipt keeps the verified hash/size. This is
artifact binding, not proof that discovery is complete or that evidence is true.

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
chain remains retained and may contain supplied customer names/text. Applicable
copy custody records and their review states are included in the inventory hash.
Unconfirmed removals are additional blockers. Every plan still has an inventory
coverage/reconciliation blocker and no execution action: a manual register does
not prove all copies were discovered.

## Copy custody and removal reports

Settings supports a manual register for backups, recovery snapshots, plaintext
migration originals, evidence exports, audit checkpoints and downstream copies.
Each entry records a custodian, location reference, supplied content SHA-256,
creation/preservation dates, scope and reason. Customer/case references must belong
to the current workspace. The application never opens, fetches, executes or deletes
a supplied location. References must exclude credentials and private key material.
Manual registration is an operator assertion; it is not automatic discovery or
verification of storage content. Explicit application exports and workspace backups
also register automatically, as described below. Historical/offline copy discovery
and complete coverage reconciliation remain unfinished.

The effective preservation deadline is the later of the declared date and the
current approved policy's minimum. Backup/recovery/plaintext-original categories
use backup days; audit checkpoints use audit minimum days; evidence/downstream
copies use the longest configured period because they may contain mixed records.
A new policy may extend a deadline but cannot shorten a declared preservation date.

Removal follows `retained` → `removal_requested` → `removal_authorized` →
`removal_reported` → `removal_confirmed`. Authorization requires a different
reviewer from the requester. A custodian report supplies an evidence reference
and SHA-256; confirmation requires a different reviewer from the reporter.
Every stage rechecks current policy, preservation and applicable legal holds.
Workspace copies intersect every active/pending-release hold in the workspace;
customer copies include linked case holds, and case copies include customer and
workspace holds. A newly added hold prevents further removal workflow progression.

Authorization is pinned to the approved policy version. After a policy change,
cancel an unreported request/authorization and obtain a fresh review. Cancellation
retains the prior review history and does not claim to restore an externally deleted
file. A reported removal cannot be cancelled into a fictitious retained state.
After a policy change, a different reviewer can explicitly re-review the existing
report under the new policy before confirmation; the report/evidence and prior
policy history remain intact. Holds and minimum preservation still apply.
All state changes and their record hashes enter the immutable audit chain within
the same transaction. History is bounded at 50 events per copy; the register is
bounded at 2,000 entries and scoped case discovery at 5,000 cases. Exceeding a bound
fails without omitting history/holds.

`removal_confirmed` means a second reviewer confirmed the submitted report. It
does not mean PolicyLens independently proved physical erasure, invalidated old
recovery keys, retracted downloads or verified a provider's retention system.
No filesystem or remote-storage deletion is performed by these endpoints.
Unregistered copies and restore resurrection remain unresolved. Use the review
record alongside actual custodian/operator evidence; do not describe the register
as complete erasure verification.

## Automatically registered artifacts

Sponsor ZIPs, signed and legacy audit downloads, human case-pack downloads,
workspace backup creation/downloads and the toolkit `export_case_pack` result
create custody records before successful delivery. Human download responses expose
`X-PolicyLens-Custody-ID`; workspace backup metadata includes its local `custody_id`.
Each requested download gets a separate entry. A delivery attempt does not prove
receipt, future custody or erasure at the recipient. Ordinary detail/read-tool
responses are not counted as explicit downloads; they still expose data and may
be copied outside the application.

Byte artifacts record SHA-256 of their exact generated response/file bytes.
Toolkit exports record `canonical-json-tool-result`: the object after optional
pseudonymization, serialized with sorted keys, compact separators and unescaped
Unicode (`operations.canonical`). The hash does not describe the transport envelope
or the unmasked source context. Case packs contain customer transaction history,
so their custody scope covers the customer rather than only one case.

Generated copies are registered even before an approved retention policy exists.
Such records have no invented policy or preservation date; removal review requires
an approved policy and uses its minimum. Once a policy exists at creation, the
generated preservation floor is retained. Register-capacity failures refuse delivery;
no untracked successful export is returned. In-memory artifacts are discarded on
failure, while native backup generation reserves custody before creating the file.

Local backup reservations start as `pending`; finalization records the file's hash
and size. Failed creation leaves `failed_unknown`, with no claim that a partial file
was removed. These states block removal review. Administrators can use **Inspect
backup** to verify integrity/hash at the server-selected UUID backup path, or record
`observed_missing` without recreating it. Symlinks/redirected paths and supplied paths
are refused. Inspection is bound to the original storage directory; a restored
installation cannot treat absence in its new directory as proof about the old copy.
Inspection does not establish recipient receipt or physical erasure elsewhere.

A backup's own pending reservation can appear inside its bytes: its final hash
is recorded in the live source database after creation, since embedding a file's
own final hash is not possible. Similarly, a signed export's custody hash enters
the audit chain after the signed snapshot. That later event remains visible as
unanchored until the next capture; it is not retroactively included in the artifact.
Sponsor packs include prior retention-policy, hold and copy-custody records in both
JSON and PDF. Native backup downloads verify the saved content hash when available.

## Boundaries still requiring implementation

The [explicit-root discovery command](COPY_DISCOVERY.md) now produces private,
bounded file-hash inventories for operator-selected backup/export/original folders.
Its report hash can support human discovery review, but it does not infer customer
ownership, automatically register copies, authorize deletion or establish complete
system/downstream discovery. Unreadable, redirected, changing or oversized input
refuses a complete report instead of silently omitting files.

The daily backup source script now preserves dated snapshots rather than pruning
after thirteen days. The previous unconditional filesystem rule could bypass
approved preservation periods and holds. Removal requires explicit operator copy
discovery/reconciliation and reviewed evidence; source tests execute the shell's
failure/restart behavior while preserving an aged synthetic snapshot. This has not
been deployed to Oracle. Free-space monitoring and preservation planning remain
operator responsibilities.

Restore now requires the current external deletion guard and an independently
retained digest for every snapshot. It refuses recorded operational targets and
changed/omitted receipts before creating a restored installation, with a second
check on copied bytes. This prerequisite is documented in
`DELETION_RESTORE_GUARD.md`. The offline executor publishes pending suppression
before atomic row removal and retains receipts. Intact pending operations require
proof of commit or full rollback before restart. Automatic off-machine publication
and deployed recovery acceptance remain pending; synthetic tests are not erasure proof.

- Prove offline execution and crash recovery on the deployed filesystem. Shared
  and ambiguous references remain blockers. Complete discovery/reconciliation of
  saved exports and copies still requires operator evidence and integration.
- Keep policy/control versions, approval evidence, deletion receipts and the audit
  chain's integrity. Existing immutable audit events can include customer names
  and other supplied text. Deleting operational rows cannot erase retained text
  without redesigning integrity/retention handling. Do not claim complete erasure
  or anonymization.
- Register/import offline whole-installation snapshots, off-machine archives,
  migration originals and historical copies; reconcile discovery coverage and
  connect custody results to deletion requests and restored data.
  A database deletion cannot retract downloaded files or downstream model context.
- Define physical deletion/compaction behavior for SQLite WAL, free pages and
  plaintext migration originals, and prove restoration cannot silently resurrect
  deleted records. Encryption does not itself remove those copies.

An offline [encrypted compaction command](ENCRYPTED_COMPACTION.md) now rebuilds
retained logical data into new encrypted files with zero free-list pages and
verified row hashes. It preserves original files/WAL and does not establish
physical erasure or dispose of any copy. Guarded recovery requirements still
apply; media disposal, audit-PII policy and complete copy reconciliation remain.

All policy/hold changes and their audit events share a write transaction.
Role checks, CSRF and tenant isolation apply; agent keys cannot call these human
routes. History reads fail above 2,000 records per kind rather than sampling.
Encrypted full-installation backup/restore preserves active policies and pending
holds. Automated tests cover independence, concurrent approval, stale parents,
rollback and recovery; deployed/operator/browser checks are pending.
