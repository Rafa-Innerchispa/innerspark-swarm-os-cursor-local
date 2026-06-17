#!/usr/bin/env bash
# Tras reinicio: espera API, seed idempotente, guarda URL pública ngrok.
set -euo pipefail

PROJECT="/home/rlopez/projects/innerspark-swarm-os-cursor-local"
API="http://127.0.0.1:8100/api/v1"
OUT="$PROJECT/data/public_demo_url.txt"
LOG="$PROJECT/data/bootstrap.log"

mkdir -p "$PROJECT/data"
echo "[$(date -Iseconds)] bootstrap start" >>"$LOG"

bash "$PROJECT/scripts/ensure_mongo.sh" >>"$LOG" 2>&1 || true

for _ in $(seq 1 90); do
  if curl -sf "$API/stats" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

if curl -sf "$API/stats" >/dev/null 2>&1; then
  curl -sf -X POST "$API/hackathon/seed-demo" >>"$LOG" 2>&1 || true
  echo "[$(date -Iseconds)] seed-demo done" >>"$LOG"
else
  echo "[$(date -Iseconds)] API no disponible" >>"$LOG"
fi

sleep 8
NGROK_URL=""
if curl -sf "http://127.0.0.1:4040/api/tunnels" >/dev/null 2>&1; then
  NGROK_URL=$(python3 - <<'PY' 2>/dev/null || true
import json, urllib.request
d = json.load(urllib.request.urlopen("http://127.0.0.1:4040/api/tunnels"))
for t in d.get("tunnels", []):
    u = t.get("public_url", "")
    if u.startswith("https://"):
        print(u)
        break
PY
)
fi

{
  echo "updated: $(date -Iseconds)"
  echo "local_admin: http://192.168.1.4:5173/inneros"
  echo "local_api: http://192.168.1.4:8100/docs"
  if [[ -n "$NGROK_URL" ]]; then
    echo "ngrok_demo: ${NGROK_URL}/inneros"
    echo "ngrok_datacenter: ${NGROK_URL}/datacenter"
  else
    echo "ngrok_demo: (pending — check: systemctl status swarm-ngrok)"
  fi
} >"$OUT"

echo "[$(date -Iseconds)] bootstrap end url=${NGROK_URL:-none}" >>"$LOG"
