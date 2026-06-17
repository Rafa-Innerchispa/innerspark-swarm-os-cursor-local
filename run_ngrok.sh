#!/usr/bin/env bash
# Túnel público Devpost → admin :5173 (InnerOS /inneros)
set -euo pipefail

PROJECT="$(cd "$(dirname "$0")" && pwd)"
PORT="${ADMIN_PORT:-5173}"

if [[ -f "$PROJECT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source <(grep -E '^(NGROK_AUTHTOKEN|ADMIN_PORT)=' "$PROJECT/.env" | sed 's/\r$//')
  set +a
fi

if ! command -v ngrok >/dev/null 2>&1; then
  echo "ngrok no instalado" >&2
  exit 1
fi

if [[ -n "${NGROK_AUTHTOKEN:-}" ]]; then
  ngrok config add-authtoken "$NGROK_AUTHTOKEN" 2>/dev/null || true
fi

for _ in $(seq 1 60); do
  if curl -sf "http://127.0.0.1:${PORT}/" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

exec ngrok http "$PORT" --log=stdout
