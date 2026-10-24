# PolicyLens project state — 24 October 2026

PolicyLens now provides a governance and evidence workspace around monitoring
engines and AI-assisted investigations. People review and approve; agents retrieve
evidence, prepare cited drafts and request review. The synthetic pilot works, but
the full master plan and real-customer release gates are not complete.

This report covers source, deployed checks and retained results as of this date,
including runtime PRs #13–#15. The latest reviewed runtime source is `9b652450`;
its main merge is `294ab232`. Documentation commits after that merge do not
change the deployed runtime identity.
The requirement ledger is [RELEASE_READINESS.md](RELEASE_READINESS.md), and the
original scope remains [MASTER_PLAN.md](MASTER_PLAN.md). A percentage would mix
implemented code with human, market and independent-review gates; it is not a
verified completion measure.

## What users can do

| Area | Behavior |
| --- | --- |
| Inbox | Inspect native/imported alerts, open customer cases, assign work, add notes/tasks, review cited preparation, escalate and request independent resolution. View relationships inside the case. |
| Policies & Controls | Upload operating policies, retain versions, retrieve cited excerpts, inspect obligation/control gaps, draft controls, simulate historical effects and obtain independent activation. |
| Evidence | Download signed sponsor packs containing PDF, JSON, policy/control/approval history, case evidence, freshness records, agent work and audit checkpoints. Inspect scorecards and their limits. |
| Settings & Agents | Manage team/account/password access, connections/sources, scoped agent keys, run configuration, retention policies, holds and custody records. Account 2FA was removed at the owner's request. |
| Advanced | Inspect detailed agent logs, additional analytics and per-source diagnostics under `/advanced`. These are outside the four primary areas. |

The starter monitoring engine supports amount, velocity, same-currency aggregate,
corridor and due-diligence controls. It validates amounts/timestamps, deduplicates
external transaction references, snapshots alert evidence and groups customer
cases. Historical simulation does not activate a rule or create live alerts.
Internal thresholds are supplied by users; they are not statutory limits.

## Eight requested feature groups

1. **Governed toolkit:** MCP stdio bridge, Python SDK and CLI expose scoped
   read/draft/request-approval tools. Expiry, revocation, request/run budgets,
   agent audit identity and optional masking apply. There are no agent tools to
   approve, activate, close, file or execute payments. An actual stdio MCP client
   investigated the deployed HTTPS fixture and retained a one-attempt Groq draft
   with six verified quotations, a review task, decision denials and revocation.
   Its narrative incorrectly described four transactions as five. Quotations
   verify source text, not the factual correctness of the entire draft.
   Claude/Cursor configuration examples are documented; host-specific UI checks
   would provide additional assurance.
2. **Sponsor evidence:** complete signed PDF/JSON packs and verification tooling
   are implemented. A browser-downloaded deployed pack independently verified.
   The Oracle 1,000-transaction run generated and verified a pack in 47.397 seconds.
   Signatures bind covered content relative to the trusted key; they do not prove
   its legal meaning or the truth of source records.
3. **Traceability:** suggested policy obligations, explicit human control mappings,
   current/version gaps, simulations, alert counts and evidence links are
   implemented. Suggestions require review and are not an exhaustive legal
   obligation inventory. Browser mapping/simulation/mobile unlink/relink passed.
   A policy-version update retained the old five suggestions and mapping while
   explicitly flagging their historical version and missing current analysis.
   Current-version analysis and broader linked-screening acceptance remain open.
4. **Scorecard:** 50 synthetic labeled cases were replayed through the real
   provider/runner. Forty-six completed and four produced invalid output;
   109/109 retained citations verified, and disposition agreement was 43/50 (86%).
   Ten scenario families with five variants each are correlated, not independent
   compliance investigations. Human-label validation and historical-source replay
   remain open; preparation quality gate failed.
5. **Tuning:** supplied threshold candidates are compared against historical
   workload and a supplied target. A pinned proposal remains a draft until a
   different human approves. Browser stale-parent refusal and independent
   activation passed. A new browser comparison tested three thresholds against
   six transactions, kept the one-to-two match comparison visible after approval
   and superseded the parent. Workload match counts do not measure detection
   accuracy; no live alerts are created by the comparison.
