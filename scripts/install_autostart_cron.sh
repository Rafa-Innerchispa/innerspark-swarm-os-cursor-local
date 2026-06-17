#!/usr/bin/env bash
# Registra arranque automático en crontab (sin sudo).
set -euo pipefail

PROJECT="/home/rlopez/projects/innerspark-swarm-os-cursor-local"
MARKER="# inneros-autostart"
LINE="@reboot sleep 45 && $PROJECT/scripts/start_on_boot.sh"

chmod +x "$PROJECT/scripts/start_on_boot.sh"
chmod +x "$PROJECT/scripts/bootstrap_on_boot.sh"
chmod +x "$PROJECT/run_ngrok.sh"

(crontab -l 2>/dev/null | grep -v "$MARKER" | grep -v "start_on_boot.sh"; echo "$MARKER"; echo "$LINE") | crontab -

echo "Crontab @reboot instalado."
echo "Tras reinicio: cat $PROJECT/data/public_demo_url.txt"
