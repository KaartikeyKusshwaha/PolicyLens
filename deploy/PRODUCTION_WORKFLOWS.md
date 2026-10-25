# Production policy workflows

Normal registration creates a named, isolated workspace. A workspace administrator can invite an email address with a role. Acceptance requires that exact email and the existing account password, or a password for a new account. Invitations expire after 48 hours, work once, and grant no membership before acceptance. Workspace settings show pending, expired, and accepted invitations.

## Email delivery

Configure the following in the server's protected environment file. Never commit credentials:

```
PUBLIC_URL=https://your-policylens-host
SMTP_HOST=your-mail-server
SMTP_PORT=587
SMTP_SECURITY=starttls
SMTP_FROM=PolicyLens <invitations@your-verified-domain>
SMTP_USERNAME=your-mail-username
SMTP_PASSWORD=your-private-mail-password
```

Use `SMTP_SECURITY=ssl` with port 465 when required by the provider. TLS certificate verification is always enabled. The sender must be authorized by the mail service. Restart the application after configuration. Send a real invitation to a consenting teammate and verify inbox delivery and acceptance; SMTP acceptance alone does not establish inbox delivery. Until configured, the UI explicitly reports that email was not sent and provides a private invitation link.

## Automation

Set `AUTOMATIC_POLICY_ANALYSIS=true` with the existing `GROQ_API_KEY` and a running application worker. Uploading or updating a policy queues version-pinned cited preparation and reviews recorded transactions against approved checks for that exact version. The three-dot policy menu exposes preparation, full transaction review, update, and reversible removal. Archived policies remain accessible in the archive view and can be restored by an administrator.

Transactions, customer updates, and check approvals/disabling coalesce durable refresh requests; the worker refreshes policy results automatically. New transaction ingestion already evaluates active checks and groups triggered alerts into cases. Policy updates disable checks approved for the old version. Restoring a policy does not reactivate disabled checks. Historical policy versions and case evidence remain available.

Results distinguish flagged activity, no configured check hit, and activity without approved check coverage. No-hit results do not establish compliance with the entire document. AI preparation proposes a limited set of cited requirements; it does not create or approve executable checks automatically. Requirements needing interpretation still require a person. Full transaction review is bounded at 10,000 transactions per workspace on this deployment and fails explicitly above that limit. Provider failures and daily run limits remain visible, with manual retry from policy actions.

## Production data

The main deployment never seeds examples. Local automated test fixtures remain separate from user workspaces. Withdraw public synthetic acceptance hosts and retain their recovery material privately. Never identify real records as fictional based solely on workspace names or delete real user workspaces during cleanup.
