#!/bin/bash
# Bus Display Installation Script

set -e
echo "=== Bus Display Installation ==="

if [ "$EUID" -ne 0 ]; then
    echo "ERROR: Run as root (sudo ./install.sh)"
    exit 1
fi

ACTUAL_USER=${SUDO_USER:-pi}
INSTALL_DIR="/home/pi/bus-display"

echo "Installing for user: $ACTUAL_USER"
apt update && apt upgrade -y
apt install -y python3 python3-flask python3-requests python3-bs4 python3-pil git hostapd dnsmasq

# Waveshare library
cd /tmp && git clone https://github.com/waveshare/e-Paper.git || true
cd e-Paper/RaspberryPi_JetsonNano/python && pip3 install .

# Services
systemctl enable bus-display-boot bus-display bus-display-web
echo "Installation complete! Reboot to start."
