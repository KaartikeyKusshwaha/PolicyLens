"""Reviewable synthetic labels; no legal thresholds or real customers. Ten scenarios, five variations each."""

POLICY = (
    "Synthetic training policy for transaction investigation; this is not regulatory guidance. "
    "Investigate transaction transfers using the supplied customer and case evidence. "
    "A documented identity mismatch or admitted falsified invoice is a supported policy breach. "
    "A documented duplicate alert, verified namesake, or validated invoice explaining the alert is a false positive. "
    "Missing identity records, absent invoices, uncertain ownership, or conflicting unverified documents require more evidence. "
    "Do not infer a breach solely from payment amount, country, or transaction volume. "
    "Potential sanctions name matches require human investigation and are never clearance. "
    "Only an independent human reviewer can resolve a case."
)

SCENARIOS = [
    (
        "identity_mismatch",
        "confirmed",
        "Verified identity records show the account holder and payment sender are different people; the customer acknowledges using another person's identity.",
        "The supplied admission and verified identity mismatch support the explicit synthetic policy breach.",
    ),
    (
        "falsified_invoice",
        "confirmed",
        "The customer admits the supplied consulting invoice was fabricated. The original issuer confirms it never issued that invoice.",
        "The admitted fabricated invoice supports a breach of the explicit synthetic training policy.",
    ),
    (
        "identity_and_invoice",
        "confirmed",
        "Verified records show an identity mismatch and the customer admits the payment invoice was falsified. Both findings are documented in the reviewed case evidence.",
        "Two documented violations support confirmed under this synthetic policy, without deciding legal liability.",
    ),
    (
        "duplicate_alert",
        "false_positive",
        "The analyst verified this alert duplicates an already reviewed payment. Both alerts reference the same bank settlement and no additional payment occurred.",
        "Verified duplicate settlement evidence explains the alert under the synthetic policy.",
    ),
    (
        "validated_invoice",
        "false_positive",
        "The reviewed issuer records validate the invoice and delivery. Verified sender identity matches the account holder. The supplied invoice fully explains the alerted transfer.",
        "Validated invoice and identity evidence explain the alert without inventing a clearance conclusion.",
    ),
    (
        "verified_namesake",
        "false_positive",
        "The alerted name belongs to a different person. Verified date of birth and identity documents establish the customer is a namesake; the payment invoice and delivery are validated.",
        "Verified disambiguation and payment evidence explain this synthetic alert; no universal sanctions clearance follows.",
    ),
    (
        "missing_identity",
        "insufficient_evidence",
        "The customer identity documents are absent. The payment description alone does not establish sender identity. No verification or admission is available.",
        "Missing identity evidence prevents either a supported breach or an explained alert disposition.",
    ),
    (
        "missing_invoice",
        "insufficient_evidence",
        "The alerted payment has no supplied invoice or delivery records. The customer says it was for services but has not provided supporting evidence.",
        "An unsupported explanation leaves the transfer unresolved under the synthetic policy.",
    ),
    (
        "uncertain_ownership",
        "insufficient_evidence",
        "The counterparty company ownership is uncertain and the requested ownership evidence is absent. Payment amount and country alone do not establish a breach.",
        "Ownership evidence is missing and the policy forbids inferring a breach from amount or country alone.",
    ),
    (
        "conflicting_documents",
        "insufficient_evidence",
        "Two unverified documents give conflicting sender identities. Neither document has been authenticated and there is no customer admission or independent verification.",
        "Conflicting unauthenticated records require investigation rather than a confident breach or false-positive claim.",
    ),
]


def dataset():
    cases = []
    for category, disposition, description, rationale in SCENARIOS:
        for variation in range(1, 6):
            reference = f"{category}-{variation}"
            cases.append(
                {
                    "id": reference,
                    "category": category,
                    "customer": {
                        "external_id": f"synthetic-customer-{len(cases) + 1:03}",
                        "name": f"Synthetic Customer {len(cases) + 1:03}",
                        "country": ["IN", "GB", "US", "DE", "SG"][variation - 1],
                        "kyc_status": "pending",
                    },
                    "title": f"Synthetic transaction investigation {len(cases) + 1:03}",
                    "description": description,
                    "transactions": [
                        {
                            "external_id": f"synthetic-payment-{len(cases) + 1:03}",
                            "amount": str(100 * variation + 15),
                            "currency": "USD",
                            "counterparty": f"Synthetic Trading Company {variation}",
                            "counterparty_country": "GB",
                            "description": "Synthetic consulting payment for evaluation only.",
                            "occurred_at": "2026-01-01T00:00:00Z",
                        }
                    ],
                    "expected_disposition": disposition,
                    "label_reference": "synthetic-scenario-v1:" + category,
                    "label_rationale": rationale,
                }
            )
    return {
        "schema_version": "policylens.agent-evaluation.v1",
        "title": "Fifty synthetic investigation cases, ten scenario families",
        "origin": "synthetic",
        "label_author": "PolicyLens synthetic scenario authors",
        "limitations": [
            "Fifty labeled cases comprise ten scenario families with five amount/country/customer variations each. They are correlated examples, not fifty independent real-world investigations.",
            "Labels are explicit scenario-author judgments against a synthetic policy. No compliance lead or independent analyst validation is claimed.",
            "The local screening snapshot is empty synthetic data. This corpus does not measure real sanctions matching accuracy or freshness.",
            "Case descriptions summarize supplied evidence. The corpus does not test document forensics, full transaction histories, or adversarial narrative reliability.",
        ],
        "policy": {
            "title": "Synthetic transaction investigation policy",
            "version": "evaluation-1",
            "topic": "aml",
            "content": POLICY,
        },
        "cases": cases,
    }
