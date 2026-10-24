# PolicyLens final product scope

Owner-directed simplification, 24 October 2026.

The user journey is policies and controls → investigate flagged activity → review
the decision → export supporting evidence. The product retains policy versions,
cited obligation suggestions, control drafting/simulation and independent activation,
native CSV/webhook ingestion, sanctions evidence, case notes/tasks, separate case
review, signed reports and offline verification. Normal account access, encrypted
storage, backups, preservation safeguards and Telegram health monitoring remain.

Removed from the product and its supported distribution:

- MCP server, CLI and Python SDK; external agent-key/toolkit API routes and bearer access.
- Marble importer and its API/UI. Historical imported records remain readable as
  retained source evidence; removing an integration does not erase case history.
- YAML control import/export and controls-as-code pages/API.
- Agent scorecard page/API and raw agent-operation/log pages.
- Relationship graphs and their API/tab.

Cited policy/investigation preparation remains an in-app action. Its result page
shows the draft, quotations, limitations and status without raw step JSON or a
global run-management dashboard. It cannot approve or resolve work. Evaluation
artifacts remain offline engineering evidence for the disabled automatic-brief
quality gate; they are not a user-facing scorecard feature.

Settings no longer advertises agent keys, runs or engine imports. Removed links
and old feature bookmarks do not restore the removed functionality. Historical
database records, audit events, signed packs and backups are preserved; no data
migration or deletion is needed for this simplification. Internal legacy-key
compatibility only supports refusing old jobs/access and safely restoring history.

Dated master plans, acceptance records and toolkit instructions describe earlier
versions. This file and the current README define the supported product scope.
Independent review and partner validation remain deferred at the owner's request;
this release does not turn synthetic evidence into real-customer approval.

## Automatic review experience — 25 October 2026

Cases now open on a prepared Review screen. Existing monitoring still groups
alerts automatically. Reading a case assembles recorded control hits, archived
policy context, exact decimal totals per currency for the displayed history,
evidence gaps and open tasks without starting a model job. New activity appears
automatically within 30 seconds while the case is visible, and on window focus.
The same factual preparation is included in case JSON exports;
no separate report-drafting job is required for that export.

The first release automates factual preparation, not policy extraction/activation,
customer outreach, case assignment or final dispositions. It does not create tasks
for inferred gaps. Optional AI assistance is collapsed by default and still needs
verification. Automatic AI narrative generation remains disabled pending its
quality gate. A preparation gap is advisory, not proof of a breach or a complete
evidence inventory. Source freshness warnings refer to attached snapshots.

The case screen keeps existing content visible while refreshing after an action,
offers evidence tasks directly in the review, and provides responsive review
cards, explicit history limits and reduced-motion styling.

Inbox queues and alerts refresh while visible and when returning to the app.
Cases are sorted by priority, then due time. Existing content stays visible during
successful background refreshes. The prepared review can prefill an evidence-task
request for confirmation; it never sends a message to a customer. Eligible
independent reviewers can jump directly to the final decision form.

The application uses native system typography, neutral grouped surfaces, a blue
action accent, consistent 44-pixel primary controls, keyboard focus indicators,
light/dark themes and responsive layouts. External web-font downloads are removed.
These changes follow Apple's hierarchy, clarity and consistency guidance; this is
a web application, not a claim of native Apple platform certification.
