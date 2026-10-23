# Deployment and recovery

The supported deployment is one native Python process serving the React build and API on one origin, with persistent local SQLite storage. No containers or external database service are needed. Do not run multiple Uvicorn workers or horizontal replicas.

## Hosting choice, checked 19 October 2026

| Option | Fit for this application |
| --- | --- |
| Your own computer | Recommended card-free pilot. Run `python run.py`; data remains on your disk. Agents and scheduled screening run only while the process and computer remain awake. It is not public hosting. |
| Cloudflare Quick Tunnel + your computer | Recommended temporary card-free sharing option after local setup. No Cloudflare account/domain is required. Your computer still runs the application and stores SQLite; the URL changes on restart and has no uptime guarantee. This is a development/demo option. |
| Oracle Always Free VM | A potential full pilot host if phone/card verification and capacity availability are acceptable. Use only resources explicitly marked Always Free, not trial credits. Keep separate backups; free resources have no SLA and idle accounts/resources can be reclaimed. |
| AWS EC2 Free plan | A capable native VM alternative for an eligible new-account pilot, using its free credits. The Free plan ends after six months or when credits run out, whichever is first; it is not permanent free hosting. Do not convert to paid or activate paid-only services without reviewing costs. |
| Google Compute Engine Free Tier | One eligible `e2-micro` VM and 30 GB-months standard persistent disk in selected US regions. A billing account is required; network/public-IP charges and usage outside the allowance can still apply. |
| Railway free | Supports a small persistent volume and Python, with a $5 trial for up to 30 days, followed by $1 monthly free usage credit. That credit is not a guarantee of continuous monthly runtime for this app. |
| ClawCloud Run free | Candidate only, not a verified deployment: advertises recurring $5 credit for GitHub accounts older than 180 days and supports persistent volumes. Its documented application route uses container images, requiring a separate optional packaging decision under the project's no-Docker requirement. Free apps stop after 30 days without a console login. The site could not be reached from the local environment during this review; confirm current dashboard eligibility, credits and capacity before selecting it. |
| Sealos | Current pricing lists a seven-day, card-free trial, followed by paid resource packages. This is not an ongoing free alternative. |
| Render free | Unsuitable for SQLite persistence: local files are lost on restart/redeploy/spindown, free services cannot attach a persistent disk, and sleeping stops the scheduler. |
| PythonAnywhere free | Candidate for a limited experiment only: ASGI remains beta, outbound APIs are allowlisted, accounts have storage/CPU limits and web apps expire unless renewed. Verify every source endpoint and long-running worker behavior before choosing it. No deployment compatibility is claimed. |
| alwaysdata free | Advertises card-free signup, 1 GB storage and 256 MB RAM, with personal/non-profit use restrictions and no separate services. Not recommended for this commercial product's full feeds/background workload. |
| Netlify | React preview only. Static hosting does not run the Python process or preserve SQLite. A successful frontend preview is not a full application deployment. |
| Vercel | Can serve the React frontend, but function filesystems cannot preserve the application's local SQLite database. The free Hobby plan permits personal, non-commercial use only. This application would still require a separate backend/storage host or an architecture change. |

