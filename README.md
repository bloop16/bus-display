# 🚍 eBusDisplay

**Real-Time Bus Display für Vorarlberg** - E-Ink Display mit Live-Abfahrtszeiten  
Powered by VMobil.at | Open Source | Raspberry Pi Zero W

![Status](https://img.shields.io/badge/status-beta-yellow)
![License](https://img.shields.io/badge/license-MIT-blue)
![Python](https://img.shields.io/badge/python-3.9+-blue)

---

## ✨ Features

- **📺 E-Ink Display** (Waveshare 2.13") - stromsparend, immer sichtbar
- **🚏 Live-Abfahrten** - Echte Daten von VMobil.at
- **📱 Web-Interface** - 3 Tabs für einfache Konfiguration (Haltestellen speichern!)
- **📡 WiFi Setup** - Hotspot für erste Einrichtung
- **🔋 Smart Power** - Battery-Modus mit PiSugar (optional)
- **🏠 Offline Mode** - Funktioniert auch ohne Internet (GTFS-Caching)
- **🗺️ GTFS-Daten** - Offizielle Fahrplandaten von data.mobilitaetsverbuende.at

---

## 🎯 Hardware

- **Raspberry Pi Zero W** - oder Zero 2 W
- **Waveshare 2.13" e-Paper HAT** (250x122px)
- **PiSugar 2** (optional, Battery-Management)
- **SD Card** min. 4GB

---

## 🚀 Quick Start

### Lokal Testen (Docker)
```bash
git clone https://github.com/YOUR-USER/ebisdisplay.git
cd ebisdisplay

# Schnell-Test
./test-local-amd64.sh

# Öffne Browser: http://localhost:5000
```

### Auf Raspberry Pi
```bash
# 1. Raspberry Pi OS Lite flashen
# 2. SSH aktivieren

# 3. Installation
git clone https://github.com/YOUR-USER/ebisdisplay.git
cd ebisdisplay
sudo ./install.sh

# 4. Web-Interface
# http://<PI-IP>:5000
```

---

## 📋 Web-Interface Tabs

### 🚏 Haltestellen
- Suche nach Lieblingshaltstellen (mit GTFS-Daten)
- **Speichere Favoriten** - Werden persistent gespeichert
- Live-Preview der gefundenen Stationen
- Verwaltung von bis zu 5 Favoritenhaltestellen

### ⏱️ Live-Abfahrten  
- Nächste Busse in Echtzeit (Web-scraping)
- Verspätungsanzeige (±min)
- Auto-Refresh alle 30 Sekunden
- Fallback auf GTFS-Sollzeiten wenn Live-Daten fehlen

### 📡 WiFi
- WiFi-Verbindung einrichten
- Status prüfen (Connected/Standby)
- Hotspot-Info für Setup

---

## 🔧 Architektur

```
eBusDisplay/
├── src/
│   ├── api/              # VMobil Daten-Fetcher
│   ├── display/          # E-Ink Rendering
│   ├── web/              # Flask Web-UI
│   ├── wifi/             # AP-Manager & WiFi
│   └── power/            # PiSugar Battery  
├── config/               # stops.json (Konfiguration)
├── tests/                # Pytest Unit-Tests
├── main.py               # Haupt-Loop
├── boot_display.py       # Boot-Screen
└── install.sh            # Installer
```

---

## �️ Datenquellen

### GTFS - Fahrplandaten
eBusDisplay nutzt **offizielle GTFS-Daten** vom österreichischen Mobilitätsdaten-Portal:
- **Portal:** https://data.mobilitaetsverbuende.at/de/data-sets
- **Verband:** Verkehrsverbund Vorarlberg (VMobil)
- **Format:** GTFS (Static Schedule)
- **Updates:** Tägliche Aktualisierungen wenn Fahrpläne ändern
- **Abdeckung:** Alle öffentlichen Verkehrsmittel in Vorarlberg

### Live-Daten - Web-Scraping
Für **Echtzeit-Verspätungen** scrapt eBusDisplay die VMobil-Webseite:
- **Quelle:** https://www.vmobil.at
- **Verspätungen:** Aus aktuellen Bus-Positionen extrahiert
- **Fallback:** GTFS-Sollzeiten wenn Live-Daten nicht verfügbar

### Lokales Caching
- **GTFS-Cache:** 24h lokales Caching (funktioniert offline)
- **Config:** Gespeicherte Haltestellen in `config/stops.json`

---

## �💻 Entwicklung

**Tests ausführen:**
```bash
python3 -m pytest tests/unit/ -v
# 26/26 Tests passing
```

**Web-UI lokal starten:**
```bash
python3 -m src.web.app
```

**Display-Rendering testen:**
```bash
python3 main.py --mock-display --mock-battery
```

---

## 📖 Dokumentation

- [INSTALL.md](INSTALL.md) - Detaillierte Installation
- [FEATURES.md](FEATURES.md) - Alle Features
- [docs/LOCAL_TESTING.md](docs/LOCAL_TESTING.md) - Lokales Testing
- [docs/IMAGE_BUILD.md](docs/IMAGE_BUILD.md) - SD-Image erstellen

---

## 🐛 Troubleshooting

**Display zeigt nichts:**
```bash
python3 main.py --mock-display
journalctl -u ebisdisplay -f
```

**Web-UI nicht erreichbar:**
```bash
sudo systemctl restart ebisdisplay-web
sudo netstat -tulpn | grep 5000
```

---

## 🤝 Contributing

Contributions sind willkommen!

```bash
git clone https://github.com/YOUR-USER/ebisdisplay.git
git checkout -b feature/xyz
# ... code ...
git push origin feature/xyz
# → Create Pull Request
```

---

## 📄 Lizenz

MIT License - siehe [LICENSE](LICENSE)

---

**Made with ❤️ für Vorarlberg Transit**

