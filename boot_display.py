#!/usr/bin/env python3
"""
Boot display script - shows status during startup.
Run this at boot BEFORE main service starts.
"""
import socket
import time
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.display.driver import DisplayDriver
from src.display.status_display import StatusDisplay


def get_hostname():
    """Get system hostname"""
    return socket.gethostname()


def get_ip_address():
    """Get IP address (WiFi or Ethernet)"""
    try:
        # Try to connect to external host to get our IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return None


def get_wifi_ssid():
    """Get connected WiFi SSID"""
    try:
        import subprocess
        result = subprocess.run(
            ['iwgetid', '-r'],
            capture_output=True,
            text=True,
            timeout=2
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except:
        pass
    return None


def main():
    """Show boot screen with network info"""
    print("=== Bus Display Boot Screen ===")
    
    # Initialize display
    driver = DisplayDriver(mock=False)
    status = StatusDisplay()
    
    # Show boot screen
    hostname = get_hostname()
    print(f"Hostname: {hostname}")
    
    image = status.boot_screen(hostname)
    driver.display_image(image)
    
    # Wait for network
    print("Waiting for network...")
    time.sleep(5)
    
    # Get network info
    ip_address = get_ip_address()
    wifi_ssid = get_wifi_ssid()
    
    print(f"IP: {ip_address}")
    print(f"WiFi: {wifi_ssid}")
    
    # Check if configured
    config_file = Path('/home/pi/bus-display/config/stops.json')
    if not config_file.exists() or config_file.stat().st_size < 20:
        # Show setup screen
        print("No configuration found - showing setup screen")
        image = status.setup_screen(wifi_ssid, ip_address)
        driver.display_image(image)
    else:
        print("Configuration found - main service will take over")
    
    print("Boot display complete")


if __name__ == '__main__':
    main()
