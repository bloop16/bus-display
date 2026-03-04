#!/usr/bin/env python3
import time, json, logging, threading
from datetime import datetime
from pathlib import Path
from typing import Optional
from src.api import VMobilAPI
from src.display.renderer import DisplayRenderer
from src.display.driver import DisplayDriver
from src.power.pisugar import PiSugar

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MAX_SLEEP_SEC        = 20 * 60   # Fallback wenn keine Abfahrten mehr heute
DEPARTURE_BUFFER_SEC = 30        # Sekunden VOR Abfahrt refreshen (frische Daten)
NO_CONFIG_SLEEP_SEC  = 5         # Schneller Retry bis Stops konfiguriert sind


def _start_web_server(api: VMobilAPI, on_config_saved=None):
    """Flask Web-UI in Hintergrund-Thread. Nutzt geteilte VMobilAPI-Instanz."""
    try:
        from src.web.app import create_app
        app = create_app(api=api, on_config_saved=on_config_saved)
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.WARNING)
        app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
    except Exception as e:
        logger.error(f"Web-UI Fehler: {e}")


class BusDisplay:
    def __init__(self, config_path='config/stops.json', mock_display=False, mock_battery=False):
        logger.info("Init Bus Display...")
        self.config_path = Path(config_path)
        self.api = VMobilAPI()
        self.renderer = DisplayRenderer()
        self.display = DisplayDriver(mock=mock_display)
        self.pisugar = PiSugar(mock=mock_battery)
        self.button_pressed = False
        self.wakeup_event = threading.Event()
        self.pisugar.register_button_callback(self._on_button)

    def _on_button(self):
        """Button-Callback: weckt den Schlaf-Loop sofort auf."""
        logger.info("Button gedrückt – sofortiges Update")
        self.button_pressed = True
        self.wakeup_event.set()

    def notify_config_changed(self):
        """Wird von der Web-UI aufgerufen wenn Konfiguration gespeichert wurde."""
        logger.info("Konfiguration geändert – sofortiges Display-Update")
        self.wakeup_event.set()

    def _get_wifi_signal(self) -> Optional[int]:
        """WiFi-Signalstärke aus /proc/net/wireless (0-100 oder None)."""
        try:
            with open('/proc/net/wireless') as f:
                for line in f:
                    if 'wlan' in line:
                        quality = int(line.split()[2].rstrip('.'))
                        return min(100, quality * 100 // 70)
        except Exception:
            pass
        return None

    def _load_config(self) -> dict:
        if self.config_path.exists():
            return json.load(open(self.config_path))
        return {'stops': [], 'destinations': []}

    def update_display(self) -> Optional[list]:
        """
        Display aktualisieren.
          None  → keine Stops konfiguriert (bald nochmal versuchen)
          []    → Stops konfiguriert, aber keine Abfahrten
          [...] → Abfahrten gefunden und angezeigt
        """
        config = self._load_config()
        stops = config.get('stops', [])
        destinations = config.get('destinations', [])

        if not stops:
            logger.info("Keine Stops konfiguriert – warte auf Web-UI Konfiguration")
            return None

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

    def _seconds_until_next_update(self, departures: list) -> int:
        """Liefert Sekunden bis kurz VOR der nächsten Abfahrt (für frische Daten)."""
        now = datetime.now()
        future = [d for d in departures if d.departure_time > now]

        if not future:
            logger.info(f"Keine anstehenden Abfahrten – nächstes Update in {MAX_SLEEP_SEC // 60} min")
            return MAX_SLEEP_SEC

        next_dep = future[0]
        seconds_until = (next_dep.departure_time - now).total_seconds()
        # DEPARTURE_BUFFER_SEC vor Abfahrt aufwachen → Display zeigt aktuelle Daten
        sleep_sec = max(10, int(seconds_until - DEPARTURE_BUFFER_SEC))
        sleep_sec = min(sleep_sec, MAX_SLEEP_SEC)

        wake_at = next_dep.departure_time.strftime('%H:%M')
        logger.info(f"Nächste Abfahrt: Linie {next_dep.line} um {wake_at} → Refresh in {sleep_sec}s")
        return sleep_sec

    def run_once(self):
        self.update_display()

    def run_continuous(self):
        """
        Haupt-Loop:
        - Netzstrom (AC): automatisches Update kurz vor jeder Abfahrt
        - Batterie:       nur auf Button-Druck aktualisieren
        - Beide Modi:     sofortiges Update beim Start und nach Config-Änderung
        """
        last_on_battery = None

        while True:
            try:
                on_battery = not self.pisugar.is_charging()

                if on_battery != last_on_battery:
                    mode_str = "Batterie (nur Button)" if on_battery else "Netzbetrieb (auto)"
                    logger.info(f"Betriebsmodus: {mode_str}")
                    last_on_battery = on_battery

                # Sofortiges Update – beim Start, nach Button, nach Config-Änderung
                deps = self.update_display()

                if deps is None:
                    # Noch nicht konfiguriert → häufiger retry
                    self.wakeup_event.wait(timeout=NO_CONFIG_SLEEP_SEC)
                    self.wakeup_event.clear()
                elif on_battery:
                    # Batterie: unbegrenzt warten bis Button oder Config-Änderung
                    logger.info("Warte auf Button-Druck…")
                    self.wakeup_event.wait()
                    self.wakeup_event.clear()
                else:
                    # Netzstrom: automatisch vor nächster Abfahrt aufwachen
                    timeout = self._seconds_until_next_update(deps)
                    self.wakeup_event.wait(timeout=timeout)
                    self.wakeup_event.clear()

            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Loop error: {e}")
                time.sleep(60)


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--mock-display', action='store_true')
    p.add_argument('--mock-battery', action='store_true')
    p.add_argument('--continuous', action='store_true')
    p.add_argument('--no-web', action='store_true', help='Web-UI nicht starten')
    args = p.parse_args()

    d = BusDisplay(mock_display=args.mock_display, mock_battery=args.mock_battery)

    # Web-UI als Daemon-Thread mit geteilter api-Instanz → kein zweiter GTFS-Download
    if not args.no_web:
        web_thread = threading.Thread(
            target=_start_web_server, args=(d.api, d.notify_config_changed), daemon=True, name='web-ui'
        )
        web_thread.start()
        logger.info("Web-UI gestartet auf http://0.0.0.0:5000")

    d.run_continuous() if args.continuous else d.run_once()
