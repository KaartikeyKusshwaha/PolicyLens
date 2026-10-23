# Governed toolkit implementation ledger

The full user-provided master plan is retained in `MASTER_PLAN.md`. This ledger
tracks implementation separately from deployment, browser acceptance, external
review and market validation. None of those gates can be inferred from a green CI run.

## Operational watchdog checkpoint

The receiver now also has `PolicyLens-Operational-Watchdog`, repeating every five
minutes while signed in. An actual triggered invocation exited zero with all five
checks healthy. Atomic local latest/failure reports and an isolated injected disk
alarm were verified; 56 focused tests passed (three platform skips). External
notification delivery remains unconfigured. See `OPERATIONAL_WATCHDOG.md`.

Windows scheduled execution: a real console-launched task returned interrupted
status despite direct CLI success. The installed task now uses matching
`pythonw.exe` and an explicit working directory; an actual scheduled invocation
completed with result zero and a fresh successful combined receipt. Source now
uses that background launcher and suppresses child SSH console windows. The
focused strict-host/noninteractive collection test passes with the platform flag
assertion, PowerShell syntax parses, and Ruff passes. All five real watchdog
checks pass after moving receiver storage to C:. Next daily trigger and external
notification delivery remain unobserved.

Actual deployment: PR #2 merged as `210ffd2d`; reviewed source plus built frontend
is running on Oracle after separate SQLCipher migration/guarded restore. Verified
SSH access, real backup logs, HTTPS asset hashes and readiness were inspected.
The SSH exporter needed an explicit private service environment; its deployed
hotfix is recorded on the follow-up branch. All 23 focused export/environment
checks pass (two POSIX tests skipped on Windows), plus 19 scheduled-history
regressions and Ruff. Combined encrypted off-machine DB/history verification and
a separate restore drill passed. Daily Windows receiver task installed only after
successful transfer, then moved to C: after the watchdog detected D: below its
disk floor. See `DEPLOYED_CHECKPOINT_20261023.md`. Browser/external gates remain.

Populated acceptance expansion: the isolated fixture now previews/imports an
explicitly fictional Marble case and decision through real endpoints, retains
an open local review despite a closed upstream case, assigns/starts a native
investigation, refuses its investigator's final decision and resolves it through
the separate reviewer. Aggregate simulation records the expected one hit. The
traceability API must report the policy's missing current analysis; no model
analysis is forged. Both focused restart/refusal tests pass, checking four cases,
six transactions, independent resolver identity and imported provenance. Ruff
passes. Browser/deployment acceptance remains pending.

Final browser preparation: `evaluation/browser_fixture.py` creates a new isolated
SQLCipher installation with three random-password human accounts, the fictional
policy/customer/payment pack, four independently approved controls, one draft,
six transactions/alerts and three open cases. Input hashes and object IDs are
retained separately from private credentials. External providers and the worker
are disabled; no successful model, fresh feed or browser result is invented.
An actual preparation completed. Both focused tests pass, including restart and
role/count verification plus refusal to overwrite an existing directory. Ruff
passes. The final acceptance instructions and README now distinguish implemented
logical deletion from unfinished physical/cross-copy handling. Exact `790d8f7`
CI completed successfully (run `39975691261`); current changes await new CI.
No browser, merge or deployment action occurred at this checkpoint.

Recovery-set consistency: combined receiver success now additionally verifies
each signed checkpoint head against its snapshot's exact full audit chain and
matches workspace rosters. Deletion receipts must match external hashes, removed
targets must be absent, and uncommitted history needs a matching proved-abort
request. Individually valid but inconsistent generations fail without a new
success receipt. The existing 19 combined-backup tests pass; dedicated stale-head,
pre-deletion snapshot and roster regression tests pass. All 24 combined recovery/
scheduling tests and five final consistency tests pass, including proved abort
and historical deletion guards before later tenant creation. Ruff passes.
Exact preceding `ad42486` CI passed 572 backend and 73 frontend tests
(run `39974775463`); source now has 577 backend tests. No deployment or
live-source consistency claim follows from this local verification.

History-archive monitoring: deletion/checkpoint receiver receipts now record exact
saved ciphertext size/SHA-256 and source creation time. Optional watchdog archive
directories require matching latest combined receipts, fresh source metadata and
unchanged archive bytes, without giving the monitor decryption keys. Eighteen
new failure/healthy tests cover both families; the real three-artifact receiver
test also checks its produced history receipts. All 95 focused watchdog/receiver/
history tests pass; three Windows symlink tests remain enabled for Linux CI.
Ruff passes. Source now contains 572 backend tests; latest exact CI is pending.
This does not establish deployed monitoring, current source state or recovery.

