# Operational watchdog

`deploy/watchdog.py` is a read-only operator command that emits bounded JSON and
exits **0** only when every configured check succeeds; failures exit **1**.
Argument-parser errors exit **2**. It does not send email, webhooks or other
messages. Connect its exit status/service failure to your authorized monitoring
system and test the notification path separately.

Run it on the machine receiving the encrypted off-machine backups:

```sh
python deploy/watchdog.py --origin https://YOUR_PILOT_HOST --offsite-directory /private/policylens-offsite --disk-path /private/policylens-offsite
```

Defaults: a 1,024 MiB free-space floor and a 30-hour maximum backup age. Override
with `--min-free-mib` and `--max-backup-age-hours` (1–168). Use a separate disk-path
check/run for the server volume if it differs from the receiver. The command
makes no model calls and does not write receipts or change backup data.

- **Readiness:** GET `/api/ready` with a five-second HTTP timeout. Requires HTTP
  200 and JSON `status: ready`; redirects, login pages, malformed/oversized bodies,
  TLS/network errors and negative readiness fail. HTTPS is mandatory except for
  HTTP loopback. URLs may not contain credentials, paths, queries or fragments.
  Proxy environment variables are ignored; no account or agent key is sent.
  Readiness detects identity storage failure, missing/damaged registered tenant
  databases, terminated worker and recorded checkpoint failures. Every tenant,
  including uncached ones, is opened read-only and its core tables queried; the
  probe never initializes replacement storage. Identity file presence is checked
  before session lookup. It does not run full database integrity checks or prove
  every business workflow works. Probe cost grows with the tenant count.
- **Backup:** both `last-attempt.json` and `last-success.json` must describe the
  same successful completed attempt and archive. A newer failed attempt stays a
  failure even if an older success exists. Both completion and snapshot timestamps
  must be aware and within the age limit; more than five minutes of future clock
  skew fails. The referenced encrypted archive must have the exact saved byte
  count and SHA-256. Symlinks/redirected parents, unsafe filenames, missing files,
  oversized/malformed receipts and absent integrity metadata fail closed.
- **Disk:** the requested path must be readable and have at least the configured
  free bytes. A readiness or backup failure does not skip the other checks.

The backup receiver now writes `encrypted_bytes` and `encrypted_sha256` after its
existing decrypt-and-database verification. Older receipts without those fields
do not pass: complete a new successful transfer before enabling this watchdog.
Receipts are bounded at 64 KiB and the watchdog's encrypted artifact at 192 MiB,
covering the receiver's 128 MiB plaintext archive bound plus Fernet overhead.

The report exposes check codes and disk byte counts, without printing origins,
paths, backup contents, provider exceptions or credentials. It does not decrypt
archives on each run, authenticate unsigned receipt metadata against a malicious
host, prove that storage is independently off-machine, or prove recovery works.
It also does not monitor external deletion-state freshness or replace the current
independently retained deletion guard digest.

## Optional deletion and checkpoint archive checks

For a combined receiver, add `--deletion-state-directory PRIVATE_HISTORY_DIRECTORY`
and/or `--checkpoint-directory PRIVATE_CHECKPOINT_ARCHIVE_DIRECTORY`. These paths
refer to encrypted receiver archives, not the application's runtime state roots.
Each configured family becomes a required check. The latest success/attempt
receipts must agree on that family's complete metadata and successful outcome;
the source timestamp must be fresh and its exact ciphertext file must match saved
size/SHA-256. Unsafe names, mismatched bundle identity, missing metadata, absent
archives, same-size byte changes and failed latest attempts report unhealthy.
No signing, installation or archive-decryption key is needed by the watchdog.

Both history receivers now record encrypted size/hash; older successful receipts
without these fields require a new verified transfer. These checks verify retained
bytes against local receipts, not signatures or decrypted content on each run.
They do not detect changes to old history bundles not referenced by the latest
receipt, prove current source history between stages, or replace independently
trusted fingerprints/digests and full receiver/recovery verification.

To use the optional checks in the Linux timer, configure an explicit reviewed
`ExecStart` override including the selected private archive directories. The base
template continues checking database backup only. A source update does not modify
installed units; verify healthy and failure states before enabling monitoring.

## Optional Linux timer

Source templates `deploy/policylens-watchdog.service` and `.timer` run every five
minutes and log JSON/service failures to journald. They are **not installed** by
this change. On a Linux receiver, provision a least-privilege `policylens-backup`
account that can read the encrypted backup directory, and configure:

```text
# /etc/policylens-watchdog.env, owned privately by the operator
POLICYLENS_ORIGIN=https://YOUR_PILOT_HOST
POLICYLENS_OFFSITE_DIRECTORY=/var/lib/policylens-offsite
```

