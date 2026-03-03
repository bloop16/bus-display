#!/usr/bin/env python3
import time, json, logging, re, subprocess
from datetime import datetime
from pathlib import Path
from typing import Optional
from src.api import VMobilAPI
from src.display.renderer import DisplayRenderer
from src.display.driver import DisplayDriver
from src.power.pisugar import PiSugar

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Maximales Schlaf-Intervall zwischen Updates (Sicherheitsnetz falls keine Abfahrten)
MAX_SLEEP_SEC = 20 * 60   # 20 Minuten
# Puffer nach einer Abfahrt bevor neu geladen wird
DEPARTURE_BUFFER_SEC = 45


class BusDisplay:
    def __init__(self, config_path='config/stops.json', mock_display=False, mock_battery=False):
        logger.info("Init Bus Display...")
        self.config_path = Path(config_path)
        self.api = VMobilAPI()
        self.renderer = DisplayRenderer()
        self.display = DisplayDriver(mock=mock_display)
        self.pisugar = PiSugar(mock=mock_battery)
        self.button_pressed = False
        self.pisugar.register_button_callback(
            lambda: setattr(self, 'button_pressed', True) or self.update_display()
        )

    def _get_wifi_signal(self) -> Optional[int]:
        """Read WiFi signal quality from /proc/net/wireless (returns 0-100 or None)."""
        try:
            with open('/proc/net/wireless') as f:
                for line in f:
                    if 'wlan' in line:
                        # Format: "wlan0: 0000  62.  -48.  -93. ..."
                        quality = int(line.split()[2].rstrip('.'))
                        return min(100, quality * 100 // 70)
        except Exception:
            pass
        return None

    def _load_config(self) -> dict:
        if self.config_path.exists():
            return json.load(open(self.config_path))
        return {'stops': [], 'destinations': []}

    def update_display(self) -> list:
        """Update display. Returns fetched departures for timing calculation."""
        config = self._load_config()
        stops = config.get('stops', [])
        destinations = config.get('destinations', [])

        if not stops:
            logger.warning("No stops configured")
            return []

        stop_label = " & ".join(s['name'] for s in stops[:2])
        logger.info(f"Update: {stop_label}")

        try:
            deps = self.api.get_all_departures(stops, destinations, limit=6)
            bat = self.pisugar.get_battery_level()
            wifi = self._get_wifi_signal()
            img = self.renderer.render_departures(deps, stop_label, battery_percent=bat, wifi_signal=wifi)
            self.display.display_image(img)
            self.button_pressed = False
            return deps
        except Exception as e:
            logger.error(f"Update failed: {e}")
            return []

    def _sleep_until_next_departure(self, departures: list) -> None:
        """
        Warte bis kurz nach der nächsten Abfahrt, dann neu laden.
        Logik: Abfahrt verpasst → Liste vorrücken → Update.
        """
        now = datetime.now()
        future = [d for d in departures if d.departure_time > now]

        if not future:
            logger.info(f"Keine anstehenden Abfahrten, warte {MAX_SLEEP_SEC // 60} min")
            time.sleep(MAX_SLEEP_SEC)
            return

        next_dep = future[0]
        seconds_until = (next_dep.departure_time - now).total_seconds()

        # Puffer nach der Abfahrt, damit die Buslinie wirklich weg ist
        sleep_sec = seconds_until + DEPARTURE_BUFFER_SEC

        # Sicherheitsgrenzen
        sleep_sec = max(30, sleep_sec)
        sleep_sec = min(sleep_sec, MAX_SLEEP_SEC)

        wake_at = next_dep.departure_time.strftime('%H:%M')
        logger.info(
            f"Nächste Abfahrt: Linie {next_dep.line} um {wake_at} "
            f"→ Update in {sleep_sec:.0f}s"
        )
        time.sleep(sleep_sec)

    def run_once(self):
        self.update_display()

    def run_continuous(self):
        mode = "auto" if self.pisugar.is_charging() else "button"
        logger.info(f"Mode: {mode}")
        while True:
            try:
                if mode == "auto":
                    deps = self.update_display()
                    self._sleep_until_next_departure(deps)
                elif mode == "button":
                    if not self.button_pressed:
                        time.sleep(1)
            except KeyboardInterrupt:
                break
            except Exception:
                time.sleep(60)


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--mock-display', action='store_true')
    p.add_argument('--mock-battery', action='store_true')
    p.add_argument('--continuous', action='store_true')
    args = p.parse_args()
    d = BusDisplay(mock_display=args.mock_display, mock_battery=args.mock_battery)
    d.run_continuous() if args.continuous else d.run_once()
