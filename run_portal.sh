#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
PORT="${PORTAL_PORT:-8800}"
exec python3 -m http.server "$PORT" --bind 0.0.0.0 --directory portal
