"""
E-Ink display renderer for bus departures.
Optimized for Waveshare 2.13" (250x122px B/W).
"""
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)


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
            self.font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
            self.font_medium = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 13)
            self.font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 10)
        except:
            logger.warning("TrueType fonts not available, using default")
            self.font_large = ImageFont.load_default()
            self.font_medium = ImageFont.load_default()
            self.font_small = ImageFont.load_default()
    
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
            departures: List of Departure objects
            stop_name: Name of bus stop
            battery_percent: Battery level (0-100), None if AC powered
            wifi_connected: WiFi status
            
        Returns:
            PIL Image (1-bit B/W, 250x122px)
        """
        # Create white background
        image = Image.new('1', (self.width, self.height), 255)
        draw = ImageDraw.Draw(image)
        
        y_pos = 2
        
        # Header: Stop name + status icons
        header_text = self._truncate_text(stop_name, max_width=180)
        draw.text((2, y_pos), header_text, font=self.font_medium, fill=0)
        
        # WiFi icon (simple text for now)
        if wifi_connected:
            draw.text((self.width - 25, y_pos), "W", font=self.font_small, fill=0)
        
        # Battery icon
        if battery_percent is not None:
            bat_text = f"{battery_percent}%"
            draw.text((self.width - 50, y_pos), bat_text, font=self.font_small, fill=0)
        
        y_pos += 20
        
        # Divider line
        draw.line((0, y_pos, self.width, y_pos), fill=0, width=1)
        y_pos += 4
        
        # Departures
        if not departures:
            # No departures
            msg = "Keine Abfahrten"
            draw.text((self.width//2 - 40, self.height//2 - 10), msg, font=self.font_medium, fill=0)
        else:
            # Show up to 4 departures
            for i, dep in enumerate(departures[:4]):
                if y_pos + 20 > self.height:
                    break
                
                # Line number (bold, left)
                line_text = dep.line
                draw.text((4, y_pos), line_text, font=self.font_large, fill=0)
                
                # Destination (middle)
                dest_text = self._truncate_text(dep.destination, max_width=130)
                draw.text((30, y_pos + 2), dest_text, font=self.font_medium, fill=0)
                
                # Time (right)
                time_text = self._format_time(dep.departure_time)
                time_width = draw.textlength(time_text, font=self.font_medium)
                draw.text((self.width - time_width - 4, y_pos + 2), time_text, font=self.font_medium, fill=0)
                
                y_pos += 23
        
        # Footer: Current time
        now_str = datetime.now().strftime("%H:%M")
        draw.text((self.width - 40, self.height - 12), now_str, font=self.font_small, fill=0)
        
        return image
    
    def _format_time(self, departure_time: datetime) -> str:
        """Format departure time as minutes from now or HH:MM"""
        now = datetime.now()
        delta = (departure_time - now).total_seconds() / 60
        
        if delta < 1:
            return "jetzt"
        elif delta < 60:
            return f"{int(delta)} min"
        else:
            return departure_time.strftime("%H:%M")
    
    def _truncate_text(self, text: str, max_width: int) -> str:
        """Truncate text to fit width (approximate)"""
        if len(text) * 7 <= max_width:  # Rough estimate
            return text
        
        # Truncate with ellipsis
        max_chars = max_width // 7
        if len(text) > max_chars:
            return text[:max_chars-3] + "..."
        return text
