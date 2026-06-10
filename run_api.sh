#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
source venv/bin/activate
exec uvicorn api.main:app --host 0.0.0.0 --port "${API_PORT:-8100}"
