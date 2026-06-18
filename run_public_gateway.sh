#!/usr/bin/env bash
# Gateway público :5188 — InnerOS (/inneros) + Hackathon (/) en un solo puerto ngrok
set -euo pipefail
cd "$(dirname "$0")"
PORT="${PUBLIC_GATEWAY_PORT:-5188}"

if command -v fuser >/dev/null 2>&1; then
  fuser -k "${PORT}/tcp" 2>/dev/null || true
  sleep 1
fi

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source <(grep -v '^\s*#' .env | sed 's/\r$//')
  set +a
fi

source venv/bin/activate
exec python scripts/public_gateway.py
