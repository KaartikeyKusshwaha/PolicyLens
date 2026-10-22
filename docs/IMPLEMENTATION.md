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
- [ ] Tag a verified baseline and update stale documentation.
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
- [ ] Agent-scoped keys, immediate revocation, scopes, rate limits and run budgets.
- [ ] Agent identity, pinned model/version and pseudonymized model context.
- [ ] Checkpoints retained outside the database.
- [ ] Honest security one-pager covering deployed protections and limits.

## Phase 2: governed toolkit

- [ ] Registry classes: read, draft, request-approval. Tools:
  search_policy, get_control, simulate_control, list_alerts, get_case_context,
  draft_investigation_brief, verify_evidence, create_review_task, export_case_pack.
- [ ] MCP server over the existing runner; no approval/activation/closure/filing tool.
- [ ] Thin CLI and Python SDK; Claude Desktop and Cursor examples.
- [ ] Client-level seeded investigation, citations, audit and permission-denial tests.

## Phase 3: evidence and traceability

- [ ] Sponsor evidence pack: PDF, JSON, verification script; policy versions,
  controls/approvals, dispositions/notes, audit checkpoint, source freshness, agent logs.
- [ ] Policy obligation matrix: linked controls, latest simulation, alert volumes,
  evidence and explicit coverage gaps.
- [ ] Seeded pack generation within approximately one minute; chain re-verification.

## Phase 4: adapters and controls-as-code

- [ ] Inspect Marble's current official API/export formats before adapter implementation.
- [ ] Adapter interface, Marble alerts/cases import with provenance and deduplication.
- [ ] One transaction-source adapter selected with design partners (selection pending).
- [ ] YAML export/import into drafts, schema validation, maker-checker-only activation.
- [ ] Git-to-draft round-trip and imported inbox acceptance tests.

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
