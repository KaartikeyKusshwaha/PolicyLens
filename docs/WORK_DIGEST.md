# Workspace digest and evidence freshness

Inbox shows a read-only workspace digest. `GET /api/evidence/digest` is available
to authenticated human members of every role; agent bearer credentials cannot use
this human route. No model is called, job queued, disposition changed or email sent.

Each request holds one SQLite read transaction for its entire summary: open and
overdue cases, control drafts, pending policy changes, selected source metadata,
and the preceding 24 hours of alerts and failed runs. Queue counts cover the
complete relevant inventory, with at most 20 preview items per queue. Cases with
unparseable or timezone-free due dates are counted separately rather than quietly
classified as on time. Resolved cases are excluded from open and overdue counts.

The complete case/control/change input is bounded at 10,000 rows and 8 MB; exceeding
either bound returns `409 digest_unavailable` without partial counts. Malformed
records or source selection also refuse the digest. Counts are tenant-local.
The Inbox's detailed work queues retain their own pagination/loading limits.

Only enabled sanctions feeds generate freshness warnings. Missing snapshots,
expired retrieval times and invalid/future timestamps need attention. The same
future/invalid-time check now gates ordinary source status and screening, so a
future clock value cannot keep a source perpetually fresh. Freshness measures
retrieval age, not completeness or screening accuracy. No match is not clearance.

The digest refreshes on Inbox entry, work-queue refresh or **Refresh digest**.
Errors hide prior digest counts and expose retry. It does not poll in the
background or deliver notifications outside the app. Opt-in scheduled feed
refresh/customer screening remains a separate, existing zero-model workflow.
Automatic brief preparation remains disabled following the retained scorecard's
failed quality gate; this deterministic summary does not promote that agent.

Tests cover counts beyond preview bounds, UTC due dates, rolling-window limits,
source selection and aging, tenant/role isolation, bearer refusal, capacity and
malformed data, and a concurrent write between summary sections. The concurrency
test proves later counts still use the first read snapshot; a subsequent refresh
sees the new work. Frontend tests cover warnings, links, failure/retry, refresh
and screening-limit wording. Browser acceptance remains pending.
