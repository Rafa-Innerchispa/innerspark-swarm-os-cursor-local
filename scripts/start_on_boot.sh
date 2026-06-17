#!/usr/bin/env bash
# Ejecutar al reiniciar (cron @reboot o manual). No requiere intervención humana.
set -euo pipefail

PROJECT="/home/rlopez/projects/innerspark-swarm-os-cursor-local"
LOG="$PROJECT/data/start_on_boot.log"
mkdir -p "$PROJECT/data"

{
  echo "=== $(date -Iseconds) start_on_boot ==="

  bash "$PROJECT/scripts/ensure_mongo.sh" || true

  # API y Admin: systemd del sistema (si están habilitados)
  if systemctl is-enabled swarm-api >/dev/null 2>&1; then
    sudo -n systemctl start swarm-api swarm-admin 2>/dev/null || systemctl start swarm-api swarm-admin 2>/dev/null || true
  else
    pgrep -f "uvicorn api.main:app" >/dev/null || nohup bash "$PROJECT/run_api.sh" >>"$LOG" 2>&1 &
    sleep 5
    pgrep -f "vite preview" >/dev/null || nohup bash "$PROJECT/run_admin.sh" >>"$LOG" 2>&1 &
  fi

  sleep 15

  # ngrok (URL pública Devpost)
  if ! curl -sf "http://127.0.0.1:4040/api/tunnels" >/dev/null 2>&1; then
    nohup bash "$PROJECT/run_ngrok.sh" >>"$PROJECT/data/ngrok.log" 2>&1 &
    echo "ngrok launching..."
    for _ in $(seq 1 30); do
      curl -sf "http://127.0.0.1:4040/api/tunnels" >/dev/null 2>&1 && break
      sleep 2
    done
  fi

  bash "$PROJECT/scripts/bootstrap_on_boot.sh" || true

  echo "=== done ==="
} >>"$LOG" 2>&1
