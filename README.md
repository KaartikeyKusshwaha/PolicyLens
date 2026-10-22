# PolicyLens Operations

A cross-border fintech compliance pilot built with **React 19, Python/FastAPI, and SQLite**. Connect customer activity to documented controls, investigate exceptions, and retain the evidence behind human decisions.

The application runs as one native Python process with persistent SQLite storage. It does not fabricate answers, switch AI providers after failures, or seed business records. SQLite FTS5/BM25 is the primary document retrieval engine.

## Run locally

Install Python 3.11+ and Node.js 22.12+, then run:

```sh
python run.py
```

The launcher installs dependencies when their manifests change, builds React, and serves the app and API at **http://127.0.0.1:8000**. Stop with Ctrl+C.

1. Open the local app. Read `backend/data/.bootstrap-token` locally and use it to create your owner account and first workspace. With a custom database path, the file is beside that database. The token is consumed after setup; never commit or share it.
2. Add `GROQ_API_KEY` to ignored `backend/.env` and restart. Obtain your own [free-tier key](https://console.groq.com/keys); no other integration requires an API key.
3. Sync the enabled feeds in **Data sources**. All three official feeds are enabled initially.
4. Add your actual operating policies and customer records.
5. Invite a second person from **Workspace settings**. An independent administrator or reviewer must approve a drafted control before it becomes active.
6. Ingest transactions manually, by CSV, or through a signed webhook. Investigate triggered alerts and use agents to prepare reviewable drafts.

Business data starts empty. Offline/provider failures remain visible and never produce substitute decisions. The app can manage documents and deterministic monitoring without an AI key. Agent analysis and policy Q&A require Groq.

## Product workflows

| Area | Working capabilities |
| --- | --- |
| Team access | Owner bootstrap; invite-only membership; administrator, analyst, reviewer and read-only auditor roles; TOTP MFA with encrypted seeds and single-use recovery codes; password changes; access revocation; workspace switching and separate tenant databases. |
| Customers | Individuals and companies, country, internal risk tier, recorded due diligence status, notes, public LEI lookup, sanctions screening, and an observed transaction relationship graph. |
| Monitoring | Validated money and UTC timestamps, idempotent external IDs, CSV validation/import results, signed webhook ingestion, explicit internal controls, immutable alert snapshots and customer case grouping. |
| Control workbench | Amount, transaction velocity, same-currency aggregate, corridor and due diligence conditions; draft versions; independent approval; historical simulation without live alerts. No regulatory thresholds are supplied or inferred. |
| Investigations | Assignment, status transitions, escalation, notes, tasks, linked alerts and evidence, independent resolution review, and downloadable JSON case packs. Agents cannot close cases. |
| Policy library | Text, text PDF and DOCX upload, lexical retrieval, archived versions, grounded Q&A and verified verbatim citations. Scanned PDFs need OCR before upload. |
| Policy change impact | Archived version diff, linked controls, explicitly unconfirmed customer candidates, an analyst draft, human approval/dismissal and applicability review tasks. |
| Agents | Investigation, screening, policy analyst, policy change and report roles; fixed tool sequence, durable jobs, recorded steps, pause/resume/cancel, budget limits, and deterministic evidence verification. |
| Governed toolkit | Scoped expiring agent keys, per-tool permissions, request/run budgets, audited MCP stdio tools, thin CLI and Python SDK. Agents cannot approve, activate controls, close cases or file. |
| Continuous screening | Opt-in scheduled refresh of selected sanctions feeds and customer name screening. Creates review cases for potential matches; uses no model calls. Requires the Python process to stay running. |
| Audit and operations | Real counts, corridor/disposition analytics, overdue cases, hash-linked audit events, downloadable checkpoints, workspace SQLite backup and integrity verification. |
| Sponsor evidence | Workspace-wide PDF and JSON, policy/control/approval records, case notes, source freshness, agent logs, signed audit snapshot and offline archive verifier. |

React supplies the interactive interface, with responsive layouts, light/dark themes, loading/error/empty states, accessible form labels and source provenance.

## Public integrations

| Provider | Purpose | Account / scope |
| --- | --- | --- |
| [Groq](https://console.groq.com/docs/structured-outputs) | Strict schema AI drafts and Q&A; default `openai/gpt-oss-20b` | Free-tier key required; [account/model limits](https://console.groq.com/docs/rate-limits) apply. No automatic paid upgrade or model/provider switching. |
| [OFAC](https://ofac.treasury.gov/sanctions-list-service) | Official full SDN XML names and aliases | Key-free. |
| [United Nations](https://main.un.org/securitycouncil/en/content/un-sc-consolidated-list) | Official consolidated XML names and aliases | Key-free. |
| [UK FCDO](https://www.gov.uk/government/publications/the-uk-sanctions-list) | Official UK Sanctions List XML names and aliases | Key-free. |
| [GLEIF](https://www.gleif.org/en/lei-data/gleif-api) | Reference lookup for a supplied LEI | Key-free; reference data, not identity verification or complete ownership coverage. |
| [Frankfurter](https://frankfurter.dev/) | Daily USD reference conversion for individual AI assessments | Key-free. USD uses identity rate 1; no unsupported currency substitution. Monitoring controls operate in their configured currency. |

Every enabled sanctions source must have a valid snapshot, fresh within 24 hours by default. Failed syncs preserve the previous snapshot and its original age. Download/publication times and SHA-256 checksums are recorded. Source selection is explicit in settings; disabled lists are outside screening coverage.

Matching uses normalized name/alias similarity >= 0.88. Potential matches require identity review. No match is not clearance. Beneficial ownership rules, PEP/adverse-media datasets, every sanctions list and every transliteration are outside this implementation. No hardcoded FATF lists or unimplemented regulatory scraping claims are included.

Non-USD assessments stop if reference rates are unavailable, invalid, older than seven days or future-dated. Invalid AI schemas, unverified quotations and inconsistent clearance recommendations fail visibly. A potential sanctions match cannot receive an acceptable assessment.

## Agent boundaries

The Python orchestrator controls available tools and ordering. Policy text and transaction descriptions cannot grant tool permissions. Each workflow records evidence collection, optional sanctions screening, model draft and evidence verification. Verification checks citations and constraints; it does not prove every narrative inference.

The default limit is 30 new agent runs per workspace per UTC day and one model attempt per run. Pausing takes effect at a step boundary; an already-sent API request may finish. Restarted running jobs become interrupted and require explicit resume. A consumed/failed model attempt requires a new run, retaining the failed history. Completed steps may be reused only within the same run; expired or changed sanctions evidence prevents resume.

Context is limited to 18,000 characters. Investigation samples use up to 50 recent transactions, reduced explicitly to 10 if needed. Policy analysis uses an explicit partial-document coverage summary; large cases fail instead of silently dropping evidence. Policy impact candidates are not confirmed affected customers. Agent drafts never activate controls, approve customers, execute payments, submit filings or resolve investigations.

## Configuration and persistence

See [governed toolkit setup](docs/GOVERNED_TOOLKIT.md) for the registry, agent keys,
CLI/Python SDK, MCP stdio transport and Claude Desktop/Cursor examples. Queued runs
use saved model configuration. Explicit provider revisions are enforced when
configured; the default `provider-unreported` does not establish immutable model weights.

Copy `backend/.env.example` if starting manually. Relevant settings:

```dotenv
GROQ_API_KEY=
GROQ_MODEL=openai/gpt-oss-20b
SANCTIONS_MAX_AGE_HOURS=24
COOKIE_SECURE=false
DEPLOYMENT_MODE=local
ALLOWED_HOSTS=127.0.0.1,localhost,testserver
SESSION_HOURS=12
AGENT_DAILY_RUNS=30
AGENT_MAX_CONTEXT_CHARS=18000
# DATABASE_PATH=/absolute/persistent/path/policylens-v2.db
```

The existing filename `backend/data/policylens-v2.db` is retained to preserve v2 data. The first created workspace adopts that database. Later workspaces have separate files under `data/workspaces/`; central identities, memberships and sessions live in `data/identity.db`. Original pre-v2 sample data is not imported. All data, local environment files and generated exports are ignored by Git.

Sessions use HttpOnly, SameSite=Strict cookies, hashed session IDs and per-session CSRF tokens. Passwords use scrypt; login attempts are throttled in SQLite. Production requires HTTPS, `COOKIE_SECURE=true`, an explicit hostname allowlist and a trusted reverse proxy. Invitation tokens expire after 48 hours and are single-use/email-bound; share the generated invitation link yourself. The app does not send email.

Account MFA is configured in Workspace settings -> Account. Public enrollment requires a separately provisioned `SECURITY_KEY_PATH`; seeds are encrypted with AES-256-GCM. Recovery codes are displayed once and stored hashed. Password resets preserve MFA, and existing-account invitations cannot bypass it. Keep the installation key separate from database snapshots. This protects MFA secrets, not whole database files. See [trust operations](docs/TRUST_OPERATIONS.md) for provisioning, recovery and the verified encrypted off-machine backup tooling.

Use **Audit & analytics -> Create backup** for an administrator-only workspace backup. A full disaster-recovery backup must also include `identity.db` and every workspace database. See [deployment and recovery](docs/DEPLOYMENT.md).

Configure `CHECKPOINT_DIRECTORY` outside the database directory to retain signed audit checkpoints automatically. Audit & analytics shows retention status and exports a signed audit bundle; `manage.py verify-checkpoint` verifies it offline against an independently trusted signing fingerprint. Retained checkpoints detect conflicting database rewrites. Same-host storage does not protect against host or signing-key compromise and is not off-machine retention. See [external checkpoint operations](docs/EXTERNAL_CHECKPOINTS.md).

The same area exports a [sponsor evidence pack](docs/SPONSOR_EVIDENCE.md) with a printable PDF, complete business JSON, signed file manifest and offline verifier. Generation requires configured external checkpoints and refuses oversized exports without silently dropping records. Exported copies contain private workspace data and need their own access controls.

The operator command `python manage.py backup --output <new-private-folder>` takes a verified full snapshot while the server is stopped. `manage.py verify` checks it, and `manage.py restore ... --destination <new-folder>` performs a separate restore with rebased workspace paths and revoked sessions. The OS installation lock rejects concurrent server/backup writers. Private environment/API keys are excluded from snapshots.

Public hosting must explicitly set `DEPLOYMENT_MODE=public` and `COOKIE_SECURE=true`. Public mode requires HTTPS, hides API docs, and applies restrictive browser headers; `/api/ready` exposes minimal readiness for storage and the background worker. See the [generated fictional acceptance pack](examples/fintech-pilot/README.md) for a complete test policy, customer/payment scenarios and independent-review workflow.

## Development and checks

```sh
python -m venv .venv
# Windows; use .venv/bin/python on Linux/macOS
.venv\Scripts\python -m pip install -r backend/requirements-dev.txt
.venv\Scripts\python -m uvicorn main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

In another terminal:

```sh
cd frontend
npm ci
npm run dev
```

Vite serves **http://127.0.0.1:3000** and proxies `/api` to Python. Production uses the React build served by FastAPI. Interactive API documentation: **http://127.0.0.1:8000/docs**.

```sh
.venv\Scripts\python -m pytest
.venv\Scripts\python -m ruff check backend run.py
.venv\Scripts\python -m ruff check manage.py
cd frontend
npm test
npm run lint
npm run build
npm audit
```

CI uses isolated SQLite databases and mocked provider responses; no key or network is required. Tests cover access boundaries, cross-tenant isolation, source and AI failures, rules/approvals, late arrivals, simulations, case review, webhooks/replay, policy changes, durable agents, backups and audit tampering, plus React onboarding/forms/errors/citations/navigation. Live integrations should also be checked with fictional data before deploying.

See the [dated validation record](docs/VALIDATION.md) for the generated live workflow, recovery drill and outstanding browser/deployment checks.

## Deployment scope

This is a working single-process product pilot, not a certification of regulatory compliance. Scheduled screening supports at most 2,000 customers per run. Historical control simulations support 10,000 transactions, and one late event can recheck at most 1,000 subsequent windows. CSV imports allow 500 rows / 1 MB; policy uploads allow 5 MB / 300,000 characters / 300 PDF pages. Lists and graphs state their sample bounds. These are operational limits, not claims of enterprise scale.

Run one Python worker on one machine with persistent disk. Horizontal replicas and multiple Uvicorn workers are unsupported because scheduling and local SQLite ownership assume one process. Netlify can preview the React build, but it cannot host this persistent Python/SQLite backend. Free hosts that erase local files are unsuitable.

SSO, verified KYC, external notification delivery, transaction blocking, regulatory filing, automated retention/deletion policies, whole-database encryption at rest and high availability are not implemented. Relevant selected evidence is sent to Groq; evaluate its data terms before using confidential records. AI risk scores are estimates, not calibrated probabilities or legal/payment approval. Use synthetic data for a public demonstration until your operational and data-handling requirements are satisfied.

The [governed toolkit master plan](docs/MASTER_PLAN.md) and [implementation ledger](docs/IMPLEMENTATION.md) track the next stages and their independent deployment, acceptance and external-validation gates. New source should not be assumed deployed to the Oracle pilot.