6. **Autopilot preparation:** deterministic digests and stale-source warnings work.
   Automatic model briefs remain disabled under the failed gate. One successful
   draft does not justify enabling them.
7. **Adapters and YAML:** Marble export-bundle import preserves provenance and
   uses explicit customer mappings; upstream closure does not close a local case.
   YAML export, pinned preview/import and independent activation passed through
   the browser, including a real local Git commit. Supplied Git metadata is an
   assertion, not remote-repository verification. Actual Marble-account comparison
   and a partner-named transaction source remain missing.
8. **Trust baseline:** email/password/session controls, SQLCipher, versioned
   retention policies/holds, scoped keys and outside-database checkpoints are
   implemented. Oracle encrypted migration and separate restore passed. Account
   2FA was removed by the owner's 24 October scope amendment. Complete
   historical copy discovery and physical-erasure evidence remain unresolved.

## Deployment and operations

| Component | Observed state |
| --- | --- |
| Main pilot | `https://policylens.129-225-126-21.sslip.io/`, Oracle, Caddy HTTPS and one Uvicorn worker. |
| Synthetic browser installation | Separate data/key/workspace at `https://acceptance.129-225-126-21.sslip.io/`. Fictional accounts and data; provider/worker disabled for this browser fixture. |
| VM | Oracle `VM.Standard.E2.1.Micro`, about 954 MiB OS-reported memory and two logical CPUs. This is the single-process pilot architecture. |
| Storage | Encrypted live identity/tenant files, protected installation key, external checkpoint/deletion-state roots. Original plaintext migration copies remain preserved. |
| Server backups | Enabled daily timer and actual successful logs inspected. Database and complete history exports use explicit protected server settings. |
| Off-machine receiver | Encrypted database, deletion-state and checkpoint-history archives on the Windows receiver; protected separate recovery/archive keys. Verified transfer and separate restore passed. |
| Receiver schedule | Daily 09:00 local while signed in. Task last ran 24 October at 14:08:31 local with exit 0; today's three receiver archives match their receipt hashes. Automatic-versus-manual trigger origin is unproved because scheduler operational logging was disabled. |
| Operational monitor | Every five minutes while signed in; readiness, archive freshness/integrity and disk floor checks. Healthy scheduled execution and isolated disk alarm passed. Local latest/failure reports survive recovery; no external notification delivery is configured. |
| Render | Signed-in fallback was prepared; no Render deployment replaced Oracle. |

The live deployment was built from the governance release with reviewed exporter,
mobile, draft-input-summary and password-only authentication fixes applied.
PR #14 upgraded deployed pypdf to 6.21.2 and pip to 26.2.2. PR #15 fixed the
frontend's policy-selection loading race; both HTTPS sites serve matching asset
hashes. A release-directory name alone does not identify all later applied files.
Private deployment receipts record this composition; CI alone does not prove it.

## Retained acceptance results

- [Oracle load and deployed MCP](../evaluation/results/20261024-oracle-acceptance/README.md):
  100 synthetic customers, 1,000 unique transactions plus duplicate replay, four
  clients, 2,000 ingest requests and zero HTTP failures. Ingest p95 was 398.770 ms;
  the slowest measured read p95 was 1,891.485 ms. All 13 correctness invariants and
  selected gate checks passed. Service peak memory was about 204.6 MiB. This is
  one bounded run, not sustained production capacity or a partner-agreed profile.
- [Live MCP and populated recovery](../evaluation/results/20261024-live-mcp-recovery/README.md):
  one live provider attempt, four verified quotations, review required, decisions
  denied, temporary key revoked. Separate encrypted restore preserved every row
  across 20 workspace tables, four cases and the cited draft; 77 audit entries
  verified against recovered checkpoint history. No provider was called in restore.
