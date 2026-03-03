#!/usr/bin/env python3
import time, json, logging
from pathlib import Path
from src.api import VMobilAPI
from src.display.renderer import DisplayRenderer
from src.display.driver import DisplayDriver
from src.power.pisugar import PiSugar

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

    def _load_config(self) -> dict:
        if self.config_path.exists():
            return json.load(open(self.config_path))
        return {'stops': [], 'destinations': []}

    def update_display(self):
        config = self._load_config()
        stops = config.get('stops', [])
        destinations = config.get('destinations', [])

        if not stops:
            logger.warning("No stops configured")
            return

        stop_label = " & ".join(s['name'] for s in stops[:2])
        logger.info(f"Update: {stop_label}")

        try:
            deps = self.api.get_all_departures(stops, destinations, limit=6)
            bat = self.pisugar.get_battery_level()
            img = self.renderer.render_departures(deps, stop_label, battery_percent=bat)
            self.display.display_image(img)
            self.button_pressed = False
        except Exception as e:
            logger.error(f"Update failed: {e}")

    def run_once(self):
        self.update_display()

    def run_continuous(self, interval=5):
        mode = "auto" if self.pisugar.is_charging() else "button"
        logger.info(f"Mode: {mode}")
        while True:
            try:
                if mode == "auto":
                    self.update_display()
                    time.sleep(interval * 60)
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
    p.add_argument('--interval', type=int, default=5)
    args = p.parse_args()
    d = BusDisplay(mock_display=args.mock_display, mock_battery=args.mock_battery)
    d.run_continuous(args.interval) if args.continuous else d.run_once()
