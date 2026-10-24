# Account authentication

On 24 October 2026 the owner explicitly removed two-factor authentication from
PolicyLens and retained normal sign-in. This supersedes MFA items in the original
master plan and dated implementation/acceptance records. SentinelOps is outside
this change.

Accounts sign in with email and password. Passwords remain scrypt-hashed;
authenticated sessions, expiry, logout, CSRF/origin protections, login throttling,
invite-only membership and workspace roles remain. Existing-account invitations
still require the existing account password. Password changes verify the current
password and revoke other sessions. Operator-issued password reset links remain
short-lived and single-use, and reset revokes existing sessions. Creating a scoped
agent key still requires password confirmation.

Authenticator enrollment, factor verification, recovery-code management and their
API/UI are removed. Old factor records are not consulted during authentication or
password changes. Existing databases and historical backups may retain obsolete
encrypted factor rows and audit events; this rollout does not erase historical
records or modify their audit history. Restore retains compatibility with those
snapshots without re-enabling two-factor authentication.

The original installation key remains required for SQLCipher databases, protected
integration values and audit-signing derivations. Removing account 2FA does not
remove encryption, reset passwords, replace installation keys or grant agent
approval authority. Independent security review and real-data release gates
remain open.
