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
    icons: List[str] = None             # ['home', 'train', ...] – alle passenden Icons
    trip_id: Optional[str] = None       # GTFS trip_id für Via-Halt-Matching (intern)
    boarding_stop_id: Optional[str] = None  # Stop-ID des Einstiegs (intern)

    def __post_init__(self):
        if self.icons is None:
            self.icons = []

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        data = asdict(self)
        data['departure_time'] = self.departure_time.isoformat()
        data.pop('trip_id', None)           # interne Felder nicht an Web-UI senden
        data.pop('boarding_stop_id', None)
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
        self._via_ids_cache = {}

    def _resolve_via_ids(self, via: Dict, gtfs=None) -> List[str]:
        """Liefert robuste ID-Liste für Via-Stop (ids[] bevorzugt, sonst via Name auflösen)."""
        via_ids = via.get('ids') or [via.get('id')]
        via_ids = [sid for sid in via_ids if sid]

        if len(via_ids) > 1 or not gtfs:
            return via_ids

        via_name = via.get('name')
        if not via_name:
            return via_ids

        cache_key = via_name.strip().lower()
        cached = self._via_ids_cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            matches = gtfs.search_stops(via_name, limit=10)
            exact = next((m for m in matches if m.get('name') == via_name), None)
            resolved = exact.get('ids', []) if exact else via_ids
            resolved = [sid for sid in resolved if sid]
            if not resolved:
                resolved = via_ids
            self._via_ids_cache[cache_key] = resolved
            return resolved
        except Exception as e:
            logger.debug(f"Via-ID resolve failed for {via_name}: {e}")
            self._via_ids_cache[cache_key] = via_ids
            return via_ids

    def _infer_trip_id_for_live(self, dep: 'Departure', gtfs) -> Optional[str]:
        """Live-Abfahrt ohne trip_id per GTFS approximieren."""
        if dep.trip_id or not dep.boarding_stop_id or not gtfs:
            return dep.trip_id
        try:
            return gtfs.find_trip_id_for_departure(
                stop_id=dep.boarding_stop_id,
                line=str(dep.line),
                departure_time=dep.departure_time,
                destination=dep.destination,
                max_diff_minutes=8,
            )
        except Exception as e:
            logger.debug(f"Trip inference failed for {dep.line}/{dep.destination}: {e}")
            return None

    def _resolve_configured_stop_ids(self, stop: Dict) -> List[str]:
        """
        Resolve stop IDs from config robustly.
        Keeps configured IDs first and appends GTFS-resolved IDs by stop name
        (useful for legacy numeric IDs from older configs).
        """
        configured = stop.get('ids') or [stop.get('id')]
        configured = [sid for sid in configured if sid]

        if not (self.use_gtfs and self.gtfs):
            return configured

        stop_name = (stop.get('name') or '').strip()
        if not stop_name:
            return configured

        try:
            matches = self.gtfs.search_stops(stop_name, limit=10)
            exact = next((m for m in matches if (m.get('name') or '').strip() == stop_name), None)
            resolved = (exact or {}).get('ids') or []
            combined = list(configured)
            for sid in resolved:
                if sid and sid not in combined:
                    combined.append(sid)
            if combined != configured:
                logger.info(f"Resolved additional stop IDs for '{stop_name}': {combined}")
            return combined
        except Exception as e:
            logger.debug(f"Stop-ID resolution failed for '{stop_name}': {e}")
            return configured
    
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
                            delay_minutes=dep.get('delay_minutes'),
                            trip_id=dep.get('trip_id'),
                        )
                        for dep in scheduled
                    ]
            except Exception as e:
                logger.warning(f"GTFS fallback failed: {e}")

        logger.warning(f"No live or GTFS departures available for stop {stop_id or stop_name}")
        return []

    def get_all_departures(
        self,
        stops: List[Dict],
        destinations: List[Dict],
        limit: int = 6
    ) -> List[Departure]:
        """
        Aggregate departures from all configured stops, sorted by time.
        Jeder Stop kann mehrere IDs haben (stops[n]['ids'] oder ['id'] als Fallback).
        """
        all_deps: List[Departure] = []

        for stop in stops:
            stop_ids = self._resolve_configured_stop_ids(stop)
            for sid in stop_ids:
                try:
                    deps = self.get_departures(stop_id=sid, limit=limit)
                    for dep in deps:
                        dep.boarding_stop_id = sid  # Einstiegs-Stop merken für Richtungsprüfung
                    all_deps.extend(deps)
                except Exception as e:
                    logger.warning(f"Failed to get departures for {stop.get('name')} / {sid}: {e}")

        # Sort by departure time
        all_deps.sort(key=lambda d: d.departure_time)

        # Duplikate entfernen: gleiche Linie + Abfahrtszeit + Ziel = selbe Fahrt
        seen: set = set()
        unique_deps: List[Departure] = []
        for dep in all_deps:
            key = (dep.line, dep.departure_time, dep.destination)
            if key not in seen:
                seen.add(key)
                unique_deps.append(dep)

        # Icons via Via-Halt-Matching (GTFS) oder Keyword-Fallback (Scraper)
        gtfs = self.gtfs if self.use_gtfs else None
        for dep in unique_deps:
            if gtfs and not dep.trip_id:
                dep.trip_id = self._infer_trip_id_for_live(dep, gtfs)
            dep.icons = self._match_destination_icons(dep, destinations, gtfs)

        return unique_deps[:limit]

    def _match_destination_icons(
        self,
        dep: 'Departure',
        destinations: List[Dict],
        gtfs=None,
    ) -> List[str]:
        """
        Sammelt ALLE passenden Icons für eine Abfahrt (nicht nur das erste).
        - Primär: via_stops (GTFS) – Trip hält an konfigurierter Zwischen-Haltestelle
        - Fallback: keywords auf Destination-Text (Scraper / kein trip_id)
        """
        matched: List[str] = []
        seen_icons: set = set()

        for entry in destinations:
            icon = entry.get('icon')
            if not icon or icon in seen_icons:
                continue

            matched_entry = False

            # Via-Halt-Matching (GTFS) – nur wenn Via-Stop NACH dem Einstieg kommt
            via_stops = entry.get('via_stops', [])
            if via_stops and dep.trip_id and gtfs:
                for via in via_stops:
                    if matched_entry:
                        break
                    via_ids = self._resolve_via_ids(via, gtfs)
                    for via_id in via_ids:
                        if not via_id:
                            continue
                        if dep.boarding_stop_id:
                            if gtfs.trip_passes_stop_after(dep.trip_id, dep.boarding_stop_id, via_id):
                                matched_entry = True
                                break
                        else:
                            if gtfs.trip_passes_stop(dep.trip_id, via_id):
                                matched_entry = True
                                break

            # Keyword-Fallback (rückwärtskompatibel / Scraper-Daten)
            if not matched_entry:
                keywords = entry.get('keywords', [])
                if keywords:
                    dest_lower = dep.destination.lower()
                    for kw in keywords:
                        if kw.lower() in dest_lower:
                            matched_entry = True
                            break

            if matched_entry:
                matched.append(icon)
                seen_icons.add(icon)

        return matched
