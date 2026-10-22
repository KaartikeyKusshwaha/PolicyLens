# Final deployment and browser acceptance

User instruction: finish implementation and automated checks before a single
final browser acceptance pass. Do not use the computer-use skill. This checklist
prepares that pass; no item below is established by writing this document.

## Entry evidence required before opening the browser

- Reconcile every master-plan implementation item against `IMPLEMENTATION.md`.
  Retention execution/copy reconciliation, partner transaction integration,
  scorecard/tuning/preparation, four-area UI and operational hardening currently
  remain incomplete. Record genuinely external gates separately; never substitute
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

Use the connected browser extension directly, without the computer-use skill.
Record the deployed SHA, URL, timestamp, synthetic workspace, viewport and
screenshots for each checkpoint. Exercise real populated screens and mutations,
not only page loads. Include a narrow mobile viewport and keyboard navigation.

| Area | Checkpoints |
| --- | --- |
| Account | Sign-in, MFA enrollment/confirmation, required second factor, recovery handling and revoked sessions. Never record secrets in screenshots or acceptance logs. |
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
