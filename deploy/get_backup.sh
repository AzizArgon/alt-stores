#!/bin/bash
# Downloads the newest server DB backup to _local/backups/server/ and keeps the last 14 there
# (run through get_backup.bat, every day by the Windows Task Scheduler). Must never ask for anything: BatchMode.
set -euo pipefail
SSH_HOST=pcmarket
REMOTE=/opt/alt-stores/data/backups
KEEP=14
# _local: ALT_LOCAL_DIR (set by get_backup.bat), otherwise <repo>/_local
DEST="$(cygpath -u "${ALT_LOCAL_DIR:-$(dirname "$0")/../_local}")/backups/server"
mkdir -p "$DEST"
# Phase 20: ONE ssh connection (the home internet sometimes refuses a quick second one):
# the newest copy comes inside a tar, which also carries its name
ssh -o BatchMode=yes "$SSH_HOST" "cd $REMOTE && tar -cf - \"\$(ls -1t *.db.gz | head -1)\"" > "$DEST/latest.tar.part"
name=$(tar -tf "$DEST/latest.tar.part" | head -1)
[ -n "$name" ] || { rm -f "$DEST/latest.tar.part"; echo "no backup received"; exit 1; }
# A broken download must not replace a good copy or push an old one out of the 14
tar -xOf "$DEST/latest.tar.part" "$name" > "$DEST/$name.part"
rm -f "$DEST/latest.tar.part"
gzip -t < "$DEST/$name.part"
mv "$DEST/$name.part" "$DEST/$name"
gzip -df "$DEST/$name"
echo "saved: $DEST/${name%.gz}"
ls -1t "$DEST"/*.db | tail -n +$((KEEP + 1)) | while read -r old; do rm -f "$old"; echo "removed: $old"; done
