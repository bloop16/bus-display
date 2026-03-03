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
        wifi_connected: bool = True
    ) -> Image.Image:
        """
        Render bus departures to image.

        Args:
            departures: List of Departure objects (up to 6 shown)
            stop_name: Name of bus stop (shown in header)
            battery_percent: Battery level 0-100, None if AC powered
            wifi_connected: WiFi status indicator

        Returns:
            PIL Image (1-bit B/W, 250x122px)
        """
        image = Image.new('1', (self.width, self.height), 255)
        draw = ImageDraw.Draw(image)

        # ── Header ───────────────────────────────────────────────
        y = 1
        header_text = self._truncate(stop_name, max_px=165)
        draw.text((2, y), header_text, font=self.font_header, fill=0)

        # Status icons (right side)
        x_right = self.width - 2
        if battery_percent is not None:
            bat_text = f"{battery_percent}%"
            bat_w = int(draw.textlength(bat_text, font=self.font_small))
            draw.text((x_right - bat_w, y + 1), bat_text, font=self.font_small, fill=0)
            x_right -= bat_w + 4

        if wifi_connected:
            w_w = int(draw.textlength("W", font=self.font_small))
            draw.text((x_right - w_w, y + 1), "W", font=self.font_small, fill=0)

        # ── Divider ───────────────────────────────────────────────
        y += 14
        draw.line((0, y, self.width, y), fill=0, width=1)
        y += 2

        # ── Departure rows (max 6, 15px each) ────────────────────
        ROW_H = 15
        if not departures:
            draw.text((4, y + 16), "Keine Abfahrten", font=self.font_dep, fill=0)
        else:
            for dep in departures[:6]:
                if y + ROW_H > self.height - 12:
                    break

                x = 2
                row_y_center = y + (ROW_H - ICON_SIZE) // 2  # vertical center for icon

                # Icon (12×12) if set
                icon_img = self._get_icon(dep.icon) if dep.icon else None
                if icon_img:
                    image.paste(icon_img, (x, row_y_center))
                    x += ICON_SIZE + 2

                # Line number (bold)
                line_text = str(dep.line)
                line_w = int(draw.textlength(line_text, font=self.font_line))
                draw.text((x, y + 1), line_text, font=self.font_line, fill=0)
                x += line_w + 4

                # Time (right-aligned)
                time_text = self._format_time(dep.departure_time)
                time_w = int(draw.textlength(time_text, font=self.font_dep))
                draw.text((self.width - time_w - 2, y + 2), time_text, font=self.font_dep, fill=0)

                # Destination (between line and time)
                dest_max_px = self.width - x - time_w - 8
                dest_text = self._truncate(dep.destination, max_px=dest_max_px)
                draw.text((x, y + 2), dest_text, font=self.font_dep, fill=0)

                y += ROW_H

        # ── Footer: current time ──────────────────────────────────
        now_str = datetime.now().strftime("%H:%M")
        now_w = int(draw.textlength(now_str, font=self.font_small))
        draw.text((self.width - now_w - 2, self.height - 11), now_str, font=self.font_small, fill=0)

        return image

    # ── Helpers ──────────────────────────────────────────────────

    def _format_time(self, departure_time: datetime) -> str:
        """Format departure as minutes-from-now or HH:MM."""
        delta = (departure_time - datetime.now()).total_seconds() / 60
        if delta < 1:
            return "jetzt"
        if delta < 60:
            return f"{int(delta)} min"
        return departure_time.strftime("%H:%M")

    def _truncate(self, text: str, max_px: int) -> str:
        """Truncate text to fit within max_px (character estimate: 7px/char)."""
        if len(text) * 7 <= max_px:
            return text
        max_chars = max(0, max_px // 7 - 1)
        return text[:max_chars] + "…" if len(text) > max_chars else text
