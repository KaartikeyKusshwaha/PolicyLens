# Oracle official-source acceptance

On 23 October 2026 UTC (24 October local time), the deployed source parser/sync
code downloaded the actual official OFAC SDN XML into a new isolated SQLCipher
source store on Oracle. No model credential, customer record or existing pilot
workspace was used. The official endpoint and exact returned publication/fetch
timestamps and source SHA-256 are retained in `summary.json`.

Download and validation completed with **19,471 entries**. The system marked the
just-fetched snapshot ready while retaining the reported publication date
`10/21/2026`; ready does not mean the publisher revised the feed that day. An exact
name from the fetched feed matched itself through the normal screening path.
This is an integration sanity check, not a representative accuracy assessment,
identity determination or customer clearance.

The run used an unprivileged hardened transient systemd service with a 384 MiB
memory ceiling, two-minute runtime bound and writes restricted to the new
synthetic root. It completed with exit zero, approximately 145.7 MiB peak memory,
10.764 CPU seconds and zero peak swap. The first launch refused an output path
outside that root before any source request; the path was corrected inside the
same filesystem restrictions before the successful invocation.

A subsequent explicitly injected HTTP 503 was refused as `source_unavailable`;
the entire prior parsed snapshot remained unchanged. A simulated future clock,
25 hours later, returned stale through the normal freshness function. The failed
refresh and simulated age are separate checks, not claims that the official
endpoint failed or that 25 real hours elapsed. All those checks used only this
isolated source store. Both live HTTPS readiness endpoints passed afterward.

This does not establish all enabled feeds, UI source sync, scheduled refresh,
screening accuracy, sustained load, live case/model integration or production
source configuration. No complete-browser or sanctions-clearance claim is made.
The actual feed snapshot, private key and store remain outside Git; only aggregate
results are retained. Artifact SHA-256 binds bytes, not independent attestation.
