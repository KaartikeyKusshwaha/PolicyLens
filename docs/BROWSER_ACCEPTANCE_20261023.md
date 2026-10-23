# Deployed synthetic browser acceptance, 23 October 2026

The final browser pass started after full CI passed for `ecbaea0` and PR #3
merged as `3f4d976`. It used the connected Edge extension directly, without the
computer-use skill. The separate HTTPS acceptance installation on the actual
Oracle VM contains fictional data and independently authenticated owner/reviewer
accounts. Provider calls and the agent worker are disabled. It does not establish
owner-workspace acceptance or successful live-model/public-feed behavior.

Observed through the browser:

- Sign-in and sign-out with the fictional owner and separate reviewer worked.
- Inbox showed three open cases, seven alerts and one pending control; the
  missing-source freshness warnings remained visible.
- The control author saw the independent-review restriction and no activation
  form. A browser simulation tested six transactions and returned zero matches.
- The separate reviewer activated the fictional draft and its review note was
  displayed with Active status.
- Sponsor evidence downloaded through the browser. The download-event tool timed
  out, but the actual saved ZIP was found and independently verified with the
  separately obtained signing fingerprint: all five payload files and audit
  sequence 44 passed. No embedded verifier script was executed.
- All four primary areas rendered at the 390 by 844 mobile viewport. Drawer
  Escape closed it and returned focus to Open navigation. Horizontal subnavigation
  remains scrollable. The viewport override was reset afterward.
- The imported fictional upstream case remained Open locally despite its closed
  upstream status. A browser-added note persisted under Activity. Relationships
  rendered as a case tab, with source/identity limitations visible.
- The reference scorecard displayed retained failures and its explicit synthetic,
  label, provider-version and quotation-measurement limits.

The relationship view exposed a real responsive defect: its grid child's minimum
content size expanded the document to 514 px at a 390 px viewport. The CSS fix in
`da8de7e` allows that child to shrink. Lint/build passed, and the corrected build
was deployed with previous assets retained. A focused settled-browser recheck
measured document width 375 px, graph container width 292 px and internal graph
content width 450 px. The graph now scrolls within its panel. This is an observed
fix and recheck, not a claim that every browser checkpoint passed.

Still unverified in this pass: MFA enrollment/recovery, password lifecycle,
complete YAML/tuning/retention mutations, model-backed extracted obligation
mappings, live provider/feed/MCP acceptance and owner production-workspace
acceptance. Independent security review, partner validation and real-data gates
remain open. No successful model response or complete erasure was fabricated.

Private screenshots, the downloaded-pack verification result and the structured
acceptance record are retained in the operator workspace. Some first mobile
captures used a browser screenshot method that produced scaled captures; the
native-size case recheck is the evidence for the measured overflow correction.
Passwords and session tokens are excluded from this document and the record.