- [Deployed governance API](../evaluation/results/20261024-live-mcp-recovery/deployed-governance.json):
  maker self-approval denied, independent tuning activation and hold release
  accepted, other deletion blockers retained; 83 audit entries verified.
- [Browser acceptance](BROWSER_ACCEPTANCE_20261023.md): four populated areas,
  sign-in/out, simulation, distinct-reviewer activation, YAML/Git round trip,
  evidence download, case notes, policy approval, effective pending hold and
  mobile drawer exercised. A real mobile graph overflow was fixed and rechecked.
  Later browser checks covered real model-backed mappings, historical policy
  version gaps, current-policy control drafting, independent tuning activation
  and independent hold release. Password lifecycle, remaining deletion/custody,
  linked-screening and owner acceptance are incomplete.
- The operator's protected `browser-governance-20261024` evidence directory
  outside Git retains the latest deployment receipt, browser screenshots and
  read-only API confirmation: distinct tuning author/approver, superseded parent,
  released hold with different requester/reviewer and valid audit.
- The protected `dependency-security-20261024` evidence directory retains the
  deployed package inventory and before/after pip-audit reports. Three pypdf and
  six distinct pip advisory IDs were found; after remediation all 32 installed
  packages were checked with zero known advisories and none skipped. This does
  not assess OS/native dependencies or replace independent security review.

Full CI at runtime source `9b652450` passed **591 backend tests** and **75 frontend
tests**, plus Ruff, frontend lint/build, npm audit and the new Python dependency
audit. The three new policy-loading regressions fail against the previous source
and pass with the fix. Counts alone never establish release readiness.

## Code and data flow

React 19 renders the control room. FastAPI authenticates humans or scoped agent
keys, selects their workspace and enforces the workflow boundary. SQLite/SQLCipher
stores identity and separate tenant databases; FTS5 provides lexical policy
retrieval. No vector database is required. Deterministic monitoring creates alert
evidence, and the durable agent runner prepares drafts from bounded snapshots.
Groq is the configured model provider. Returned quotations are verified against
collected excerpts before a successful draft is retained.
New drafts also retain server-computed transaction counts and exact totals per
currency for their bounded model input; reviewers can compare those facts with
the prose. Older runs are explicitly identified as lacking that summary. These
checks do not establish narrative correctness or clear the failed quality gate.

Hash-linked audit and independently retained signed checkpoints bind covered
history. Evidence archives include verification material; verification requires
a trusted public fingerprint outside the archive. Backups exclude the installation
key. Restore needs that original key and a separately pinned current deletion
guard, revokes credentials and refuses overwriting an existing installation.

## What still prevents full completion

| Requirement | Required evidence/action |
| --- | --- |
| User account acceptance | Normal email/password browser sign-in/out passed. Password-change/reset handoff and remaining session checks need operator participation. 2FA is removed from scope. |
| Final populated browser pass | Complete current-policy analysis, broader linked-screening, custody/deletion and remaining account scenarios; retain actual outcomes. The live draft is visible with its factual failure preserved. |
| Production-owner acceptance | Authenticated acceptance in the owner's intended operational workspace, separately from fictional acceptance. |
| Provider identity/quality | Immutable provider revision remains unproved; fix and independently validate the failed preparation gate before considering automatic briefs. |
| Complete retention handling | Reconcile historical/offline/downstream copies, audit-PII policy and physical-copy evidence; conduct populated deployed deletion/recovery drills. Logical deletion is not a complete-erasure claim. |
| Operational release | Observe next unattended daily transfer, agree failure handling and verify an authorized external notification path/independent monitoring. |
| Partner integration | Obtain the partner-selected transaction system and validate actual Marble/source records. |
| Market gate | At least five interviews, 2–3 design partners and three independent confirmations of evidence-assembly pain. Public prospect research is not an interview or agreement; no outreach was sent. |
| Real customer data | Independent security review, documented remediation and signed data-handling agreement before use. Internal tests or another coding-agent review do not satisfy independent review. |

The repository remains MIT as requested. HA/multiple workers, SSO, Postgres,
PEP/adverse-media coverage, SAR filing and payment blocking remain parked.
