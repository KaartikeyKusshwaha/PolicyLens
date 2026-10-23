# Actual Oracle synthetic load and deployed toolkit acceptance

Retained aggregate evidence only. No credentials, keys, databases, customer
narratives or raw private audit trail are included.

`load-report.json` is the unchanged report from the isolated harness on the
recorded Oracle VM. Its canonical digest (excluding `report_sha256`) is
`cbe3d6ddb422c27797fdb7a25e91fd72c022372cba19250e1021c5ed81de3564`.
The receiver recomputed that digest and the full gate from the retained metrics.

`host-receipt.json` records verified-SSH source hashes, 976,904 KiB total memory,
two logical CPUs and the previously authenticated OCI shape
`VM.Standard.E2.1.Micro`. The transient systemd unit completed successfully;
its journal reported 204.6 MiB peak memory and 241.094 seconds aggregate CPU.
These are this service's observed values, not whole-host capacity guarantees.

The unmodified harness contains conservative local-run boilerplate saying no
Oracle VM was tested and `oracle_vm_proven: false`. The harness itself does not
attest infrastructure identity. Those fields are preserved rather than rewritten;
the separate verified-host receipt establishes where this particular run occurred.
The report's measured results and gate were not changed to obtain a pass.

Chosen workload: 100 fictional customers, 1,000 unique transactions submitted
twice over four clients, SQLCipher, one worker and ten rounds over six populated
read endpoints. There were zero HTTP failures. Exact transaction/duplicate/alert/
case counts, audit integrity, tenant isolation and encrypted headers passed.
Total elapsed time was 210.590 seconds. Ingestion p95 was 398.770 ms; the slowest
read p95 was 1,891.485 ms for cases. The complete signed evidence pack verified
in 47.397 seconds. The chosen p95 gate was 2,000 ms; it is not a partner SLA.

The main pilot was left running. The harness uses a new isolated installation,
disables provider networking and its agent worker, and stops its server afterward.
It does not test live AI, full external feeds, partner-agreed concurrency, sustained
growth, browser latency or an independent security review. Ten samples per read
endpoint are limited evidence; do not infer broader latency distributions.

`mcp-acceptance.json` records an actual local CLI and MCP stdio process addressing
the separate deployed synthetic HTTPS acceptance site. Only search, case context
and review-task scopes were granted, with zero daily model runs. Context retrieval
and task creation passed; approval, closure and out-of-scope control access were
denied. Completed/denied tool events were inspected in the authenticated audit
response. The temporary key was revoked, refused afterward and removed locally.
No successful cited live-model draft or Claude/Cursor UI configuration is proved.
