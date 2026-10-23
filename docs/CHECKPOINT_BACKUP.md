# Off-machine signed checkpoint history

`deploy/checkpoint_backup.py` exports complete signed external-anchor history,
verifies it against an independently supplied public fingerprint at a receiver,
encrypts it with a separate Fernet key, and reconstructs a new checkpoint root.
This source functionality has been tested on isolated synthetic installations.
No actual off-machine transfer or schedule is installed.

Stop the authoritative installation and select its original configuration/key:

```sh
python deploy/checkpoint_backup.py export > /private/staging/checkpoint-history-UNIQUE.json
```

Export holds the installation lock, captures current audit heads for every
registered workspace, then locks external checkpoint storage and reads **all**
retained documents. It refuses unregistered directories, incomplete/unknown files,
unsafe names and capacity excess. It signs the complete workspace/history roster
with the same Ed25519 identity. No installation keys, account credentials or raw
audit narratives are copied. IDs, timestamps and audit hashes remain private.

Transfer private bytes through an independently verified channel, such as the
existing strict-host-key SSH workflow. On the separate receiver:

```sh
python deploy/checkpoint_backup.py receive --fingerprint INDEPENDENTLY_TRUSTED_CHECKPOINT_FINGERPRINT --key-file /private/keys/offsite-fernet.key --destination /private/checkpoint-history < /private/staging/checkpoint-history-UNIQUE.json
```

The receiver needs a trusted public fingerprint and archive-encryption key, not
the master/signing key. Keep the key outside the destination. The outer signature
binds the complete roster. Every anchor must verify against that fingerprint and
workspace; sequences increase and signed predecessor digests match from the zero
predecessor. Missing/reordered/changed intermediate anchors are refused.

The source timestamp must be aware, at most 30 hours old and at most five minutes
in the future. Receive decrypts and verifies every retained encrypted bundle.
New history cannot predate the newest retained state or omit/rewrite any retained
anchor, even with a valid outer signature. This catches authentic truncation
against preserved history. First receipt still depends on the trusted identity
and source: it cannot prove that an initially received valid prefix is newest.

Ciphertext is written exclusively, flushed and atomically published. Identical
bundles are idempotent. Unknown/pending files, conflicts, wrong keys/fingerprints,
stale data and corruption fail without replacing old archives. Nothing prunes
history. Output includes bundle SHA-256, encrypted filename, fingerprint, anchor
count and per-workspace heads. Retain the **current** digest independently of
archive/database rollback.

## Recovery

```sh
python deploy/checkpoint_backup.py recover --archive /private/checkpoint-history/checkpoint-history-DIGEST.fernet --fingerprint TRUSTED_SIGNING_FINGERPRINT --key-file /private/keys/offsite-fernet.key --destination /private/NEW-checkpoint-root --bundle-sha256 INDEPENDENTLY_RETAINED_CURRENT_BUNDLE_SHA256
```

Recovery requires a new nonredirected directory, trusted fingerprint, archive key
and exact current bundle digest. Disaster recovery may use older creation times;
current selection relies on that separate trust material. All signatures/links
are checked before output creation. Canonical reconstructed documents preserve
signed content and filenames. A durable `restoration.pending` marker remains
until all files/directories are flushed; normal checkpoint operations refuse an
incomplete recovered root. Existing roots/archives are not overwritten or deleted.

Restore matching database data through the normal guarded recovery process,
retain the original installation key, and configure the recovered checkpoint root.
Normal verification still checks DB audit history against the retained head; an
anchor alone cannot prove a restored DB contains that history. Older DB recovery
must fail when it would erase independent evidence.

Bounds: 32 MiB per bundle, 10,000 anchors, 16 KiB per anchor and 2,000 workspaces.
The receiver verifies at most 2,000 bundles/256 MiB total ciphertext. Capacity
refusal never samples history. Full audits/events remain in DB/evidence backups;
this tool preserves independent anchor documents.

Actual off-machine custody, freshness between exports, schedule integration,
deployed recovery and independent review remain pending. Signatures establish
integrity relative to trusted identity, not record truth or resistance to signing
host/key compromise. Joint rollback with stale trust material cannot establish
current history. The tool sends no messages, changes no cloud settings and
performs no physical erasure.
