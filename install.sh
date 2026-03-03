#!/bin/bash
# Bus Display – Installation für Raspberry Pi Zero
# Waveshare 2.13" e-Paper HAT V4 + PiSugar 3
# Ausführen als root: sudo ./install.sh

set -e
echo "=== Bus Display Installation ==="

if [ "$EUID" -ne 0 ]; then
    echo "FEHLER: Als root ausführen (sudo ./install.sh)"
    exit 1
fi

ACTUAL_USER=${SUDO_USER:-pi}
INSTALL_DIR="/home/${ACTUAL_USER}/bus-display"

echo "Benutzer: $ACTUAL_USER"
echo "Verzeichnis: $INSTALL_DIR"

# ── System-Pakete ─────────────────────────────────────────────
apt-get update
apt-get install -y \
    python3 python3-pip \
    python3-pil \
    python3-rpi.gpio \
    python3-spidev \
    python3-flask \
    git curl

# ── SPI aktivieren (Waveshare Display) ───────────────────────
echo "SPI aktivieren..."
raspi-config nonint do_spi 0

# ── I2C aktivieren (PiSugar 3) ────────────────────────────────
echo "I2C aktivieren..."
raspi-config nonint do_i2c 0

# ── Waveshare e-Paper Bibliothek (nur Python-Lib, kein voller Clone) ──
echo "Waveshare Bibliothek installieren (sparse checkout)..."
rm -rf /tmp/waveshare-epd
git clone \
    --depth=1 \
    --filter=blob:none \
    --sparse \
    https://github.com/waveshare/e-Paper.git \
    /tmp/waveshare-epd
cd /tmp/waveshare-epd
git sparse-checkout set RaspberryPi_JetsonNano/python
pip3 install ./RaspberryPi_JetsonNano/python/ \
    --break-system-packages 2>/dev/null || \
    pip3 install ./RaspberryPi_JetsonNano/python/
cd /
rm -rf /tmp/waveshare-epd

# ── pip Dependencies ──────────────────────────────────────────
cd "$INSTALL_DIR"
pip3 install -r requirements.txt \
    --break-system-packages 2>/dev/null || \
    pip3 install -r requirements.txt

# ── PiSugar 3 Daemon ──────────────────────────────────────────
echo "PiSugar 3 installieren..."
curl -s https://cdn.pisugar.com/release/pisugar-power-manager.sh | bash

# ── Systemd Services ──────────────────────────────────────────
echo "Services einrichten..."

for SERVICE in bus-display bus-display-web; do
    cp "$INSTALL_DIR/systemd/${SERVICE}.service" /etc/systemd/system/
    sed -i "s|/home/pi/bus-display|$INSTALL_DIR|g" /etc/systemd/system/${SERVICE}.service
    sed -i "s|User=pi|User=$ACTUAL_USER|g"          /etc/systemd/system/${SERVICE}.service
done

systemctl daemon-reload
systemctl enable bus-display bus-display-web
systemctl start bus-display bus-display-web

echo ""
echo "=== Fertig! ==="
echo "Display-Log: journalctl -u bus-display -f"
echo "Web-UI:      http://$(hostname -I | awk '{print $1}'):5000"
