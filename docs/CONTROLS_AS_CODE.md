# Controls as code

Deployed to Oracle. The synthetic browser pass verified export, a local Git-reviewed
title change, preview, draft import and activation by a separate reviewer. Other
failure paths and owner-workspace acceptance remain distinct; see
`BROWSER_ACCEPTANCE_20261023.md`. YAML creates configuration drafts; independent in-app review remains
the only route to activation. This feature performs no Git push, merge, fetch or
external API operation.

## Working flow

1. Open Control workbench -> **Controls as code**, or select **Export this control
   as YAML** on a control version. Load the YAML and download it into your repository.
2. Review configuration changes in Git and commit them. Keep the exported policy and
   parent pins unless you have explicitly reviewed/remapped their current versions.
3. Paste/read the reviewed YAML in PolicyLens. Optionally record the full Git commit
   SHA and repository file path, then preview the normalized configuration.
4. Import the reviewed drafts. Open each resulting control for historical simulation
   and independent review. Importing does not activate or supersede anything.
5. A second admin/reviewer approves each draft through the existing control workflow.
   The author cannot self-approve. Activation supersedes the prior version under the
   same existing maker-checker rules.

Git commit/path are supplied provenance assertions. PolicyLens does not authenticate
a remote repository, verify commit signatures or claim that pasted content came from
that commit. Review your repository and file through your own trusted process.

## Schema

The versioned root has exactly `schema_version: policylens.controls.v1`,
`workspace_id` and a `controls` list. Each entry contains:

- `key`: a document-unique stable label, not execution authority.
- `policy`: workspace-local policy ID, exact version and SHA-256 over the canonical
  title/content/topic/version/source URL. Current stored policy must match all pins.
- `replaces`: existing control ID and configuration/version hash, or `null` when
  intentionally creating a new control. Parents must belong to the same policy and
  must not already be superseded.
- `configuration`: the native validated control input fields: title, kind, policy ID,
  currency, threshold, time window, countries, priority and description.

Exports omit status, author, approval and execution metadata. Such extra fields are
rejected on import rather than silently granted or ignored. The server constructs new
IDs, versions, author identity and draft state itself. Workspace exports include up to
100 non-superseded controls. An individual superseded version is not an import target.
Old-policy controls retain their original archived policy pin on export; they cannot
be silently rebound to a new policy. Use the normal editor to review a current-policy
draft before exporting it, or deliberately update/review the complete policy pin.

PyYAML's [safe constructor set](https://github.com/yaml/pyyaml/blob/main/README.md)
is used with an additional bounded loader. Input is limited to 256 KB, one document,
100 controls, 20,000 composed nodes and depth 16. Anchors, aliases, duplicate or
non-string mapping keys and custom object tags are rejected. Native field bounds and
cross-field validation still apply. YAML is data; it is never executed as Python.

## Preview, concurrency and replay

`POST /api/control-code/preview` accepts YAML and optional source provenance. It
validates every workspace/policy/parent pin and returns normalized control data plus
`preview_sha256`. `POST /api/control-code/import` requires the same content/provenance
and preview digest. Modified content requires a new preview. Pins are rechecked
inside the write transaction, so changes after preview fail explicitly.

All drafts, the immutable import receipt and the import audit entry commit together.
A failed member leaves no partial control batch or audit prefix. A replay of the
same normalized document and supplied provenance returns the original receipt with
`replayed: true`; it creates no duplicate drafts. The receipt contains the original
draft snapshots. Open the linked controls for their current state, which may have
changed through later human review. Comments/formatting are not configuration changes.

Admins/analysts can preview and import. Other human roles may export, while auditors
cannot write and reviewers cannot import as authors through this endpoint. Agent
bearer identities cannot use ordinary configuration/approval routes. Import receipts
are retained in signed sponsor packs alongside control versions and audit history.

## Automated evidence

Tests export an independently approved control, edit and commit YAML in an isolated
real Git repository, import a next-version draft, reject self-approval, and activate
through a second reviewer. They also check replay after activation, exclusion of
superseded exports, authority-field injection, parser attacks/ambiguity/depth,
changed policy/preview, tenant and role isolation, size limits, and late-failure
transactional rollback. Component tests cover export/preview/import, stale preview
invalidation and auditor visibility. These are automated tests using synthetic data;
they do not prove live deployment or independent security review.
