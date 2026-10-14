#!/bin/bash
# ============================================
#  AI Shorts Generator - systemd service
#
#  Makes the app run 24/7 and restart automatically after a crash or reboot.
#  Run on the VM as your normal user:
#      bash ~/shorts-generator/deploy/setup_service.sh
#
#  (setup_server.sh calls this for you at the end.)
# ============================================
set -e

if [ "$(id -u)" -eq 0 ]; then
    echo "[ERROR] Don't run this with sudo/root."
    echo "        Run it as your normal user:  bash ~/shorts-generator/deploy/setup_service.sh"
    exit 1
fi

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_DIR="$APP_DIR/backend"
RUN_USER="$(id -un)"

if [ ! -x "$BACKEND_DIR/venv/bin/python" ]; then
    echo "[ERROR] Virtual environment not found at: $BACKEND_DIR/venv"
    echo "        Run deploy/setup_server.sh first."
    exit 1
fi

echo "[SERVICE] Installing systemd service (runs as user: $RUN_USER)..."

sudo tee /etc/systemd/system/shorts-generator.service > /dev/null <<EOF
[Unit]
Description=AI Shorts Generator
After=network.target

[Service]
Type=simple
User=$RUN_USER
WorkingDirectory=$BACKEND_DIR
ExecStart=$BACKEND_DIR/venv/bin/python app.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1
# Login password + session secret (created by setup_server.sh).
# The leading '-' means the service still starts if the file is missing.
EnvironmentFile=-/etc/shorts-generator.env

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable shorts-generator
sudo systemctl restart shorts-generator

sleep 3
echo ""
echo "============================================="
echo "  Service installed and started!"
echo ""
echo "  Status:  sudo systemctl status shorts-generator"
echo "  Logs:    sudo journalctl -u shorts-generator -f"
echo "  Restart: sudo systemctl restart shorts-generator"
echo ""
IP=$(curl -s ifconfig.me || echo "YOUR_SERVER_IP")
echo "  🌐 Open your website at:  http://$IP:8000"
echo "============================================="