Adjust the repository/venv paths and account to the actual receiver. The hardened
unit cannot read home directories, so use a private `/var/lib/...` location.
Run the exact command manually and prove both healthy and injected failure
states before installing/enabling the timer. Inspect failures with
`journalctl -u policylens-watchdog.service`; check timer activity with
`systemctl list-timers policylens-watchdog.timer`. Journald is an operator-visible
failure record, not a claim that anyone received an external notification.

## Installed Windows receiver monitor (2026-10-24 local)

`deploy/install_watchdog.ps1` installs `PolicyLens-Operational-Watchdog` every
five minutes using the matching `pythonw.exe`, an explicit repository working
directory, limited privileges and an interactive user session. It requires a
healthy manual baseline before registration, ignores overlapping runs and limits
execution to two minutes. The computer must be awake and the user signed in.

The actual receiver task was installed and manually triggered; Task Scheduler
returned exit zero and a fresh report at `2026-10-23T18:58:43.142885+00:00`.
All five checks passed against the Oracle HTTPS pilot and the encrypted database,
deletion-history and checkpoint-history archives under
`C:\Users\LENONO\PolicyLens-Recovery\daily`. Free receiver disk space was about
22 GB, above the 1 GiB floor. This is a triggered scheduled invocation, not proof
of the next unattended daily backup or continuous availability.

The optional `--report-directory` must be an existing private directory. Reports
replace `latest.json` atomically; failures also replace `last-failure.json`, which
survives a later healthy run. These two bounded reports are retained; opting into
Telegram also retains one bounded notification-state file. Actual
reports are under `C:\Users\LENONO\PolicyLens-Recovery\monitor`, restricted to
the current user and SYSTEM. Report-write failure exits 2 rather than claiming
healthy operation. An isolated invocation with an intentionally impossible disk
floor exited 1 and retained `disk_below_floor`; actual archive receipts were not
modified. Focused tests also verify failure retention after recovery.

Telegram notification support is implemented as described below, but actual bot
credentials, pairing and delivery are still pending. This local receiver monitor
is not an independent availability service. Backup/restore
evidence and its remaining limits are recorded in `DEPLOYED_CHECKPOINT_20261023.md`.

## Optional Telegram alerts

Telegram was selected by the operator. `--telegram-config PRIVATE_JSON` opts in
using exactly two private fields: `bot_token` and numeric `chat_id` (as strings).
It requires `--report-directory`; keep the configuration outside the repository,
archive directories and report directory, with POSIX mode 0600 or an equivalent
private Windows ACL. The prepared local file is
`C:\Users\LENONO\PolicyLens-Recovery\telegram.json`, restricted to the user and
SYSTEM. It contains blank values until the operator pairs a bot. No token is
passed in process arguments or printed.

Create a dedicated bot through official [BotFather](https://t.me/BotFather), then
run this in an interactive local terminal from the repository root:

```powershell
.venv\Scripts\python.exe deploy/setup_telegram.py --config C:\Users\LENONO\PolicyLens-Recovery\telegram.json --report-directory C:\Users\LENONO\PolicyLens-Recovery\monitor
```

The helper prompts for a hidden token, prints a random pairing message, and asks
the operator to send it to the bot in a **private** chat. It selects exactly that
message's private chat; unrelated/old messages or groups cannot select the
recipient. Ambiguous matches fail. It does not remove a webhook, acknowledge
updates by advancing their offset or overwrite an existing nonblank configuration.
It preserves the prepared Windows file ACL, saves the configuration and sends an
explicit test. A successful API response proves Telegram accepted the message,
not that the person read it. The operator must verify the intended recipient.

After successful pairing, rerun `install_watchdog.ps1` with the existing verified
arguments plus `-TelegramConfig C:\Users\LENONO\PolicyLens-Recovery\telegram.json`.
Pairing alone does not update the installed task. An explicit later test can use
the normal watchdog arguments plus `--telegram-config ... --test-telegram`; a test
does not alter incident state or suppress an actual failure.

The first healthy run establishes a quiet baseline. A failure or changed failure
sends check names/codes; recovery sends a single recovery message. Unchanged
results are suppressed. No customer/case data, raw errors, local paths, archive
contents or credentials enter the text. `telegram-state.json` contains only a
schema, opaque destination digest and incident digest. Delivery failure leaves
the last accepted state unchanged for the next run to retry, and exits 2 even if
operational checks are healthy. The normal local reports preserve that failure.
Health failures still exit 1 when notification delivery succeeds.

Requests use only the official HTTPS Bot API, bounded responses, no proxy
inheritance, no redirects and no automatic HTTP retries. Telegram rejection,
network errors, malformed/oversized responses, invalid private configuration and
corrupt state return a generic failure without exposing the token-bearing URL.
An acknowledgement lost after remote acceptance, or a local state-write failure,
can cause a duplicate on the next run; exactly-once delivery is not claimed.
No periodic reminders or inbound bot commands are implemented. The receiver must
still be awake and signed in. See Telegram's [sendMessage API](https://core.telegram.org/bots/api#sendmessage).
