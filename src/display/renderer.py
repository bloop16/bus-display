"""
E-Ink display renderer for bus departures.
Optimized for Waveshare 2.13" (250x122px B/W).
"""
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

# Icon size used in departure rows
ICON_SIZE = 12

# Fixed column widths for departure rows
LINE_COL_W = 44   # px reserved for line name


class DisplayRenderer:
    """Renders bus departures to e-ink display format"""

    # Waveshare 2.13" dimensions
    WIDTH = 250
    HEIGHT = 122

    def __init__(self):
        self.width = self.WIDTH
        self.height = self.HEIGHT

        # Try to load fonts, fallback to default
        try:
            self.font_header = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 11)
            self.font_line   = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 13)
            self.font_dep    = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11)
            self.font_small  = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 9)
        except Exception:
            logger.warning("TrueType fonts not available, using default")
            self.font_header = ImageFont.load_default()
            self.font_line   = ImageFont.load_default()
            self.font_dep    = ImageFont.load_default()
            self.font_small  = ImageFont.load_default()

        # Lazy-load icons to avoid circular import at module level
        self._icon_cache: dict = {}

    def _get_icon(self, name: str) -> Image.Image | None:
        if name not in self._icon_cache:
            try:
                from .icons import get_icon
                self._icon_cache[name] = get_icon(name)
            except Exception:
                self._icon_cache[name] = None
        return self._icon_cache[name]

    def render_departures(
        self,
        departures: List,
        stop_name: str,
        battery_percent: Optional[int] = None,
        wifi_signal: Optional[int] = None
    ) -> Image.Image:
        """
        Render bus departures to image.

        Args:
            departures: List of Departure objects (up to 6 shown)
            stop_name: Name of bus stop (shown in header)
            battery_percent: Battery level 0-100, None if AC powered
            wifi_signal: WiFi signal quality 0-100, None if not connected

        Returns:
            PIL Image (1-bit B/W, 250x122px)
        """
        image = Image.new('1', (self.width, self.height), 255)
        draw = ImageDraw.Draw(image)

        # Mehrere Haltestellen? → Stop-Kürzel pro Zeile zeigen
        unique_stops = {dep.stop_name for dep in departures if dep.stop_name}
        show_stop_col = len(unique_stops) > 1

        # ── Header ───────────────────────────────────────────────
        y = 1
        now_str = datetime.now().strftime("%H:%M")
        now_w = int(draw.textlength(now_str, font=self.font_line))
        draw.text(((self.width - now_w) // 2, y), now_str, font=self.font_line, fill=0)

        status_y = y + 11
        if wifi_signal is not None:
            wifi_text = f"W:{wifi_signal}"
            draw.text((2, status_y), wifi_text, font=self.font_small, fill=0)
        if battery_percent is not None:
            bat_text = f"B:{battery_percent}%"
            bat_w = int(draw.textlength(bat_text, font=self.font_small))
            draw.text((self.width - bat_w - 2, status_y), bat_text, font=self.font_small, fill=0)

        # ── Divider ───────────────────────────────────────────────
        y += 22
        draw.line((0, y, self.width, y), fill=0, width=1)
        y += 2

        # ── Departure rows (max 6, 15px each) ────────────────────
        ROW_H = 15
        if not departures:
            draw.text((4, y + 16), "Keine Abfahrten", font=self.font_dep, fill=0)
        else:
            for dep in departures[:6]:
                if y + ROW_H > self.height - 2:
                    break

                row_y_center = y + (ROW_H - ICON_SIZE) // 2  # vertical center for icon

                # ── Spalte 1: Linienname (fest LINE_COL_W px) ──────
                line_text = str(dep.line)[:15]
                draw.text((2, y + 1), line_text, font=self.font_line, fill=0)

                # ── Rechte Seite: Zeit + Haltestellen-Kürzel ───────
                time_text = self._format_time(dep.departure_time)
                time_w = int(draw.textlength(time_text, font=self.font_dep))
                draw.text((self.width - time_w - 2, y + 2), time_text, font=self.font_dep, fill=0)

                stop_reserve = 0
                if show_stop_col and dep.stop_name:
                    abbr = self._abbrev_stop(dep.stop_name)
                    abbr_w = int(draw.textlength(abbr, font=self.font_small))
                    draw.text((self.width - time_w - abbr_w - 18, y + 3), abbr,
                              font=self.font_small, fill=0)
                    stop_reserve = abbr_w + 18

                # ── Icons rechts neben Destination ─────────────────
                icon_list = dep.icons if hasattr(dep, 'icons') and dep.icons else ()
                icon_total_w = len(icon_list) * (ICON_SIZE + 2) if icon_list else 0

                # Icons direkt links von Stop/Zeit platzieren
                icon_x = self.width - time_w - stop_reserve - icon_total_w - 4
                for icon_name in icon_list:
                    icon_img = self._get_icon(icon_name)
                    if icon_img:
                        image.paste(icon_img, (icon_x, row_y_center))
                        icon_x += ICON_SIZE + 2

                # ── Spalte 2: Destination (füllt zwischen Linie und Icons) ──
                dest_x = 2 + LINE_COL_W
                dest_max_px = self.width - dest_x - time_w - stop_reserve - icon_total_w - 8
                dest_text = self._truncate(dep.destination, max_px=dest_max_px)
                draw.text((dest_x, y + 2), dest_text, font=self.font_dep, fill=0)

                y += ROW_H

        return image

    # ── Helpers ──────────────────────────────────────────────────

    def _format_time(self, departure_time: datetime) -> str:
        """Immer absolute Uhrzeit HH:MM, bei < 1 min 'jetzt'."""
        delta = (departure_time - datetime.now()).total_seconds() / 60
        if delta < 1:
            return "jetzt"
        return departure_time.strftime("%H:%M")

    def _abbrev_stop(self, stop_name: str) -> str:
        """Letztes Wort des Stop-Namens, max 4 Zeichen für eInk-Spalte."""
        last_word = stop_name.strip().split()[-1] if stop_name.strip() else stop_name
        return last_word[:4]

    def _truncate(self, text: str, max_px: int) -> str:
        """Truncate text to fit within max_px (character estimate: 7px/char)."""
        if len(text) * 7 <= max_px:
            return text
        max_chars = max(0, max_px // 7 - 1)
        return text[:max_chars] + "…" if len(text) > max_chars else text
