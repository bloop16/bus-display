#!/bin/bash
# Bus Display – Installation für Raspberry Pi Zero
# Waveshare 2.13" e-Paper HAT V4 + PiSugar 3
# Ausführen als root: sudo ./install.sh
# Idempotent: kann mehrfach ausgeführt werden ohne Probleme

set -e
echo "=== Bus Display Installation ==="

if [ "$EUID" -ne 0 ]; then
    echo "FEHLER: Als root ausführen (sudo ./install.sh)"
    exit 1
fi

# Verzeichnis = wo install.sh liegt (kein Hardcode auf /home/pi)
INSTALL_DIR="$(cd "$(dirname "$0")" && pwd)"
ACTUAL_USER=${SUDO_USER:-$(logname 2>/dev/null || stat -c '%U' "$INSTALL_DIR")}

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
    git curl netcat-openbsd

# ── SPI aktivieren (Waveshare Display) ────────────────────────
if ! grep -q "^dtparam=spi=on" /boot/config.txt 2>/dev/null && \
   ! grep -q "^dtparam=spi=on" /boot/firmware/config.txt 2>/dev/null; then
    echo "SPI aktivieren..."
    raspi-config nonint do_spi 0
else
    echo "SPI bereits aktiv"
fi

# ── I2C aktivieren (PiSugar 3) ────────────────────────────────
if ! grep -q "^dtparam=i2c_arm=on" /boot/config.txt 2>/dev/null && \
   ! grep -q "^dtparam=i2c_arm=on" /boot/firmware/config.txt 2>/dev/null; then
    echo "I2C aktivieren..."
    raspi-config nonint do_i2c 0
else
    echo "I2C bereits aktiv"
fi

# ── Waveshare e-Paper Bibliothek ──────────────────────────────
if python3 -c "from waveshare_epd import epd2in13_V4" 2>/dev/null; then
    echo "Waveshare bereits installiert"
else
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
    echo "✓ Waveshare installiert"
fi

# ── pip Dependencies ──────────────────────────────────────────
cd "$INSTALL_DIR"
pip3 install -r requirements.txt \
    --break-system-packages 2>/dev/null || \
    pip3 install -r requirements.txt

# ── PiSugar 3 Daemon ──────────────────────────────────────────
if systemctl is-enabled pisugar-server &>/dev/null; then
    echo "PiSugar bereits installiert"
    systemctl start pisugar-server 2>/dev/null || true
else
    echo "PiSugar 3 installieren..."
    curl -s https://cdn.pisugar.com/release/pisugar-power-manager.sh | bash
    systemctl enable pisugar-server 2>/dev/null || true
    systemctl start  pisugar-server 2>/dev/null || true
fi

# Kurz warten und PiSugar-Status prüfen
sleep 3
if systemctl is-active --quiet pisugar-server; then
    echo "✓ pisugar-server läuft"
    if echo "get battery" | nc -U /tmp/pisugar-server.sock 2>/dev/null | grep -q "battery:"; then
        echo "✓ PiSugar Socket antwortet"
    else
        echo "⚠ PiSugar Socket nicht erreichbar (Hardware angeschlossen?)"
    fi
else
    echo "⚠ pisugar-server nicht gestartet – läuft ohne Akku-Unterstützung"
fi

# ── Systemd Service (ein einziger für alles) ──────────────────
echo "Bus Display Service einrichten..."

cp "$INSTALL_DIR/systemd/bus-display.service" /etc/systemd/system/
sed -i "s|/home/pi/bus-display|$INSTALL_DIR|g" /etc/systemd/system/bus-display.service
sed -i "s|User=pi|User=$ACTUAL_USER|g"          /etc/systemd/system/bus-display.service

# Alten Web-Service entfernen falls vorhanden
systemctl stop    bus-display-web 2>/dev/null || true
systemctl disable bus-display-web 2>/dev/null || true
rm -f /etc/systemd/system/bus-display-web.service

systemctl daemon-reload
systemctl enable bus-display
systemctl restart bus-display

# ── Status-Übersicht ──────────────────────────────────────────
sleep 2
echo ""
echo "=== Installations-Status ==="
for SVC in pisugar-server bus-display; do
    if systemctl is-active --quiet "$SVC"; then
        echo "  ✓ $SVC"
    else
        echo "  ✗ $SVC  ← Fehler! (journalctl -u $SVC)"
    fi
done

echo ""
echo "=== Fertig! ==="
echo "Log:     journalctl -u bus-display -f"
echo "PiSugar: journalctl -u pisugar-server -f"
echo "Web-UI:  http://$(hostname -I | awk '{print $1}'):5000"
