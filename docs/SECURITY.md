# PolicyLens security overview

Status: 24 October 2026. This is an implementation summary, not a certification.
The [independent review handoff](SECURITY_REVIEW_HANDOFF.md) records proposed
scope, evidence and required reviewer outputs; no independent review has occurred.
Governance source is deployed to Oracle with SQLCipher, separate key recovery,
verified off-machine transfer and a receiver monitor. Deployed synthetic browser
acceptance is partial; password/session and owner-workspace acceptance
remain unverified. See `DEPLOYED_CHECKPOINT_20261023.md` and `RELEASE_READINESS.md`.
Use synthetic or non-production data until independent
security review, remediation and a signed data-handling agreement are complete.

| Boundary | Implemented behavior and limits |
| --- | --- |
| Human access | Email/password sign-in, invite-only workspace membership, role checks, hashed sessions, throttling, CSRF/origin checks and secure cookies in public mode. Account 2FA was removed at the owner's request; SSO remains outside scope. See ACCOUNT_AUTHENTICATION.md. |
| Agent authority | Per-agent scoped, expiring, revocable keys with request/run limits. Tools can read, draft or request approval. They cannot approve/activate controls, close cases, file reports or execute payments. Human maker-checker and case-review separation remain required. |
| Database storage | Explicit SQLCipher 4 mode encrypts identity and tenant files with purpose-derived keys. It refuses wrong/missing keys and plaintext fallback. Actual Oracle migration and separate off-machine restore passed. Restore revokes credentials and rebases tenant paths. Default mode remains plaintext for compatibility. Original plaintext copies were preserved during migration and remain outside the encrypted-live-data guarantee. |
| Key custody | The raw installation key is separate from database snapshots and required for protected integration data, database decryption and audit signing derivations. Preserve its protected recovery copy. Off-machine archive encryption uses a separate Fernet key. POSIX key mode is 0600; Windows ACLs require operator provisioning. No implemented rotation or key-loss bypass exists. |
| Backups | Verified SSH export, freshness/path/size/hash/integrity checks and encrypted off-machine database/history transfer passed; a separate restore drill passed. The installed Windows pull task had a successful triggered invocation; its next daily trigger remains unobserved. Receiver checks run every five minutes while signed in, with local reports. No external notifications are configured. SQLCipher verification needs the original installation recovery key and stages ciphertext. |
| Evidence integrity | Hash-linked audit, Ed25519 external checkpoints and signed PDF/JSON archives detect covered tampering relative to trusted fingerprints/heads. Actual external checkpoint configuration, encrypted off-machine history transfer and recovery passed; a separate populated local restore verified 77 entries. Same-host copies do not survive signing-key/host compromise; retained trust material and receiver custody remain operator responsibilities. |
| Model exposure | Groq receives bounded selected context. Optional pseudonymization masks structured identifiers; it is not full anonymization of free text. Runs retain model/configured revision and reject explicit mismatches. A provider-unreported revision does not prove immutable model weights. Citation checks cannot establish every narrative inference. |

Retention policy versions and legal holds now have independent human approval
and release review in source; pending release holds remain effective. Deletion
inventory previews bind candidate hashes, policy/holds and age while flagging
shared references. A manual custody register adds preservation deadlines,
independent removal authorization and custodian-report confirmation, with repeated
hold/policy checks. Explicit application exports/backups register custody and exact
content hashes automatically. Historical/offline discovery and complete copy
reconciliation remain unfinished. Independent deletion-plan review pins inventory
and refuses stale/blocked approval. A stopped-installation SQLCipher operator
command can remove exact eligible operational rows after publishing external
suppression; interrupted execution blocks restart pending reconciliation. This
does not certify discovery completeness or physical erasure. Confirmed reports are human attestations,
not automated proof of physical erasure.
No automated deletion or complete erasure guarantee is claimed. See
[retention status](RETENTION.md). Backups, snapshots, exports and downstream copies
need a unified retention procedure. Tenant databases
isolate application workspaces, not a hostile host administrator. One Python worker
and SQLite are the pilot architecture; HA, multiworker operation and SSO are parked.

Automated tests cover isolation, permission denials, password/session lifecycle, key failures,
migration, archive tampering and isolated recovery. They do not prove production
configuration, real-model accuracy, regulatory compliance or independent review.
The final deployed synthetic browser pass is in progress after implementation;
its observed results and remaining scenarios are in `BROWSER_ACCEPTANCE_20261023.md`. See
[implementation gates](IMPLEMENTATION.md), [key/migration details](DATABASE_ENCRYPTION.md),
[operator procedures](TRUST_OPERATIONS.md) and [checkpoint limits](EXTERNAL_CHECKPOINTS.md).
