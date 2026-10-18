# Validation record: 19 October 2026

This records the local pilot checks performed on the overhaul branch. It is not a production certification or evidence that a cloud deployment has been tested.

## Automated checks

- 71 backend tests: authentication, isolation, policies, external-service failures, monitoring, independent approvals, cases, agent execution/recovery, audit integrity and backup restoration.
- 20 React tests, ESLint, production build and Ruff.
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

This is a local recovery copy. Automated scheduling/retention, encryption and an off-machine backup destination have not been configured. Private environment/API-key files are excluded and must be preserved separately.

## Outstanding checks and deployment

Visual browser review is pending: the browser tool reports that local browser use is disabled in Work settings. React tests and API/static-serving checks do not substitute for that review.

No cloud account, public backend, domain or paid service was provisioned. The native Linux service and proxy files are templates, not a verified cloud deployment. A selected host needs persistent storage, one Python process, outbound HTTPS and a trusted TLS proxy; see [deployment instructions](DEPLOYMENT.md). Load testing, operational monitoring, incident response and production data-handling reviews remain necessary before a production launch.
