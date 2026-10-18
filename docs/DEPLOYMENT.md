# Deployment and recovery

The supported deployment is one native Python process serving the React build and API on one origin, with persistent local SQLite storage. No containers or external database service are needed. Do not run multiple Uvicorn workers or horizontal replicas.

## Hosting choice, checked 19 October 2026

| Option | Fit for this application |
| --- | --- |
| Your own computer | Recommended card-free pilot. Run `python run.py`; data remains on your disk. Agents and scheduled screening run only while the process and computer remain awake. It is not public hosting. |
| Cloudflare Quick Tunnel + your computer | Recommended temporary card-free sharing option after local setup. No Cloudflare account/domain is required. Your computer still runs the application and stores SQLite; the URL changes on restart and has no uptime guarantee. This is a development/demo option. |
| Oracle Always Free VM | A potential full pilot host if phone/card verification and capacity availability are acceptable. Use only resources explicitly marked Always Free, not trial credits. Keep separate backups; free resources have no SLA and idle accounts/resources can be reclaimed. |
| Render free | Unsuitable for SQLite persistence: local files are lost on restart/redeploy/spindown, free services cannot attach a persistent disk, and sleeping stops the scheduler. |
| PythonAnywhere free | Candidate for a limited experiment only: ASGI remains beta, outbound APIs are allowlisted, accounts have storage/CPU limits and web apps expire unless renewed. Verify every source endpoint and long-running worker behavior before choosing it. No deployment compatibility is claimed. |
| alwaysdata free | Advertises card-free signup, 1 GB storage and 256 MB RAM, with personal/non-profit use restrictions and no separate services. Not recommended for this commercial product's full feeds/background workload. |
| Netlify | React preview only. Static hosting does not run the Python process or preserve SQLite. A successful frontend preview is not a full application deployment. |

Official references: [Oracle resources and signup](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier.htm), [Oracle FAQ](https://www.oracle.com/cloud/free/faq/), [Render free limits](https://render.com/docs/free), [PythonAnywhere ASGI](https://help.pythonanywhere.com/pages/ASGICommandLine/), [free account features](https://help.pythonanywhere.com/pages/FreeAccountsFeatures/), [outbound access](https://help.pythonanywhere.com/pages/403ForbiddenError/), [alwaysdata limits](https://help.alwaysdata.com/en/docs/admin-billing/billing/public-cloud-prices/), [alwaysdata signup description](https://www.alwaysdata.com/en/).

No cloud account, payment method, public deployment or domain is created by this change. There is no verified card-free managed host here that provides all of this application's persistence, background execution and commercial-use requirements. A limited public demo must be described as such and use fictional records.

## Card-free temporary sharing

[Cloudflare Quick Tunnels](https://developers.cloudflare.com/tunnel/get-started/quick-tunnels/) can expose your local service through a temporary HTTPS URL without an account or domain. This is a sharing route, not a hosted server: the app, disk, internet connection and scheduler remain on your computer. Cloudflare describes it as testing/development, with no uptime guarantee, a changing hostname and a 200 in-flight request limit.

1. Finish the owner-account setup locally first and use fictional records for a demo. Install `cloudflared` from the official download instructions linked in Cloudflare's documentation.
2. With PolicyLens running, start `cloudflared tunnel --url http://127.0.0.1:8000` in a separate terminal. It prints a temporary `https://...trycloudflare.com` address. The default hostname protection will reject access until the next step.
3. Add that exact hostname (without scheme/path) to `ALLOWED_HOSTS` in the private `backend/.env`, retaining `127.0.0.1,localhost`. Set `COOKIE_SECURE=true`, restart PolicyLens, and open the HTTPS URL. Sign in with your local account. Do not use a wildcard hostname allowance.
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

This template has been reviewed locally; it has not been provisioned or tested on a cloud VM in this task. See [Caddy installation](https://caddyserver.com/docs/install) and [FastAPI proxy deployment](https://fastapi.tiangolo.com/advanced/behind-a-proxy/).

## Back up and recover

The UI backup is scoped to one workspace. It includes confidential customer/integration data and must be stored privately. It does not include central accounts or other workspaces.

For a consistent whole-installation snapshot, stop the Python process, copy the complete configured data directory (including `identity.db`, workspace databases and any WAL/SHM files), copy the private environment file separately, then restart. Use a private encrypted off-machine destination and verify the copy; the repository is not a backup destination. Retain audit checkpoints outside the database if you need independent integrity evidence.

To recover on the same filesystem paths: stop the server, preserve the current data as a separate recovery copy, restore the full data directory and private environment, restore service ownership/permissions, run `PRAGMA integrity_check` against each restored database, then start one process. Sign in, check workspace membership/data and inspect interrupted jobs before explicitly resuming or starting a new run.

`identity.db` stores absolute workspace file paths. If moving to a different filesystem location, first preserve an untouched backup, then update `organizations.db_path` in the restored identity database to the new locations while the app is stopped. Do not use an identity database with missing workspace files: SQLite could create a new empty file at an outdated path.

Test restoration with fictional data before depending on a backup. The automated suite downloads a workspace backup, restores it, and verifies SQLite integrity and customer records; full-host operational recovery remains the operator's responsibility.

## Operational limits

Free Groq quotas and public-source availability can interrupt workflows. They are surfaced as errors; there is no fabricated answer or alternate provider. Durable jobs retain completed steps, but a model attempt interrupted after dispatch cannot be repeated within the same run. New runs count against the daily budget.

Scheduled screening checks at the configured interval while the server is running. Source downloads are not a legal/regulatory change-monitoring service. Names, aliases and supplied LEIs do not replace KYC, ownership analysis or jurisdiction-specific professional interpretation. Configure incident response, access reviews, retention, encryption, monitoring and independently tested backups before a production launch.
