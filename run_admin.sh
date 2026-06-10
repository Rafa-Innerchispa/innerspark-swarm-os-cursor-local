#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/admin"
if [[ ! -d node_modules ]]; then
  npm install
fi
exec npm run dev