Discovery-evidence execution binding: the stopped operator must now provide the
actual independently approved file. Bounded regular-file hashing and metadata
stability checks must match its approved SHA-256 before suppression publication
or deletion. Receipt records verified hash/size without path/content. Missing,
empty, oversized and mismatched evidence fail with no pending state or removed
rows. This closes an artifact-availability gap without claiming discovery truth
or complete-system coverage. All 46 execution/history regressions and 19 scheduled
backup regressions pass locally, with Ruff. Five new refusal tests cover absent
argument/file, changed bytes, empty and oversized artifacts. Source now contains
554 backend tests. Exact preceding `5bce983` CI passed 549 backend and 73 frontend
tests (run `39973120397`). Browser/deployed/operator acceptance remains pending.

Copy-discovery source: `manage.py copy-inventory` hashes every regular file under
explicit nonoverlapping roots and exports private metadata with inventory/report
digests. It refuses unsafe/unreadable/changing input and capacity excess without
partial success, flags hard links and never deletes/registers/infers ownership.
Twelve tests pass locally, including actual CLI invocation and generic private
failure output; one symlink test requires Linux CI because this Windows account
cannot create symlinks. Ruff passes. This supports discovery review, not complete
copy reconciliation or system-wide discovery. See `COPY_DISCOVERY.md`.

Checkpoint scheduling source: configured daily backup now stages signed complete
history while stopped. A fixed strict-SSH exporter verifies the latest staged
bundle without fallback after corruption. Receiver/Windows task options require
both checkpoint destination and independently trusted fingerprint; success updates
only after every configured DB/deletion/checkpoint copy verifies. Failure preserves
the prior success receipt and exposes a failed latest attempt. Initial 24 scheduling,
deletion and shell tests pass, with the full three-artifact regression running.
The final 29 checkpoint/scheduling/shell tests now pass, including the actual
three-artifact encrypted receiver and previous-success preservation on failure.
Source contains 536 backend tests; exact latest CI is pending.
Bash/PowerShell syntax checks and Ruff pass. No server/task installation occurred.
See `SCHEDULED_CHECKPOINT_BACKUP.md`.

Checkpoint-history backup source now exports every workspace's complete signed
anchor history after capture, verifies outer/individual Ed25519 signatures and
predecessor continuity, and encrypts at a receiver using only its archive key and
an independently trusted public fingerprint. New history cannot omit/rewrite
previously retained anchors or predate receiver state. New-directory recovery
pins a current bundle digest and keeps a blocking marker until files are durable.
Normal checkpoint access refuses incomplete recovery. All 27 initial backup/
checkpoint tests pass; all 12 final backup tests also pass, including the actual
CLI refusal and wrong recovery-digest checks. Ruff passes. Source now
contains 523 backend tests. Actual off-machine transfer/scheduling remain pending;
see `CHECKPOINT_BACKUP.md`. Exact previous `ce11a1a` CI passed 511 backend and
73 frontend tests (run `39962149535`).

Backup retention correction: removed the source shell script's unconditional
thirteen-day snapshot deletion, which could bypass approved preservation periods
and holds. Snapshots now remain until explicit reviewed copy reconciliation/removal.
Four real Bash-script tests verify database-only/combined success, both failure
paths, exact restart behavior, preserved exit status and retained aged snapshots.
Only deployment paths/service commands are redirected into the synthetic fixture;
Windows substitutes directory creation because Git Bash cannot chmod its temp
directory, while Linux CI uses real `install`. No host service or live backup was
modified. Disk monitoring and deployed rollout remain pending.
Ruff and all four shell tests pass. The source suite contains 511 backend tests;
exact previous `eb6d980` CI passed 507 backend and 73 frontend tests
(run `39961336656`). `RELEASE_READINESS.md` now audits remaining requirements
separately from source and synthetic evidence; the full goal remains incomplete.

Scheduled deletion-history source integration: configured daily server backups
stage complete authenticated history while stopped. The fixed verified-SSH latest
exporter refuses corrupt/newest/pending state without fallback. The receiver and
Windows installer accept an optional separate history destination requiring the
original recovery key. Combined success is recorded only after both copies verify;
history failure records a failed latest attempt. The service permits the specific
conventional external-state directory. All 29 scheduling/offsite tests pass;
PowerShell syntax parses and Ruff passes. Actual rollout/transfer remain pending.
See `SCHEDULED_DELETION_BACKUP.md`.
The final 26 scheduling/deletion-history tests also pass after staging permission
checks. Bash syntax validation passes. Exact preceding `6d1b0f3` CI passed 499
backend and 73 frontend tests (run `39960233947`); source now has 507 backend tests.

