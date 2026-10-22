# Sponsor evidence pack

The governance branch implements a workspace-wide evidence archive. Production
deployment and browser acceptance are pending. It supports review of retained
records; it does not certify compliance or prove that supplied business facts are true.

## Generate

Configure external checkpoints and the installation signing key as described in
`EXTERNAL_CHECKPOINTS.md`. In Audit & analytics, select **Download sponsor evidence
pack**. All authenticated human workspace roles, including auditors, can export.
Agent keys cannot access this ordinary application endpoint; their existing scoped
case-pack tool remains separate. The request is recorded in the audit chain.

`GET /api/evidence/sponsor-pack` returns a ZIP containing:

- `evidence.json`: current policies, archived policy versions, all retained control
  versions and approvals, customer/case records, notes, tasks, screening evidence,
  transactions, alerts with control snapshots, assessment/review records, agent jobs
  and every retained job step, human obligation/control mappings, historical
  simulation records, plus source freshness and explicit coverage gaps.
- `report.pdf`: the same business sections rendered as labelled printable records.
  Unicode text uses visible escapes in the PDF; the JSON preserves original text.
- `audit.json`: the complete signed audit bundle for the snapshot.
- `manifest.json`: an Ed25519 signature over file SHA-256 digests and the workspace,
  audit sequence and chain head.
- `verify.py`: a copy of the offline verifier, provided for convenience.
- `README.txt`: interpretation, verification and handling instructions.

Business records and the complete audit chain are read inside the same SQLite read
transaction. A concurrent writer can append later work without changing the export's
snapshot. The corresponding external anchor is retained before a pack is returned.
The server verifies the finished archive before sending it. The PDF and JSON file
digests are signed; business rows do not become independently proven audit events
merely by being included in this server-signed snapshot.

No date filtering or silent sampling occurs. Exports refuse more than 5,000 rows per
section, 2 MB per business section/complete JSON snapshot, 200,000 printable snapshot
characters, or the checkpoint's 100,000-event/8 MB audit bound. The offline verifier
limits compressed and total uncompressed archive bytes to 32 MB. A refusal returns a
visible error and no partial/unsigned replacement. Automatic checkpoint retention
is separate from these download limits.

## Verify independently

Obtain the public signing fingerprint through an independently trusted channel.
Use a reviewed copy of `backend/verify_evidence_pack.py` from the repository. Do not
run scripts found in an untrusted archive as the first step in verifying that archive.

```sh
python -m pip install cryptography==50.0.2
python backend/verify_evidence_pack.py /private/pack.zip --fingerprint TRUSTED_SHA256
```

No server, database, model call or signing secret is needed. The verifier reads ZIP
members without extracting or executing them. It rejects missing/duplicate/extra
files, wrong keys, changed digests, invalid signatures, broken audit sequence/hash
links, unsigned tails and disagreement between the business snapshot, manifest and
audit workspace/head. Its output contains hashes/counts and workspace ID, not private
business records. A successful verification establishes integrity relative to that
trusted signing identity, not the truth or completeness of real-world events.

Source freshness includes enabled/disabled coverage, fetch/publication timestamps,
recorded SHA-256, entry count and the configured age threshold. Missing, stale or
future-dated snapshots do not count as fresh. External feed bytes are not embedded,
so their authenticity/content cannot be reconstructed from this pack alone. The
identity database, membership history, sessions, agent credentials and connector
secrets are excluded. User-entered business text and agent outputs can themselves
contain sensitive data; protect exported copies independently.

## Automated evidence

Tests generate a seeded investigation pack containing an independently approved
control, a case note, source metadata and a recorded agent step. They verify the
archive with a separate Python subprocess and check every file against tampering,
including independently re-signed manifests over invalid audit history. Separate
checks cover auditor access, tenant switching, concurrent writes, byte/row/printable
bounds and a synthetic 50-case export within one minute. The PDF is rendered and
visually inspected with Poppler during development. This is synthetic local evidence;
it does not establish deployed performance, browser acceptance or independent review.

Report generation uses [ReportLab Platypus](https://docs.reportlab.com/reportlab/userguide/ch5_platypus/)
and escapes business text before passing it to [Paragraph](https://docs.reportlab.com/reportlab/userguide/ch6_paragraphs/).
