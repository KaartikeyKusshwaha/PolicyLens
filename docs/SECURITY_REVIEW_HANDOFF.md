# Independent security review handoff

Prepared 24 October 2026. **Review not performed; no security certification or
real-data approval.** This packet helps an independent reviewer reproduce and
challenge the implementation. Coding-agent work and internal tests do not count
as the required independent review.

## Target and boundaries

Use merged baseline `77687b262eb3db3a90342c47af263d9f15640856` as the initial source
reference; record the exact commit, dependency lockfiles and deployment-file hashes
actually reviewed. Later documentation alone does not alter runtime behavior.
The deployed release is composed of the original governance build plus reviewed
exporter/mobile fixes; verify the composition rather than relying on its folder
name. See [deployment checkpoint](DEPLOYED_CHECKPOINT_20261023.md).

The system is a React/FastAPI application, one Uvicorn worker, identity database
and separate tenant SQLCipher files. Caddy terminates HTTPS. Durable jobs use Groq
for bounded model calls; official sanctions sources supply screening evidence.
The stdio MCP bridge calls the authenticated API. Human and scoped agent access
must remain separate. HA, SSO and multiple workers are outside this pilot scope.

Review source and isolated synthetic fixtures first. No authorization is granted
by this document to attack public services, retrieve real customer data, obtain
secrets, disable security, erase files, contact users or change live access.
The operator and reviewer must agree targets, test window, account roles,
permitted mutations, data handling, retention and reporting before active testing.
Do not supply master keys/provider tokens through this document or Git.

## Review questions and reproduction map

| Boundary | Source/evidence | Required independent challenge |
| --- | --- | --- |
| Human authentication | `backend/auth.py`, `backend/access_api.py`, `backend/security.py`; `test_password_auth.py` and existing account tests | Email/password sign-in, reauthentication, invitations, reset expiry/single use, session revocation and compatibility with obsolete factor records. Account 2FA was removed at the owner's request; see ACCOUNT_AUTHENTICATION.md. |
| Tenant/role selection | `backend/main.py`, `backend/auth.py`, product/retention/traceability APIs | Cross-tenant IDs, forged workspace selection, role downgrade/revocation, IDOR, CSRF/origin, cookie and host/proxy configuration. Include evidence export and nested records. |
| Human decisions | `backend/operations.py`, `backend/control_tuning.py`, `backend/retention.py`, `backend/deletion_requests.py` | Independent control activation/case review, agent-key issuer conflicts, stale parents/inventories, concurrent approval, hold release and changed membership/expiry. |
| Agent keys/MCP | `backend/agent_keys.py`, `backend/toolkit_api.py`, `backend/tool_contracts.py`, `toolkit/src/policylens_toolkit/` | Scope bypass, extra arguments, mutation class, budget/rate races, key expiry/revocation/issuer membership, agent cookie fallback and cross-agent run control. Prove approval/closure/filing remain unavailable. |
| Models and documents | `backend/agents.py`, `backend/providers.py`, `backend/privacy.py` | Prompt injection from untrusted evidence, one-attempt enforcement, persisted model settings, quote validation, output bounds, free-text PII leakage and outbound destinations. Citation grounding is not decision correctness. |
| Storage/key custody | `backend/database.py`, `backend/security.py`, `backend/recovery.py` | Missing/wrong key refusal, plaintext fallback, file/WAL/temp behavior, public key provisioning, POSIX modes/Windows ACLs, copies and recovery-key custody. Original plaintext migration copies remain. No implemented rotation or key-loss bypass. |
| Audit/evidence | `backend/checkpoints.py`, `backend/evidence.py`, `backend/verify_evidence_pack.py`, history backup exporters | Truncation/rewrites relative to trusted anchors, forged fingerprints, replay/rollback, partial exports, malicious archives/PDFs and complete history selection. State where host/signing-key compromise defeats guarantees. |
| Deletion/restore | `backend/deletion.py`, `backend/deletion_execution.py`, `backend/deletion_guard.py`, `backend/copy_inventory.py`, `deploy/deletion_state_backup.py` | Exact-row binding, dependencies/shared references, holds/copies, discovery-artifact binding, interruption/durability, suppression authentication and resurrection by old DB/history rollback. Distinguish logical removal from physical erasure. |
| Ingestion/sources | `backend/operations.py`, adapter modules, `backend/intelligence.py` | Webhook authentication/replay, malformed CSV/engine bundles, archive/path bounds, duplicates/late windows, stale or changed source snapshots and upstream statuses gaining local authority. |
| Operations/notifications | `deploy/`, systemd/Caddy configuration, scheduled tasks | Single-process ownership, service privileges, dependency provenance, backup selection/restore, sleep/sign-out gaps, disk failures, alert suppression and Telegram secret/error leakage. Verify actual intended recipient privately. |

Test filenames above are relative to `backend/tests/`. The map is a starting
scope, not an exhaustive attack inventory. Discover and document additional paths.

## Existing evidence and its limits

- [50-case live scorecard](../evaluation/results/20261023-gpt-oss-20b/README.md):
  failures retained; preparation gate failed. Automatic briefs remain disabled.
- [Oracle load/deployed MCP](../evaluation/results/20261024-oracle-acceptance/README.md):
  bounded hardware run and scoped API/MCP denials. No sustained-capacity claim.
- [Live MCP/populated recovery](../evaluation/results/20261024-live-mcp-recovery/README.md):
  separate local real-provider draft and logical-table-preserving encrypted restore.
- [Deployed policy analysis](../evaluation/results/20261024-deployed-policy-analysis/README.md):
  one real attempt, verified citations and partial browser mapping/simulation.
- [Oracle deletion/off-machine recovery](../evaluation/results/20261024-oracle-deletion-recovery/README.md):
  seven selected in-process synthetic tests and executed-history recovery. No
  complete copy discovery, physical erasure or full HTTPS deletion acceptance.
- [Browser acceptance](BROWSER_ACCEPTANCE_20261023.md) remains partial. Credentials,
  database files and private screenshots are not embedded in this handoff.

Recompute retained artifact hashes and inspect the assertions they cover. CI
success does not prove production configuration or independent review. Reproduce
security-relevant behavior on an agreed isolated target; record both refusals
and successful workflows. Preserve failures and avoid modifying checks to obtain
an expected result.

## Required review output and real-data gate

The reviewer should deliver the exact reviewed source/deployment identity,
permitted scope, dates, methods, findings with reproducible evidence, severity
and affected boundary, plus limitations and untested paths. Keep exploit material
and sensitive data private. Record each finding's owner, remediation commit,
independent retest and residual-risk disposition; an empty template is not proof
of acceptance. The operator must define and approve the release criteria with
the reviewer before calling the review complete.

Outstanding known questions include password/session browser acceptance, host configuration,
complete historical/customer copy reconciliation, audit-PII handling, preserved
plaintext originals, independent monitoring and notification delivery, immutable
provider revision, failed preparation quality and partner-specific source/load
requirements. No conclusion about their legal sufficiency is supplied here.

Real customer data remains gated on independent review, documented remediation
and a signed data-handling agreement. Market interviews/design-partner commitments
are a separate master-plan gate. Read [release requirements](RELEASE_READINESS.md)
for the full remaining scope; this packet does not close any of those gates.
