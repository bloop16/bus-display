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
from collections import defaultdict
from typing import Optional

logger = logging.getLogger(__name__)

# GTFS-Download-URL für VMobil Vorarlberg (mobilitydata.gv.at).
# Falls diese URL irgendwann nicht mehr funktioniert, muss sie manuell aktualisiert werden.
# Neue URL findet man unter: https://mobilitydata.gv.at (nach "vmobil gtfs" suchen)
GTFS_URL = "https://mobilitydata.gv.at/sites/default/files/metadataset/sample_data/20231229-0218_gtfs_vmobil_2024.zip"
CACHE_DIR = Path(__file__).parent.parent.parent / "data"
STOPS_CACHE_FILE = CACHE_DIR / "stops.json"
SCHEDULE_CACHE_FILE = CACHE_DIR / "schedule.json"
CACHE_EXPIRY_HOURS = 24


class GTFSLoader:
    """Load and parse GTFS data for Vorarlberg VMobil"""

    def __init__(self):
        self.stops_data = {}
        self.routes_data = {}
        self.trips_data = {}
        self.stop_times_index = defaultdict(list)
        # stop_id → set of trip_ids that serve this stop (für Via-Halt-Matching)
        self.stop_trip_sets: dict = {}
        self.cache_file = STOPS_CACHE_FILE
        self.schedule_cache_file = SCHEDULE_CACHE_FILE
        self._ensure_cache_dir()
        self._load_or_fetch_stops()

    def _ensure_cache_dir(self):
        """Create cache directory if it doesn't exist"""
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)

    def _load_or_fetch_stops(self):
        """Load stops from cache or fetch new data"""
        if self._cache_valid() and self.schedule_cache_file.exists():
            logger.info("Loading stops from cache")
            self._load_from_cache()
            self._load_schedule_cache()
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

    def _load_schedule_cache(self):
        """Load schedule data from JSON cache"""
        try:
            with open(self.schedule_cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.routes_data = data.get('routes', {})
                self.trips_data = data.get('trips', {})
                self.stop_times_index = defaultdict(list)
                for stop_id, entries in data.get('stop_times_index', {}).items():
                    self.stop_times_index[stop_id].extend(entries)
                raw_sets = data.get('stop_trip_sets', {})
                if not raw_sets:
                    logger.info("Schedule-Cache veraltet (kein stop_trip_sets) – wird neu geladen")
                    self._fetch_and_parse()
                    return
                self.stop_trip_sets = {sid: set(tids) for sid, tids in raw_sets.items()}
                # Cache-Version prüfen: stop_sequence muss in stop_times_index enthalten sein
                sample = next(
                    (e for entries in self.stop_times_index.values() for e in entries), None
                )
                if sample and 'stop_sequence' not in sample:
                    logger.info("Schedule-Cache veraltet (kein stop_sequence) – wird neu geladen")
                    self._fetch_and_parse()
                    return
                logger.info(
                    f"Loaded schedule cache: {len(self.routes_data)} routes, "
                    f"{len(self.trips_data)} trips, {len(self.stop_times_index)} stops"
                )
        except Exception as e:
            logger.error(f"Failed to load schedule cache: {e}. Fetching fresh data.")
            self._fetch_and_parse()

    def _fetch_and_parse(self):
        """Fetch GTFS ZIP and parse stops.txt"""
        try:
            logger.info(f"Downloading GTFS from {GTFS_URL}")
            response = requests.get(GTFS_URL, timeout=60)
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
        """Extract and parse GTFS files from ZIP"""
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
                    reader = csv.DictReader(f.read().decode('utf-8-sig').splitlines())
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

                self._parse_schedule_files(zip_file)

        except Exception as e:
            logger.error(f"Error parsing GTFS ZIP: {e}")
            self._fallback_stops()

    def _parse_schedule_files(self, zip_file):
        """Parse routes, trips and stop_times for schedule departures"""
        try:
            routes_files = [f for f in zip_file.namelist() if f.endswith('routes.txt')]
            trips_files = [f for f in zip_file.namelist() if f.endswith('trips.txt')]
            stop_times_files = [f for f in zip_file.namelist() if f.endswith('stop_times.txt')]

            if not routes_files or not trips_files or not stop_times_files:
                logger.warning("GTFS schedule files missing (routes/trips/stop_times)")
                return

            with zip_file.open(routes_files[0]) as f:
                reader = csv.DictReader(f.read().decode('utf-8-sig').splitlines())
                self.routes_data = {
                    row.get('route_id', ''): {
                        'short_name': row.get('route_short_name', '') or row.get('route_id', ''),
                        'long_name': row.get('route_long_name', ''),
                    }
                    for row in reader if row.get('route_id')
                }

            with zip_file.open(trips_files[0]) as f:
                reader = csv.DictReader(f.read().decode('utf-8-sig').splitlines())
                self.trips_data = {
                    row.get('trip_id', ''): {
                        'route_id': row.get('route_id', ''),
                        'headsign': row.get('trip_headsign', ''),
                    }
                    for row in reader if row.get('trip_id')
                }

            self.stop_times_index = defaultdict(list)
            self.stop_trip_sets = {}
            with zip_file.open(stop_times_files[0]) as f:
                reader = csv.DictReader(f.read().decode('utf-8-sig').splitlines())
                for row in reader:
                    stop_id = row.get('stop_id', '')
                    trip_id = row.get('trip_id', '')
                    dep_time = row.get('departure_time', '')
                    if not stop_id or not trip_id or not dep_time:
                        continue
                    seq = row.get('stop_sequence', '0')
                    self.stop_times_index[stop_id].append({
                        'trip_id': trip_id,
                        'departure_time': dep_time,
                        'stop_sequence': int(seq) if str(seq).isdigit() else 0,
                    })
                    # Via-Halt-Index: welche Trips halten an diesem Stop?
                    if stop_id not in self.stop_trip_sets:
                        self.stop_trip_sets[stop_id] = set()
                    self.stop_trip_sets[stop_id].add(trip_id)

            self._save_schedule_cache()
            logger.info(
                f"Parsed schedule data: {len(self.routes_data)} routes, "
                f"{len(self.trips_data)} trips, {len(self.stop_times_index)} indexed stops"
            )
        except Exception as e:
            logger.error(f"Failed to parse schedule files: {e}")

    def _save_schedule_cache(self):
        """Save parsed schedule data to JSON cache"""
        try:
            data = {
                'timestamp': datetime.now().isoformat(),
                'routes': self.routes_data,
                'trips': self.trips_data,
                'stop_times_index': dict(self.stop_times_index),
                'stop_trip_sets': {sid: list(tids) for sid, tids in self.stop_trip_sets.items()},
            }
            with open(self.schedule_cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False)
            logger.info("Saved schedule cache")
        except Exception as e:
            logger.error(f"Failed to save schedule cache: {e}")

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

    def get_scheduled_departures(self, stop_id: str, limit: int = 10, now: datetime = None) -> list:
        """Get upcoming scheduled departures from GTFS stop_times."""
        if now is None:
            now = datetime.now()

        entries = self.stop_times_index.get(stop_id, [])
        if not entries:
            return []

        upcoming = []
        now_seconds = now.hour * 3600 + now.minute * 60 + now.second

        for entry in entries:
            dep = entry.get('departure_time', '')
            dep_seconds = self._gtfs_time_to_seconds(dep)
            if dep_seconds is None:
                continue
            if dep_seconds < now_seconds:
                continue

            trip = self.trips_data.get(entry.get('trip_id', ''), {})
            route = self.routes_data.get(trip.get('route_id', ''), {})

            dep_dt = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(seconds=dep_seconds)
            destination = trip.get('headsign') or route.get('long_name') or "Unbekannt"
            line = route.get('short_name') or "?"

            upcoming.append({
                'line': str(line),
                'destination': destination,
                'departure_time': dep_dt,
                'stop_name': self.get_stop(stop_id).get('stop_name', stop_id),
                'delay_minutes': None,
                'trip_id': entry.get('trip_id'),
            })

        upcoming.sort(key=lambda x: x['departure_time'])
        return upcoming[:limit]

    def _gtfs_time_to_seconds(self, time_str: str):
        """Convert GTFS HH:MM:SS (hour may be > 23) to seconds."""
        try:
            parts = time_str.split(':')
            if len(parts) != 3:
                return None
            h, m, s = map(int, parts)
            return h * 3600 + m * 60 + s
        except Exception:
            return None

    def search_stops(self, query: str, limit: int = 10) -> list:
        """
        Suche Haltestellen nach Name.
        Stops mit identischem Namen (= verschiedene Steige/Richtungen)
        werden zu einem einzigen Eintrag zusammengefasst.
        Das zurückgegebene 'id' ist die kanonische ID (erste gefundene),
        'ids' enthält alle zugehörigen Stop-IDs.
        """
        if not query:
            return []

        query_lower = query.lower()
        # name → {ids, lat, lon}
        grouped: dict = {}

        for stop_id, stop in self.stops_data.items():
            name = stop.get('stop_name', '')
            if query_lower not in name.lower():
                continue
            if name not in grouped:
                grouped[name] = {
                    'name': name,
                    'ids':  [stop_id],
                    'lat':  stop.get('stop_lat', 0),
                    'lon':  stop.get('stop_lon', 0),
                }
            else:
                grouped[name]['ids'].append(stop_id)

        matches = list(grouped.values())

        # Sortierung: Exakter Treffer > Präfix > Enthält
        def relevance(item):
            n = item['name'].lower()
            if n == query_lower:      return 0
            if n.startswith(query_lower): return 1
            return 2

        matches.sort(key=relevance)
        result = matches[:limit]

        # 'id' = erste ID (rückwärtskompatibel)
        for m in result:
            m['id'] = m['ids'][0]

        return result

    def trip_passes_stop(self, trip_id: str, stop_id: str) -> bool:
        """True wenn der Trip an der gegebenen stop_id hält (ohne Richtungsprüfung)."""
        trip_set = self.stop_trip_sets.get(stop_id)
        if trip_set is None:
            return False
        return trip_id in trip_set

    def _get_trip_stop_sequence(self, trip_id: str, stop_id: str) -> Optional[int]:
        """Gibt die stop_sequence von stop_id im gegebenen Trip zurück, oder None."""
        for entry in self.stop_times_index.get(stop_id, []):
            if entry.get('trip_id') == trip_id:
                return entry.get('stop_sequence')
        return None

    def trip_passes_stop_after(self, trip_id: str, boarding_stop_id: str, via_stop_id: str) -> bool:
        """
        True wenn der Trip via_stop_id anfährt UND zwar NACH boarding_stop_id
        (in Fahrtrichtung, d.h. via_sequence > boarding_sequence).
        """
        boarding_seq = self._get_trip_stop_sequence(trip_id, boarding_stop_id)
        via_seq = self._get_trip_stop_sequence(trip_id, via_stop_id)
        if boarding_seq is None or via_seq is None:
            return False
        return via_seq > boarding_seq

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
