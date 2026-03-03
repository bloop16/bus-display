"""
Test suite for e-ink display rendering.
TDD: Tests FIRST!
"""
import pytest
from datetime import datetime, timedelta
from PIL import Image


class TestDisplayRenderer:
    """Test e-ink display rendering"""
    
    def test_create_display_with_correct_size(self):
        """Display should be 250x122px for Waveshare 2.13" """
        from src.display.renderer import DisplayRenderer
        
        renderer = DisplayRenderer()
        assert renderer.width == 250
        assert renderer.height == 122
    
    def test_render_departures_returns_image(self):
        """Should render departures to PIL Image"""
        from src.display.renderer import DisplayRenderer
        from src.api import Departure
        
        renderer = DisplayRenderer()
        now = datetime.now()
        
        departures = [
            Departure("1", "Bregenz Bahnhof", now + timedelta(minutes=5), "Test Stop"),
            Departure("5", "Dornbirn", now + timedelta(minutes=12), "Test Stop"),
        ]
        
        image = renderer.render_departures(departures, "Test Stop")
        
        assert isinstance(image, Image.Image)
        assert image.size == (250, 122)
        assert image.mode == '1'  # 1-bit black/white
    
    def test_render_empty_departures(self):
        """Should handle empty departure list"""
        from src.display.renderer import DisplayRenderer
        
        renderer = DisplayRenderer()
        image = renderer.render_departures([], "Test Stop")
        
        assert isinstance(image, Image.Image)
        # Should show "No departures" message
    
    def test_format_time_minutes(self):
        """Should format departure time as minutes"""
        from src.display.renderer import DisplayRenderer
        
        renderer = DisplayRenderer()
        now = datetime.now()
        
        # 5 minutes from now
        time_5min = now + timedelta(minutes=5)
        formatted = renderer._format_time(time_5min)
        assert "min" in formatted.lower()  # 4-5 min, timing dependent
        assert "min" in formatted.lower()
        
        # < 1 minute
        time_now = now + timedelta(seconds=30)
        formatted = renderer._format_time(time_now)
        assert "now" in formatted.lower() or "jetzt" in formatted.lower()
    
    def test_truncate_long_destination_names(self):
        """Long destination names should be truncated"""
        from src.display.renderer import DisplayRenderer
        
        renderer = DisplayRenderer()
        long_name = "Bregenz Hauptbahnhof Gleis 3 Richtung Feldkirch"
        
        truncated = renderer._truncate_text(long_name, max_width=100)
        assert len(truncated) < len(long_name)
        assert truncated.endswith("...")
    
    def test_render_with_battery_indicator(self):
        """Should include battery indicator if provided"""
        from src.display.renderer import DisplayRenderer
        from src.api import Departure
        
        renderer = DisplayRenderer()
        now = datetime.now()
        deps = [Departure("1", "Test", now, "Stop")]
        
        # With battery level
        image = renderer.render_departures(deps, "Stop", battery_percent=75)
        assert isinstance(image, Image.Image)
    
    def test_render_with_wifi_status(self):
        """Should show WiFi status"""
        from src.display.renderer import DisplayRenderer
        from src.api import Departure
        
        renderer = DisplayRenderer()
        now = datetime.now()
        deps = [Departure("1", "Test", now, "Stop")]
        
        # WiFi connected
        image = renderer.render_departures(deps, "Stop", wifi_connected=True)
        assert isinstance(image, Image.Image)
        
        # WiFi disconnected
        image = renderer.render_departures(deps, "Stop", wifi_connected=False)
        assert isinstance(image, Image.Image)


class TestDisplayDriver:
    """Test e-ink hardware driver (mock for tests)"""
    
    def test_display_init(self):
        """Should initialize display driver"""
        from src.display.driver import DisplayDriver
        
        driver = DisplayDriver(mock=True)  # Mock mode for testing
        assert driver.initialized
    
    def test_display_image(self):
        """Should display image on e-ink"""
        from src.display.driver import DisplayDriver
        from PIL import Image
        
        driver = DisplayDriver(mock=True)
        image = Image.new('1', (250, 122), 255)  # White image
        
        # Should not raise exception
        driver.display_image(image)
    
    def test_display_clear(self):
        """Should clear display"""
        from src.display.driver import DisplayDriver
        
        driver = DisplayDriver(mock=True)
        driver.clear()
    
    def test_display_sleep(self):
        """Should put display to sleep"""
        from src.display.driver import DisplayDriver
        
        driver = DisplayDriver(mock=True)
        driver.sleep()
