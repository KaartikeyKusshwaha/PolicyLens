# Governed toolkit implementation ledger

The full user-provided master plan is retained in `MASTER_PLAN.md`. This ledger
tracks implementation separately from deployment, browser acceptance, external
review and market validation. None of those gates can be inferred from a green CI run.

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
- [ ] Retention/deletion policy, preview, approval and execution with legal holds.
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
- [ ] Honest security one-pager covering deployed protections and limits.

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

- [ ] Opt-in cited brief preparation on new alerts, digests and stale-evidence alerts.
- [ ] Tuning agent: before/after historical simulation, proposed threshold draft,
  independent approval; no automatic activation.
- [ ] Evaluation harness with at least 50 labeled historical/seeded cases, citation
  validity, fabricated quotation rate and disposition agreement per pinned model.
- [ ] Weak citation results prevent autopilot promotion; briefs remain drafts.

## Phase 6: interface

- [ ] Four areas: Inbox, Policies & Controls, Evidence, Settings & Agents.
- [ ] Relationship graph becomes a case tab; data sources move to Settings.
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
