# Governed toolkit implementation ledger

The full user-provided master plan is retained in `MASTER_PLAN.md`. This ledger
tracks implementation separately from deployment, browser acceptance, external
review and market validation. None of those gates can be inferred from a green CI run.

## Deletion review checkpoint

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
  Execution remains disabled. Deletion execution,
  audit-PII handling and complete backup/export reconciliation remain unfinished.
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

Tuning checkpoint: local full regression passed 337 collected backend tests,
then 71 focused tuning/control-code/product tests passed after the replacement-
lineage correction. The final tuning suite contains 29 cases (341 backend tests
now in source). All 54 frontend tests and ESLint passed; the production build
also passed after the final CSS spacing adjustment. The retained tuning PDF section was
rendered with Poppler and visually inspected. No browser testing or Oracle
deployment occurred. Exact pushed-commit CI remains to be checked.

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
No complete 50-case live scorecard is claimed.

- [ ] Opt-in cited brief preparation on new alerts, digests and stale-evidence alerts.
- [x] Implement deterministic tuning playbook: before/after historical simulation,
  proposed threshold draft and independent approval; no automatic activation.
  Human control UI, scoped MCP/SDK/CLI tools, pinned evidence and atomic receipt
  are implemented. Approval revalidates changed evidence and excludes an agent's
  issuing administrator. The objective measures supplied workload, not detection
  accuracy. Encrypted recovery and signed pack inclusion are tested. Deployment,
  performance and final browser acceptance remain pending; see `CONTROL_TUNING.md`.
- [ ] Evaluation harness with at least 50 labeled historical/seeded cases, citation
  validity, fabricated quotation rate and disposition agreement per pinned model.
  Isolated source replay and deterministic scoring are implemented, with a
  reviewable 50-case synthetic corpus, hidden labels, per-model/scenario metrics,
  abstention/failure denominators and an explicit gate. The 50-case automated
  test uses a deterministic provider and cannot pass the live gate. Two live
  cases completed after a strict-schema fix; the third was rate-limited and the
  batch stopped without publishing a partial card. A full paced live run,
  historical-source replay and real-label validation remain pending. See
  `AGENT_SCORECARDS.md`.
- [ ] Weak citation results prevent autopilot promotion; briefs remain drafts.

## Phase 6: interface

- [ ] Four areas: Inbox, Policies & Controls, Evidence, Settings & Agents.
- [ ] Relationship graph becomes a case tab; data sources move to Settings.
  The graph now lives in the case Relationships tab and the duplicate customer
  tab is removed. It loads lazily, retains its customer-wide 100-transaction/
  18-node scope and can retry without losing the investigation. The populated
  case workflow checks provenance, lazy fetching and graph failure/recovery.
  Data-source consolidation and final browser/mobile acceptance remain pending.
- [ ] Raw runs, extra analytics and per-source details move under `/advanced`.
- [ ] Remove duplicate panels and misleading decision/clearance wording.
- [ ] Automated populated-screen coverage; then mobile/browser acceptance.

## Phase 7: hardening and pilot

- [ ] Design-partner-scale load/concurrency tests; operational alerting.
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