Encrypted compaction checkpoint: the stopped operator can rebuild all retained
identity/workspace content into a new SQLCipher snapshot. Schema table inventories,
row counts, sorted logical-row hashes, SQLite/SQLCipher integrity and zero target
free-list pages are verified; manifests report source/target page statistics.
Original database bytes remain intact. Four focused tests and the preceding 26
compaction/encryption/hardening checks pass, with Ruff. This handles rebuilding
storage, not physical/media erasure or removal of originals/WAL/copies. See
`ENCRYPTED_COMPACTION.md`; deployed performance/recovery remain pending.
Oracle access recheck: TCP port 22 still fails and OCI CLI reports its saved
security-token session expired. No authentication/browser or infrastructure
mutation was attempted; server logs/backups remain unverified.

External deletion-history backup checkpoint: the operator tool now exports all
authenticated committed/aborted state from a stopped, runtime-verified installation.
The receiver authenticates embedded guards, encrypts the bundle, verifies all
prior retained encrypted history and refuses changed/omitted artifacts or older
source state. Recovery reconstructs original state into a new directory with a
blocking pending marker until all bytes are flushed. Keys are excluded; a current
independently retained bundle digest is required. All seventeen initial synthetic
tests pass, including real executed and aborted history recovery, interruption,
tampering and monotonic retained history. A further actual CLI refusal test
verifies generic failure output. Ruff passes. Actual off-machine
transfer, scheduling and operator acceptance remain pending. See
`DELETION_STATE_BACKUP.md`.

Readiness hardening: probes now open identity and every registered tenant
read-only and query core business tables, including uncached tenants. Missing,
damaged or incomplete tenant storage returns generic 503 without initializing
replacement files. Identity presence is checked before session authentication so
an authenticated probe cannot recreate a missing identity database. Seven new
tests cover plaintext/encrypted uncached tenants and missing identity storage.
Full schema/page integrity and workload acceptance remain separate checks.
All 30 storage-readiness/hardening/encryption tests and Ruff pass locally. Exact
preceding `0733c7c` CI passed 470 backend and 73 frontend tests (run `39957149581`).

Synthetic HTTP load checkpoint: a separate single-worker server now exercises
SQLCipher, real maker/checker setup, concurrent duplicate transaction ingestion,
populated reads, tenant isolation, exact counts, audit integrity and signed pack
verification. The 100-customer/1,000-unique-transaction/four-client run found the
PDF's old 200,000-character cap. The print envelope now matches the existing
2 MB complete snapshot envelope without omitting records. A fresh run passed all
invariants and the chosen endpoint p95 limits, with zero HTTP failures and a
verified pack in 19.785 seconds. Both failure and success reports are retained.
First/middle/final PDF pages were rendered and inspected; PDFium confirmed the
middle-page layout after Poppler font substitution artifacts. All 25 focused
load/evidence tests and Ruff pass; a further retained-report test rechecks trusted
digests and recomputes both passing and failed gates. No browser testing occurred.
Source now has 470 backend tests; actual Oracle/partner/worker/provider load remains unproven.
See `PILOT_LOAD.md`. Exact prior `995b64a` CI passed 458 backend and 73 frontend
tests (run `39954596113`).

Source now includes the read-only readiness/backup/disk watchdog, exit-code JSON
reports and optional hardened systemd units. Receiver success receipts now bind
the actual encrypted bytes and SHA-256. Fifty-seven watchdog/offsite tests pass
locally; three symlink tests are skipped because this Windows account cannot create
symlinks and remain enabled for Linux CI. Ruff passes. This does not establish
installed monitoring, off-machine custody or delivered notifications; see
`OPERATIONAL_WATCHDOG.md`. Exact preceding `d6b7367` CI passed 419 backend and
73 frontend tests (run `39953501764`).

## Deletion review checkpoint

Execution hardening: aborted external artifacts must now identify exactly one
uncommitted receipt and match its authenticated request, cancelled state, aborted
receipt link and filename. Every prior receipt must remain committed with its
original hash. Renaming a committed guard or rolling back an aborted request
cannot turn an extension into permission to ignore suppression history.
Exact pushed `edc3388` CI passed 413 backend and 73 frontend tests
(run `39952745758`). The earlier local full run completed 412 tests; the final
execution suite separately passed 17 tests before this hardening. Twenty-one
execution tests including the four new abort-binding checks passed locally.
All six abort-binding and flush/truncated-publication checks pass, including the
two final write-failure additions. Ruff passes; source now contains 419 backend
tests. No browser/deployment work has occurred.

Offline logical-execution checkpoint: an operator command now revalidates an
independently approved, unexpired inventory under the installation/write locks.
It requires SQLCipher and external deletion state, publishes pending suppression
before exact row removal, and commits request/receipt/audit atomically. Pending
state blocks startup; reconciliation proves commit or full rollback. Abort cancels
authorization and needs a fresh independent review. Startup also refuses altered,
missing or rolled-back receipt history and resurrected targets. The web page and
signed evidence retain executed receipts; no web/agent execution route was added.
See `DELETION_EXECUTION.md`. Complete historical-copy discovery, automatic off-machine
state publication, physical storage handling and deployed recovery remain pending.
Seventeen focused execution tests and 53 guard/request/encryption/retention checks
passed locally; 73 frontend tests, Ruff, ESLint and build passed. Full local backend
regression is running; the source suite contains 413 backend tests. Previous exact
`99c4b48` CI passed 396 backend and 72 frontend tests (run `39947808780`).

