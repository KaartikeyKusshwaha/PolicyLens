#!/bin/bash
# Offline, verified snapshots: a brief daily pause, followed by an automatic restart.
set -euo pipefail
umask 077
backup_root=/var/backups/policylens
install -d -m 700 "$backup_root"
systemctl is-active --quiet policylens
trap 'systemctl start policylens' EXIT
systemctl stop policylens
snapshot="$backup_root/snapshot-$(date -u +%Y%m%dT%H%M%SZ)"
cd /opt/policylens
.venv/bin/python manage.py backup --output "$snapshot"
if [[ -n "${DELETION_STATE_DIRECTORY:-}" ]]; then
    .venv/bin/python deploy/deletion_state_backup.py stage
fi
systemctl start policylens
trap - EXIT
# Retained snapshots may be subject to approved preservation periods and holds.
# Removal requires reconciled copy custody and explicit operator evidence. Do
# not prune by age alone. Monitor free space and follow the retention procedure.
