"""
E-Ink display hardware driver.
Wraps Waveshare library with mock mode for testing.
"""
from PIL import Image
import logging

logger = logging.getLogger(__name__)


class DisplayDriver:
    """Hardware driver for Waveshare 2.13" e-Paper HAT"""
    
    def __init__(self, mock=False):
        """
        Initialize display driver.
        
        Args:
            mock: If True, run in mock mode (no hardware access)
        """
        self.mock = mock
        self.initialized = False
        
        if not mock:
            try:
                # Import Waveshare library
                from waveshare_epd import epd2in13_V4
                self.epd = epd2in13_V4.EPD()

                logger.info("Initializing e-Paper display...")
                self.epd.init()
                self.epd.Clear(0xFF)  # Clear to white
                self.epd.sleep()      # Power-save immediately after clear

                self.initialized = True
                logger.info("Display initialized successfully")

            except ImportError:
                logger.warning("Waveshare library not found, using mock mode")
                self.mock = True
                self.initialized = True
            except Exception as e:
                logger.error(f"Display init failed: {e}")
                self.mock = True
                self.initialized = False
        else:
            self.initialized = True
            logger.info("Display driver in mock mode")
    
    def display_image(self, image: Image.Image):
        """
        Display image on e-ink screen.
        
        Args:
            image: PIL Image (1-bit B/W, 250x122px)
        """
        if not self.initialized:
            logger.error("Display not initialized")
            return
        
        if self.mock:
            logger.info(f"[MOCK] Would display image: {image.size} {image.mode}")
            return

        try:
            # Wake display from sleep, show image, then sleep again
            self.epd.init()
            buf = self.epd.getbuffer(image)
            self.epd.display(buf)
            self.epd.sleep()
            logger.info("Image displayed, display sleeping")
        except Exception as e:
            logger.error(f"Display failed: {e}")
    
    def clear(self):
        """Clear display to white"""
        if self.mock:
            logger.info("[MOCK] Would clear display")
            return
        
        if self.initialized:
            try:
                self.epd.Clear(0xFF)
                logger.info("Display cleared")
            except Exception as e:
                logger.error(f"Clear failed: {e}")
    
    def sleep(self):
        """Put display to sleep (low power mode)"""
        if self.mock:
            logger.info("[MOCK] Would sleep display")
            return
        
        if self.initialized:
            try:
                self.epd.sleep()
                logger.info("Display sleeping")
            except Exception as e:
                logger.error(f"Sleep failed: {e}")
