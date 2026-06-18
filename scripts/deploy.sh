#!/usr/bin/env bash
# deploy.sh — déploiement sur le VPS Hetzner CPX41.
# Prérequis : clé SSH configurée, .env sur le serveur dans /opt/autotransfert-p2/.env
# Usage : ./scripts/deploy.sh <VPS_IP>

set -euo pipefail
VPS_IP="${1:?Usage: $0 <VPS_IP>}"
APP_DIR="/opt/autotransfert-p2"
REPO_URL="https://github.com/tobiags/AUTO-BOT-LBC-PJ2.git"

echo "==> Déploiement sur $VPS_IP"

ssh -o StrictHostKeyChecking=no root@"$VPS_IP" bash <<'REMOTE'
set -euo pipefail

APP_DIR="/opt/autotransfert-p2"

# Clone ou pull
if [ -d "$APP_DIR/.git" ]; then
    echo "-- Pull dernier code"
    cd "$APP_DIR" && git pull --ff-only
else
    echo "-- Clone initial"
    git clone https://github.com/tobiags/AUTO-BOT-LBC-PJ2.git "$APP_DIR"
fi

cd "$APP_DIR"

# Installation deps Python
pip install -e ".[dev]" --quiet

# Migrations Alembic
alembic upgrade head

# Restart services (systemd)
systemctl restart autotransfert-p2-api.service   || true
systemctl restart autotransfert-p2-worker.service || true
systemctl restart autotransfert-p2-beat.service   || true

echo "-- Services redémarrés"
REMOTE

echo "==> Vérification post-déploiement"
sleep 3
./scripts/verify_server.sh "$VPS_IP"
