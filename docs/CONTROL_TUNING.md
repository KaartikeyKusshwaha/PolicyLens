# Control tuning

Deployed to Oracle. The synthetic browser pass verified comparison, draft creation
and refusal after its pinned parent was superseded; complete successful tuning
activation and live/partner workload acceptance remain separate checks. See
`BROWSER_ACCEPTANCE_20261023.md` for exact scope.
The deterministic playbook makes no model call. It compares supplied numeric
thresholds with historical transactions and creates a separate threshold-change
draft. It never activates a control or creates live alerts/cases.

## Selection and limitations

An author supplies an active amount, velocity or aggregate control, one to eight
distinct alternative thresholds, a target historical match count and a rationale.
The playbook uses the normal monitoring engine's observation for each transaction
once, including original currency, inclusive windows and same-timestamp peers.
It selects the smallest absolute difference from the target; ties use caller
candidate order. Velocity thresholds are integers. Policy, currency, window,
destinations, priority and description remain unchanged.

The target is an operational workload judgment. Fewer historical matches do not
prove better detection, fewer false positives, lower risk or legal compliance.
The playbook infers no ground-truth labels, risk estimates or regulatory
thresholds. Human review remains required even when the target is met exactly.

## Review workflow

Administrators/analysts use Threshold tuning in an active control's detail view.
The preview shows current/candidate counts, selected threshold, added/removed
transaction references and limitations. Editing inputs clears the preview. A
failed/stale submission also clears its old approval-ready comparison.

One SQLite read transaction binds the input request, parent control, complete
policy row, all transaction columns/payloads and related current customer context.
Indexed transaction fields must agree with their retained JSON evidence. Draft
submission recomputes the comparison in an immediate write transaction and
refuses a changed hash. New control, receipt and audit event are saved atomically.
The active parent stays active. Exact retries by the same identity return the
existing draft/receipt, including after activation; conflicting submissions fail.

A reviewer reads the retained comparison on the draft's detail page. The normal
approval endpoint rechecks the configuration, parent, policy and transaction/
customer evidence inside its activation transaction. Changed evidence requires
a fresh proposal. One concurrent approval can win. Activation supersedes the
parent through the existing control workflow.

A manual edit of a pending proposal creates a new human-authored draft and does
not inherit the old simulation receipt. The record/audit retain the edited draft
reference, while its replacement points to the active ancestor. This prevents
activation from superseding only a draft and leaving the original control active.
Cyclic/missing/overlong or already-superseded ancestry is refused.

For agent submissions, both the agent and its issuing administrator are retained
as makers. Neither can approve; a different authorized human reviewer must do so.
Agent bearers cannot use human approval routes, and no activation tool exists.
The UI also hides self/issuer approval. Audit failure rolls back the entire draft.

Receipts and pinned comparisons survive encrypted backup/restore and appear in
signed sponsor JSON/PDF packs. Pack size/print bounds still apply and fail
explicitly rather than silently sample. Signatures establish retained integrity
relative to trusted keys, not correctness of a supplied workload objective.

## API and agent tools

```text
POST /api/control-tuning/preview
POST /api/control-tuning/draft
GET  /api/control-tuning/{receipt_id}
```

The draft input is the preview request plus `preview_sha256`. Existing tenant,
session, role and CSRF checks apply. Reviewers/auditors can read receipts but
cannot create proposals. MCP, CLI and Python SDK discover two scoped tools:

| Tool | Class | Effect |
| --- | --- | --- |
| `simulate_control_tuning` | draft | Compare historical workload without mutation |
| `draft_control_tuning` | request-approval | Create the pinned threshold-change draft |

Existing keys gain no scopes automatically. Request rate limits and bounded
receipt storage apply. Zero model calls means no queued model-run budget is
consumed; audit events still retain the calling agent identity. This is not
represented as an LLM-generated recommendation.

```python
preview = client.call(
    "simulate_control_tuning",
    control_id="ACTIVE-CONTROL-ID",
    candidate_thresholds=["150", "250", "500"],
    target_match_count=10,
    rationale="Compare workload against the documented human review capacity.",
)
proposal = client.call(
    "draft_control_tuning",
    **preview["request"],
    preview_sha256=preview["preview_sha256"],
)
# A different human inspects and approves the resulting control draft.
```

`get_control` includes the tuning receipt. Tool output uses the existing optional
structured masking path; opaque evidence references and supplied free text may
remain. No free-text anonymization is claimed.

## Pilot bounds and verification

Requires 1–10,000 transactions, at most 16 MB of complete input context, up to eight
thresholds and at most 1,000 receipts. Rolling simulations additionally cap the
sum of squared per-customer transaction counts at 20 million, bounding worst-case
window replay. Unsupported controls, empty history, invalid thresholds, changed
or malformed evidence and over-limit input fail without partial proposals.

Tests cover production-engine comparison for rolling/tied/late/mixed-currency
data, stale preview/activation, tampered evidence/configuration, atomic rollback,
concurrent draft/approval, agent/issuer separation, tenant isolation, bounds,
encrypted recovery and signed evidence inclusion. UI tests cover pinned
submission, stale input/refusal and retained review evidence. Production load
and final populated browser/mobile acceptance remain pending.