Exact recovery-guard commit `25221b5` passed CI with 385 backend and 72 frontend
tests, Ruff, ESLint, production build and dependency audit (run `39946957377`).
Additional recovery hardening now validates manifest paths against captured
identity-to-tenant file mappings in both local and off-machine verification.
Swapped/duplicate mappings, extra databases and inconsistent source roots fail;
Windows and Unix source path interpretation remains portable. Eleven new tests
cover those rules, including encrypted/plaintext exporter, receiver and restore
refusals. All 48 mapping/guard/off-machine backup tests and Ruff pass locally.
The source suite contains 396 backend tests; exact new CI is pending.

Recovery-guard implementation: all restores now require current external
HMAC-authenticated deletion state and an independently retained digest, even for
pre-deletion backups. Workspace coverage, receipt identity/hash and operational
target absence are checked before creating a destination and against actual
copied bytes. Input/copy changes refuse restoration before path rebasing. The
operator CLI exports guards only from a stopped installation and never overwrites
an existing guard. This is a prerequisite, not deletion execution or physical
erasure. See `DELETION_RESTORE_GUARD.md`; durable post-deletion publication and
crash recovery remain required before enabling execution.
Local validation: 25 guard/recovery/migration tests pass, including encrypted and
plaintext recovery, orphan targets, malformed/altered manifests, operator CLI
requirements and changed copied bytes. Ruff passes. The source suite contains
385 backend tests; the previous `acf5e12` CI passed 369 backend and 72 frontend
tests (run `39944668970`). No browser or deployed recovery acceptance occurred.

Exact pushed commit `40d30b0` passed CI with 301 backend and 51 frontend tests,
Ruff, ESLint, production build and npm audit (run `39853582175`).

Expiring deletion requests now retain a complete inventory snapshot and independent
review/discovery evidence. Customer changes, new holds, policy changes and new
exports invalidate the pinned plan; exporting its signed evidence pack is covered.
Local regression passed 298 backend tests, followed by 13 focused request tests
covering the final capacity, encrypted recovery and signed-pack additions (301
backend tests now in source). All 51 frontend tests, ESLint, production build and
Ruff passed. The PDF request section was rendered and visually inspected. This
checkpoint does not implement deletion execution or prove physical erasure.
Browser testing and Oracle deployment remain pending.
## Decisions and current evidence

- Retain the existing repository license (user decision, 22 October 2026).
- Finish all implementation before browser testing (user instruction).
- Research prospective design partners using public web information. No outreach
  is authorized and no interview or partner commitment has been obtained.
- Baseline main commit: `18e7492f365999801c9d0c4ca62a95358cfae938`.
- Baseline CI: 78 backend and 21 frontend tests passed. Public Oracle readiness
  passed; delivered frontend assets matched the baseline build.
- SSH timed out; the existing OCI CLI session has expired. Infrastructure repair
  requiring browser authentication is deferred under the user's browser constraint.

## Phase 0: stabilize and validate

- [ ] Restore narrow SSH access; inspect logs and daily backup results.
- [ ] Automatic off-machine backups with encryption, verification and failure visibility.
  Source implemented: verified server exporter, in-memory verification/encryption,
  failure/success receipts and Windows task installer. Ten transfer/integrity tests
  pass. No schedule is claimed installed until a first real transfer succeeds.
- [x] Tag the verified baseline (`pilot-baseline-20261022`, merged baseline commit)
  and update obsolete dependency descriptions. Product documentation continues to
  evolve as remaining features are implemented.
- [ ] Fresh authenticated production end-to-end acceptance (after implementation).
- [x] Research public design-partner candidates and interview materials; see
  `DESIGN_PARTNER_RESEARCH.md` (five prospects, no contact or validation claimed).
- [ ] Five interviews, two or three partners, and three independent confirmations
  that evidence assembly is painful (external gate; not established by research).

## Phase 1: trust baseline

- [x] Implement TOTP enrollment, encrypted seeds, anti-replay, recovery codes,
  sign-in and invitation enforcement, password-change step-up, session revocation.
- [x] Add account UI and non-browser API security tests.
- [ ] Complete review of MFA and its deployment/key recovery procedure.
- [ ] Database encryption at rest, migration and recovery verification.
  SQLCipher identity/tenant storage and encrypted workspace/full-installation
  backup/restore are implemented with wrong-key, corruption and tenant tests.
  Offline plaintext-to-encrypted snapshot migration preserves source files and
  the original MFA/signing key; restore rebases into a separate installation.
  The off-machine receiver verifies SQLCipher pages and tenant mappings with a
  separately provisioned recovery key, stages only ciphertext, and wraps the
  archive in Fernet. Automated saved-archive restoration checks both tenants and
  FTS; actual scheduling, migration/storage proof and operator acceptance remain
  pending. See `DATABASE_ENCRYPTION.md`.
