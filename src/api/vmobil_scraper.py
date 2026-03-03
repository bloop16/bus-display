"""
Real VMobil.at web scraper.
Replaces mock data with actual bus departures.
"""
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import logging
from typing import List
from src.api.vmobil import Departure

logger = logging.getLogger(__name__)


class VMobilScraper:
    """Scrape vmobil.at for real departure data"""
    
    BASE_URL = "https://www.vmobil.at"
    API_KEY = "2d54e289220de1b2211954a12cc45f97"  # Found during research
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def search_stops(self, query: str, limit: int = 10) -> List[dict]:
        """
        Search for bus stops.
        
        Args:
            query: Search term (e.g. "Bregenz Bahnhof")
            limit: Max results
            
        Returns:
            List of {id, name} dicts
        """
        logger.info(f"Searching stops: {query}")
        
        try:
            # Try API endpoint first
            url = f"{self.BASE_URL}/api/stop/search"
            params = {
                'q': query,
                'limit': limit,
                'apikey': self.API_KEY
            }
            
            response = self.session.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if isinstance(data, list):
                    results = []
                    for stop in data[:limit]:
                        results.append({
                            'id': str(stop.get('id', stop.get('stopId', ''))),
                            'name': stop.get('name', stop.get('stopName', ''))
                        })
                    return results
            
            # Fallback: Web scraping
            logger.warning("API failed, trying web scraping...")
            return self._scrape_stop_search(query, limit)
            
        except Exception as e:
            logger.error(f"Stop search failed: {e}")
            return []
    
    def _scrape_stop_search(self, query: str, limit: int) -> List[dict]:
        """Fallback: Scrape web interface for stop search"""
        try:
            # VMobil search page
            url = f"{self.BASE_URL}/de/fahrplan/fahrplanauskunft"
            
            response = self.session.get(url, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find stop suggestions (this depends on actual HTML structure)
            # This is a placeholder - need to inspect actual HTML
            stops = []
            
            # Example structure (to be adapted):
            # <div class="stop-result" data-id="123" data-name="Bregenz Bahnhof">
            for elem in soup.find_all('div', class_='stop-result')[:limit]:
                stop_id = elem.get('data-id')
                stop_name = elem.get('data-name')
                
                if stop_id and stop_name and query.lower() in stop_name.lower():
                    stops.append({
                        'id': stop_id,
                        'name': stop_name
                    })
            
            return stops
            
        except Exception as e:
            logger.error(f"Web scraping failed: {e}")
            return []
    
    def get_departures(self, stop_id: str, limit: int = 10) -> List[Departure]:
        """
        Get real-time departures for a stop.
        
        Args:
            stop_id: Stop ID from search
            limit: Max departures
            
        Returns:
            List of Departure objects
        """
        logger.info(f"Fetching departures for stop {stop_id}")
        
        try:
            # Try API endpoint
            url = f"{self.BASE_URL}/api/departure/monitor"
            params = {
                'stopId': stop_id,
                'limit': limit,
                'apikey': self.API_KEY
            }
            
            response = self.session.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if isinstance(data, list):
                    departures = []
                    
                    for dep in data[:limit]:
                        # Parse departure time
                        time_str = dep.get('departureTime', dep.get('time', ''))
                        departure_time = self._parse_time(time_str)
                        
                        if departure_time:
                            departures.append(Departure(
                                line=dep.get('line', dep.get('lineName', 'Unknown')),
                                destination=dep.get('destination', dep.get('direction', 'Unknown')),
                                departure_time=departure_time,
                                stop_name=dep.get('stopName', '')
                            ))
                    
                    return departures
            
            # Fallback: Web scraping
            logger.warning("API failed, trying web scraping...")
            return self._scrape_departures(stop_id, limit)
            
        except Exception as e:
            logger.error(f"Departure fetch failed: {e}")
            return []
    
    def _scrape_departures(self, stop_id: str, limit: int) -> List[Departure]:
        """Fallback: Scrape web interface for departures"""
        try:
            # Departure monitor URL
            url = f"{self.BASE_URL}/de/fahrplan/abfahrtsmonitor"
            params = {'stopId': stop_id}
            
            response = self.session.get(url, params=params, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            departures = []
            
            # Example HTML structure (to be adapted):
            # <div class="departure">
            #   <span class="line">1</span>
            #   <span class="destination">Bregenz Bahnhof</span>
            #   <span class="time">14:35</span>
            # </div>
            
            for elem in soup.find_all('div', class_='departure')[:limit]:
                line = elem.find('span', class_='line')
                dest = elem.find('span', class_='destination')
                time = elem.find('span', class_='time')
                
                if line and dest and time:
                    departure_time = self._parse_time(time.text.strip())
                    
                    if departure_time:
                        departures.append(Departure(
                            line=line.text.strip(),
                            destination=dest.text.strip(),
                            departure_time=departure_time,
                            stop_name=''
                        ))
            
            return departures
            
        except Exception as e:
            logger.error(f"Departure scraping failed: {e}")
            return []
    
    def _parse_time(self, time_str: str) -> datetime:
        """
        Parse time string to datetime.
        
        Supports formats:
        - "14:35" (today)
        - "5 min" (relative)
        - ISO timestamps
        """
        now = datetime.now()
        
        try:
            # Relative minutes
            if 'min' in time_str.lower():
                minutes = int(''.join(filter(str.isdigit, time_str)))
                return now + timedelta(minutes=minutes)
            
            # HH:MM format
            if ':' in time_str and len(time_str) <= 5:
                hour, minute = map(int, time_str.split(':'))
                dep_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
                
                # If time is in the past, assume tomorrow
                if dep_time < now:
                    dep_time += timedelta(days=1)
                
                return dep_time
            
            # ISO timestamp
            return datetime.fromisoformat(time_str.replace('Z', '+00:00'))
            
        except Exception as e:
            logger.error(f"Time parse failed: {time_str} - {e}")
            return None


def main():
    """Test scraper"""
    logging.basicConfig(level=logging.INFO)
    
    scraper = VMobilScraper()
    
    # Test stop search
    print("=== Searching Stops ===")
    stops = scraper.search_stops("Bregenz")
    for stop in stops:
        print(f"{stop['id']}: {stop['name']}")
    
    # Test departures (if we have stops)
    if stops:
        print("\n=== Getting Departures ===")
        stop_id = stops[0]['id']
        departures = scraper.get_departures(stop_id, limit=5)
        
        for dep in departures:
            print(f"{dep.line} → {dep.destination} @ {dep.departure_time.strftime('%H:%M')}")


if __name__ == '__main__':
    main()
