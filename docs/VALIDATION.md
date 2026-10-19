# Validation record: 19 October 2026

This records local and Oracle pilot checks performed on the overhaul branch. It is not a production certification or load/uptime guarantee.

## Automated checks

- 78 backend tests: authentication, isolation, policies, external-service failures, monitoring, independent approvals, cases, agent execution/recovery, audit integrity, backup restoration and private password reset. Reset checks cover token hashing, account binding, expiry, supersession, single use, session revocation, cross-origin rejection and throttling.
- 21 React tests, ESLint, production build and Ruff, including password-reset confirmation and removal of the URL fragment after success.
- The new generated acceptance test exercises three fictional customers, six payments, four independently approved controls, six alerts, three cases, one independently reviewed resolution and policy-change applicability tasks.
- Hardening tests cover public HTTPS/secure cookies, hidden public API docs, response headers, streamed request limits, worker readiness, missing workspace storage, concurrent installation locks and full multi-workspace recovery.

CI uses mock external responses and temporary databases; it needs no API key. On this Windows machine, the final backend run used a fresh `--basetemp` beneath ignored `.pytest-tmp/` because the default system pytest temporary directory was inaccessible.

## Live checks with fictional records

A separate local installation exercised the committed [fictional pack](../examples/fintech-pilot/README.md) through the API. It left the owner's actual workspace business records untouched.

- Ingested six payments, checked replay idempotency and historical simulation, and obtained three cases from the expected control matches.
- Verified that authors cannot approve their own controls and that the assigned analyst cannot resolve their own investigation. A separate reviewer completed the resolution.
- Completed a live Groq investigation draft with verified citations. A separately queued policy-analysis job was consumed by the actual background worker, completed evidence collection/drafting/verification, used one model attempt and retained the human-approval requirement.
- An initial live policy-analysis request failed with a provider HTTP 400. Its failed run remains recorded. Increasing the bounded completion allowance to 4,096 tokens and requesting concise prioritized themes resolved the observed request failure; no automatic retry or substitute result was added.
- Downloaded the official OFAC feed again (19,457 records). Fresh original UN (1,010) and UK (6,408) snapshots from an earlier live download were reused with their original timestamps and SHA-256 values. These counts describe the checked snapshots, not permanent source sizes.
- Verified a complete snapshot and restoration of the generated installation.

## Owner installation recovery drill

Stopped the local server, created and verified a two-database snapshot in a private directory outside the repository, restored it to a separate directory, and verified one account, one workspace and zero restored sessions. Existing password hashes were preserved and the live installation was restarted without replacing its data. Windows directory ACLs restrict the backup parent to the current user and SYSTEM.

This local recovery copy excludes private environment/API-key files. The later cloud deployment added a daily snapshot timer, verified cloud restore and one encrypted off-machine copy, as described below.

## Browser checks

Browser access was briefly available. The isolated local fictional installation was checked visually at desktop size: sign-in, dashboard, customer search, customer detail and a resolved case with independent review. The public-site browser check was then blocked because the browser tool reported local browser use disabled, including after the owner enabled Chrome settings. Mobile layouts, every screen/theme and the public owner sign-in still require visual confirmation. React tests and API/static-serving checks do not substitute for those checks.

Windows desktop control subsequently opened the public HTTPS site in Chrome and visually verified the deployed sign-in page at 1073 x 827. The owner must complete the private password reset and sign in before the authenticated public screens can be reviewed. Browser-extension access remains separate from the working desktop-control route.

## Oracle deployment and live validation

- The owner's authenticated OCI session confirmed Hyderabad as home region with no existing compute/storage. ARM launch was blocked by capacity; the free AMD Micro shape was identified by the API as `ALWAYS_FREE` and provisioned with a 50 GB disk. See [deployment record](DEPLOYMENT.md).
- Installed the Python service, React build and Caddy on one HTTPS origin. Readiness returned 200, unauthenticated customer access returned 401, setup was closed, API schema was hidden, HTTP redirected to HTTPS and security headers were present.
- Restored the actual owner account/workspace with existing password hashes and revoked sessions. No fictional customer, policy, transaction or test user was added to the public workspace.
- Downloaded and validated all three official sources directly from the cloud server: OFAC 19,457, UN 1,010 and UK 6,408 records. The authenticated app reported Groq configured and its background worker running.
- A separate unserved cloud installation exercised six fictional transactions, four approved controls, three cases, a real Groq investigation, verified citations and one independent reviewer resolution. Earlier invalid model quotations were rejected. Prompt-only changes and full-quotation schema enums did not reliably resolve transcription. Quotation reference selection with server retrieval passed the live investigation; no verifier relaxation, fabricated answer or hidden retry was added.
- The next policy-agent run encountered Groq's free rate limit and remained failed. A separately started run later completed through the actual worker, used one model attempt, recorded evidence verification and retained human approval. Free-tier limits are a material operational constraint.
- Manually ran the daily snapshot service, verified the snapshot, restored it to a separate cloud directory with revoked sessions, and verified an encrypted off-machine copy by decryption. The timer is enabled with retention of at least fourteen days. Off-machine copy delivery is not yet scheduled.

Load testing, continuous alert delivery, incident response, an owned domain and production data-handling reviews remain necessary before a broader production launch. The 1 GB shared-CPU free server and shared DNS are pilot infrastructure. No paid account upgrade or purchased domain was enabled.
