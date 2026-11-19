#!/bin/bash
# Updates the public site with one command (run through deploy.bat on the laptop). Only from the alpha branch.
# push -> images built here -> ONE ssh connection: loaded on the server -> backup of the DB -> "current" becomes "previous" -> up -> check.
# The server database (data/database.db) is never replaced: only images and docker-compose.yml change.
set -euo pipefail
cd "$(dirname "$0")/.."
SITE=https://pcmarket.khudoberdi.uz
SSH_HOST=pcmarket   # alias from ~/.ssh/config (docs/deploy.md)
DIR=/opt/alt-stores
PLATFORM=linux/amd64  # the server CPU (uname -m = x86_64)
IMAGES="alt-stores-backend alt-stores-web"

step() { echo; echo "=== $*"; }
# Docker on the laptop = Docker Engine inside WSL (Ubuntu in F:\wsl\ubuntu, docs/deploy.md); the repo is /mnt/f/... there
docker() { MSYS_NO_PATHCONV=1 wsl.exe -d Ubuntu --exec docker "$@"; }

# The server is the alpha branch. Development goes on in main and reaches the server only on the author's word
branch=$(git rev-parse --abbrev-ref HEAD)
if [ "$branch" != alpha ]; then
    echo "REFUSED: the server gets only the alpha branch, this is '$branch'. Nothing was changed."
    exit 1
fi
# The images are built from these files: uncommitted changes would reach the site without being in alpha
if [ -n "$(git status --porcelain)" ]; then
    echo "REFUSED: uncommitted changes. Commit or remove them first. Nothing was changed."
    git status --short
    exit 1
fi
# WSL starts on the first call; the Docker service needs a few seconds after that
for i in $(seq 1 15); do docker info >/dev/null 2>&1 && break; sleep 2; done
docker info >/dev/null 2>&1 || { echo "REFUSED: Docker in WSL does not answer (wsl -d Ubuntu docker info). Nothing was changed."; exit 1; }
tag=$(git rev-parse --short HEAD)

step "1/6 git push"
git push origin alpha

step "2/6 build images $tag ($PLATFORM)"
docker build --platform "$PLATFORM" -t "alt-stores-backend:$tag" ./backend
docker build --platform "$PLATFORM" -t "alt-stores-web:$tag" ./frontend

# Phase 20: ONE ssh connection for the whole server part. The home internet sometimes refuses a quick second
# connection, so the images go over stdin and the script, docker-compose.yml and the rate ride in the command.
step "3/6 CBU rate (cbu.uz answers only Uzbek addresses: the laptop fetches it and hands it to the server)"
rate_b64=""
if usd=$(curl -sf -m 15 https://cbu.uz/ru/arkhiv-kursov-valyut/json/USD/); then
    rate_b64=$(printf '%s' "$usd" | base64 -w0)
    echo "rate fetched"
else
    echo "cbu.uz did not answer: the server keeps the last known rate"
fi
compose_b64=$(base64 -w0 < docker-compose.yml)

step "4/6 one ssh connection: upload images, backup, switch images, start"
# The script reads the images from stdin first; after that stdin is /dev/null for every other command
remote=$(base64 -w0 <<'EOF'
set -euo pipefail
cd "$DIR"
gunzip | docker load
exec </dev/null
echo "$COMPOSE_B64" | base64 -d > docker-compose.yml.new
if [ -n "$(docker compose ps -q backend 2>/dev/null)" ]; then
    docker compose exec -T backend python scripts/backup_db.py before_deploy 5
fi
mv docker-compose.yml.new docker-compose.yml
# Phase 14: photos live in data/media (made here by the owner of data/, so the backend user can write there)
mkdir -p data/media
# current -> previous (kept for a rollback), the new one -> current; the version before previous is removed
for img in $IMAGES; do
    old=$(docker image inspect -f '{{.Id}}' "$img:previous" 2>/dev/null || true)
    if docker image inspect "$img:current" >/dev/null 2>&1; then docker tag "$img:current" "$img:previous"; fi
    docker tag "$img:$TAG" "$img:current"
    docker rmi "$img:$TAG" >/dev/null
    if [ -n "$old" ] && [ "$old" != "$(docker image inspect -f '{{.Id}}' "$img:previous")" ]; then
        docker rmi "$old" >/dev/null 2>&1 || true
    fi
done
docker compose up -d
# The running containers must be the new images
for svc in backend web; do
    [ "$(docker inspect -f '{{.Image}}' "$(docker compose ps -q "$svc")")" = \
      "$(docker image inspect -f '{{.Id}}' "alt-stores-$svc:current")" ] || { echo "$svc is not on the new image"; exit 1; }
done
echo "SWITCHED $TAG"
echo; echo "=== 5/6 wait for the site, CBU rate"
for i in $(seq 1 30); do
    if curl -sf http://127.0.0.1:8095/api/health >/dev/null; then echo "site is up"; break; fi
    [ "$i" = 30 ] && { echo "The site did not start, logs:"; docker compose logs --tail 40; exit 1; }
    sleep 2
done
if [ -n "$RATE_B64" ]; then echo "$RATE_B64" | base64 -d | docker compose exec -T backend python scripts/set_rate.py; fi
echo "SERVER DONE $TAG"
EOF
)
log=$(mktemp)
if ! docker save "alt-stores-backend:$tag" "alt-stores-web:$tag" | gzip -1 | \
     ssh -o ServerAliveInterval=30 -o ServerAliveCountMax=10 "$SSH_HOST" \
     "TAG=$tag DIR=$DIR IMAGES='$IMAGES' COMPOSE_B64=$compose_b64 RATE_B64=$rate_b64 bash -c \"\$(echo $remote | base64 -d)\"" \
     | tee "$log"; then
    if grep -qx "SWITCHED $tag" "$log"; then echo "DEPLOY FAILED after the switch (rollback: rollback.bat)"
    else echo "DEPLOY FAILED on the server before the switch: the site still runs the old version"; fi
    rm -f "$log"; exit 1
fi
# A step that silently cut the script short must not end in "DEPLOY OK"
grep -qx "SERVER DONE $tag" "$log" || { rm -f "$log"; echo "DEPLOY FAILED: the server did not switch to $tag"; exit 1; }
rm -f "$log"

step "6/6 check $SITE"
api=$(curl -s -o /dev/null -w "%{http_code}" -m 20 "$SITE/api/health")
page=$(curl -s -o /dev/null -w "%{http_code}" -m 20 "$SITE/")
echo "site: $page, api: $api"
[ "$api" = 200 ] && [ "$page" = 200 ] || { echo "DEPLOY CHECK FAILED (rollback: rollback.bat)"; exit 1; }
docker rmi "alt-stores-backend:$tag" "alt-stores-web:$tag" >/dev/null 2>&1 || true
echo "DEPLOY OK"
