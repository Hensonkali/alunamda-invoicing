#!/bin/bash
# ============================================
# ALUNAMDA Invoicing - Oracle Cloud Deploy Script
# Run this ONCE on your Oracle Cloud VPS
# ============================================

set -e

echo "============================================"
echo "  ALUNAMDA Invoicing - Server Setup"
echo "============================================"
echo ""

# Step 1: Update system
echo "[1/5] Updating system..."
sudo apt-get update && sudo apt-get upgrade -y

# Step 2: Install Docker
echo "[2/5] Installing Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com | sudo sh
    sudo usermod -aG docker $USER
    echo "  [OK] Docker installed. You may need to log out and back in."
else
    echo "  [OK] Docker already installed."
fi

# Step 3: Install Docker Compose
echo "[3/5] Installing Docker Compose..."
if ! command -v docker compose &> /dev/null; then
    sudo apt-get install -y docker-compose-plugin
    echo "  [OK] Docker Compose installed."
else
    echo "  [OK] Docker Compose already installed."
fi

# Step 4: Create app directory
echo "[4/5] Setting up app directory..."
sudo mkdir -p /opt/alunamda
sudo chown $USER:$USER /opt/alunamda

# Step 5: Configure firewall
echo "[5/5] Configuring firewall..."
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw --force enable

echo ""
echo "============================================"
echo "  Server setup complete!"
echo "============================================"
echo ""
echo "Next steps:"
echo "  1. Copy this project folder to /opt/alunamda/"
echo "  2. Edit .env with your settings"
echo "  3. Edit Caddyfile with your domain"
echo "  4. Run: cd /opt/alunamda && docker compose up -d"
echo ""
echo "To upload files, use SCP:"
echo "  scp -r ./alunamda-cloud/ user@YOUR_VPS_IP:/opt/alunamda/"
echo ""
