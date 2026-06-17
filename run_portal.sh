#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
PORT="${PORTAL_PORT:-8800}"
if command -v fuser >/dev/null 2>&1; then
  fuser -k "${PORT}/tcp" 2>/dev/null || true
  sleep 1
fi
exec python3 -m http.server "$PORT" --bind 0.0.0.0 --directory portal
