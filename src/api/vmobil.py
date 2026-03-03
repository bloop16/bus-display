"""
VMobil.at API client for fetching bus departures.
Uses GTFS schedule data with real-time scraping as best-effort.
"""
from datetime import datetime
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

    def __init__(self):
        # GTFS Loader für echte Haltestellen-Daten
        try:
            from .gtfs_loader import get_gtfs_loader
            self.gtfs = get_gtfs_loader()
            self.use_gtfs = True
            logger.info("GTFSLoader initialized successfully")
        except Exception as e:
            logger.warning(f"GTFSLoader failed: {e}. Using fallback stops.")
            self.gtfs = None
            self.use_gtfs = False
        
        # Versuche Web Scraper zu laden (echte Echtzeit-Daten auf Pi)
        try:
            from .vmobil_web_scraper import VMobilWebScraper
            self.scraper = VMobilWebScraper()
            self.use_scraper = True
            logger.info("VMobilWebScraper initialized successfully")
        except Exception as e:
            logger.warning(f"VMobilWebScraper failed: {e}")
            self.scraper = None
            self.use_scraper = False
    
    def search_stops(self, query: str) -> List[Dict[str, str]]:
        """
        Search for bus stops by name.
        Uses GTFS data first, then falls back to web scraper, then fallback database.
        
        Args:
            query: Stop name to search for (e.g. "Bregenz Bahnhof")
            
        Returns:
            List of stops with 'id' and 'name' keys
        """
        if not query or not query.strip():
            return []
        
        # GTFS: Echte/vollständige Haltestellen-Daten
        if self.use_gtfs and self.gtfs:
            try:
                results = self.gtfs.search_stops(query.strip(), limit=10)
                if results:
                    logger.info(f"GTFS search found {len(results)} results for '{query}'")
                    return results
            except Exception as e:
                logger.warning(f"GTFS search failed: {e}")
        
        # Web Scraper: Echte Echtzeit-Daten (fallback)
        if self.use_scraper and self.scraper:
            try:
                return self.scraper.search_stops(query)
            except Exception as e:
                logger.warning(f"Web scraper search failed: {e}")
        
        # Fallback: Hardcoded stops
        logger.warning("All search methods failed, using hardcoded fallback")
        return self._get_fallback_stops(query)
    
    def _get_fallback_stops(self, query: str) -> List[Dict[str, str]]:
        """Fallback: Use hardcoded stops when GTFS/Scraper fail"""
        try:
            fallback_stops = [
                {'id': '490085500', 'name': 'Bregenz Bahnhof'},
                {'id': '490085600', 'name': 'Bregenz Hafen'},
                {'id': '490085700', 'name': 'Bregenz Landeskrankenhaus'},
                {'id': '490078100', 'name': 'Dornbirn Bahnhof'},
                {'id': '490078200', 'name': 'Dornbirn Zentrum'},
                {'id': '490076500', 'name': 'Feldkirch Bahnhof'},
                {'id': '490079100', 'name': 'Rankweil Bahnhof'},
                {'id': '490079200', 'name': 'Rankweil Konkordiaplatz'},
            ]
            
            query_lower = query.lower()
            # Fuzzy matching
            matches = [s for s in fallback_stops if query_lower in s['name'].lower()]
            return matches[:10]
            
        except Exception as e:
            logger.error(f"Fallback search failed: {e}")
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
        
        # Versuche Web Scraper zu nutzen (echte Daten)
        if self.use_scraper and self.scraper:
            try:
                raw_deps = self.scraper.get_departures(stop_id, limit)
                if not raw_deps:
                    logger.info(f"No live scraper departures for stop {stop_id}")
                else:
                    departures = [
                        Departure(
                            line=dep['line'],
                            destination=dep['destination'],
                            departure_time=dep['departure_time'],
                            stop_name=dep['stop_name'],
                            delay_minutes=dep.get('delay_minutes')
                        )
                        for dep in raw_deps
                    ]
                    return departures
            except Exception as e:
                logger.warning(f"Web scraper failed, falling back to GTFS: {e}")
        
        # Fallback 1: GTFS Soll-Abfahrten
        if self.use_gtfs and self.gtfs and stop_id:
            try:
                scheduled = self.gtfs.get_scheduled_departures(stop_id=stop_id, limit=limit)
                if scheduled:
                    logger.info(f"Using GTFS schedule fallback for stop {stop_id}")
                    return [
                        Departure(
                            line=dep['line'],
                            destination=dep['destination'],
                            departure_time=dep['departure_time'],
                            stop_name=dep['stop_name'],
                            delay_minutes=dep.get('delay_minutes')
                        )
                        for dep in scheduled
                    ]
            except Exception as e:
                logger.warning(f"GTFS fallback failed: {e}")

        logger.warning(f"No live or GTFS departures available for stop {stop_id or stop_name}")
        return []
