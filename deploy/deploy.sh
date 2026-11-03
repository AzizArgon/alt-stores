#!/bin/bash
# Updates the public site with one command (run through deploy.bat on the laptop). Only from the alpha branch.
# push -> images built here -> loaded on the server -> backup of the DB -> "current" becomes "previous" -> up -> check.
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

step "3/6 upload images and docker-compose.yml"
docker save "alt-stores-backend:$tag" "alt-stores-web:$tag" | gzip -1 | ssh "$SSH_HOST" 'gunzip | docker load'
scp -q docker-compose.yml "$SSH_HOST:$DIR/docker-compose.yml.new"

step "4/6 server: backup, switch images, start"
ssh "$SSH_HOST" "TAG=$tag DIR=$DIR IMAGES='$IMAGES' bash -s" <<'EOF'
set -euo pipefail
cd "$DIR"
if [ -n "$(docker compose ps -q backend 2>/dev/null)" ]; then
    docker compose exec -T backend python scripts/backup_db.py before_deploy 5
fi
mv docker-compose.yml.new docker-compose.yml
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
EOF

step "5/6 wait for the site, CBU rate"
for i in $(seq 1 30); do
    if ssh "$SSH_HOST" 'curl -sf http://127.0.0.1:8095/api/health >/dev/null'; then echo "site is up"; break; fi
    [ "$i" = 30 ] && { echo "The site did not start, logs:"; ssh "$SSH_HOST" "cd $DIR && docker compose logs --tail 40"; exit 1; }
    sleep 2
done
# cbu.uz answers only Uzbek addresses: the laptop fetches the rate and hands it to the server
if usd=$(curl -sf -m 15 https://cbu.uz/ru/arkhiv-kursov-valyut/json/USD/); then
    echo "$usd" | ssh "$SSH_HOST" "cd $DIR && docker compose exec -T backend python scripts/set_rate.py"
else
    echo "cbu.uz did not answer: the server keeps the last known rate"
fi

step "6/6 check $SITE"
api=$(curl -s -o /dev/null -w "%{http_code}" -m 20 "$SITE/api/health")
page=$(curl -s -o /dev/null -w "%{http_code}" -m 20 "$SITE/")
echo "site: $page, api: $api"
[ "$api" = 200 ] && [ "$page" = 200 ] || { echo "DEPLOY CHECK FAILED (rollback: rollback.bat)"; exit 1; }
docker rmi "alt-stores-backend:$tag" "alt-stores-web:$tag" >/dev/null 2>&1 || true
echo "DEPLOY OK"
