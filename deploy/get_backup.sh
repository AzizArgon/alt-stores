#!/bin/bash
# Downloads the newest server DB backup to _local/backups/server/ and keeps the last 14 there
# (run through get_backup.bat, every day by the Windows Task Scheduler). Must never ask for anything: BatchMode.
set -euo pipefail
SSH_HOST=pcmarket
KEEP=14
# _local: ALT_LOCAL_DIR (set by get_backup.bat), otherwise <repo>/_local
DEST="$(cygpath -u "${ALT_LOCAL_DIR:-$(dirname "$0")/../_local}")/backups/server"
mkdir -p "$DEST"
latest=$(ssh -o BatchMode=yes "$SSH_HOST" 'cd /tmp && sudo -u pcmarket bash -c "ls -1t /opt/pcmarket/backups/*.db.gz | head -1"')
name=$(basename "$latest")
# A broken download must not replace a good copy or push an old one out of the 14
ssh -o BatchMode=yes "$SSH_HOST" "cd /tmp && sudo -u pcmarket cat '$latest'" > "$DEST/$name.part"
gzip -t < "$DEST/$name.part"
mv "$DEST/$name.part" "$DEST/$name"
gzip -df "$DEST/$name"
echo "saved: $DEST/${name%.gz}"
ls -1t "$DEST"/*.db | tail -n +$((KEEP + 1)) | while read -r old; do rm -f "$old"; echo "removed: $old"; done
