"""
PiSugar 3 Battery HAT Integration.
Communicates via pisugar-server Unix socket (I2C daemon).
Install pisugar-server: curl https://cdn.pisugar.com/release/pisugar-power-manager.sh | sudo bash
"""
import socket
import threading
import time
import logging
from typing import Optional, Callable

logger = logging.getLogger(__name__)

PISUGAR_SOCKET = '/tmp/pisugar-server.sock'


def _pisugar_cmd(cmd: str) -> str:
    """Send command to pisugar-server socket, return response string."""
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(2)
        s.connect(PISUGAR_SOCKET)
        s.send((cmd + '\n').encode())
        data = b''
        while b'\n' not in data:
            chunk = s.recv(256)
            if not chunk:
                break
            data += chunk
        s.close()
        return data.decode().strip()
    except Exception as e:
        logger.debug(f"pisugar-server '{cmd}' failed: {e}")
        return ''


class PiSugar:
    """Interface to PiSugar 3 battery HAT via pisugar-server daemon."""

    def __init__(self, mock=False):
        self.mock = mock
        self.available = False
        self._button_callback: Optional[Callable] = None
        self._stop_event = threading.Event()
        self._button_thread: Optional[threading.Thread] = None

        if not mock:
            self.available = self._check_availability()

    def _check_availability(self) -> bool:
        """Check if pisugar-server is running and responsive."""
        resp = _pisugar_cmd('get battery')
        available = resp.startswith('battery:')
        if not available:
            logger.warning("PiSugar not detected — is pisugar-server running?")
        else:
            logger.info("PiSugar 3 detected via pisugar-server")
        return available

    def get_battery_level(self) -> Optional[int]:
        """
        Get battery level (0-100%).

        Returns:
            Battery percentage or None if unavailable
        """
        if self.mock:
            return 75

        if not self.available:
            return None

        resp = _pisugar_cmd('get battery')
        try:
            # "battery: 75.3"
            return int(float(resp.split(':', 1)[1].strip()))
        except Exception:
            return None

    def is_charging(self) -> bool:
        """
        Check if battery is charging (USB power connected).

        Returns:
            True if charging or if PiSugar unavailable (assume AC)
        """
        if self.mock:
            return False

        if not self.available:
            return True  # Assume AC if no battery detected

        resp = _pisugar_cmd('get battery_charging')
        try:
            # "battery_charging: true" or "battery_charging: false"
            return 'true' in resp.lower()
        except Exception:
            return True

    def register_button_callback(self, callback: Callable):
        """
        Register callback for button press events.
        Polls pisugar-server every 500ms in a background thread.

        Args:
            callback: Function to call on button press
        """
        self._button_callback = callback

        if self.mock:
            logger.info("[MOCK] Button callback registered")
            return

        if not self.available:
            logger.warning("PiSugar not available, button callback skipped")
            return

        self._stop_event.clear()
        self._button_thread = threading.Thread(
            target=self._poll_button, daemon=True, name="pisugar-btn"
        )
        self._button_thread.start()
        logger.info("PiSugar button polling started")

    def _poll_button(self):
        """Poll pisugar-server for button_press events in background."""
        while not self._stop_event.is_set():
            try:
                resp = _pisugar_cmd('get button_press')
                # "button_press: single" / "button_press: double" / "button_press: "
                if resp.startswith('button_press:'):
                    value = resp.split(':', 1)[1].strip()
                    if value and value not in ('none', ''):
                        logger.info(f"Button press detected: {value}")
                        if self._button_callback:
                            self._button_callback()
            except Exception as e:
                logger.debug(f"Button poll error: {e}")
            time.sleep(0.5)

    def stop(self):
        """Stop button polling thread."""
        self._stop_event.set()

    def get_status_dict(self) -> dict:
        """Get complete power status as dictionary."""
        return {
            'battery_level': self.get_battery_level(),
            'charging': self.is_charging(),
            'available': self.available or self.mock,
        }
