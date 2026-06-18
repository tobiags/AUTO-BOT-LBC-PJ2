#!/usr/bin/env bash
# verify_server.sh — vérifie que le VPS est opérationnel après déploiement.
# Usage : ./scripts/verify_server.sh <VPS_IP>

set -euo pipefail
VPS_IP="${1:?Usage: $0 <VPS_IP>}"
PORT="${2:-8000}"

echo "==> Test connexion SSH vers $VPS_IP (timeout 5s)"
ssh -o ConnectTimeout=5 -o BatchMode=yes -o StrictHostKeyChecking=no \
    root@"$VPS_IP" "echo 'SSH OK'" || { echo "FAIL: SSH inaccessible"; exit 1; }

echo "==> Test health endpoint"
HEALTH=$(curl -sf --max-time 5 "http://$VPS_IP:$PORT/health" || echo "FAIL")
if echo "$HEALTH" | grep -q '"status":"ok"'; then
    echo "PASS: health OK"
elif echo "$HEALTH" | grep -q '"status":"degraded"'; then
    echo "WARN: health degraded — vérifier DB/Redis"
else
    echo "FAIL: health endpoint inaccessible"
    exit 1
fi

echo "==> Tous les checks passés pour $VPS_IP"
