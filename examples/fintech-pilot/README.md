# Fictional fintech acceptance pack

Every policy, customer and payment in this folder is generated software test data. None is regulatory guidance or a real business record. The policy's amounts and windows are deliberately invented internal test settings.

- `policy.txt`: uploadable policy document with identity, purpose, monitoring and independent-review requirements.
- `customers.json`: three fictional companies with verified, pending and expired due diligence inputs.
- `transactions.json`: six payment scenarios using customer references and relative times. Before using the API, map `customer_reference` to the created customer's `id`, remove `minutes_ago`, and set `occurred_at` to the current UTC time minus that many minutes. These are scenario inputs, not the direct CSV-upload format.

Use four draft controls linked to this test policy: USD amount >= 5,000; velocity >= 3 within 1 hour; USD aggregate >= 8,000 within 24 hours; and due diligence not verified. An independent reviewer must approve the drafts.

Expected results: six stored transactions, six control alerts grouped into three customer investigations, no duplicate ingestion on replay, and one aggregate backtest hit without new live alerts. EUR must not be summed into USD aggregates. The sample includes no designated sanctions identities; sanctions-match and stale-source failure cases are covered separately by provider fixtures.

The acceptance test then assigns an investigator, records a task, rejects that investigator's own final review, accepts a separate reviewer's disposition, runs a cited agent draft, creates a policy change and checks human-approved applicability tasks. CI mocks external HTTP responses; separate live checks verify the actual public integrations and Groq output.

Run from the repository root:

```sh
.venv\Scripts\python -m pytest backend/tests/test_acceptance.py
```

This uses isolated temporary databases and never adds test customers, reviewers or policies to the owner's business workspace.
