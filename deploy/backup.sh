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
systemctl start policylens
trap - EXIT
# Only this service's dated snapshot directories; keep at least fourteen days.
find /var/backups/policylens -mindepth 1 -maxdepth 1 -type d \
    -name 'snapshot-????????T??????Z' -mtime +13 -exec rm -rf -- {} +
