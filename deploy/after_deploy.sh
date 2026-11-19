#!/bin/bash
# After a deploy or before a demo (run through after_deploy.bat): ONE ssh connection that
# counts the data, re-checks the "below market" flags, refreshes the demo builds (--builds-only --no-photos),
# counts again (stores, accounts, offers, Age offers must stay the same) and shows memory and disk.
# Does not touch Age Computers, prices or passwords; no duplicate/category scripts here.
set -euo pipefail
# The script rides in the command (base64), not on stdin: so every command inside may get stdin = /dev/null
remote=$(base64 -w0 <<'EOF'
set -uo pipefail
cd /opt/alt-stores
exec </dev/null
counts() { docker compose exec -T backend python -c "
import sqlite3; c=sqlite3.connect('/data/database.db'); q=lambda s:c.execute(s).fetchone()[0]
a=c.execute(\"select id from stores where name like 'Age%' and is_demo=0\").fetchone()
print('stores',q('select count(*) from stores'),'| accounts',q('select count(*) from users'),'| offers',q('select count(*) from offers'),'| Age offers',q(f'select count(*) from offers where store_id={a[0]}') if a else '-')"; }
echo "=== data before"; before=$(counts); echo "$before"
echo "=== recheck_flags.py"; docker compose exec -T backend python scripts/recheck_flags.py 2>&1 | tail -5
echo "=== seed_demo.py --builds-only --no-photos"; docker compose exec -T backend python scripts/seed_demo.py --builds-only --no-photos 2>&1 | tail -5
echo "=== data after"; after=$(counts); echo "$after"
[ "$before" = "$after" ] && echo "DATA SAME: OK" || echo "DATA CHANGED - compare the two lines above"
echo "=== containers"; docker compose ps --format '{{.Name}}: {{.Status}}'
echo "=== memory (MB)"; free -m | head -2
echo "=== disk"; df -h / | tail -1; docker system df
EOF
)
ssh -o ServerAliveInterval=30 pcmarket "bash -c \"\$(echo $remote | base64 -d)\""
