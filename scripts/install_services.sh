#!/usr/bin/env bash
# Instala unidades systemd para que todo arranque al reiniciar el servidor.
set -euo pipefail

PROJECT="/home/rlopez/projects/innerspark-swarm-os-cursor-local"
USER_NAME="rlopez"

sudo tee /etc/systemd/system/swarm-api.service >/dev/null <<EOF
[Unit]
Description=Swarm-OS API (PC Doctor FastAPI)
After=network-online.target mongodb.service docker.service
Wants=network-online.target

[Service]
Type=simple
User=${USER_NAME}
Group=${USER_NAME}
WorkingDirectory=${PROJECT}
ExecStart=/usr/bin/bash ${PROJECT}/run_api.sh
Restart=always
RestartSec=5
Environment=API_PORT=8100

[Install]
WantedBy=multi-user.target
EOF

sudo tee /etc/systemd/system/swarm-admin.service >/dev/null <<EOF
[Unit]
Description=PC Doctor Admin (Refine React)
After=network-online.target swarm-api.service
Wants=network-online.target

[Service]
Type=simple
User=${USER_NAME}
Group=${USER_NAME}
WorkingDirectory=${PROJECT}
ExecStart=/usr/bin/bash ${PROJECT}/run_admin.sh
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo tee /etc/systemd/system/ralf-portal.service >/dev/null <<EOF
[Unit]
Description=RALF IA v2.0 Portal de acceso
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${USER_NAME}
Group=${USER_NAME}
WorkingDirectory=${PROJECT}
ExecStart=/usr/bin/bash ${PROJECT}/run_portal.sh
Restart=always
RestartSec=5
Environment=PORTAL_PORT=8800

[Install]
WantedBy=multi-user.target
EOF

sudo tee /etc/systemd/system/filebrowser.service >/dev/null <<EOF
[Unit]
Description=FileBrowser gestor de archivos web
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/bin/docker compose -f ${PROJECT}/docker/filebrowser-compose.yml up -d
ExecStop=/usr/bin/docker compose -f ${PROJECT}/docker/filebrowser-compose.yml down
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

chmod +x "${PROJECT}/run_portal.sh" "${PROJECT}/run_api.sh" "${PROJECT}/run_admin.sh"

sudo systemctl daemon-reload
sudo systemctl enable swarm-api.service swarm-admin.service ralf-portal.service filebrowser.service
sudo systemctl restart ralf-portal.service filebrowser.service swarm-api.service swarm-admin.service || true

echo ""
echo "Servicios habilitados. Tras reinicio arrancan solos."
echo "  Portal:     http://192.168.1.4:8800"
echo "  Admin:      http://192.168.1.4:5173"
echo "  Archivos:   http://192.168.1.4:8081"
echo ""
echo "FileBrowser — primera vez: usuario admin / contraseña admin (cámbiala al entrar)."
