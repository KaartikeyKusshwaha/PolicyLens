PolicyLens: market fit, agentic toolkit direction, and plan

Scope amendment, 24 October 2026: the owner requested removal of PolicyLens 2FA
and retention of normal email/password sign-in. This supersedes the original
MFA requirements below. See [current authentication](ACCOUNT_AUTHENTICATION.md).
The original plan is otherwise retained for scope/history.
Market reality first
Closest competitor is Marble. It is an open-core engine covering transaction monitoring, sanctions screening, case management and API ingestion, and it can be self-hosted. It claims 100+ banks, fintechs and crypto exchanges across 25+ countries. Its license is source-available (Elastic License 2.0), not OSI open source.
openapps.pro
 +2
AI investigation agents already ship. Unit21 says its agents run the full investigation workflow and are in production at 100+ customers. It also sells no-code build-your-own agents. Hawk’s agent gathers information, summarizes cases and supports SAR preparation.
Unit21 Relaunches as the Leader in AI Risk Infrastructure
 +2
Pricing is mixed. Flagright markets usage-based pricing, while ComplyAdvantage lists pricing on request.
flagright
capterra
Sponsor banks create real pull. The sponsor bank stays responsible for AML and must make sure fintech partners run strong programs, including transaction monitoring and customer due diligence. Banks reviewing partners ask whether you can produce case notes, alert dispositions, audit trails and evidence-ready reports quickly, and one vendor cites 48 hours. Oversight is assessed on evidence, not intent.
Sponsor Banks Are Responsible for Fintech Compliance
 +2
MCP has a governance gap. Didit’s MCP server exposes screening and case-lifecycle tools but says it targets triage and operations, not compliance governance. Hosted OFAC and FinCEN MCP servers are proprietary and send tool output to whichever LLM host you use.
didit
glama

These are mostly vendor pages and blogs. Check the OCC consent order and FinCEN proposal they mention against primary sources before building copy around them. This is analysis, not legal advice.

Conclusion: don’t compete as another monitoring engine or another investigation agent. The open spot, as a hypothesis to validate, is a governance and evidence layer for AI-assisted AML that works with any engine or agent.

Positioning

PolicyLens is the control plane for AI-assisted compliance: policies, controls, agent work and evidence in one verifiable trail. Humans use the web app, and any agent uses it through MCP.

Its existing strengths already point there: policy → control → alert → evidence links, independent approval, verified citations, hash-linked audit, and agents that cannot decide.

Toolkit shape (replaces “a website”)
Web app is the control room: inbox, approvals, review, evidence.
MCP server + CLI + SDK is where agents and developers work.
Controls-as-code (YAML in git, activated only through in-app approval) suits developer-led fintechs.
Features to add (ranked)

1. Governed agent toolkit (MCP)

Tools: search_policy, get_control, simulate_control, list_alerts, get_case_context, draft_investigation_brief, verify_evidence, create_review_task, export_case_pack.
Every tool is classed read, draft or request-approval. No tool can approve, activate, close or file.
Scoped API key per agent, run budgets, agent identity on every audit event, model and version pinned per run.
Optional pseudonymization so customer identifiers sent to a model are masked.

2. Sponsor-bank evidence pack

One click produces policy versions, control register with approval history, alert dispositions, case notes, audit checkpoint, sanctions-list freshness proof and agent run logs.
Formats: PDF, JSON and a verification script.
Built from the existing case packs and audit checkpoints.

3. Policy-to-control traceability matrix

Each extracted policy obligation shows its linked controls, last simulation, alert volume and evidence, and flags obligations with no control.
This is the signature view, and it builds on the Policy analyst and policy-change features.

4. Agent scorecard (“show me the work”)

Replay agents on labeled historical cases and measure citation validity, fabricated-quote rate and agreement with human dispositions.
Per-model scorecard supports model-risk questions and builds trust.

5. Control tuning agent

It runs historical simulations, then drafts a threshold change with before/after results. Maker-checker approval is still required.
Builds on the existing simulation feature.

6. Autopilot prep

New alerts get a pre-built, cited brief waiting before the analyst opens the case.
Digests and stale-evidence alerts, for example when sanctions data is out of date.
Agents prepare. Humans decide.

7. Adapters

Import alerts and cases from existing engines, with Marble first (check its export and API format first), plus one transaction source your design partners name.
Position the built-in monitoring as a starter engine for teams that have nothing yet.

8. Trust baseline (required to sell at all)