- [ ] Retention/deletion policy, preview, approval and execution with legal holds.
  Policy drafts/independent activation and immediate workspace/customer/case
  holds with independent release approval are implemented in source and settings
  UI. Pending release holds remain effective. Customer inventory previews now
  bind explicit row ownership, content hashes, policy/holds and retention age;
  shared/text references remain review blockers. Expiring deletion-plan requests
  now pin full snapshots, require independent review and discovery evidence,
  and reject stale/blocked approvals; cancellation/rejection retain history.
  Logical execution is now an explicit stopped-installation SQLCipher operator
  command with external suppression and commit/rollback reconciliation. Web/agent
  execution stays disabled. Audit-PII handling, physical erasure and complete
  backup/export reconciliation remain unfinished.
  Manual copy custody now records scope/custodian/deadlines and independent
  removal authorization/report confirmation; policy/hold checks repeat at each
  stage. Explicit downloads, toolkit case exports and workspace backups now register
  content hashes automatically; failed native generation remains tracked and can
  be inspected at the original location. Historical/offline discovery, complete
  reconciliation and physical erasure are not claimed; see
  `RETENTION.md`. No automatic deletion or complete-erasure claim is made.
- [x] Implement agent-scoped keys, immediate revocation, scopes, rate limits and
  per-key/workspace run budgets, plus admin UI. Deployment acceptance is pending.
- [ ] Agent identity, pinned model/version and pseudonymized model context.
  Source records identity, saved model ID, configured revision and prompt version;
  uses queued configuration; rejects reported model/revision mismatches; masks
  structured identifiers optionally. The default provider revision remains explicitly
  unreported, so immutable underlying model weights are **not** established.
  See `GOVERNED_TOOLKIT.md`.
- [x] Implement signed checkpoints outside database storage, automatic capture,
  failure visibility, signed audit exports and offline trusted-key verification.
  Deployment, off-machine checkpoint retention and operator acceptance remain
  pending. See `EXTERNAL_CHECKPOINTS.md` for the threat model and provisioning.
- [x] Honest security one-pager distinguishes implemented source from the unchanged
  pilot and lists remaining limits/gates. See `SECURITY.md`; this is not production
  acceptance or an independent security review.

## Phase 2: governed toolkit

- [x] Implement registry classes: read, draft, request-approval. Tools:
  search_policy, get_control, simulate_control, list_alerts, get_case_context,
  draft_investigation_brief, verify_evidence, create_review_task, export_case_pack.
- [x] MCP stdio server over the existing runner; no approval/activation/closure/filing tool.
- [x] Thin CLI and Python SDK; Claude Desktop and Cursor examples.
- [x] Automated MCP client seeded investigation, citations, audit and permission-denial tests.
- [x] Actual stdio subprocess and installed CLI against a loopback HTTP test service.
- [ ] Deployed MCP/live-provider and configured-host acceptance after implementation.
  Automated tests use isolated data and mocked Groq responses. These prove protocol
  and enforcement behavior, not real-model accuracy or live desktop-host setup.

## Phase 3: evidence and traceability

- [x] Implement sponsor evidence pack: PDF, JSON, signed manifest and offline
  verification script; policy versions, controls/approvals, dispositions/notes,
  audit checkpoint, source freshness, agent logs. See `SPONSOR_EVIDENCE.md`.
  Production provisioning and browser acceptance are pending.
- [x] Implement policy obligation matrix: explicit human mappings, linked controls,
  latest recorded simulation, alert volumes, screening evidence and coverage gaps.
  Current/historical versions and superseded analyses require deliberate review.
  Populated component and API tests cover mapping boundaries. See `TRACEABILITY.md`.
  Production/mobile acceptance is pending.
- [x] Automated seeded pack and synthetic 50-case export within one minute;
  offline chain/signature re-verification and tampering/tenant/concurrency checks.
  Deployed performance remains unverified.

## Phase 4: adapters and controls-as-code

- [x] Inspect Marble's official v1 decision and beta case OpenAPI contracts before
  adapter implementation. See `MARBLE_ADAPTER_RESEARCH.md` for inspected blob IDs,
  pagination, tenant mapping and upstream outcome boundaries. No live import claimed.
- [x] Adapter registry/interface and previewed Marble v1 decision/v1beta case
  export imports, explicit customer mapping, provenance, deduplication and atomic
  replay. Source outcomes never activate controls or close cases. See `ENGINE_IMPORTS.md`.
  A live Marble export comparison and production/browser acceptance remain pending.
