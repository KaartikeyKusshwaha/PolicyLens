# Release requirements still requiring evidence

This is a release audit against `MASTER_PLAN.md`, not a completion certificate.
Source implementation, automated synthetic checks and current deployed behavior
are different evidence classes. PR #2 merged as `210ffd2d` and the governance
release is deployed to Oracle with SQLCipher. A deployed SSH-export environment
hotfix is being retained in a follow-up branch. See the dated evidence and limits
in `DEPLOYED_CHECKPOINT_20261023.md`; final browser acceptance remains pending.

| Master-plan requirement | Current evidence | Remaining requirement |
| --- | --- | --- |
| Scoped MCP, CLI, SDK; agents cannot decide | Governed toolkit, actual stdio/HTTP tests, permissions/role/tenant tests | Configured-host and deployed acceptance |
| One click sponsor PDF/JSON/verifier | Signed complete packs; retained 1,000-transaction local run; full PDF sampled visually | Deployed time/memory and independent verifier acceptance |
| Traceability matrix and gaps | Explicit mappings, cited suggestions, version gaps, simulations and alert evidence in source/UI tests | Populated browser and deployed acceptance |
| At least 50 labeled scorecard cases | Retained/recomputed live synthetic 50-case result, including failures | Human-label validation and historical-source acceptance; current quality gate failed |
| Tuning with independent activation | Deterministic historical preview, pinned inputs, scoped draft tools, revalidated human approval | Deployed workload/acceptance |
| Autopilot prep | Automatic briefs disabled; deterministic digest/freshness warnings implemented | Failed preparation gate must be resolved before enabling; do not bypass master-plan stop gate |
| Marble plus partner-selected transaction source | Marble export adapter and source interface, native CSV/webhook ingestion | Actual Marble comparison and partner-named transaction source; no partner selection exists |
| MFA | TOTP encrypted seeds/replay protection/recovery tests | Operator key procedure, deployed acceptance and independent review |
| Encryption | SQLCipher migration, snapshots, compaction, guarded restore and key-failure tests; actual pilot migration/key recovery/off-machine restore passed | Authenticated encrypted deployment acceptance and independent review |
| Retention/deletion policy and holds | Reviewed policies/holds, exact approved offline logical execution, external suppression, custody and compaction | Complete historical/offline discovery, audit-PII handling policy, physical-copy evidence and deployed drills; no complete-erasure claim |
| Outside-DB checkpoints | Signed capture, anti-truncation, complete signed-history encrypted receiver/recovery; actual configured first transfer and recovery passed | Populated deployed audit verification, next scheduled transfer and operator acceptance |
| Off-machine backups | Actual SSH/log verification, daily server backup, combined encrypted transfer, separate restore drill and Windows task installed | Observe next daily receiver trigger; populated recovery/ongoing custody and notification handling |
| Operational alerting | Readiness for registered storage/worker/checkpoints; backup/disk watchdog and service templates | Install monitor and prove authorized notification path; no messages sent |
| Four-area web control room | Four canonical areas, advanced routing, populated component tests and keyboard checks | One final populated desktop/mobile browser pass after implementation |
| Load/concurrency at partner scale | Retained single-worker local synthetic 100-customer/1,000-transaction/four-client results and failures | Partner-agreed profile and measurement on actual 1 GB pilot hardware; provider/agent/full-feed load unproven |
| Independent security review | Internal tests, source controls and honest security notes | Independent reviewer and documented remediation before real customer data |
| Interviews/design partners | Public prospect research only; no outreach sent | Five interviews, 2–3 partners, three independent pain confirmations; no invented evidence |
| Synthetic pilot and real-data gate | Isolated synthetic functional/load/recovery tests | Deployed synthetic pilot; signed agreement and independent review before real data |
| License | User retained current license | No license change requested |
| Parked scope | HA/multiworker, SSO, Postgres, PEP/adverse media, SAR filing/payment blocking remain parked | Do not add these to satisfy pilot requirements |

Latest infrastructure evidence: Oracle CLI/verified SSH access restored, live
service and backup logs inspected, separate SQLCipher migration/restore passed,
and combined off-machine database/history verification plus a separate Windows
restore drill passed. HTTPS served assets match the reviewed build. The daily
Windows pull task is installed; its next daily trigger remains unobserved.
See `DEPLOYED_CHECKPOINT_20261023.md` for scope and remaining gates.

Explicit-root local copy discovery now supports private inventory evidence;
complete cross-system/customer ownership reconciliation remains incomplete. Checkpoint
backup scheduling source is implemented; actual transfer and installation remain
unverified. The partner-selected adapter has an unresolved
external specification. Automatic briefs remain gated. Deployed/operator, market
and independent-review evidence cannot be manufactured by adding more unit tests.
Keep the full master-plan objective active while those requirements remain open.
