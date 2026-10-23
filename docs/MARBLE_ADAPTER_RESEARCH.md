# Marble adapter contract research

Inspected 22 October 2026 before adapter implementation. This is contract research,
not a live connection, importer or proof that a partner uses Marble.

## Primary sources inspected

- [Official API introduction](https://docs.checkmarble.com/reference/intro-getting-started):
  bearer authentication, `data` response envelope and cursor pagination.
- [Official migration guide](https://docs.checkmarble.com/reference/migrating-from-the-legacy-api-to-v1):
  legacy API deprecation and v1 changes. New integration must target versioned APIs.
- [Official get-decision reference](https://docs.checkmarble.com/reference/getdecision):
  stable `GET /v1/decisions/{decisionId}`.
- [Official v1 OpenAPI source](https://github.com/checkmarble/marble-backend/blob/main/pubapi/openapi/v1.yml),
  observed Git blob `e634b9ce7dad4d991b5d47cf4ee03bdec5004c04`.
- [Official v1beta OpenAPI source](https://github.com/checkmarble/marble-backend/blob/main/pubapi/openapi/v1beta.yml),
  observed Git blob `3bdcd784dbb6f3c325c505878d052d69b33df1c7`.

The OpenAPI files were read directly through GitHub's contents API. Local research
copies are ignored development artifacts, not vendored dependencies. Re-check the
contract before enabling a live connector, particularly the explicitly beta cases API.

## Findings relevant to import

Stable decision list/detail live under `/v1/decisions`. The decision schema identifies
the record, scenario, trigger object, outcome, review status, score and creation time.
The trigger object's `object_id` is an application-defined object reference; additional
trigger fields depend on the customer's Marble data model. It is not inherently a
transaction or a PolicyLens customer reference.

The inspected beta specification exposes case list/detail and separate comments/files
resources. Case records identify an inbox, status, outcome, contributors, tags, review
level and creation time. Beta contracts may change without a stability guarantee.
Decisions have an optional case reference; source cases do not intrinsically identify
a local PolicyLens customer. An adapter must keep source IDs/types and require an
explicit, validated tenant-local mapping before creating customer-linked records.

Responses wrap objects/arrays in `data`. Paginated responses supply `has_more` and a
next cursor; subsequent requests use `after`. A file import must identify whether a
supplied response is only one page. It must not imply complete source coverage when
more pages exist. Decision date filters have bounded windows; defaults cannot be
treated as complete history.

## Required implementation boundaries

- Begin with explicit read/export import; validate a declared supported version and
  retain provenance, original source status/outcome, source IDs, schema digest/version,
  import time, content digest and deduplication identity.
- Preview validation, missing mappings, pagination coverage and replay/conflict results
  before committing records. Never invent a customer or transaction interpretation.
- Preserve upstream outcomes as source evidence. Importing an upstream closed case
  must not silently close a local investigation or bypass independent human review.
- Source scenario/rule snapshots must not become active local controls. Native control
  activation remains subject to independent approval.
- Replays of the same source identity and unchanged content are idempotent. Changed
  evidence needs versioned provenance or an explicit conflict; no silent overwrite.
- Do not execute upstream workflow, payment, screening-review or case-lifecycle write
  APIs. Credentials, if a live read connector is later configured, require encrypted
  storage and a fixed/validated origin with bounded pagination and no redirects.

No adapter is marked implemented by this research. A transaction-source adapter still
needs partner selection; public prospects are not design partners or interview evidence.
