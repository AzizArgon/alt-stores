#!/bin/bash
# One-time move of the site from the systemd service (/opt/pcmarket) to Docker (/opt/alt-stores). Run by the author:
#   ssh -t pcmarket 'sudo bash /home/azi/alt-stores-new/migrate_to_docker.sh'
# Prepared beforehand without sudo: /home/azi/alt-stores-new/{docker-compose.yml,.env}, images alt-stores-*:current.
# If anything fails, the old service is started again and nginx gets its old file back: the site never stays broken.
# Only our things are touched: pcmarket.service, /opt/alt-stores, /etc/nginx/snippets/pcmarket-app.conf.
set -euo pipefail
NEW=/home/azi/alt-stores-new
DIR=/opt/alt-stores
OLD=/opt/pcmarket
SNIP=/etc/nginx/snippets/pcmarket-app.conf
STAMP=$(date +%F_%H%M)
[ "$(id -u)" = 0 ] || { echo "Run with sudo"; exit 1; }
[ -f "$NEW/docker-compose.yml" ] && [ -f "$NEW/.env" ] && [ -f "$NEW/pcmarket-app.conf" ] || { echo "Not prepared: $NEW"; exit 1; }

rollback() {
    echo "!!! FAILED - returning the old site"
    [ -f "$SNIP.bak-$STAMP" ] && cp "$SNIP.bak-$STAMP" "$SNIP" && nginx -t && systemctl reload nginx
    (cd "$DIR" 2>/dev/null && sudo -u azi docker compose down) || true
    systemctl start pcmarket
    echo "Old site is back (pcmarket.service). Nothing was deleted."
}
trap rollback ERR

echo "=== 1/5 folder $DIR (owner azi)"
install -d -o azi -g azi -m 750 "$DIR" "$DIR/data" "$DIR/data/samples" "$DIR/data/backups"
install -o azi -g azi -m 644 "$NEW/docker-compose.yml" "$DIR/docker-compose.yml"
install -o azi -g azi -m 600 "$NEW/.env" "$DIR/.env"

echo "=== 2/5 stop the old service (downtime starts), copy the database"
systemctl stop pcmarket
sudo -u pcmarket "$OLD/app/deploy/backup.sh" before_docker 5
cp "$OLD/app/backend/database.db" "$DIR/data/database.db"
cp "$OLD"/private/* "$DIR/data/samples/"
cp "$OLD"/backups/*.db.gz "$DIR/data/backups/"
chown -R azi:azi "$DIR/data"
chmod 600 "$DIR/data/database.db"

echo "=== 3/5 start the containers"
cd "$DIR"
sudo -u azi docker compose up -d
for i in $(seq 1 45); do curl -sf http://127.0.0.1:8095/api/health >/dev/null && break; sleep 2; done
curl -sf http://127.0.0.1:8095/api/health >/dev/null

echo "=== 4/5 nginx: our snippet -> 127.0.0.1:8095 (copy of the old one: $SNIP.bak-$STAMP)"
cp "$SNIP" "$SNIP.bak-$STAMP"
install -m 644 "$NEW/pcmarket-app.conf" "$SNIP"
nginx -t
systemctl reload nginx

echo "=== 5/5 check (downtime ends)"
sleep 2
for url in https://pcmarket.khudoberdi.uz/api/health https://pcmarket.khudoberdi.uz/ https://khudoberdi.uz/; do
    echo "$(curl -s -o /dev/null -w '%{http_code}' -m 20 "$url")  $url"
done
[ "$(curl -s -o /dev/null -w '%{http_code}' -m 20 https://pcmarket.khudoberdi.uz/api/health)" = 200 ]
trap - ERR
echo "MIGRATION OK. The old service is stopped but kept (fallback: docs/deploy.md)."
