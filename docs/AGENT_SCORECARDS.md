# Agent replay and scorecards

Source implementation; browser acceptance and Oracle deployment remain pending.
The harness replays the existing `AgentEngine` investigation workflow in a **new,
isolated installation**. It uses the same one-attempt rule, saved model/revision,
prompt version, context limit, citation verifier, run budget and audit writes as
ordinary agent work. It never approves, resolves or changes a case disposition.

## Dataset and labels

`evaluation/seeded-cases.json` contains 50 reviewable synthetic cases across ten
scenario families, five variations each. Each label has a disposition, rationale
and reference. `evaluation/seeded_cases.py` is its deterministic source. The
training policy expressly supplies its own fictional investigation criteria; no
regulatory threshold is invented or claimed. These are correlated variations,
not fifty independent real investigations or compliance-lead judgments.

The seeder copies only the customer, case description and transactions into a
fresh tenant. Expected dispositions, rationales, label references and categories
stay outside the model context. Cases begin open with an empty human disposition.
All screening data is explicitly synthetic and empty; the harness does not claim
official-list freshness or sanctions accuracy. Historical datasets can be scored
by the deterministic scorer, but this CLI deliberately refuses historical seeding
until an archived-source replay path exists. User-supplied descriptions still
require review for label leakage and evidence quality.

The dataset schema rejects unknown fields, duplicate case/customer/transaction
references, more than 500 cases, more than 50 transactions per case or a complete
dataset above 4 MB. An oversized dataset is never silently sampled.

## Replay

Configure the existing `GROQ_API_KEY` privately. Run from the repository root:

```powershell
.venv\Scripts\python.exe evaluate_agents.py `
  --dataset evaluation/seeded-cases.json `
  --output C:\PolicyLens-Evaluations\new-run `
  --daily-run-budget 50 `
  --interval-seconds 60
```

The parent output folder must exist; the run directory must not exist. The
configured default budget is 30, so 50-case replay requires an explicit sufficient
evaluation budget. The separate installation has its own databases, security key
and checkpoints. Existing pilot database/key paths are not reused. Environment
database-encryption mode is retained. POSIX file modes are restricted; on Windows,
protect the parent directory with appropriate ACLs. No credential is printed.

`--model` and `--model-revision` override evaluation configuration only. An
unreported provider revision remains explicitly unreported; a saved model name
does not prove immutable underlying weights. Quote-ID constrained generation and
the schema change use prompt version `policylens-governance-v2`. Existing keys and
queued runs pinned to v1 are refused rather than silently reinterpreted; reissue
keys and submit reviewed new runs after deployment.

Replay is sequential, with a configurable 0–60 second inter-request interval
(default three). Each case makes at most one model attempt. Access failures,
request rejection or rate limits stop the batch after retaining the failed run
and `replay-stopped.json`; **no partial scorecard is published**. Do not repeatedly
restart a rate-limited batch. Other individual run failures remain in the full
score denominator. An interrupted run retains its completed artifacts; there is
currently no automatic resume or retry facility.

The output contains the normalized dataset, initial manifest, one complete run
JSON per case and, only after every case has a terminal run, `scorecard.json`.
Each score row binds hashes of the retained run and collected context. Dataset
and scorecard hashes detect changes relative to a separately retained digest;
they are not signatures or proof that a supplied label is correct. Retain the
whole output in controlled evidence storage and apply its own custody policy.

## Measurements and gate

Investigation briefs can include `draft_disposition`: `confirmed`,
`false_positive`, `insufficient_evidence`, or null for abstention. It is a
nonbinding suggestion; human case disposition stays separate. Older results
without this field count as abstentions.

- Citation validity: verified source-ID/verbatim-quote pairs divided by observed
  retained citations. Whitespace is normalized; narrative support is not scored.
- Fabricated-quote rate: quotations absent from a known cited chunk divided by
  observed citations. Unknown IDs are counted separately.
- Disposition agreement: completed runs whose draft matches the supplied label,
  divided by **all labeled cases**, including failures and abstentions.
- Counts include failed runs, drafts unavailable for inspection, fully cited
  completions, abstentions and a confusion matrix. Reports split results by model,
  configured revision, prompt and returned provider identity, and by scenario.

These are post-schema, resolved-quotation metrics. A provider rejection before a
draft is retained has no observable quotation denominator and cannot be called
zero hallucination. Null citation rates mean no observed citations. The report
states these limits and retains failures alongside successful outputs.

The engineering gate requires at least 50 cases, one model/prompt identity,
current prompt, all runs completed with verified citations, no unsupported or
unknown quotations, at least 80% disposition agreement, and live-provider
measurement. This threshold is not an independently validated model-risk or legal
standard. Test-transport measurements cannot pass the live gate. Passing never
enables autopilot or authorizes final decisions; opt-in preparation, its promotion
workflow and independent review remain separate work.

## Current evidence

The automated 50-case replay exercises the production runner with a deterministic
HTTP test provider. It measures the harness, hidden-label boundary, normal audit
and budgets, not live model quality. All 50 test runs complete with unchanged open
human cases; the report's live-provider gate remains false.

A live check found and corrected strict-schema handling of nullable fields. Two
subsequent live cases completed with verified citations and `confirmed` drafts;
the third hit `groq_rate_limited`, stopping the run. This is **not** a complete
50-case live scorecard, and no full live citation/agreement claim is made from it.
