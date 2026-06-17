#!/usr/bin/env bash
# Instala unidades systemd — todo arranca solo tras apagón/reinicio.
set -euo pipefail

PROJECT="/home/rlopez/projects/innerspark-swarm-os-cursor-local"
USER_NAME="rlopez"

chmod +x "${PROJECT}/run_portal.sh" "${PROJECT}/run_api.sh" "${PROJECT}/run_admin.sh" "${PROJECT}/run_ngrok.sh"
chmod +x "${PROJECT}/scripts/ensure_mongo.sh" "${PROJECT}/scripts/bootstrap_on_boot.sh"

sudo tee /etc/systemd/system/swarm-api.service >/dev/null <<EOF
[Unit]
Description=Swarm-OS API (PC Doctor FastAPI)
After=network-online.target docker.service
Wants=network-online.target docker.service

[Service]
Type=simple
User=${USER_NAME}
Group=${USER_NAME}
WorkingDirectory=${PROJECT}
ExecStartPre=${PROJECT}/scripts/ensure_mongo.sh
ExecStart=/usr/bin/bash ${PROJECT}/run_api.sh
Restart=always
RestartSec=5
Environment=API_PORT=8100

[Install]
WantedBy=multi-user.target
EOF

sudo tee /etc/systemd/system/swarm-admin.service >/dev/null <<EOF
[Unit]
Description=PC Doctor Admin (Refine React + InnerOS)
After=network-online.target swarm-api.service
Wants=network-online.target

[Service]
Type=simple
User=${USER_NAME}
Group=${USER_NAME}
WorkingDirectory=${PROJECT}
ExecStart=/usr/bin/bash ${PROJECT}/run_admin.sh
Restart=always
RestartSec=10
TimeoutStartSec=300
Environment=ADMIN_PORT=5173

[Install]
WantedBy=multi-user.target
EOF

sudo tee /etc/systemd/system/swarm-ngrok.service >/dev/null <<EOF
[Unit]
Description=ngrok tunnel — public Devpost demo (:5173)
After=network-online.target swarm-admin.service
Wants=network-online.target

[Service]
Type=simple
User=${USER_NAME}
Group=${USER_NAME}
WorkingDirectory=${PROJECT}
ExecStart=/usr/bin/bash ${PROJECT}/run_ngrok.sh
Restart=always
RestartSec=15
Environment=ADMIN_PORT=5173

[Install]
WantedBy=multi-user.target
EOF

sudo tee /etc/systemd/system/swarm-bootstrap.service >/dev/null <<EOF
[Unit]
Description=InnerOS hackathon bootstrap (seed demo + save public URL)
After=swarm-api.service swarm-ngrok.service
Wants=swarm-api.service

[Service]
Type=oneshot
User=${USER_NAME}
Group=${USER_NAME}
WorkingDirectory=${PROJECT}
ExecStart=/usr/bin/bash ${PROJECT}/scripts/bootstrap_on_boot.sh
RemainAfterExit=yes

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

sudo systemctl daemon-reload
sudo systemctl enable \
  swarm-api.service \
  swarm-admin.service \
  swarm-ngrok.service \
  swarm-bootstrap.service \
  ralf-portal.service \
  filebrowser.service

sudo systemctl restart swarm-api.service
sudo systemctl restart swarm-admin.service
sudo systemctl restart swarm-ngrok.service || true
sudo systemctl start swarm-bootstrap.service || true
sudo systemctl restart ralf-portal.service filebrowser.service || true

echo ""
echo "=== Arranque automático configurado ==="
echo "Tras reinicio o corte de luz, todo sube solo:"
echo "  swarm-api      → :8100"
echo "  swarm-admin    → :5173 (build + preview)"
echo "  swarm-ngrok    → URL pública Devpost"
echo "  swarm-bootstrap → seed demo + data/public_demo_url.txt"
echo ""
echo "Tu URL pública (cuando ngrok esté listo):"
echo "  cat ${PROJECT}/data/public_demo_url.txt"
echo ""
echo "Estado:"
systemctl is-active swarm-api swarm-admin swarm-ngrok 2>/dev/null || true
