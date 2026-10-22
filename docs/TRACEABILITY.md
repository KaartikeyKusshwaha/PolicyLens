# Policy-to-control traceability

Source implementation is available from **Policy library -> Open policy-to-control
traceability**, at `/policies/traceability`. Production and browser acceptance are
pending. This view records human assertions of applicability and observed work; it
does not certify complete policy coverage, legal interpretation or detection accuracy.

## Sources and interpretation

The matrix displays the latest completed policy-analyst run for each retained
policy version. It uses the existing runner's verified verbatim citations and
displays the analysis's partial-document coverage and non-exhaustive scope. Policies
with no extracted suggestions for their current version appear explicitly as awaiting
analysis. Failed/queued runs do not supply invented obligation rows.

Each obligation shows its exact quote, policy title/version, originating run, explicit
human control mappings, control status, latest recorded simulation for that control
version, observed alert count and screening evidence attached to the alerts' cases.
Historical policy versions, missing mappings, missing active controls, partial
analysis and active controls without a recorded simulation are flagged. A control
sharing the policy does not acquire a mapping automatically.

Admin, analyst and reviewer roles can add or remove mappings with a rationale.
Auditors can read only. Adding a mapping requires a control from the same current
policy version; old mappings can be removed. Mapping a draft leaves it a draft.
Activation continues through the existing independent approval workflow. Ordinary
traceability routes are unavailable to agent bearer identities.

Rerunning analysis creates new obligation identities and requires explicit remapping;
previous assertions are not silently transferred onto new model text. Old analysis,
mapping records and mapping audit events remain retained. Matrix rows use only the
latest completed analysis per version; superseded analysis identities cannot be
edited through the current matrix. Policy updates mark previous-version mappings
historical and require current analysis before adding mappings.

Simulations use historical transactions with current customer state. The matrix
reports their recorded time and sample size; it does not claim that an old simulation
incorporates newly arrived transactions. Alert volume does not establish sensitivity,
precision or effectiveness. Screening evidence may be absent even when alerts exist;
case notes and the complete audit remain available in the case/evidence pack.

## Persistence and boundaries

Mappings are workspace records of kind `traceability_link`, containing the originating
obligation identity, control ID, rationale, actor and timestamps. Mapping changes and
their audit events commit together under an SQLite write transaction. A read matrix
uses one SQLite read transaction, including selectable control choices.

`GET /api/traceability` returns the matrix. `PUT
/api/traceability/obligations/{id}/links` accepts `control_id`, `linked` and `notes`.
Unknown/obsolete obligations and other-tenant IDs fail; policy-version mismatches
return a conflict. Any source section above 10,000 rows returns an explicit error,
not a silently sampled matrix. Partner-scale load verification remains a later gate.

Sponsor packs include retained human mappings, historical simulation records and
the originating agent results in their signed PDF/JSON sections, allowing review
alongside the full audit chain. Model-derived obligation suggestions remain drafts.

Automated tests cover the no-inferred-link boundary, draft versus independently
approved controls, simulations/alert/evidence joins, multiple obligations, replacement
analysis, changed policy versions, cross-policy/tenant denials, auditor permissions,
pack inclusion and populated component error/read-only states. Browser/mobile
acceptance remains deferred until implementation is complete.