Official references: [Oracle resources and signup](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier.htm), [Oracle FAQ](https://www.oracle.com/cloud/free/faq/), [Render free limits](https://render.com/docs/free), [PythonAnywhere ASGI](https://help.pythonanywhere.com/pages/ASGICommandLine/), [free account features](https://help.pythonanywhere.com/pages/FreeAccountsFeatures/), [outbound access](https://help.pythonanywhere.com/pages/403ForbiddenError/), [alwaysdata limits](https://help.alwaysdata.com/en/docs/admin-billing/billing/public-cloud-prices/), [alwaysdata signup description](https://www.alwaysdata.com/en/).

A pilot was deployed to the owner's Oracle account on 19 October 2026; see the deployment record below. No payment method, paid account upgrade or purchased domain was created by this work. There is no verified card-free managed host here that provides all of this application's persistence, background execution and commercial-use requirements. A limited public demo must be described as such and use fictional records.

Additional official references: [AWS Free plan terms](https://aws.amazon.com/free/), [Google free allowances](https://docs.cloud.google.com/free/docs/free-cloud-features), [Google networking prices](https://cloud.google.com/vpc/network-pricing), and [Railway pricing](https://railway.com/pricing). Render's paid service plus persistent disk is another compatible option; its free service remains unsuitable for local SQLite.

Additional candidates researched at the user's request: [ClawCloud credit eligibility](https://docs.run.claw.cloud/clawcloud-run/faq), [persistent storage](https://docs.run.claw.cloud/clawcloud-run/guide/app-launchpad/persistent-storage), [image deployment](https://docs.run.claw.cloud/clawcloud-run/guide/app-launchpad), [free-plan inactivity policy](https://question.run.claw.cloud/questions/10010000000002545), and [Sealos current pricing](https://sealos.io/pricing/). These are provider claims and deployment constraints, not verified compatibility or a promise of permanent free operation. No container packaging or new Docker dependency was introduced.

Vercel references: [SQLite support](https://vercel.com/kb/guide/is-sqlite-supported-in-vercel) and [Hobby plan restrictions](https://vercel.com/docs/plans/hobby).

## Card-free temporary sharing

[Cloudflare Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/) can expose your local service through a temporary HTTPS URL without an account or domain. This is a sharing route, not a hosted server: the app, disk, internet connection and scheduler remain on your computer. Cloudflare describes it as testing/development, with no uptime guarantee, a changing hostname and a 200 in-flight request limit.

1. Finish the owner-account setup locally first and use fictional records for a demo. Install `cloudflared` from the official download instructions linked in Cloudflare's documentation.
2. With PolicyLens running, start `cloudflared tunnel --url http://127.0.0.1:8000` in a separate terminal. It prints a temporary `https://...trycloudflare.com` address. The default hostname protection will reject access until the next step.
3. Add that exact hostname (without scheme/path) to `ALLOWED_HOSTS` in the private `backend/.env`, retaining `127.0.0.1,localhost`. Set `DEPLOYMENT_MODE=public` and `COOKIE_SECURE=true`. Configure Uvicorn to trust forwarded headers only from the loopback tunnel proxy, restart PolicyLens, and open the HTTPS URL. Sign in with your local account. Do not use a wildcard hostname allowance.
4. Keep the app, tunnel and computer running while sharing. The app's authentication remains required. Stop `cloudflared` when finished; restarting it creates a different hostname that must be allowed explicitly. Restore your local-only settings when returning to local development.

No tunnel is started automatically by PolicyLens or by `run.py`. Review who should have access before sharing the URL; generated app invitations also require an authenticated owner to create them. The cloud VM template below is a separate option for a server you control.

## Native Linux VM template

The files in `deploy/` are templates, not an installed service. Use a Linux server with Python 3.11+, Node 22.12+, a persistent disk and outbound HTTPS. A practical starting point is at least 1 GB RAM; measure full-feed parsing/screening under your workload before inviting users.

1. Create a dedicated, unprivileged `policylens` service user. Check out the reviewed branch to `/opt/policylens` and create a Python venv there. Install `backend/requirements.txt`. Build React using `npm ci && npm run build` from `frontend/` as your deployment user; runtime does not need Node.
2. Create `/var/lib/policylens`, owned by the service user and mode 0700. This stores the workspace database, central identity database, later workspaces and backups.
3. Create `/etc/policylens.env`, readable only by root and the service group, containing:

   ```dotenv
   DATABASE_PATH=/var/lib/policylens/policylens-v2.db
   GROQ_API_KEY=your_own_key
   GROQ_MODEL=openai/gpt-oss-20b
   COOKIE_SECURE=true
   DEPLOYMENT_MODE=public
   ALLOWED_HOSTS=your.actual.domain,127.0.0.1,localhost
   SANCTIONS_MAX_AGE_HOURS=24
   SESSION_HOURS=12
   AGENT_DAILY_RUNS=30
   AGENT_MAX_CONTEXT_CHARS=18000
   ```

4. Install the `deploy/policylens.service` template as a systemd service. It binds only to loopback and runs exactly one worker. Enable/start it after checking all paths and permissions. `systemctl status policylens` and `journalctl -u policylens` show startup errors.
5. Install Caddy from its official package instructions. Replace the example hostname in `deploy/Caddyfile`, point DNS to the server, and allow inbound ports 80/443 through the OS and hosting firewall. Keep port 8000 private. Let Caddy terminate HTTPS and proxy to loopback. Set request limits and access-log retention to your requirements.
6. Open the HTTPS site, read `/var/lib/policylens/.bootstrap-token` through the server's private console, and create the owner account yourself. Do not send bootstrap/password/API values through chat or repository files. Invite team members from settings after setup.
7. Sync all enabled lists, upload your policies, verify independent approvals, ingest a fictional transaction, and run a cited agent draft. Confirm the authenticated `/api/health` reports `agent_worker: running`. Configure periodic screening only after testing a complete run.

The service and proxy templates were installed on the Oracle pilot described below. See [Caddy installation](https://caddyserver.com/docs/install) and [FastAPI proxy deployment](https://fastapi.tiangolo.com/advanced/behind-a-proxy/).

## Oracle pilot deployment record

On 19 October 2026 the owner authenticated a temporary official OCI CLI session. Read-only inventory confirmed Hyderabad (`ap-hyderabad-1`) is the home region, with no existing compute or block storage and 200 GB of unused free storage. The planned 1 OCPU / 6 GB Ampere A1 instance could not launch because Oracle reported out of host capacity. No ARM instance was created and no paid shape was substituted.

The deployed instance uses `VM.Standard.E2.1.Micro`, which the OCI API identifies as `ALWAYS_FREE`, Ubuntu 24.04 Minimal, 1 GB RAM, a 50 GB boot disk and a 4 GB swap file on that disk. This is a small pilot: AMD Micro has shared CPU capacity, and concurrent source parsing or screening can be slow. The application peaked around 293 MiB during the initial sequential official-feed download checks; this is an observation, not a workload guarantee. Oracle may reclaim idle free instances; maintain backups. Current [Always Free documentation](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm) remains the authority for allowances.

One dedicated VCN/subnet, internet gateway and route table were created. Its security list permits HTTPS/HTTP and SSH only from the operator's detected public IPv4 `/32`, plus ICMP fragmentation feedback. Port 8000 binds to loopback only. No NAT gateway, paid load balancer, paid database, account upgrade or container runtime was added. If the operator's internet address changes, review and update the SSH source restriction before reconnecting.

The React production build was built on the operator's computer and uploaded with the reviewed Python source. Caddy 2.11.7 was installed from its official signed package repository. An exact IP-based `sslip.io` hostname uses publicly trusted HTTPS with automatic renewal. This avoids buying a domain but depends on third-party shared DNS and the assigned public IP; replace it with an owned domain for a branded launch. Do not bypass a browser certificate warning.

The owner's complete identity/workspace snapshot was verified and restored with rebased Linux paths and revoked sessions. Existing owner passwords are preserved; cloud users sign in again. The Groq key was transferred privately over SSH into root/service-group-readable `/etc/policylens.env`, outside the source tree. SSH host identity was checked against console history retrieved through authenticated OCI before sending account files or secrets. Upload staging was removed. Test credentials belong exclusively to an isolated, unserved acceptance installation and cannot sign in to the public site.

Treat the cloud installation as the authoritative pilot after signing in there. The original local installation remains a separate copy; subsequent changes are not synchronized between them. Resource IDs, the SSH identity and backup decryption key are kept privately on the operator's computer, not in this repository. The OCI session is temporary; the SSH identity remains available for server administration.

## Back up and recover

Database snapshots require separately retained current deletion state. The
[complete deletion-history backup tool](DELETION_STATE_BACKUP.md) supports
stopped-source export, authenticated encrypted receiver retention and new-directory
reconstruction. It is not yet installed or scheduled on the pilot/receiver.
The [scheduling integration](SCHEDULED_DELETION_BACKUP.md) is now available in the
daily backup, fixed SSH exporter and optional receiver/task arguments. Combined
success requires both copies to verify. Operator rollout remains pending.

The read-only [operational watchdog](OPERATIONAL_WATCHDOG.md) checks readiness,
receiver disk space and fresh matching backup receipts/encrypted bytes. It emits
JSON and exits nonzero on failure. Optional service/timer templates are supplied;
installation, notification integration and actual receiver/Oracle checks remain
pending. New successful transfers record encrypted archive size/hash for the
watchdog; older receipts must be refreshed by a successful verified transfer.

The operator CLI now supports a complete, verified snapshot and restore drill. It shares an OS-level installation lock with the server and refuses to snapshot while that installation is running. It includes identity and all workspace databases, checks SHA-256 hashes and SQLite integrity, rebases workspace paths when restored, and revokes sessions in the restored copy. It never overwrites an existing destination.

Stop the Python server, then run these commands from the repository root (use `.venv/bin/python` on Linux/macOS):

```sh
.venv\Scripts\python manage.py backup --output /private/backups/policylens-snapshot-UNIQUE
.venv\Scripts\python manage.py verify /private/backups/policylens-snapshot-UNIQUE
.venv\Scripts\python manage.py deletion-guard --output /private/recovery/deletion-guard-UNIQUE.json
.venv\Scripts\python manage.py restore /private/backups/policylens-snapshot-UNIQUE --destination /private/restore-drills/policylens-UNIQUE --deletion-guard /private/recovery/deletion-guard-UNIQUE.json --deletion-guard-sha256 CURRENT_INDEPENDENTLY_RETAINED_SHA256
```

Restart the live server after taking the snapshot. A restore drill can run while the live server is back online because it creates a separate destination. The private environment/API-key file is intentionally excluded; preserve it separately. Backups contain confidential records and integration secrets: protect directory permissions and encrypt them before sending to an off-machine destination. Checksums detect corruption but do not authenticate a backup against a malicious administrator who can replace both the files and manifest.

Before using a restored installation, point `DATABASE_PATH` at its restored primary database and start only that copy. Existing login passwords remain valid; browser sessions must sign in again. Running jobs become interrupted. Neither the source backup nor live installation is changed by the restore command.

The UI backup is scoped to one workspace. It includes confidential customer/integration data and must be stored privately. It does not include central accounts or other workspaces.

Use the CLI for whole-installation recovery: it updates absolute workspace paths and invalidates restored sessions automatically. Preserve the old installation separately, restore service ownership/permissions, then sign in to the restored copy, check workspace membership/data and inspect interrupted jobs before explicitly resuming or starting a new run. Missing registered workspace files now prevent startup or return a storage error. Retain audit checkpoints outside the database if you need independent integrity evidence.

Test restoration with fictional data before depending on a backup. The automated suite covers both workspace backups and a complete multi-workspace restore, including SQLite integrity, customer records, session/reset-link revocation and checksum tampering. Full-host operational recovery and ongoing off-machine encrypted storage remain the operator's responsibility.

The Oracle pilot installs `deploy/backup.sh` and its systemd service/timer. At 02:30 UTC daily (with up to five minutes of jitter), it briefly stops the app, creates a verified snapshot in root-only `/var/backups/policylens`, restarts the app even if snapshotting fails, and removes only its own snapshot directories older than thirteen full days. This pauses availability and background work briefly. A manual service run and separate cloud restore drill passed. A cloud snapshot was downloaded over verified SSH, encrypted with Fernet and verified by decryption on the owner's computer. Archive and decryption key are stored separately. This is one off-machine copy, not an automatic remote-backup schedule; losing the key makes the encrypted copy unrecoverable.

## Private account recovery

Passwords are scrypt hashes and cannot be retrieved. An operator with server access can run `manage.py password-reset --email owner@example.com --origin https://your.actual.domain --output /private/reset-link-UNIQUE.txt` with the same protected environment used by the service. It creates a one-use 15-minute reset link and leaves the old password valid until the user completes the form.

Use a root/private shell and private output directory. Never print the environment, place a reset link in an issue/chat, or commit it. Give the file privately to the account owner. The link carries its token in the URL fragment, which is not sent in the initial page request. The user enters and confirms a new password in `/reset-password`; the application sends it only to its own HTTPS API, revokes all sessions for that user, consumes the token and clears the fragment. There is no public reset-token issuance endpoint or email-provider dependency. Tokens are stored hashed, bound to the named account, throttled when used, invalidated by reissuance and removed from restored backups. Operator access is equivalent to account-recovery authority and must remain private.

## Operational limits

For public deployment set `DEPLOYMENT_MODE=public` and `COOKIE_SECURE=true`, use explicit `ALLOWED_HOSTS`, and configure a trusted HTTPS reverse proxy. Public mode rejects plain HTTP except liveness/readiness probes and hides API documentation. The frontend hides its API-documentation link in that mode. CSP limits browser scripts/connections to this origin, allows only the named Google Fonts styles/font endpoints, blocks framing/plugins, and restrictive browser permission headers disable camera/microphone/location/payment/USB access.

Use `/api/ready` for the host's readiness check. It returns 503 when central storage cannot be queried or the agent worker has stopped, without exposing account or configuration details. `/api/health` is the minimal public liveness endpoint. One installation lock prevents a second worker or recovery tool from starting against the same data directory. Missing registered workspace databases produce an explicit storage error instead of a new empty database.

Free Groq quotas and public-source availability can interrupt workflows. They are surfaced as errors; there is no fabricated answer or alternate provider. Durable jobs retain completed steps, but a model attempt interrupted after dispatch cannot be repeated within the same run. New runs count against the daily budget.

AI completions are bounded to 4,096 output tokens per call. Policy agents return up to five prioritized obligation themes with exact evidence and explicit coverage limitations; they do not claim exhaustive extraction. Models select quotation reference IDs from a catalog of supplied source excerpts; Python retrieves their exact text, validates the chunk/reference pairing and independently verifies the quotation against the source. This replaces unreliable model transcription without repairing or accepting fabricated quotations. Provider failures remain explicit, with one attempt per agent run. Groq's free organization-wide token limits can require spacing runs; there is no automatic retry or paid-provider substitution. Provider failure logs contain schema/status/error-code metadata, never request bodies, policy text or credentials.

Scheduled screening checks at the configured interval while the server is running. Source downloads are not a legal/regulatory change-monitoring service. Names, aliases and supplied LEIs do not replace KYC, ownership analysis or jurisdiction-specific professional interpretation. Configure incident response, access reviews, retention, encryption, monitoring and independently tested backups before a production launch.
