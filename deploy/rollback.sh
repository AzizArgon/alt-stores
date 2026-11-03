#!/bin/bash
# Returns the site to the previous version (images "previous" kept by deploy.sh); the database is not touched.
# Run through rollback.bat. A second run goes back to the newer version (current and previous swap places).
set -euo pipefail
SSH_HOST=pcmarket
ssh "$SSH_HOST" bash -s <<'EOF'
set -euo pipefail
cd /opt/alt-stores
for img in alt-stores-backend alt-stores-web; do
    docker image inspect "$img:previous" >/dev/null 2>&1 || { echo "No previous version of $img - nothing changed"; exit 1; }
done
for img in alt-stores-backend alt-stores-web; do
    docker tag "$img:current" "$img:swap"
    docker tag "$img:previous" "$img:current"
    docker tag "$img:swap" "$img:previous"
    docker rmi "$img:swap" >/dev/null
done
docker compose up -d </dev/null
for i in $(seq 1 30); do
    curl -sf http://127.0.0.1:8095/api/health >/dev/null && { echo "ROLLBACK OK"; exit 0; }
    sleep 2
done
echo "The site did not start:"; docker compose logs --tail 40 </dev/null; exit 1
EOF