- [ ] One transaction-source adapter selected with design partners (selection pending).
- [x] YAML export/import into atomic draft batches, pinned policy/parent hashes,
  bounded safe schema, preview/replay protection and maker-checker-only activation.
  See `CONTROLS_AS_CODE.md`; production and browser acceptance remain pending.
- [x] Automated Git-to-draft round-trip with a real isolated repository and second
  reviewer; imported engine records appear in the case inbox with source provenance.
  Populated component checks cover import and case views; live/browser acceptance
  remains pending.

## Phase 5: autopilot and scorecard

Workspace-digest checkpoint: Inbox now shows a single-snapshot, zero-model work
summary and selected-feed freshness warnings. Complete counts refuse oversized
or malformed input; previews are bounded separately. Invalid due dates remain
visible, and future/invalid source retrieval timestamps also block screening.
Ten new backend tests include concurrent-write snapshot consistency, tenant/role
isolation, capacity and rolling-window boundaries. All 39 digest/workflow backend
tests and 72 frontend tests pass, with Ruff, ESLint and production build. Details:
`WORK_DIGEST.md`. No background email/notification delivery or agent promotion.

Retained-scorecard checkpoint: all 12 artifact verification tests pass, including
full 50-run recomputation, altered source context/labels/identities/metrics,
missing/extra/oversized artifacts, an offline subprocess and read-only API refusal
without partial metrics. All 69 frontend tests, Ruff, ESLint and production build
pass. The prior local full regression passed 358 tests, followed by the final
artifact-context test (359 tests then in source). Exact pushed `1a5b315` CI passed
359 backend and 69 frontend tests (run `39942651455`).
The live synthetic reference is visible in Evidence; its failed quality gate and
four uninspectable failed drafts stay explicit. Browser acceptance and Oracle
deployment remain pending.

Tuning checkpoint: local full regression passed 337 collected backend tests,
then 71 focused tuning/control-code/product tests passed after the replacement-
lineage correction. The final tuning suite contains 29 cases (341 backend tests
now in source). All 54 frontend tests and ESLint passed; the production build
also passed after the final CSS spacing adjustment. The retained tuning PDF section was
rendered with Poppler and visually inspected. No browser testing or Oracle
deployment occurred. Commit `b12391f` subsequently passed exact CI with 341 backend
and 54 frontend tests, Ruff, ESLint, build and audit (run `39934536951`).

Scorecard source checkpoint: ten focused evaluation tests passed, including a
complete 50-case real-runner replay with deterministic HTTP transport, strict
schema handling, hidden labels, SQLCipher isolation and stop-on-provider-failure.
All 48 existing toolkit/product regression tests also passed after the v2 change.
Exact commit `6c2a03b` passed CI with 311 backend and 51 frontend tests, Ruff,
ESLint, production build and npm audit (run `39855723808`). A separate local
backend regression subsequently passed all 310 collected tests. A paced live replay completed three cases
before a provider request rejection stopped the fourth; no partial card was
published. A subsequent isolated diagnostic of that case completed, so the
failure was not reproduced. Provider error accounting was tightened to
distinguish rejected generation from systemic configuration/access failures.
A subsequent complete 50-case live replay finished on 23 October 2026: 46 runs
completed; four failed without a retained draft; 109/109 retained citations
verified; known-source unsupported quotes and unknown IDs were zero; disposition
agreement was 43/50 (86%) including failures. The preparation gate failed due to
incomplete runs and differing provider fingerprints under an unreported revision.
Automatic preparation remains disabled. The dataset, report and all 50 runs are
retained and recomputed; the read-only Evidence reference is explicitly separate
from workspace results. See `AGENT_SCORECARDS.md` and the retained result README.

- [x] In-app deterministic digests and stale-evidence warnings; complete snapshot
  counts, explicit refresh and zero model calls. No off-app delivery is claimed.
- [ ] Opt-in cited brief preparation on new alerts. Quality gate remains failed;
  automatic brief preparation is disabled.
- [x] Implement deterministic tuning playbook: before/after historical simulation,
  proposed threshold draft and independent approval; no automatic activation.
  Human control UI, scoped MCP/SDK/CLI tools, pinned evidence and atomic receipt
  are implemented. Approval revalidates changed evidence and excludes an agent's
  issuing administrator. The objective measures supplied workload, not detection
  accuracy. Encrypted recovery and signed pack inclusion are tested. Deployment,
  performance and final browser acceptance remain pending; see `CONTROL_TUNING.md`.
- [x] Evaluation harness with at least 50 labeled historical/seeded cases, citation
  validity, fabricated quotation rate and disposition agreement per pinned model.
  Isolated source replay and deterministic scoring are implemented, with a
  reviewable 50-case synthetic corpus, hidden labels, per-model/scenario metrics,
  abstention/failure denominators and an explicit gate. The 50-case automated
  test uses a deterministic provider and cannot pass the live gate. The completed
  live synthetic scorecard and all attempts are now retained and independently
  recomputed, including failures and disagreements. Historical-source replay,
  real-label validation and a passing preparation gate remain pending. See
  `AGENT_SCORECARDS.md`.
