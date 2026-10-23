# Live MCP draft and populated recovery acceptance

Observed on Windows on 24 October 2026 local time (23 October UTC), using the
reviewed source tree merged in PR #5 as `04808f4`. This is synthetic local
acceptance, separate from the deployed HTTPS browser installation.

## Live provider through MCP

A fresh SQLCipher installation was populated through `evaluation/browser_fixture.py`.
Its provider-disabled baseline marker describes preparation only. A separate
acceptance runner then explicitly enabled one live Groq request, one background
worker, pseudonymization and a one-run workspace/key budget. A private synthetic
empty sanctions snapshot with a `urn:policylens:synthetic-mcp-acceptance-feed` URL
was supplied locally. It is not an official sanctions feed or clearance evidence.

The MCP client connected to a separate stdio bridge process, which called the
actual application over loopback HTTP. It obtained case context, queued an
investigation, read its completed result, reverified quotations and requested
human review. Calls to `approve_control` and `close_case` were denied. Completion
events for all five allowed tools and denial events for both forbidden tools
were inspected in the valid 76-entry audit chain. The case remained open.
The temporary agent key was revoked and its private token file removed; the
application subprocess stopped. Revocation appended the 77th audit event.

`live-run.json` retains the synthetic evidence snapshot, completed draft,
verification steps and model identity. All four retained quotations were also
independently rechecked against the retained policy excerpts after publication.
The model returned `openai/gpt-oss-20b`, fingerprint `fp_a4315eb300`; the provider
does not report an immutable revision, and `revision_enforced` remains false.
This one successful run does not change the failed 50-case preparation gate or
enable automatic briefs. It establishes neither decision quality nor Claude/
Cursor host configuration nor a successful deployed HTTPS model run.

## Populated recovery

With that isolated installation stopped, the operator captured a full signed
audit bundle, exported complete checkpoint history, encrypted it with a fresh
separate archive key, and reconstructed a new checkpoint directory. The trusted
public fingerprint was derived from the retained source installation key before
the export. A stopped SQLCipher snapshot of identity and workspace databases was
verified and restored into a new directory using the independently retained
current deletion-guard digest. No source database was replaced.

All rows in all 20 workspace tables matched their pre-backup logical hashes;
the source tables remained unchanged. The restored installation verified against
the recovered checkpoint history and its 77-entry audit chain. Four cases,
including three open cases, and the completed four-citation draft survived.
Sessions and agent keys were revoked. A fresh authenticated request succeeded
with providers and workers disabled, then the restored app stopped.

This drill contains zero deletion-execution receipts. It does not prove deletion
suppression after an executed deletion, complete copy discovery, physical erasure,
off-machine custody, production recovery, MFA recovery or independent review.
The source key, archive key, databases and credentials remain private and are
excluded from these artifacts. `sha256.json` binds the retained aggregate reports
and synthetic run; it is not an independent signature or time attestation.

## Deployed governance API follow-up

`deployed-governance.json` records a separate HTTPS check on the existing isolated
Oracle acceptance installation, using distinct owner/reviewer API sessions. It
did not operate the browser tab handed to the user for MFA.

A fresh tuning draft against the active YAML-imported control compared the
fictional 4,000/7,000 candidates against a caller-supplied target of one match.
The author was refused approval (HTTP 403). The separate reviewer activated the
selected 4,000 draft, superseding its parent; the existing alerts were unchanged.
These numbers measure synthetic workload and are not detection or legal advice.

The requester of the existing fictional pending hold release was refused
self-approval (HTTP 403); a different reviewer released it. The subsequent
deletion preview had no blocking holds, while open cases/tasks, retention time,
shared/text references and registered/external copy blockers remained. It exposed
no deletion execution. No records or external copies were removed. The deployed
audit chain verified 83 entries. These are API observations; browser hold-release,
MFA/recovery, complete deletion and genuine legal authority remain unverified.
