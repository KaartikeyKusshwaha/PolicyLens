# Synthetic single-worker HTTP load check

`evaluation/pilot_load.py` starts a separate loopback Uvicorn process against a
**new** isolated directory, with SQLCipher identity/tenant databases and external
checkpoints. It has no live-target URL option, loads no `.env` file, and sets an
empty model key. External providers and the agent worker are disabled. It never
uses an existing customer installation or deletes old run directories.

```sh
python evaluation/pilot_load.py --directory .pytest-tmp/NEW-UNIQUE-LOAD-RUN --customers 100 --transactions 1000 --concurrency 4 --read-rounds 10 --p95-ms 2000
```

The directory must not exist. It retains private test databases, generated keys,
ephemeral credentials/session state, server log, synthetic signed ZIP and report.
Do not publish that directory. The JSON report contains aggregate synthetic
metrics, platform information, correctness booleans, thresholds and a canonical
SHA-256, with no password/token/cookie/customer identifiers. It is safe to review
separately after inspecting it. Hashes provide integrity relative to a trusted
copy; they do not authenticate hardware, timings or investigator conclusions.

The runner creates an owner and independent reviewer through the real API,
verifies refusal of maker self-approval, approves one internal amount control,
and adds synthetic customers. The threshold is a test workload choice, not a
regulatory recommendation. Each unique transaction is submitted **twice** under
bounded concurrency. It checks exactly one original and duplicate per reference,
exact transaction/alert counts, unique alerts and one open case per flagged
customer. Concurrent populated reads cover cases, paged alerts, digest,
traceability, analytics and transaction history. The run then checks audit
integrity, digest counts, encrypted database headers, a fully verified signed
evidence pack, a new empty tenant and cross-tenant customer refusal.

Latency samples include every measured request, including HTTP errors/timeouts;
p50/p95/max are reported separately by endpoint. Request failure, any correctness
failure, any endpoint p95 above the chosen threshold, an invalid or over-one-minute
signed export, or failure to stop the server fails the run. Setup, correctness
queries and evidence export are outside the concurrent ingestion/read latency
samples; export time is reported separately. Quantiles use nearest rank, not an
average of endpoint percentiles. These are repeatable local observations, not an
independent performance attestation.

Bounds: 1–2,000 customers, 1–10,000 unique transactions, 1–16 concurrent clients,
1–100 read rounds and 1–60,000 ms selected p95. Those are harness bounds, not a
claim that every allowed combination fits the application's export/capacity
bounds. A failed run is retained and must not be overwritten or silently sampled.

## Recorded envelope on 23 October 2026

Reports are retained under `evaluation/results/20261023-http-load/`.
The measured machine was Windows 11, Python 3.12.10, 20 logical CPUs. The service
used one worker and encrypted databases. This does **not** prove behavior on the
1 GB Oracle VM or at a design partner's actual workload.

For 100 customers, 1,000 unique transactions submitted twice, four concurrent
clients and ten rounds of six populated read endpoints:

- All 2,000 ingestion requests returned 201, with exactly 1,000 original and
  1,000 duplicate outcomes. All correctness invariants passed.
- Ingestion took 52.585 seconds, approximately 38.034 requests/second, including
  duplicates. Ingestion p95 was 148.258 ms. All measured endpoint p95 values were
  below the explicitly chosen 2,000 ms limit.
- The complete signed evidence ZIP generated in 19.785 seconds and verified.
  There were zero request failures. The complete run took 87.277 seconds.

The first larger run **failed** at PDF export: its complete JSON fit the 2 MB
snapshot bound, but exceeded the old 200,000-character print bound. The print
bound now matches the 2,000,000-character envelope; every record remains rendered.
The failed report is retained beside the fresh successful rerun. This is not a
retroactive reinterpretation of the failed run. The complete roughly 1.6-million-
character snapshot renders to a 955-page PDF, about 1.6 MB; completeness produces
a large document. First/middle/final pages were rendered, with PDFium used to
cross-check a Poppler font-substitution anomaly. Sample text was legible and
inside page margins. No browser acceptance occurred.

No partner interviews have defined a real load target. Full sanctions-feed
parsing/screening, model latency/limits, agent-worker throughput, tuning stress,
browser/mobile performance, sustained production traffic and deployed memory/CPU
capacity remain outside this run. Run an agreed synthetic envelope on the actual
pilot hardware before claiming deployed performance. Independent security review,
partner acceptance and operational deployment remain separate gates.
# Actual Oracle hardware follow-up

An isolated run on the recorded Oracle micro VM passed the same synthetic
100-customer/1,000-transaction/four-client envelope. Ingestion p95 was 398.770 ms,
slowest read p95 1,891.485 ms, and verified signed-pack generation 47.397 seconds.
Systemd reported 204.6 MiB peak service memory. Source hashes and host identity
were checked separately; see the unchanged report, hardware receipt and explicit
limits in `evaluation/results/20261024-oracle-acceptance/README.md`. This is a
selected synthetic profile, not partner-agreed capacity or live-provider load.
