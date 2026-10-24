# Final deployment and browser acceptance

User instruction: finish implementation and automated checks before a single
final browser acceptance pass. Do not use the computer-use skill. This checklist
prepares that pass; no item below is established by writing this document.

## Entry evidence required before opening the browser

- Reconcile every master-plan implementation item against `RELEASE_READINESS.md`
  and `IMPLEMENTATION.md`. Offline logical deletion, scorecard, tuning, four-area
  UI and operational tools now have source/test evidence. Complete copy
  reconciliation, partner transaction integration and deployed operations remain
  incomplete; automatic briefs remain disabled by the failed quality gate.
  Record genuinely external gates separately; never substitute
  public prospect research for partner interviews or a signed agreement.
- Record exact Git SHA, clean worktree, remote SHA, PR merge state, full backend
  and frontend tests, lint/build/audit results and seeded scorecard artifact.
  The scorecard must contain at least 50 labeled cases and the required metrics.
- Repair SSH and inspect real service/worker logs, backup timer results and storage
  persistence. Provision original installation/recovery keys and external anchors.
  Deploy the exact reviewed commit. Prove migration and a separately restored
  off-machine backup with the deployed configuration. Verify failure visibility.
- Check HTTPS, cookie/header settings, readiness and unauthenticated denials with
  commands/APIs. Compare served frontend asset hashes with the reviewed build.
- Create a separate synthetic acceptance workspace with two human roles, agent
  credentials, policies, approved/draft controls, linked obligations, customers,
  transactions, imported engine records, open/resolved cases and fresh/stale
  source evidence. Keep the owner's operational workspace unchanged. Retain the
  fixture IDs, expected outcomes and source SHA in the acceptance record.
- Prepare MCP/CLI live-host checks through supported configuration and APIs.
  Real provider failures must remain visible; do not retry invisibly or relax
  citation verification to obtain a passing result.

## One final browser pass

For local synthetic preparation (not production acceptance), run:

```powershell
.venv\Scripts\python.exe evaluation/browser_fixture.py prepare --directory .pytest-tmp/browser-final
.venv\Scripts\python.exe evaluation/browser_fixture.py serve --directory .pytest-tmp/browser-final --port 8765
```

Preparation creates only a **new** isolated SQLCipher installation. `fixture.json`
records input digests, object IDs and verified expected counts: six transactions,
six native alerts plus one fictional imported alert, three open cases and one
independently resolved case, four independently approved controls and one pending
draft. Aggregate backtesting records one hit; the policy appears as lacking a
current analysis, without inserting a simulated successful model response.
The fictional upstream case is closed while its local case remains open.
Three randomly generated human accounts are stored only in
`private/accounts.json`; do not publish that directory or capture passwords.
Existing directories are refused rather than reused or overwritten. The server
binds only to `127.0.0.1`, disables the worker and external provider calls, and
loads no repository `.env`. No successful model draft, fresh external feed or
browser result is fabricated. Imported evidence is explicitly fictional and is
processed through preview/import; case resolution uses a separate reviewer and
the real workflow. Model-backed mappings and live-source scenarios still need
explicit setup during acceptance. Run the reviewed
frontend build first; record the exact Git SHA and screenshots when testing.

Use the connected browser extension directly, without the computer-use skill.
Record the deployed SHA, URL, timestamp, synthetic workspace, viewport and
screenshots for each checkpoint. Exercise real populated screens and mutations,
not only page loads. Include a narrow mobile viewport and keyboard navigation.

| Area | Checkpoints |
| --- | --- |
| Account | Normal email/password sign-in, sign-out, password changes, single-use operator password reset and revoked sessions. Account 2FA was removed at the owner's request. Never record passwords or reset tokens in screenshots or logs. |
| Inbox | Imported/native alerts, customer links, case tabs including graph, cited draft, notes/tasks, evidence age, reviewer resolution and denial for the assigned investigator. Distinguish preparation from final decisions. |
| Policies & Controls | Policy versions, traceability mappings/gaps, linked simulations/evidence, YAML preview/import and stale-parent denial. An author cannot activate their control; a different reviewer can approve. Tuning shows before/after results and remains a draft until approval. |
| Evidence | Populated PDF/JSON pack export, recorded freshness and audit anchor. Independently run the trusted verifier against the downloaded artifact and trusted fingerprint. Show scorecard metrics and explicit coverage/accuracy limits. |
| Settings & Agents | Connectors/sources, key scopes/revocation/budgets, saved run configuration, optional masking, retention policy versions/holds and complete implemented deletion workflow. Pending-release holds and stale previews must prevent deletion. Preparation/digests are opt-in and honor the scorecard gate. |
| Advanced | Raw operations, extra analytics and per-source details are reachable under `/advanced`; the primary navigation remains the four specified areas. |
| Responsive/accessibility | Every area remains usable with populated data at a narrow viewport: no obscured actions, unreadable tables, lost dialogs or inaccessible navigation. Keyboard focus, validation and errors remain visible. |

## Completion evidence

The final acceptance record must separate passed, failed and externally blocked
items and link exact artifacts. A failed checkpoint needs a fix and focused
re-verification; a one-pass intention cannot override an observed defect. Do not
report deployment verified from CI alone. Do not mark the whole master plan
complete while market validation, independent review, real-data agreement or
another original gate is missing. Begin with synthetic/non-production pilot data.
