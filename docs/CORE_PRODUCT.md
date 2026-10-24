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
