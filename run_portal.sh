#!/usr/bin/env bash
set -euo pipefail
cd /home/rlopez/inneros/inneros_core/workspaces/innerspark-swarm-os-cursor-local
PORT="${PORTAL_PORT:-2002}"
nohup /home/rlopez/projects/innerspark-swarm-os-cursor-local/run_redirect_8800.sh >/tmp/ralfia-redirect-8800.log 2>&1 &
exec /home/rlopez/projects/innerspark-swarm-os-cursor-local/venv/bin/uvicorn portal_server:app --host 0.0.0.0 --port "$PORT"
