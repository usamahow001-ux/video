#!/bin/bash
# ============================================
#  AI Shorts Generator - Server Setup (Ubuntu / Oracle Cloud Free)
#
#  Run this ON THE VM as your normal user (NOT with sudo):
#      bash ~/shorts-generator/deploy/setup_server.sh
#
#  It installs Python, FFmpeg and fonts, creates the virtualenv, installs the
#  Python dependencies, generates a login password, and registers the app to
#  run 24/7 as a systemd service.
# ============================================
set -e

# Must run as a normal user (not root): the venv is created and owned by this
# user, and the systemd service runs as this user. `sudo` is used internally.
if [ "$(id -u)" -eq 0 ]; then
    echo "[ERROR] Don't run this with sudo/root."
    echo "        Run it as your normal user:  bash ~/shorts-generator/deploy/setup_server.sh"
    exit 1
fi

APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKEND_DIR="$APP_DIR/backend"
ENV_FILE="/etc/shorts-generator.env"
NEW_PASSWORD=""

echo "============================================="
echo "  AI Shorts Generator - Server Setup"
echo "  App dir: $APP_DIR"
echo "============================================="

if [ ! -d "$BACKEND_DIR" ]; then
    echo "[ERROR] Could not find backend at: $BACKEND_DIR"
    echo "        Upload the project first (see deploy/DEPLOY_ORACLE.md)."
    exit 1
fi

# ── 1. System packages ──────────────────────────────────────────────
# fonts-dejavu-core is REQUIRED: the video text is rendered with Pillow and
# needs a real .ttf font on the machine (Windows fonts don't exist here).
echo "[1/6] Installing system packages (python3, ffmpeg, fonts)..."
sudo apt-get update -y
sudo apt-get install -y \
    python3 python3-venv python3-pip \
    ffmpeg git curl \
    fonts-dejavu-core

# ── 2. Firewall (ufw + Oracle iptables) ─────────────────────────────
# NOTE: this only opens the VM's own firewall. You must ALSO add an ingress
# rule for TCP 8000 in the Oracle Cloud VCN Security List — see the guide.
echo "[2/6] Configuring firewall (port 8000)..."
# Oracle Cloud Ubuntu images ship their own iptables rules that can block the
# port even after ufw is opened, so add an explicit rule and persist it too.
sudo iptables -C INPUT -p tcp --dport 8000 -j ACCEPT 2>/dev/null || \
    sudo iptables -I INPUT -p tcp --dport 8000 -j ACCEPT || true
if command -v netfilter-persistent >/dev/null 2>&1; then
    sudo netfilter-persistent save || true
fi
sudo ufw allow 22/tcp  || true
sudo ufw allow 8000/tcp || true
sudo ufw --force enable || true

# ── 3. Virtualenv + Python dependencies ─────────────────────────────
echo "[3/6] Creating virtual environment..."
cd "$BACKEND_DIR"
if [ ! -d venv ]; then
    python3 -m venv venv
fi

# shellcheck disable=SC1091
source venv/bin/activate
echo "[3/6] Installing Python dependencies (this can take a few minutes)..."
pip install --upgrade pip
pip install -r requirements.txt

# ── 4. Runtime directories ──────────────────────────────────────────
echo "[4/6] Creating runtime directories..."
mkdir -p uploads output assets

# ── 5. Login password + session secret ──────────────────────────────
# Kept in an env file (read by the systemd service) so it isn't baked into
# the code. Re-running keeps the existing password.
if [ ! -f "$ENV_FILE" ] || ! grep -q '^APP_PASSWORD=' "$ENV_FILE" 2>/dev/null; then
    echo "[5/6] Generating a login password (saved to $ENV_FILE)..."
    APP_PW="$(head -c 24 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 16)"
    SECRET="$(head -c 48 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 40)"
    echo "APP_PASSWORD=$APP_PW" | sudo tee "$ENV_FILE" > /dev/null
    echo "SECRET_KEY=$SECRET"   | sudo tee -a "$ENV_FILE" > /dev/null
    sudo chmod 600 "$ENV_FILE"
    NEW_PASSWORD="$APP_PW"
else
    echo "[5/6] Keeping the existing password in $ENV_FILE"
fi

# ── 6. systemd service (runs 24/7, auto-restarts) ───────────────────
echo "[6/6] Installing systemd service..."
bash "$APP_DIR/deploy/setup_service.sh"

echo ""
echo "============================================="
echo "  DONE!"
IP=$(curl -s ifconfig.me || echo "YOUR_SERVER_IP")
echo ""
echo "  Open your site at:  http://$IP:8000"
if [ -n "$NEW_PASSWORD" ]; then
    echo "  🔑 Login password:  $NEW_PASSWORD"
    echo "     (also saved in $ENV_FILE — change it there and restart)"
else
    echo "  🔑 Login password:  unchanged — see $ENV_FILE"
fi
echo ""
echo "  If it doesn't load, add an ingress rule for TCP 8000"
echo "  in your Oracle VCN Security List (see deploy/DEPLOY_ORACLE.md)."
echo "============================================="
