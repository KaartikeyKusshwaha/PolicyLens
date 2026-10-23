# Oracle governance deployment checkpoint, 23 October 2026

PR #2 merged into main as `210ffd2dcaf27ce665dab016a4d02f1fbe830ff8`.
Its tree matches tested source `981de5e14b219efdf138aa2e38fa2d964156a852`.
Both exact-head CI runs passed (`39977736919`, `39977729927`).

Oracle CLI authentication was renewed. The VM was running; SSH was limited to
the original connection's address. Adding the current connection as a single
IPv4 `/32` restored verified-host SSH without opening SSH globally or changing
HTTP/HTTPS rules. This may need updating again if the connection address changes.

The existing service/Caddy were active. Daily backup logs proved successful runs
on 21–23 October. A fresh pre-upgrade snapshot was transferred over verified SSH,
encrypted off-machine and verified. Original code, environment and plaintext
storage remain preserved for rollback and require later retention reconciliation.

The reviewed source and freshly built frontend were staged in a separate release
directory. All 281 source/build file hashes matched its manifest. SQLCipher 4.19
loaded on the actual VM. The owner installation had one user/one workspace and
no installation key; a new 32-byte key was provisioned separately with an
independently recovered Windows copy restricted by ACL. No key bytes are in this
document, Git or backup archives.

Both databases migrated into a new encrypted snapshot and passed integrity and
guarded restore into a separate directory. Full source table-row inventories
still matched the snapshot immediately before switching. Sessions were revoked.
The hardened service now runs the new release with SQLCipher, an external
checkpoint root and external deletion-history root. Startup, readiness and
unauthenticated customer denial passed. HTTPS index, JavaScript and CSS hashes
match the reviewed local build. These checks do not establish authenticated or
browser acceptance.

The first post-deployment daily backup staged database, deletion and checkpoint
history successfully. Its initial SSH pull exposed a real configuration defect:
the exporter did not inherit systemd's `/etc/policylens.env`. The exporter hotfix
explicitly loads that fixed private root-owned environment, without printing it.
The deployed release therefore includes the reviewed tree plus the exporter
patch recorded in the follow-up branch; do not call it an unmodified release.

The combined off-machine receiver subsequently verified both SQLCipher databases,
authenticated deletion history, signed checkpoint history and cross-copy
consistency. A separate restore drill from those encrypted off-machine archives
restored both DBs, recovered the external anchor and deletion state, and passed
runtime suppression checks. The actual pilot has zero deletion receipts and one
audit anchor at sequence zero; populated deletion/audit recovery is not proved
by this drill. No live browser or model acceptance is implied.

The Windows daily 09:00 task was installed only after a complete successful pull.
It runs while the user is signed in. A manually triggered task completed, but the
next daily trigger has not yet occurred. D: was below the watchdog's 1 GiB floor,
so the new daily receiver was moved to the owner's C: recovery directory and
the task configuration was updated. Recovery keys remain outside archive roots.
No notification delivery path has been configured or message sent.

The first console-based task launch was interrupted (`0xC000013A`). Switching
the task to the matching `pythonw.exe`, with an explicit working directory,
produced an actual scheduler exit code `0` and a fresh successful receiver
receipt. The source installer now selects that background launcher; SSH children
also use `CREATE_NO_WINDOW` on Windows. Manual initial validation still uses
console Python synchronously before task registration. The final watchdog passed
readiness, database archive, both history archives and the disk floor (about
14.9 GB free on C:). This proves a manual scheduler invocation, not the future
daily trigger or notification delivery.

Still open: final populated desktop/mobile browser acceptance, authenticated
production workflow, deployed MCP/provider acceptance, populated load on the
1 GB VM, complete copy/physical retention handling, actual Marble comparison,
partner-selected source, interviews/partners, independent security review and
signed real-data agreement. Automatic briefs remain disabled by the failed gate.
