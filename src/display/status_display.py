"""
Status display screens for various system states.
Shows helpful info on e-ink display.
"""
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class StatusDisplay:
    """Render status screens for e-ink display"""
    
    WIDTH = 250
    HEIGHT = 122
    
    def __init__(self):
        try:
            self.font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 18)
            self.font_medium = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
            self.font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 11)
        except:
            self.font_large = ImageFont.load_default()
            self.font_medium = ImageFont.load_default()
            self.font_small = ImageFont.load_default()
    
    def boot_screen(self, hostname: str = "bus-display") -> Image.Image:
        """Boot screen shown during startup"""
        image = Image.new('1', (self.WIDTH, self.HEIGHT), 255)
        draw = ImageDraw.Draw(image)
        
        # Title
        draw.text((self.WIDTH//2 - 60, 20), "🚍 Bus Display", font=self.font_large, fill=0)
        
        # Status
        draw.text((self.WIDTH//2 - 40, 50), "Booting...", font=self.font_medium, fill=0)
        
        # Hostname
        draw.text((10, self.HEIGHT - 15), f"Hostname: {hostname}", font=self.font_small, fill=0)
        
        return image
    
    def setup_screen(self, wifi_ssid: str = None, ip_address: str = None) -> Image.Image:
        """Setup screen - shown when no stops configured"""
        image = Image.new('1', (self.WIDTH, self.HEIGHT), 255)
        draw = ImageDraw.Draw(image)
        
        y = 5
        
        # Title
        draw.text((10, y), "Setup Required", font=self.font_large, fill=0)
        y += 25
        
        # Divider
        draw.line((5, y, self.WIDTH-5, y), fill=0, width=1)
        y += 8
        
        # WiFi Info
        if wifi_ssid:
            draw.text((10, y), f"WiFi: {wifi_ssid}", font=self.font_small, fill=0)
            y += 16
        else:
            draw.text((10, y), "WiFi: Connecting...", font=self.font_small, fill=0)
            y += 16
        
        # IP Address
        if ip_address:
            draw.text((10, y), f"IP: {ip_address}", font=self.font_medium, fill=0)
            y += 20
        else:
            draw.text((10, y), "Getting IP address...", font=self.font_small, fill=0)
            y += 18
        
        # Instructions
        draw.text((10, y), "1. Connect to WiFi", font=self.font_small, fill=0)
        y += 14
        draw.text((10, y), "2. Visit web interface:", font=self.font_small, fill=0)
        y += 14
        
        if ip_address:
            url = f"   http://{ip_address}:5000"
        else:
            url = "   http://bus-display.local:5000"
        
        draw.text((10, y), url, font=self.font_small, fill=0)
        
        return image
    
    def wifi_ap_screen(self, ssid: str = "BusDisplay", password: str = None) -> Image.Image:
        """WiFi AP mode screen - shown when AP is active"""
        image = Image.new('1', (self.WIDTH, self.HEIGHT), 255)
        draw = ImageDraw.Draw(image)
        
        y = 5
        
        # Title
        draw.text((10, y), "WiFi Setup Mode", font=self.font_large, fill=0)
        y += 25
        
        # Divider
        draw.line((5, y, self.WIDTH-5, y), fill=0, width=1)
        y += 10
        
        # Instructions
        draw.text((10, y), "1. Connect to WiFi:", font=self.font_medium, fill=0)
        y += 18
        draw.text((20, y), f"SSID: {ssid}", font=self.font_medium, fill=0)
        y += 18
        
        if password:
            draw.text((20, y), f"Pass: {password}", font=self.font_small, fill=0)
            y += 16
        
        y += 5
        draw.text((10, y), "2. Browser opens auto", font=self.font_small, fill=0)
        y += 14
        draw.text((10, y), "   or visit:", font=self.font_small, fill=0)
        y += 14
        draw.text((20, y), "http://192.168.4.1", font=self.font_medium, fill=0)
        
        return image
    
    def error_screen(self, error_msg: str, details: str = None) -> Image.Image:
        """Error screen"""
        image = Image.new('1', (self.WIDTH, self.HEIGHT), 255)
        draw = ImageDraw.Draw(image)
        
        y = 10
        
        # Title
        draw.text((10, y), "⚠ Error", font=self.font_large, fill=0)
        y += 28
        
        # Divider
        draw.line((5, y, self.WIDTH-5, y), fill=0, width=1)
        y += 10
        
        # Error message
        lines = self._wrap_text(error_msg, 30)
        for line in lines[:3]:  # Max 3 lines
            draw.text((10, y), line, font=self.font_small, fill=0)
            y += 14
        
        if details:
            y += 5
            detail_lines = self._wrap_text(details, 30)
            for line in detail_lines[:2]:  # Max 2 lines
                draw.text((10, y), line, font=self.font_small, fill=0)
                y += 12
        
        return image
    
    def _wrap_text(self, text: str, max_chars: int) -> list:
        """Wrap text to fit width"""
        words = text.split()
        lines = []
        current_line = []
        
        for word in words:
            test_line = ' '.join(current_line + [word])
            if len(test_line) <= max_chars:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                current_line = [word]
        
        if current_line:
            lines.append(' '.join(current_line))
        
        return lines
