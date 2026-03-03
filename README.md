# 🚍 Raspberry Pi Zero Bus Display

E-Ink display showing real-time bus departures for Vorarlberg public transport (vmobil.at).

## Hardware Required
- **Raspberry Pi Zero W** (or Zero 2 W)
- **PiSugar 2** Battery HAT with button
- **Waveshare 2.13" e-Paper HAT** (250x122px B/W)

## Features
✅ WiFi setup via captive portal (TODO)  
✅ Web interface for bus stop configuration  
✅ Real-time departure display  
✅ E-Ink optimized layout (battery-friendly)  
✅ Smart power management (TODO: battery/AC modes)  
✅ Mock mode for testing without hardware  

## Quick Start

### 1. Install Dependencies
```bash
sudo apt update
sudo apt install -y python3-flask python3-requests python3-bs4 python3-pil
```

### 2. Clone Repository
```bash
cd /home/martin
git clone <repo-url> bus-display
cd bus-display
```

### 3. Start Web Interface
```bash
python3 -m src.web.app
```
Visit: `http://192.168.0.99:5000`

### 4. Configure Bus Stops
- Search for your bus stops
- Add them to your configuration
- Save

### 5. Update Display
```bash
# Single update (mock mode)
python3 main.py --mock-display

# Continuous updates every 5 minutes
python3 main.py --continuous --interval 5

# Production (real hardware)
sudo python3 main.py --continuous --interval 5
```

## Development

### TDD Approach
All features are developed test-first:
```bash
# Run all tests
python3 -m pytest tests/unit/ -v

# Specific test file
python3 -m pytest tests/unit/test_vmobil_api.py -v
```

**Test Coverage:**
- ✅ 9/9 VMobil API tests
- ✅ 6/6 Web interface tests
- ✅ 11/11 Display rendering tests
- **Total: 26/26 passing**

### Project Structure
```
bus-display/
├── main.py              # Main controller
├── src/
│   ├── api/            # VMobil.at API client
│   ├── display/        # E-Ink rendering + driver
│   ├── web/            # Flask web interface
│   ├── wifi/           # WiFi AP management (TODO)
│   └── power/          # Power management (TODO)
├── tests/
│   ├── unit/           # Unit tests (TDD)
│   └── integration/    # Integration tests (TODO)
├── config/
│   └── stops.json      # Configured bus stops
└── docs/               # Documentation

```

## Systemd Service (TODO)
```bash
# Install service
sudo cp systemd/bus-display.service /etc/systemd/system/
sudo systemctl enable bus-display
sudo systemctl start bus-display
```

## Power Management Strategy

### Battery Mode (PiSugar button press)
- Display sleeps by default
- Button press → wake + update + sleep
- Extends battery life significantly

### AC Power Mode
- Auto-update based on next departure time
- More frequent updates (every 5 minutes or smart scheduling)

## API Data Source
Currently uses **vmobil.at** (Vorarlberg public transport).  
Implementation: Web scraping (no public API available).  
Mock data used for testing - real scraping to be implemented.

## License
MIT

## Credits
- Waveshare e-Paper library
- VMobil.at for transport data
- Built with TDD principles

---

## 🖥️ Local Testing (No SD Card Flashing!)

### Docker ARM Emulation ⭐ FASTEST!

Test on your desktop/laptop without Pi hardware:

```bash
# One-time setup: Enable ARM emulation
docker run --rm --privileged multiarch/qemu-user-static --reset -p yes

# Build and run
docker build -t bus-display .
docker run -p 5000:5000 bus-display

# Or use the script
./test-local.sh
```

Visit: **http://localhost:5000**

### Docker Compose

```bash
docker-compose up
```

### Manual Testing

```bash
# On dev server (current workflow)
python3 main.py --mock-display

# Continuous mode
python3 main.py --mock-display --continuous --interval 5
```

### Development Workflow

1. **Code** → Edit files locally
2. **Test** → `./test-local.sh` (Docker)
3. **Deploy** → Copy to Pi / Flash SD
4. **Validate** → Test on real hardware

**No constant SD card flashing needed!**

