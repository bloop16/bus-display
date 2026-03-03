"""
GTFS Loader for Vorarlberg (VMobil)
Downloads and parses official GTFS data from data.mobilitaetsverbuende.at
"""

import os
import json
import zipfile
import csv
import logging
import requests
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

GTFS_URL = "https://mobilitydata.gv.at/sites/default/files/metadataset/sample_data/20231229-0218_gtfs_vmobil_2024.zip"
CACHE_DIR = Path(__file__).parent.parent.parent / "data"
STOPS_CACHE_FILE = CACHE_DIR / "stops.json"
CACHE_EXPIRY_HOURS = 24


class GTFSLoader:
    """Load and parse GTFS data for Vorarlberg VMobil"""

    def __init__(self):
        self.stops_data = {}
        self.cache_file = STOPS_CACHE_FILE
        self._ensure_cache_dir()
        self._load_or_fetch_stops()

    def _ensure_cache_dir(self):
        """Create cache directory if it doesn't exist"""
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)

    def _load_or_fetch_stops(self):
        """Load stops from cache or fetch new data"""
        if self._cache_valid():
            logger.info("Loading stops from cache")
            self._load_from_cache()
        else:
            logger.info("Fetching fresh GTFS data")
            self._fetch_and_parse()

    def _cache_valid(self) -> bool:
        """Check if cached data is still valid"""
        if not self.cache_file.exists():
            return False
        
        file_age = datetime.now() - datetime.fromtimestamp(
            self.cache_file.stat().st_mtime
        )
        return file_age < timedelta(hours=CACHE_EXPIRY_HOURS)

    def _load_from_cache(self):
        """Load stops data from JSON cache"""
        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.stops_data = {stop['stop_id']: stop for stop in data.get('stops', [])}
                logger.info(f"Loaded {len(self.stops_data)} stops from cache")
        except Exception as e:
            logger.error(f"Failed to load cache: {e}. Fetching fresh data.")
            self._fetch_and_parse()

    def _fetch_and_parse(self):
        """Fetch GTFS ZIP and parse stops.txt"""
        try:
            logger.info(f"Downloading GTFS from {GTFS_URL}")
            response = requests.get(GTFS_URL, timeout=30)
            response.raise_for_status()

            # Save ZIP to temp location
            zip_path = self.cache_file.parent / "gtfs_temp.zip"
            with open(zip_path, 'wb') as f:
                f.write(response.content)

            # Extract and parse stops.txt
            self._parse_zip(zip_path)

            # Clean up
            zip_path.unlink()

        except requests.RequestException as e:
            logger.error(f"Failed to download GTFS: {e}")
            logger.warning("Using fallback: loading from local cache or hardcoded stops")
            self._fallback_stops()

    def _parse_zip(self, zip_path):
        """Extract and parse stops.txt from GTFS ZIP"""
        try:
            with zipfile.ZipFile(zip_path, 'r') as zip_file:
                # Find stops.txt (might be in subdirectory)
                stops_files = [f for f in zip_file.namelist() if f.endswith('stops.txt')]
                if not stops_files:
                    logger.error("stops.txt not found in GTFS ZIP")
                    self._fallback_stops()
                    return

                stops_file = stops_files[0]
                logger.info(f"Parsing {stops_file}")

                with zip_file.open(stops_file) as f:
                    reader = csv.DictReader(f.read().decode('utf-8').splitlines())
                    stops = []
                    for row in reader:
                        stop = {
                            'stop_id': row.get('stop_id', ''),
                            'stop_name': row.get('stop_name', ''),
                            'stop_lat': float(row.get('stop_lat', 0)),
                            'stop_lon': float(row.get('stop_lon', 0)),
                        }
                        stops.append(stop)
                        self.stops_data[stop['stop_id']] = stop

                    logger.info(f"Parsed {len(stops)} stops from GTFS")
                    self._save_to_cache(stops)

        except Exception as e:
            logger.error(f"Error parsing GTFS ZIP: {e}")
            self._fallback_stops()

    def _save_to_cache(self, stops):
        """Save parsed stops to JSON cache"""
        try:
            data = {
                'timestamp': datetime.now().isoformat(),
                'stops': stops
            }
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved {len(stops)} stops to cache")
        except Exception as e:
            logger.error(f"Failed to save cache: {e}")

    def _fallback_stops(self):
        """Fallback: Hardcoded Vorarlberg stops for testing"""
        logger.warning("Using fallback hardcoded stops")
        fallback = [
            {'stop_id': '490085500', 'stop_name': 'Bregenz Bahnhof', 'stop_lat': 47.5038, 'stop_lon': 9.7472},
            {'stop_id': '490085600', 'stop_name': 'Bregenz Hafen', 'stop_lat': 47.5057, 'stop_lon': 9.7533},
            {'stop_id': '490079200', 'stop_name': 'Rankweil Konkordiaplatz', 'stop_lat': 47.2627, 'stop_lon': 9.6569},
            {'stop_id': '490053300', 'stop_name': 'Feldkirch Bahnhof', 'stop_lat': 47.2336, 'stop_lon': 9.6010},
            {'stop_id': '490039900', 'stop_name': 'Dornbirn Bahnhof', 'stop_lat': 47.4128, 'stop_lon': 9.7412},
        ]
        self.stops_data = {s['stop_id']: s for s in fallback}

    def search_stops(self, query: str, limit: int = 10) -> list:
        """Search for stops by name or partial match"""
        if not query:
            return []

        query_lower = query.lower()
        matches = []

        for stop_id, stop in self.stops_data.items():
            name = stop.get('stop_name', '').lower()
            if query_lower in name:
                matches.append({
                    'id': stop_id,
                    'name': stop.get('stop_name', ''),
                    'lat': stop.get('stop_lat', 0),
                    'lon': stop.get('stop_lon', 0),
                })

        # Sort by relevance (exact match, then prefix, then contains)
        def relevance_score(item):
            name = item['name'].lower()
            if name == query_lower:
                return 0
            elif name.startswith(query_lower):
                return 1
            else:
                return 2

        matches.sort(key=relevance_score)
        return matches[:limit]

    def get_stop(self, stop_id: str) -> dict:
        """Get stop details by ID"""
        return self.stops_data.get(stop_id, {})

    def get_all_stops(self) -> list:
        """Get all stops"""
        return list(self.stops_data.values())

    def refresh(self):
        """Force refresh of GTFS data"""
        logger.info("Forcing GTFS refresh")
        self.stops_data = {}
        self._fetch_and_parse()


# Singleton instance
_loader = None


def get_gtfs_loader():
    """Get or create GTFS loader instance"""
    global _loader
    if _loader is None:
        _loader = GTFSLoader()
    return _loader
