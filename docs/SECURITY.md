# PolicyLens security overview

Status: 23 October 2026. This is an implementation summary, not a certification.
The governance changes in draft PR #2 have not been deployed to the Oracle pilot.
Current production authentication, backups and storage protections require fresh
operator acceptance. Use synthetic or non-production data until independent
security review, remediation and a signed data-handling agreement are complete.

| Boundary | Implemented behavior and limits |
| --- | --- |
| Human access | Invite-only workspace membership, role checks, hashed sessions, CSRF/origin checks and secure cookies in public mode. Optional account TOTP MFA has encrypted seeds, replay prevention and hashed single-use recovery codes. MFA is not enforced organization-wide; SSO is outside scope. |
| Agent authority | Per-agent scoped, expiring, revocable keys with request/run limits. Tools can read, draft or request approval. They cannot approve/activate controls, close cases, file reports or execute payments. Human maker-checker and case-review separation remain required. |
| Database storage | Explicit SQLCipher 4 mode encrypts identity and tenant files with purpose-derived keys. It refuses wrong/missing keys and plaintext fallback. Offline migration preserves originals; encrypted restore revokes credentials and rebases tenant paths. Default mode is plaintext for compatibility; production migration is unverified. Old plaintext copies remain until deliberately removed. |
| Key custody | The raw installation key is separate from database snapshots and required for MFA, database decryption and audit signing derivations. Preserve its protected recovery copy. Off-machine archive encryption uses a separate Fernet key. POSIX key mode is 0600; Windows ACLs require operator provisioning. No implemented rotation or key-loss bypass exists. |
| Backups | Source includes verified SSH export, freshness/path/size/hash/integrity checks and encrypted off-machine archives. SQLCipher verification needs the original installation recovery key and stages only ciphertext; decrypted pages stay in memory. First transfer must succeed before task registration. Live scheduling and operator recovery drills remain unverified. |
| Evidence integrity | Hash-linked audit, Ed25519 external checkpoints, signed PDF/JSON evidence archives and independent trusted-fingerprint verification detect covered tampering. External checkpoint storage must be configured. Same-host copies do not survive signing-key/host compromise; off-machine checkpoint retention is still pending. |
| Model exposure | Groq receives bounded selected context. Optional pseudonymization masks structured identifiers; it is not full anonymization of free text. Runs retain model/configured revision and reject explicit mismatches. A provider-unreported revision does not prove immutable model weights. Citation checks cannot establish every narrative inference. |

Retention policy versions and legal holds now have independent human approval
and release review in source; pending release holds remain effective. Deletion
inventory previews bind candidate hashes, policy/holds and age while flagging
shared references. A manual custody register adds preservation deadlines,
independent removal authorization and custodian-report confirmation, with repeated
hold/policy checks. Automatic copy discovery/registration, deletion execution and
complete reconciliation remain unfinished. Confirmed reports are human attestations,
not automated proof of physical erasure.
No automated deletion or complete erasure guarantee is claimed. See
[retention status](RETENTION.md). Backups, snapshots, exports and downstream copies
need a unified retention procedure. Tenant databases
isolate application workspaces, not a hostile host administrator. One Python worker
and SQLite are the pilot architecture; HA, multiworker operation and SSO are parked.

Automated tests cover isolation, permission denials, MFA/replay, key failures,
migration, archive tampering and isolated recovery. They do not prove production
configuration, real-model accuracy, regulatory compliance or independent review.
Production browser acceptance waits until implementation is finished. See
[implementation gates](IMPLEMENTATION.md), [key/migration details](DATABASE_ENCRYPTION.md),
[operator procedures](TRUST_OPERATIONS.md) and [checkpoint limits](EXTERNAL_CHECKPOINTS.md).