Account MFA, encryption at rest, retention and deletion policy, checkpoint retention outside the database.
Keep as-is
Item	Note
Independent approval for controls, case review separation	Core of the governance story
Hash-linked audit and checkpoints	Store checkpoints outside the DB
Evidence verifier and quote verification	Basis for the scorecard
Agent job runner (budgets, pause, cancel, one model attempt, bounded context)	Becomes the MCP execution layer
Roles, tenant databases, CSRF and session security	Keep
Sanctions pipeline with freshness gating	Keep. “No match is not clearance” wording stays
Policy versioning, SQLite FTS5 retrieval	Fine for the pilot scale
Webhook, CSV ingestion, historical simulation	Keep
Backup tooling, CI (78 backend, 21 frontend tests)	Extend
Convert
Current	Becomes
Orchestrator tools and permissions	MCP tool registry with read/draft/request-approval classes
Five agents	Callable playbooks through the UI and MCP
JSON case packs	Sponsor-bank evidence pack
Policy-change impact	Part of the traceability matrix and autopilot
Control workbench and simulation	Controls-as-code and the tuning agent
Webhook and CSV ingestion	Adapter framework
12 website sections	4 areas: Inbox (alerts, cases, approvals), Policies & Controls (with traceability), Evidence (packs, audit), Settings & Agents (connectors, keys, runs)
Relationship graph	A tab inside the case view
Data sources page	Part of Settings
Hide under /advanced

Raw agent operations log, extra analytics beyond overdue cases, per-source sanctions detail.

Remove
Stale Milvus, Docker and OpenAI references in README, docs and tests. The overhaul already dropped the dependencies.
Duplicate panels after each conversion.
Any UI copy that reads as clearance, approval or legal advice.
Park

HA and multiple workers, SSO (do MFA first), Postgres migration (until a partner needs it), PEP and adverse-media data (licensing weight), SAR filing automation, payment blocking, more sanctions sources.

Finish vs. drop from your remaining list
Item	Decision
SSH access, log and backup verification	Finish now
Automatic off-machine backups	Finish
Fresh authenticated end-to-end test on production	Finish
Account MFA, encryption at rest, retention policy	Finish (Phase 1)
Load and concurrency testing	Limit to design-partner scale
Populated mobile and browser acceptance	Limit to the 4 consolidated areas
Independent security review	Finish before real customer data
SSO, HA, broader sanctions coverage	Drop for now
Implementation plan from current state

Baseline: hosted pilot, SQLite single-process on a 1 GB VM, SSH unreachable, MFA absent, 21 frontend tests. Durations are rough, for one developer with Codex.

Phase 0: Stabilize and validate (1 week)

Restore SSH, confirm the daily backup ran, set up automatic off-machine backups.
Fresh authenticated end-to-end run on production. Tag a baseline and fix stale docs.
Talk to 5 or more small-fintech compliance leads and recruit 2–3 design partners. Ask: “When your sponsor bank asks for evidence, what do you send, and how long does it take?”
Exit: ops visibility restored, and at least 3 teams call evidence assembly a real pain.

Phase 1: Trust baseline (2 weeks)

TOTP MFA, encryption at rest, retention and deletion policy, API keys with scopes and rate limits.
Agent identity and pinned model version in audit events. Pseudonymization option for model calls. Checkpoints stored outside the DB.
Exit: an honest security one-pager that lists the remaining limits.

Phase 2: Governed toolkit v1 (2–3 weeks)

MCP server over the existing orchestrator tools, with the three tool classes and scoped keys. Thin CLI and Python SDK.
Docs with Claude Desktop and Cursor configuration examples.
Exit: an MCP client investigates a seeded case, creates a cited draft, and is refused when it tries to approve or close. Permission-denial tests pass and all calls are audited.

Phase 3: Evidence and traceability (2 weeks)

Sponsor-bank evidence pack, traceability matrix, coverage-gap flags.
Exit: a pack for a seeded customer generates in about a minute, and the verification script re-checks the chain.

Phase 4: Adapters and controls-as-code (2–3 weeks)

Adapter interface, Marble import, and one transaction source from your partners.
YAML control export and import, with activation only through approval.
Exit: a control round-trips from git to draft to approved, and imported alerts appear in the inbox.

Phase 5: Autopilot and scorecard (2–3 weeks)

Pre-built briefs on new alerts, the tuning agent, and the evaluation harness.
Exit: a scorecard on at least 50 labeled cases (partner data or seeded) with citation-validity and disposition-agreement numbers you can show.

Phase 6: UI consolidation (2 weeks)

Reduce to the 4 areas, move the rest under /advanced, and add frontend tests for the populated screens.

Phase 7: Hardening and pilot (3–4 weeks)

Load test to partner scale, independent security review, operational alerting.
Pilot first on synthetic or non-production data. Real customer data only after the review and a signed agreement.
Decisions you need to make
License: the repo is MIT, so anyone may host it as a competing service. Decide whether to stay fully MIT with paid hosting and support, or move future versions to a source-available license. You can’t revoke what is already released under MIT.
Business model: open core plus hosted evidence and governance, rather than per-transaction pricing against Marble’s free self-hosted option.
Gates (stop and rethink if missed)
Partners don’t describe evidence assembly as a pain: switch to an open-source developer toolkit with no sales motion, or stop.
The scorecard shows weak citation validity: ship briefs as drafts only and don’t build autopilot.
No partner will run it on real data after Phase 7: positioning or trust is wrong.

Sources:

Marble on openapps.pro
Marble site
Unit21 relaunch
Unit21 BYOA
Top agentic AML solutions 2026
Flagright pricing note
ComplyAdvantage on Capterra
Jumio: sponsor banks and fintech compliance
Youverify: OCC order and fintech AML
Sphinx: bank-fintech oversight
Didit: AML screening MCP
OFAC MCP on Glama