- [ ] Weak citation results prevent autopilot promotion; briefs remain drafts.

## Phase 6: interface

UI checkpoint: all 347 backend tests passed locally, including the paged alert
feed and the corrected tuning assertion against a successful alert response.
All 64 frontend tests passed before the last advisory/read-only record check;
all 42 workflow tests then passed with that addition. Exact commit `8356b4e`
passed CI with 347 backend and 65 frontend tests, Ruff, ESLint, production build
and npm audit (runs `39939892756` / `39939886117`). An additional partial-feed-sync
workflow check subsequently passed with all 43 workflow tests (66 frontend tests
now in source). The current production build passes. The source navigation has
four primary areas; raw details live in Advanced. No browser acceptance or Oracle
deployment occurred.

- [x] Implement four primary areas: Inbox, Policies & Controls, Evidence, Settings & Agents.
- [x] Move the relationship graph into a case tab and data sources into Settings.
  The graph now lives in the case Relationships tab and the duplicate customer
  tab is removed. It loads lazily, retains its customer-wide 100-transaction/
  18-node scope and can retry without losing the investigation. The populated
  case workflow checks provenance, lazy fetching and graph failure/recovery.
  Settings now shows aggregate connections; per-source details are in Advanced.
  Browser/mobile acceptance remains pending.
- [x] Move raw runs, extra analytics and per-source details under `/advanced`.
- [x] Remove obsolete dashboard/overview pages and duplicated analytics/graph/key panels.
  Favorable AI assessments are labelled advisory; unauthorized human-review forms
  are hidden. Backend enums and authorization boundaries are unchanged.
- [x] Add populated component/workflow coverage for the four areas, advanced routes,
  legacy links, alert paging, failures, role restrictions and keyboard navigation.
- [ ] Final populated desktop/mobile browser acceptance after all implementation.
  See `UI_CONSOLIDATION.md` for canonical routes, scope and remaining acceptance.

## Phase 7: hardening and pilot

- [ ] Design-partner-scale load/concurrency tests; operational alerting.
  A read-only operator watchdog now checks public readiness, the receiver disk
  floor, latest backup attempt/snapshot age and exact encrypted archive size/hash.
  Any failure yields nonzero status and a bounded report without raw exception,
  URL or private-path output. The backup receiver records encrypted integrity
  metadata; optional hardened systemd timer/service templates are supplied.
  Local watchdog/offsite tests pass; actual installation, failure notification
  integration and deployed measurements remain pending. The retained local
  synthetic load run passes its chosen envelope; actual partner/Oracle capacity
  remains unproven. See `PILOT_LOAD.md` and
  `OPERATIONAL_WATCHDOG.md`.
- [ ] Independent security review and documented remediation.
- [ ] Synthetic/non-production pilot; signed agreement and review before real data.
- [ ] Reassess positioning if evidence pain or partner adoption gates fail.

Parked as specified: HA/multiple workers, SSO, Postgres migration, PEP/adverse-media
data, SAR filing, payment blocking and additional sanctions sources.

## Implemented MFA boundaries

Generated-artifact custody checkpoint: a full backend run passed 283 tests; all
18 focused generation/custody tests passed after adding tamper/path/policy checks
(288 backend tests now in source). All 47 frontend tests passed before the final
UI assertion; all six focused custody component tests then passed (48 in source).
Ruff, ESLint and build passed. Sponsor PDF custody sections were rendered with
Poppler and visually inspected. The artifact's own custody event follows its
signed snapshot; prior custody/policy/hold records are included in later packs.
Offline discovery/reconciliation, deletion execution and deployment remain pending.

Copy custody checkpoint: the full backend suite passed 266 tests, followed by
all 24 focused custody tests after final policy re-review/validation/bound checks
(270 backend tests now in source). All 47 frontend tests, Ruff, ESLint and build
pass. The encrypted recovery test retains custody records and pending holds.
Supplied content/evidence hashes and confirmed reports are operator attestations;
no automatic storage discovery or physical erasure is established.

Customer deletion inventory checkpoint: all 17 focused API/planner tests and
all 42 frontend tests pass, along with Ruff, ESLint and production build. Coverage
includes read-snapshot consistency during a concurrent update, SQLCipher storage,
policy/hold/content binding, residual references, retention timestamps and bounds.
CI passed all 246 backend and 42 frontend tests at `6555753`. The older local
245-test snapshot also finished successfully. No deletion executor or physical
copy-removal claim is made.

Retention governance checkpoint: the full backend suite passed 228 tests; all 14
focused retention tests then passed after adding encrypted recovery (229 backend
tests now in source). All 39 frontend tests, ESLint, production build and Ruff
passed. No deletion executor or browser acceptance is claimed.

