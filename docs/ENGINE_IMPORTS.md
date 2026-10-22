# Engine adapters and Marble import

Implemented on the governance branch, using the official contracts recorded in
`MARBLE_ADAPTER_RESEARCH.md`. Production deployment, browser acceptance and a live
Marble-account export comparison remain pending. No upstream API is called by this
implementation; it imports supplied exported JSON records.

## Use the import screen

Open Workspace settings -> **Import records from an existing engine** at
`/settings/imports`. Admins and analysts can author imports. Other roles can read
the resulting investigations/evidence; they cannot import. Agent bearer identities
cannot use ordinary import routes.

Supply a stable instance label and paste the complete `data`/`pagination` envelopes
for the Marble case and decision pages. Either page may be `{"data": []}`. Cases
target the reviewed `v1beta` contract; decisions target `v1`. Preview the records,
explicitly map each new source case (or caseless decision) to an existing customer,
then preview again and import. A decision with a case reference inherits that source
case's mapping. Referenced cases must be included or previously imported. Trigger
object references are never assumed to identify customers or transactions.

`examples/marble-import/fictional-bundle.json` is a fictional complete bundle for
API/testing reference. For the screen, paste its `cases` and `decisions` objects into
the matching fields and select an actual synthetic workspace customer. The placeholder
customer reference is deliberately not a real record; nothing is seeded automatically.

## Resulting behavior

- Each newly imported source case creates a separate local open investigation,
  including when upstream status is closed. Existing local cases are not merged,
  escalated or closed by import. Medium priority is the import queue default, not an
  interpretation of the upstream score or a regulatory threshold.
- Non-approve decisions create review alerts. An approve decision without a case
  creates retained source evidence only. Upstream decline/block outcomes never execute
  payment actions. Source outcome/status is not a local disposition or clearance.
- A caseless review decision requires its own explicit customer mapping and creates
  an open investigation. A new alert cannot be appended to a locally resolved source
  case until a human reopens that investigation through the normal workflow.
- No transactions, native controls, approvals or filings are inferred. Independent
  control activation and case resolution rules remain enforced.
- Imported alerts display source provenance instead of fabricated native-control
  links or inferred currency/threshold facts. Case context distinguishes upstream
  status/outcome from the local review state.

## Provenance, preview and replay

The adapter registry defines a parse/object interface; the implemented engine adapter
is Marble. `GET /api/adapters` lists supported import transports. `POST
/api/adapters/marble/preview` accepts `{"bundle": ...}` and returns source identities,
hashes, new/replay status, missing mappings/conflicts and a preview digest. `POST
/api/adapters/marble/import` requires the same bundle and `preview_sha256`.

The versioned wrapper is `policylens.marble-import.v1`. It records the stable source
instance, declared source API versions, case/decision envelopes, explicit customer
mappings and partial-page acknowledgement. A source-object identity combines provider,
instance, type and source UUID. Its digest covers the normalized source JSON including
unknown upstream object properties, retained as evidence rather than execution fields.
Normalization canonicalizes typed UUID/timestamp representations; it is not a digest
of original HTTP response bytes or an upstream digital signature.

Object records retain source JSON, digest, inspected contract blob, API version,
mapping, local case/alert IDs, author and import time. Batch receipts retain pagination,
source metadata, coverage and object references. Source-object import audit entries
include the object digest and local linkage. Sponsor evidence packs include source
objects and receipts alongside the signed chain.

All changes commit in one SQLite write transaction. Replays of an identical batch
return the original receipt; overlapping bundles reuse unchanged objects. A changed
object under the same source identity or a changed customer mapping produces an
explicit conflict, never a silent overwrite. This version does not synchronize later
source-state changes; a future versioned reconciliation workflow needs separate review.
Concurrent identical imports serialize and commit one case/alert set. Failed batches
leave no partial cases, alerts, provenance or audit prefix.

## Bounds and coverage

Bundles are limited to 2 MB, 500 cases, 500 decisions, 1,000 explicit mappings and
bounded source reference collections. IDs, enum values, timezone-aware timestamps,
versions and duplicate objects/mappings are validated. Non-finite JSON values fail.
Unknown fields in an upstream object are retained; unsupported wrapper/envelope
fields or source versions are rejected. No network origin, credential or arbitrary
URL is accepted, and no remote write API is exposed.

When a page declares `has_more`, explicit acknowledgement is required. Every receipt
states **selected exported records**, even for a final page; source date/query filters
and omitted pages can limit completeness. Separate upstream comments/files endpoints
are outside this importer. Missing attachments/history must be reviewed at the source.

Arbitrary source/trigger/scenario fields remain in retained evidence and are excluded
from the model context used for investigations. The model gets a bounded projection
of source facts and scenario identity. Optional structured masking also covers trigger
object references and source case names; it remains pseudonymization, not full
anonymization of every possible free-text fact.

Automated checks cover import-to-inbox/case visibility, retained provenance/pack
inclusion, no inferred transaction/control/closure, customer and tenant mapping,
auditor denials, source/preview conflicts, partial pages, duplicate IDs, invalid source
versions/timestamps, resolved-case protection, late-failure rollback, concurrent replay,
source masking and populated import/case component states. Live source compatibility
and operational/browser acceptance remain unverified. The partner-selected transaction
source adapter is still pending partner selection.
