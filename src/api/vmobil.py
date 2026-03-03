"""
VMobil.at API client for fetching bus departures.
Uses web scraping since public API is not available.
"""
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)


class VMobilAPIError(Exception):
    """Raised when vmobil.at API fails"""
    pass


@dataclass
class Departure:
    """Bus departure information"""
    line: str
    destination: str
    departure_time: datetime
    stop_name: str
    delay_minutes: Optional[int] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        data['departure_time'] = self.departure_time.isoformat()
        return data


class VMobilAPI:
    """Client for vmobil.at bus departure data"""
    
    BASE_URL = "https://www.vmobil.at"
    
    def __init__(self, timeout: int = 10):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'BusDisplay/1.0 (Raspberry Pi)'
        })
    
    def search_stops(self, query: str) -> List[Dict[str, str]]:
        """
        Search for bus stops by name.
        
        Args:
            query: Stop name to search for (e.g. "Bregenz Bahnhof")
            
        Returns:
            List of stops with 'id' and 'name' keys
        """
        if not query or not query.strip():
            return []
        
        try:
            # Try autocomplete endpoint first
            url = f"{self.BASE_URL}/de/api/autocomplete"
            params = {'term': query.strip()}
            
            response = self.session.get(
                url,
                params=params,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                # Parse JSON response (structure TBD during testing)
                if isinstance(data, list):
                    return [
                        {'id': str(item.get('id', '')), 'name': item.get('label', item.get('name', ''))}
                        for item in data
                        if item.get('label') or item.get('name')
                    ]
            
            # Fallback: scrape from routing page
            logger.warning("Autocomplete failed, using fallback search")
            return self._search_stops_fallback(query)
            
        except requests.Timeout:
            raise VMobilAPIError(f"Search timeout after {self.timeout}s")
        except requests.RequestException as e:
            raise VMobilAPIError(f"Search failed: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in search_stops: {e}")
            return []
    
    def _search_stops_fallback(self, query: str) -> List[Dict[str, str]]:
        """Fallback: scrape stops from routing page"""
        # TODO: Implement scraping if autocomplete doesn't work
        # For now return mock data for testing
        if "Bregenz" in query:
            return [
                {'id': '1', 'name': 'Bregenz Bahnhof'},
                {'id': '2', 'name': 'Bregenz Hafen'},
            ]
        return []
    
    def get_departures(
        self,
        stop_id: Optional[str] = None,
        stop_name: Optional[str] = None,
        limit: int = 10
    ) -> List[Departure]:
        """
        Get next departures for a bus stop.
        
        Args:
            stop_id: Stop ID from search_stops()
            stop_name: Alternative: stop name for direct lookup
            limit: Maximum number of departures to return
            
        Returns:
            List of Departure objects
        """
        if not stop_id and not stop_name:
            raise VMobilAPIError("Either stop_id or stop_name required")
        
        try:
            # Use stop name if provided, otherwise resolve ID
            name = stop_name if stop_name else self._resolve_stop_id(stop_id)
            
            # Fetch departure board
            departures = self._fetch_departure_board(name, limit)
            return departures
            
        except requests.Timeout:
            raise VMobilAPIError(f"Departure fetch timeout after {self.timeout}s")
        except requests.RequestException as e:
            raise VMobilAPIError(f"Departure fetch failed: {e}")
    
    def _resolve_stop_id(self, stop_id: str) -> str:
        """Convert stop ID to name (for scraping)"""
        # Mock implementation - would normally query API/scrape
        id_map = {
            '1': 'Bregenz Bahnhof',
            '2': 'Bregenz Hafen',
            'test_stop': 'Test Stop'
        }
        return id_map.get(stop_id, stop_id)
    
    def _fetch_departure_board(self, stop_name: str, limit: int) -> List[Departure]:
        """
        Scrape departure board from vmobil.at
        
        This is the core scraping logic - will be refined during testing
        """
        url = f"{self.BASE_URL}/de/routen"
        
        # For now: return mock data for testing
        # TODO: Implement actual scraping once we analyze page structure
        now = datetime.now()
        
        mock_departures = [
            Departure(
                line="1",
                destination="Bregenz Bahnhof",
                departure_time=now + timedelta(minutes=5),
                stop_name=stop_name
            ),
            Departure(
                line="5",
                destination="Dornbirn",
                departure_time=now + timedelta(minutes=12),
                stop_name=stop_name,
                delay_minutes=2
            ),
            Departure(
                line="3",
                destination="Bludenz",
                departure_time=now + timedelta(minutes=18),
                stop_name=stop_name
            ),
        ]
        
        return mock_departures[:limit]
    
    def _parse_time(self, time_str: str) -> datetime:
        """
        Parse time string from vmobil.at to datetime.
        
        Args:
            time_str: Time in format "HH:MM" (e.g. "14:35")
            
        Returns:
            datetime object with today's date and parsed time
        """
        try:
            hour, minute = map(int, time_str.split(':'))
            now = datetime.now()
            parsed = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            
            # If time is in the past, assume it's tomorrow
            if parsed < now:
                parsed += timedelta(days=1)
            
            return parsed
        except (ValueError, AttributeError) as e:
            raise VMobilAPIError(f"Invalid time format: {time_str}")

    def enable_real_scraping(self):
        """Switch to real VMobil scraping instead of mock data"""
        from .vmobil_scraper import VMobilScraper
        self.scraper = VMobilScraper()
        self.use_real_data = True
        logger.info("Real scraping enabled")
    
    def search_stops_real(self, query: str, limit: int = 10) -> List[dict]:
        """Search stops using real scraper"""
        if hasattr(self, 'scraper'):
            return self.scraper.search_stops(query, limit)
        return self.search_stops(query, limit)  # Fallback to mock
    
    def get_departures_real(self, stop_id: str, limit: int = 10) -> List[Departure]:
        """Get departures using real scraper"""
        if hasattr(self, 'scraper'):
            return self.scraper.get_departures(stop_id, limit)
        return self.get_departures(stop_id, limit)  # Fallback to mock
