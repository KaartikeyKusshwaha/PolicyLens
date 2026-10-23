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

Operator installation, actual Oracle/receiver readings, an independent monitor,
notification delivery and deployed backup/restore acceptance remain pending.
