#!/bin/bash
# Bus Display Installation Script
# Run as root: sudo ./install.sh

set -e
echo "=== Bus Display Installation ==="

if [ "$EUID" -ne 0 ]; then
    echo "ERROR: Run as root (sudo ./install.sh)"
    exit 1
fi

ACTUAL_USER=${SUDO_USER:-pi}
INSTALL_DIR="/home/${ACTUAL_USER}/bus-display"

echo "Installing for user: $ACTUAL_USER"
echo "Install dir: $INSTALL_DIR"

# ── System packages ───────────────────────────────────────────
apt-get update
apt-get install -y \
    python3 python3-pip python3-venv \
    python3-pil python3-numpy \
    python3-flask python3-requests \
    python3-bs4 \
    git curl

# ── Enable SPI (required for Waveshare display) ───────────────
echo "Enabling SPI interface..."
raspi-config nonint do_spi 0
echo "SPI enabled."

# ── Enable I2C (required for PiSugar 3) ──────────────────────
echo "Enabling I2C interface..."
raspi-config nonint do_i2c 0
echo "I2C enabled."

# ── Waveshare e-Paper library ─────────────────────────────────
echo "Installing Waveshare e-Paper library..."
cd /tmp
rm -rf e-Paper
git clone --depth=1 https://github.com/waveshare/e-Paper.git
cd e-Paper/RaspberryPi_JetsonNano/python
pip3 install . --break-system-packages 2>/dev/null || pip3 install .
echo "Waveshare library installed."

# ── PiSugar 3 server ─────────────────────────────────────────
echo "Installing PiSugar power manager..."
curl -s https://cdn.pisugar.com/release/pisugar-power-manager.sh | bash
echo "PiSugar server installed."

# ── Python dependencies ───────────────────────────────────────
cd "$INSTALL_DIR"
pip3 install -r requirements.txt --break-system-packages 2>/dev/null || pip3 install -r requirements.txt

# ── Systemd services ──────────────────────────────────────────
echo "Installing systemd services..."
cp "$INSTALL_DIR/systemd/bus-display.service"     /etc/systemd/system/
cp "$INSTALL_DIR/systemd/bus-display-web.service" /etc/systemd/system/

# Fix WorkingDirectory and user in service files
sed -i "s|/home/pi/bus-display|$INSTALL_DIR|g"  /etc/systemd/system/bus-display.service
sed -i "s|User=pi|User=$ACTUAL_USER|g"           /etc/systemd/system/bus-display.service
sed -i "s|/home/pi/bus-display|$INSTALL_DIR|g"  /etc/systemd/system/bus-display-web.service
sed -i "s|User=pi|User=$ACTUAL_USER|g"           /etc/systemd/system/bus-display-web.service

systemctl daemon-reload
systemctl enable bus-display bus-display-web
echo "Services enabled."

echo ""
echo "=== Installation complete! ==="
echo "Reboot the Pi, then:"
echo "  - Display should start automatically"
echo "  - Web UI: http://$(hostname -I | awk '{print $1}'):5000"
echo ""
echo "Check logs: journalctl -u bus-display -f"