Database encryption checkpoint: the full backend suite passed 202 tests, followed
by all 10 expanded encryption/migration tests (204 backend tests now in source).
The migration test retains both tenant databases, FTS retrieval and enabled MFA,
rejects an incorrect original MFA key, restarts the encrypted installation and
creates another verified encrypted backup. Ruff and dependency consistency pass.
Linux CI passed all 204 backend and 36 frontend tests at `20efa22`. Subsequent
encrypted off-machine integration adds ciphertext-only temporary verification,
mode/key/page/tenant rejection and a saved-archive recovery drill. Live deployment
and operator acceptance remain unverified.

Encrypted off-machine checkpoint: the full backend suite passed 214 tests, then
all 21 focused backup tests passed after adding CLI key-loss receipts (215 tests
now in source). Ruff passed. The Windows installer was parsed and exercised with
stubbed task commands: both invocations retain absolute recovery-key paths, and
a failed initial transfer prevents registration. No real schedule was installed.

Marble adapter checkpoint: 191 backend tests passed in the full suite, followed by
all 14 focused adapter tests after adding concurrent replay and separate-case checks
(193 tests now in source). All 36 frontend tests, ESLint, production build, Ruff and
dependency consistency passed. Imported source records and receipts were rendered
in the sponsor PDF and visually inspected. Disk space is available again; prior
disposable artifacts were consolidated at the user's request. Browser testing,
real Marble-account comparison and Oracle deployment remain pending.

The shared adapter service was then separated from provider field projection; a
test-only engine with different raw fields verifies that boundary. The focused
suite now contains 15 adapter tests (194 backend tests in source).

Controls-as-code checkpoint: 178 backend tests passed in the full suite; all 14
focused code-import tests then passed after adding a YAML-indentation preservation
case (179 tests now in source). All 34 frontend tests, ESLint, production build,
Ruff and dependency consistency passed. Tests include an actual isolated Git commit
round-trip, independent activation, replay after approval and atomic rollback. The
pack's new import-receipt section was rendered and visually inspected. No browser
testing or Oracle deployment occurred.

Traceability checkpoint: 164 backend tests passed in the full suite, then all six
traceability tests passed after adding explicit partial-analysis/row-bound coverage
and indexing the joins (165 backend tests now in source). All 32 frontend tests,
ESLint, production build and Ruff passed. The pack's new mapping/simulation
sections were rendered with Poppler and visually inspected. An earlier concurrent
frontend run timed out waiting for an async control; the subsequent complete
32-test run passed. Browser acceptance and Oracle deployment remain pending.

Sponsor evidence checkpoint: 159 backend tests, 30 frontend tests, Ruff, ESLint,
production build and dependency consistency passed. The archive verifier ran in a
separate subprocess; a 50-case synthetic pack generated within one minute. PDF
pages were rendered with Poppler and visually inspected. No browser testing or
production deployment occurred.

External checkpoint checkpoint: 145 backend tests passed, including signed bundle
tampering, database rewrite/truncation detection, missing-key recovery boundaries,
automatic worker capture and export failure handling. All 28 frontend tests,
ESLint, production build and Ruff passed. Disk space is available again; these
checks ran on C: in a new test directory. Browser acceptance and deployment are pending.

Latest governed toolkit checkpoint: 129 backend tests passed, including in-memory
MCP seeded investigation and actual stdio/HTTP subprocess tests; 26 frontend tests,
ESLint, the production build, Ruff and dependency checks passed. The final backend
run used a new D: test directory with pytest's C: cache disabled after C: filled.
Cleanup of disposable C: test directories was rejected by automatic approval review;
the existing folders were left intact. No browser testing or deployment occurred.

Governance foundation checks: 107 backend tests passed in the full suite, then
the added public-key provisioning test passed separately (108 tests in source).
Twenty-four frontend component/workflow tests, ESLint, production build and Ruff
passed. These are automated non-browser checks; no browser acceptance was run.

TOTP uses RFC 6238 SHA1, six digits, 30-second steps and a one-step clock window.
The last consumed counter and recovery-code deletion are transactional. Enabling,
disabling and replacing codes require password reauthentication and revoke sessions.
Existing-account invitation acceptance cannot bypass MFA. Password reset preserves MFA.
Restore removes pending enrollments and invalidates old recovery codes, preserving the
authenticator requirement and preventing previously consumed backup codes from returning.

Seeds use AES-256-GCM with user-bound associated data. Keys are separate from database
snapshots. This encrypts MFA seeds; it does **not** yet encrypt whole SQLite databases.
Production enrollment fails until the original private key is provisioned. Local
development can create a private installation key. Missing keys are never regenerated
to decrypt existing ciphertext. Recovery from loss of all factors needs a separately
reviewed operator procedure; password reset is not that procedure.
