# Live synthetic reference evaluation, 23 October 2026

This is a completed **live-provider** replay of all 50 synthetic cases, not a
production or customer-data evaluation. It ran from 09:51:09 to 10:41:52 UTC
through the existing investigation runner using `openai/gpt-oss-20b`, prompt
`policylens-governance-v2`, an explicit 50-run budget and a 60-second interval.
Each case made at most one attempt. No failed case was retried within this batch.
The run began from tuning checkpoint `b12391f`; subsequent UI-only work did not
change its model prompt, dataset or retained scoring calculation.

| Measurement | Observed result |
| --- | --- |
| Labeled cases | 50, across ten scenario families with five correlated variations each |
| Completed runs | 46/50 |
| Failed runs without a retained draft | 4/50 (`invalid_ai_response`) |
| Retained citation validity | 109/109 (100%) |
| Unsupported quotes in known sources | 0/109 (0%) |
| Unknown citation IDs | 0 |
| Disposition agreement | 43/50 (86%), including all failures in the denominator |
| Draft-preparation quality gate | **Not passed** |
| Automatic preparation | **Disabled** |

The gate failed because not every case completed with a cited draft, and returned
provider identities varied. All calls requested the same model name and saved
prompt; the configured revision was `provider-unreported`. Fingerprints are
preserved separately. They do not establish immutable weights. There are three
completed disposition disagreements in addition to the four failed cases.

100% retained citation validity does **not** mean zero raw-model hallucinations,
that every inference is supported, or that failed provider outputs contained no
fabrication. Quote-ID constrained generation resolves quotes before retention;
four failed requests have no inspectable draft/quotation denominator. No failed
output is silently accepted, and no all-case success or automatic promotion is
claimed.

The labels are scenario-author judgments against a fictional policy, not real
analyst decisions, partner evidence or regulatory truth. Screening used an empty
synthetic snapshot, so these numbers do not measure sanctions matching. The
dataset description/limitations, every case result and complete retained steps
are supplied for inspection. No identities, credentials, databases or installation
keys from the user's live workspace are included.

## Retained artifacts and verification

This directory contains the normalized dataset, initial replay manifest, original
scorecard and 50 terminal run JSON artifacts. The digest and every score row,
model/scenario aggregate and gate were independently recomputed before retention.
The report and runs are ordinary artifacts, not signed provider attestations.

From the repository root:

```powershell
.venv\Scripts\python.exe verify_agent_evaluation.py `
  evaluation/results/20261023-gpt-oss-20b `
  --scorecard-sha256 8f1b3b85e5a3da3cbcf808036db190f9d3368dc4f1fa8b5b0e75097ff6ad84fc
```

The expected scorecard SHA-256 is:
`8f1b3b85e5a3da3cbcf808036db190f9d3368dc4f1fa8b5b0e75097ff6ad84fc`.
Dataset SHA-256:
`b1ddc272a2b33e2771c5aece1c14ff566ec8da93aed33dbf4177bf5331c83072`.
The scorecard digest covers canonical JSON excluding its `scorecard_sha256`
field. Trust this value through a separate reviewed source before using it for
verification; changing a report and its supplied hash together is not trustworthy.

The verifier rejects missing/extra JSON artifacts, identity/manifest mismatches,
changed labels, altered metrics, invalid digest, nonterminal runs, redirected
files and bounded-file/bundle overflow. It recomputes from retained evidence
without invoking the model. It does not authenticate the provider transport or
independently validate labels, source truth or original wall-clock chronology.

The Evidence → Agent scorecards page exposes this same verified synthetic
reference to authenticated users, clearly separated from their workspace's
customers/configuration. A missing or changed reference returns an error rather
than partial metrics. Reference downloads contain only the original scorecard;
they are not workspace evidence exports or a new workspace retention claim.
