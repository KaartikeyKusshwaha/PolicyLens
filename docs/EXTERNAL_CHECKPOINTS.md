# Signed audit checkpoints outside database storage

The source [checkpoint-history backup tool](CHECKPOINT_BACKUP.md) now supports
complete signed export, independently pinned encrypted receiver retention and
new-directory recovery. Actual off-machine transfer and scheduling remain pending.

Implemented on the governance branch. Production provisioning and browser
acceptance are still pending. This feature does not claim off-machine retention,
an independent timestamp, or resistance to a compromised application host/signing key.

## What is retained

The existing hash-linked audit remains the application record. A new independent
directory stores Ed25519-signed anchors with workspace ID, event sequence, chain
head, server timestamp and a digest of the previous retained checkpoint. The
private signing seed is derived with a separate purpose from the installation
security key, not stored in SQLite. The public-key fingerprint can be pinned by
an auditor through a trusted separate channel.

Each capture verifies the complete database chain in a consistent read transaction
and checks it against the latest retained anchor. A database-only rewrite or
truncation cannot produce a new accepted anchor that contradicts retained history.
The first anchor establishes a trust baseline for the then-current history; it
cannot prove that previously unanchored history was authentic.

The existing worker captures changed heads every five minutes by default, even
when scheduled sanctions screening is disabled. An unchanged head reuses the
existing document. Writers use a cross-process lock and publish files atomically
after flushing them. Existing anchors are never overwritten or silently selected
around when validation fails. Partial `.pending` files are not trusted anchors.

No retention/deletion of these anchors is enabled yet. They must be included in
the upcoming approved retention policy and off-machine operational backup scope.
The existing database-only backup exporter does not automatically include them.

## Provision the separate directory

For the supplied service template, create a private directory before enabling it:

```sh
sudo install -d -m 700 -o policylens -g policylens /var/lib/policylens-checkpoints
```

Set these in the same private environment as the running service:

```dotenv
CHECKPOINT_DIRECTORY=/var/lib/policylens-checkpoints
CHECKPOINT_INTERVAL_SECONDS=300
SECURITY_KEY_PATH=/etc/policylens/security.key
```

Provision and protect the original installation key using `TRUST_OPERATIONS.md`.
Keep a private recovery copy separate from the database backups. Missing original
keys are not regenerated when retained anchors exist. Do not change that key or
reuse a different signing identity without an explicit key-transition procedure.

The configured directory must resolve outside `DATABASE_PATH`'s parent. It cannot
be a subdirectory of installation data, and workspace paths cannot redirect through
symlinks/junctions. Linux directory permissions must be 0700. On Windows restrict
the directory ACL to the service/current user and SYSTEM. The service template
permits writes to `/var/lib/policylens-checkpoints`; other deployment paths need
an equivalent explicit systemd allowance.

The installation and checkpoint directories are deliberately separate. A restore
to a historical database can conflict with later retained anchors. That is a
rollback warning, not a reason to delete or reset the anchors. Restore into an
isolated installation and reconcile the recovery point with the trusted evidence
before any production cutover.

## Export and verify

The Audit page shows configuration, last retained anchor, signing fingerprint and
unanchored event count. `Export signed audit bundle` takes a consistent snapshot,
retains its anchor and downloads the complete verified chain as JSON. Read-only
auditors may export; signing this server-generated evidence grants no authority to
approve controls or decide cases. Download failures are shown in the interface.

Operator equivalents, using the service's private environment:

```sh
python manage.py checkpoint --workspace YOUR_WORKSPACE_UUID --output /private/audit-bundle.json
python manage.py verify-checkpoint /private/audit-bundle.json --fingerprint TRUSTED_SHA256_FINGERPRINT
```

Output files are created exclusively; an existing file is never overwritten. The
verifier needs no server access, database or signing secret. It verifies the pinned
public identity, signature, event fields, contiguous sequence, every audit hash and
exact signed head. Missing events, altered records and unsigned tails fail.

A key embedded in an untrusted bundle is not its own trust root. Obtain the
fingerprint independently before verifying it. The verifier prints only the
result, workspace ID and hashes/counts, not business data.

## Failure behavior and pilot bounds

The authenticated health response includes checkpoint status. Capture/verification
failures are logged without private data and make readiness fail until a successful
capture clears them. The worker does not substitute a new key, discard a conflicting
anchor or fabricate a successful attestation. An export-size refusal is distinct:
it does not poison otherwise successful automatic retention.

The pilot verifies at most 100,000 audit events and retains at most 100,000 checkpoint
files per workspace before requiring an explicit scale/retention decision. Full
JSON exports have an 8 MB estimated payload bound and offline CLI input is bounded
to 16 MB. Larger scoped sponsor evidence packs are a later master-plan phase.

The stored timestamp is the host's reported time; there is no third-party timestamp
authority. A host administrator who controls the signing key can forge signatures.
Keep independently trusted fingerprints and exported anchors/bundles off-machine
for stronger assurance. No external upload or messaging is performed automatically
by this checkpoint feature.

Implementation uses the installed cryptography library's
[Ed25519 signing and verification API](https://cryptography.io/en/latest/hazmat/primitives/asymmetric/ed25519/).
