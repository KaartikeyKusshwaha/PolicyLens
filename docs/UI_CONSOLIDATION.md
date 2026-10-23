# Four-area control room

Implemented in governance source. This is not Oracle deployment or populated
browser/mobile acceptance; the user requires finishing implementation first.

| Primary area | Canonical root | Work |
| --- | --- | --- |
| Inbox | `/inbox` | Open/overdue investigations, paged native/imported alerts, control/policy/retention reviews, customers and starter transaction ingestion |
| Policies & Controls | `/policies` | Traceability first; policy library, control versions/tuning/YAML, policy changes and cited research |
| Evidence | `/evidence` | Signed sponsor packs, external checkpoints, audit chain and advisory assessment records |
| Settings & Agents | `/settings` | Workspace/account/MFA, connections, agent keys, playbooks/recent runs, imports and retention/holds |

The sidebar has exactly four primary links. Secondary navigation groups related
work and highlights the area on detail/editor routes. Settings sections use
query parameters for shareable links and browser history. The mobile drawer
implements keyboard focus trapping/return and Escape; its background is inert
while open. Narrow secondary navigation scrolls horizontally.

## Investigation work

The Inbox replaces the former dashboard/marketing panels with work queues and
explicit loaded-record counts. Failures show retries rather than invented zero
counts or empty-success states. Case/control counts use the loaded 2,000/1,000
pilot bounds; queue previews show up to 20 records. Retention review requests are
not fetched for analysts whose role cannot access that API.

`GET /api/alerts` supplies tenant-local read-only pages with limit, offset and
`has_more`. Limits are 1–200 records and offset 0–100,000. The web app uses pages
of 50 and retains a way back from an empty page. Native and real Marble-imported
alerts retain provenance. Concurrent arrivals can change offset-based pages;
refresh for current work. This feed is not a signed snapshot or disposition.

The case Relationships tab retains the customer-wide observed graph and its
transaction/node scope. Links do not establish wrongdoing or case-only activity.
Completed cited briefs appear in Agent work with limitations and human-review
wording. Detailed execution remains in Advanced.

## Diagnostics and duplicates

`/advanced` is diagnostic navigation, not a fifth primary area:

- `/advanced/agents` and `/advanced/agents/{id}`: loaded execution history and raw
  run details. Settings shows playbooks and up to ten recent model runs instead.
- `/advanced/analytics`: activity/corridor/disposition breakdowns. Evidence no
  longer fetches or duplicates those analytics.
- `/advanced/sources`: per-source dates, publication metadata, checksums and sync
  controls. Settings shows aggregate enabled-feed freshness and connection actions;
  sequential sync failures disclose how many feeds completed.

Obsolete CommandCenter/Overview files were removed. Agent keys have one dedicated
settings destination; the customer profile no longer duplicates the case graph.
The legacy favorable assessment enum stays unchanged in storage/API while the UI
says “Advisory: no flag”. Neither it nor no name matches grants legal approval or
sanctions clearance. Auditors/analysts do not receive a human-assessment review
form that their server role cannot submit.

## Existing links and API boundaries

Old case/customer/control/assessment/source/agent/editor links redirect into the
canonical areas while preserving query strings and fragments. Existing page Link
and navigate calls use a small destination adapter; API requests are not rewritten.
`/policies` now opens traceability. The library is `/policies/library`; old policy
editor/traceability bookmarks redirect accordingly. There are no duplicate legacy
pages behind those redirects.

Populated tests cover queues, source provenance/paging, traceability, signed pack
failures/downloads, case drafts, advanced-only details, deep links, settings
sections, roles and keyboard focus. Permissions remain server-side. Actual desktop/
mobile layout and live deployment still need the final browser acceptance pass.
